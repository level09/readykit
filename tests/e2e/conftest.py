"""Live browser journeys against a real app process and a Stripe sandbox.

Run with: RUN_E2E=1 uv run --extra e2e pytest tests/e2e
Needs the Stripe CLI and an sk_test_ STRIPE_SECRET_KEY (environment or .env).
The app runs on its own temporary database; .env is only read for the key.
"""

import os
import re
import secrets
import socket
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from dotenv import dotenv_values

if not os.environ.get("RUN_E2E"):
    collect_ignore_glob = ["*.py"]

ROOT = Path(__file__).parents[2]
EVENTS = (
    "checkout.session.completed,checkout.session.async_payment_succeeded,"
    "customer.subscription.created,customer.subscription.updated,"
    "customer.subscription.deleted,customer.subscription.paused,"
    "customer.subscription.resumed,invoice.payment_failed,invoice.paid"
)
ADMIN = ("admin@example.com", "E2e-Admin-Pass-2026!")


def _free_port():
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _wait(predicate, timeout, message):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.5)
    raise AssertionError(message)


@pytest.fixture(scope="session")
def stripe_key():
    key = os.environ.get("STRIPE_SECRET_KEY") or dotenv_values(ROOT / ".env").get(
        "STRIPE_SECRET_KEY", ""
    )
    if not key.startswith("sk_test_"):
        pytest.skip("E2E needs an sk_test_ STRIPE_SECRET_KEY")
    return key


@pytest.fixture(scope="session")
def live(tmp_path_factory, stripe_key):
    import stripe

    from enferno.commands import PRO_PRICE_LOOKUP_KEY

    stripe.api_key = stripe_key
    prices = stripe.Price.list(lookup_keys=[PRO_PRICE_LOOKUP_KEY], active=True).data
    price = (
        prices[0]
        if prices
        else stripe.Price.create(
            unit_amount=2900,
            currency="usd",
            recurring={"interval": "month"},
            product_data={"name": "Pro"},
            lookup_key=PRO_PRICE_LOOKUP_KEY,
        )
    )
    cli_env = {**os.environ, "STRIPE_API_KEY": stripe_key}
    webhook_secret = subprocess.run(
        ["stripe", "listen", "--print-secret"],
        env=cli_env,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()

    tmp = tmp_path_factory.mktemp("e2e")
    database = tmp / "e2e.sqlite3"
    port = _free_port()
    # Explicit values win over .env, which load_dotenv never overrides.
    env = {
        **os.environ,
        "FLASK_APP": "run.py",
        "FLASK_DEBUG": "0",
        "SECRET_KEY": secrets.token_hex(16),
        "SECURITY_PASSWORD_SALT": secrets.token_hex(16),
        "SECURITY_TOTP_SECRETS": secrets.token_hex(16),
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database}",
        "SESSION_COOKIE_SECURE": "False",
        "REDIS_SESSION": "",
        "REDIS_URL": "",
        "CELERY_BROKER_URL": "",
        "CELERY_RESULT_BACKEND": "",
        "GOOGLE_OAUTH_CLIENT_ID": "",
        "GITHUB_OAUTH_CLIENT_ID": "",
        "BILLING_PROVIDER": "stripe",
        "STRIPE_SECRET_KEY": stripe_key,
        "STRIPE_PRO_PRICE_ID": price.id,
        "STRIPE_WEBHOOK_SECRET": webhook_secret,
        "ADMIN_EMAIL": ADMIN[0],
        "ADMIN_PASSWORD": ADMIN[1],
    }
    flask = [sys.executable, "-m", "flask"]
    for command in (["create-db"], ["install", "-n"]):
        subprocess.run(
            flask + command, cwd=ROOT, env=env, check=True, capture_output=True
        )

    app_log = (tmp / "app.log").open("w")
    listen_log = tmp / "listen.log"
    processes = [
        subprocess.Popen(
            flask + ["run", "--port", str(port), "--no-reload"],
            cwd=ROOT,
            env=env,
            stdout=app_log,
            stderr=subprocess.STDOUT,
        ),
        subprocess.Popen(
            [
                "stripe",
                "listen",
                "--events",
                EVENTS,
                "--forward-to",
                f"localhost:{port}/stripe/webhook",
            ],
            env=cli_env,
            stdout=listen_log.open("w"),
            stderr=subprocess.STDOUT,
        ),
    ]
    try:
        _wait(lambda: "Ready!" in listen_log.read_text(), 30, "stripe listen not ready")
        _wait(lambda: "Running on" in (tmp / "app.log").read_text(), 30, "app not up")

        def query(sql, *args):
            with sqlite3.connect(database) as connection:
                return connection.execute(sql, args).fetchone()

        yield SimpleNamespace(
            url=f"http://localhost:{port}",
            query=query,
            wait=_wait,
            price=price,
            logs=tmp,
        )
    finally:

        def drained():
            log = listen_log.read_text()
            return log.count("<--") >= log.count("-->")

        try:
            _wait(drained, 30, "stripe listen still has undelivered events")
        finally:
            # Listener first, so no event is forwarded to a stopped app.
            for process in reversed(processes):
                process.terminate()
                try:
                    process.wait(10)
                except subprocess.TimeoutExpired:
                    process.kill()
            app_log.close()
    # Every forwarded webhook must succeed; a failure would make Stripe retry.
    log = listen_log.read_text()
    failed = re.findall(r"<--\s+\[(?!200\])\d+\].*|.*\[ERROR\].*", log)
    assert not failed, f"Webhook deliveries failed: {failed}"


@pytest.fixture(scope="session")
def browser():
    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch()
        yield browser
        browser.close()


@pytest.fixture
def page(browser):
    context = browser.new_context()
    page = context.new_page()
    page.set_default_timeout(20_000)
    yield page
    context.close()
