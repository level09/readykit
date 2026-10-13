from types import SimpleNamespace

import pytest
import stripe
from dotenv import dotenv_values

from enferno import commands


@pytest.fixture
def stripe_env(app, tmp_path, monkeypatch):
    for name, value in {
        "PROJECT_ROOT": str(tmp_path),
        "BILLING_PROVIDER": "stripe",
        "STRIPE_SECRET_KEY": "sk_test_app",
        "STRIPE_PRO_PRICE_ID": None,
        "STRIPE_WEBHOOK_SECRET": None,
        "PRO_PRICE_INTERVAL": "month",
    }.items():
        monkeypatch.setitem(app.config, name, value)
    (tmp_path / ".env").write_text("SECRET_KEY=keep\n")

    calls = []

    def cli(*args, api_key=None):
        calls.append((args[0], api_key))
        assert args == ("listen", "--print-secret")
        return "whsec_local\n"

    prices = []

    def create(**params):
        assert stripe.api_key == "sk_test_app"
        price = SimpleNamespace(
            id="price_new",
            unit_amount=params["unit_amount"],
            currency=params["currency"],
            recurring=SimpleNamespace(interval=params["recurring"]["interval"]),
        )
        prices.append(price)
        return price

    monkeypatch.setattr(commands, "_stripe_cli", cli)
    monkeypatch.setattr(stripe.Price, "create", create)
    monkeypatch.setattr(
        stripe.Price, "list", lambda **params: SimpleNamespace(data=list(prices))
    )
    return SimpleNamespace(env=tmp_path / ".env", calls=calls, prices=prices)


def test_stripe_setup_writes_billing_settings_once(app, stripe_env, monkeypatch):
    runner = app.test_cli_runner()

    result = runner.invoke(commands.stripe_setup, ["--amount", "1950"])
    assert result.exit_code == 0, result.output

    values = dotenv_values(stripe_env.env)
    assert values == {
        "SECRET_KEY": "keep",
        "STRIPE_PRO_PRICE_ID": "price_new",
        "PRO_PRICE_DISPLAY": "$19.50",
        "PRO_PRICE_INTERVAL": "month",
        "STRIPE_WEBHOOK_SECRET": "whsec_local",
    }
    assert stripe_env.calls == [("listen", "sk_test_app")]
    assert "sk_test_app" not in result.output

    # A rerun with the saved settings changes nothing.
    for name, value in values.items():
        monkeypatch.setitem(app.config, name, value)
    calls = len(stripe_env.calls)
    result = runner.invoke(commands.stripe_setup)
    assert result.exit_code == 0, result.output
    assert len(stripe_env.calls) == calls
    assert dotenv_values(stripe_env.env) == values

    # Losing the price ID reuses the lookup-key price instead of creating another.
    monkeypatch.setitem(app.config, "STRIPE_PRO_PRICE_ID", None)
    result = runner.invoke(commands.stripe_setup)
    assert result.exit_code == 0, result.output
    assert len(stripe_env.prices) == 1


@pytest.mark.parametrize(
    "key", [None, "sk_test_your_secret_key_here", "rk_test_cli", "sk_live_real"]
)
def test_stripe_setup_requires_a_test_secret_key(app, stripe_env, monkeypatch, key):
    monkeypatch.setitem(app.config, "STRIPE_SECRET_KEY", key)

    result = app.test_cli_runner().invoke(commands.stripe_setup)

    assert result.exit_code != 0
    assert "sk_test_" in result.output
    assert stripe_env.calls == stripe_env.prices == []


def test_stripe_setup_refuses_chargebee(app, stripe_env, monkeypatch):
    monkeypatch.setitem(app.config, "BILLING_PROVIDER", "chargebee")

    result = app.test_cli_runner().invoke(commands.stripe_setup)

    assert result.exit_code != 0
    assert "BILLING_PROVIDER=stripe" in result.output
    assert stripe_env.calls == []
