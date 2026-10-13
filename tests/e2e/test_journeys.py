import time
import uuid

import stripe

from tests.e2e.conftest import ADMIN


def log_in(page, live, email, password):
    page.goto(live.url + "/login")
    page.get_by_label("Email").fill(email)
    page.get_by_label("Password").fill(password)
    page.get_by_role("button", name="Log In").click()
    page.wait_for_url(lambda url: "/login" not in url)


def create_workspace(page, live):
    name = f"E2E {uuid.uuid4().hex[:8]}"
    page.get_by_role("button", name="Create Workspace").first.click()
    page.get_by_label("Workspace Name").fill(name)
    page.get_by_role("button", name="Create", exact=True).click()
    page.wait_for_url("**/workspace/")
    return name


def plan(live, name):
    return live.query("SELECT plan FROM workspace WHERE name = ?", name)[0]


def wait_for_plan(live, name, expected, timeout=60):
    live.wait(
        lambda: plan(live, name) == expected,
        timeout,
        f"{name} never reached {expected}; see {live.logs}",
    )


def subscribe(page, live, name):
    page.goto(live.url + "/workspace/settings/")
    page.get_by_role("link", name="Upgrade to Pro").last.click()
    page.wait_for_url("https://checkout.stripe.com/**")
    page.locator("#cardNumber").fill("4242424242424242")
    page.locator("#cardExpiry").fill("12/34")
    page.locator("#cardCvc").fill("123")
    page.locator("#billingName").fill("E2E Admin")
    page.get_by_test_id("hosted-payment-submit-button").click()
    page.wait_for_url(live.url + "/billing/success**", timeout=60_000)
    wait_for_plan(live, name, "pro")


def test_upgrade_portal_and_cancellation(live, page):
    log_in(page, live, *ADMIN)
    name = create_workspace(page, live)
    assert plan(live, name) == "free"

    subscribe(page, live, name)

    page.goto(live.url + "/workspace/billing")
    page.wait_for_url("https://billing.stripe.com/**")

    customer = live.query(
        "SELECT billing_customer_id FROM workspace WHERE name = ?", name
    )[0]
    for subscription in stripe.Subscription.list(customer=customer).auto_paging_iter():
        stripe.Subscription.cancel(subscription.id)
    wait_for_plan(live, name, "free")


def test_failed_renewal_loses_and_recovery_restores_pro(live, page):
    log_in(page, live, *ADMIN)
    name = create_workspace(page, live)
    now = int(time.time())
    clock = stripe.test_helpers.TestClock.create(frozen_time=now)
    try:
        # Checkout reuses a linked customer, so attach one that runs on the clock.
        customer = stripe.Customer.create(email=ADMIN[0], test_clock=clock.id)
        live.query(
            "UPDATE workspace SET billing_customer_id = ? WHERE name = ?",
            customer.id,
            name,
        )
        subscribe(page, live, name)
        subscription = stripe.Subscription.list(customer=customer.id).data[0]

        failing = stripe.PaymentMethod.attach(
            "pm_card_chargeCustomerFail", customer=customer.id
        )
        stripe.Subscription.modify(subscription.id, default_payment_method=failing.id)
        period_end = subscription["items"]["data"][0]["current_period_end"]
        stripe.test_helpers.TestClock.advance(clock.id, frozen_time=period_end + 3600)
        live.wait(
            lambda: stripe.test_helpers.TestClock.retrieve(clock.id).status == "ready",
            120,
            "test clock did not finish advancing",
        )
        wait_for_plan(live, name, "free", timeout=120)
        page.goto(live.url + "/workspace/settings/")
        page.get_by_role("link", name="Update payment method").wait_for()
        assert page.get_by_role("link", name="Restore Pro").is_visible()
        assert page.get_by_role("link", name="Upgrade to Pro").count() == 0

        working = stripe.PaymentMethod.attach("pm_card_visa", customer=customer.id)
        stripe.Subscription.modify(subscription.id, default_payment_method=working.id)
        invoice = stripe.Subscription.retrieve(subscription.id).latest_invoice
        stripe.Invoice.pay(invoice, payment_method=working.id)
        wait_for_plan(live, name, "pro")
    finally:
        stripe.test_helpers.TestClock.delete(clock.id)


def test_member_uses_workspace_without_billing_access(live, browser, page):
    log_in(page, live, *ADMIN)
    name = create_workspace(page, live)
    page.goto(live.url + "/workspace/team/")
    page.get_by_role("button", name="Add Team Member").click()
    member = f"member-{uuid.uuid4().hex[:8]}"
    email, password = f"{member}@example.com", "E2e-Member-Pass-2026!"
    page.get_by_label("Full Name").fill("E2E Member")
    page.get_by_label("Username").fill(member)
    page.get_by_label("Email Address").fill(email)
    page.get_by_label("Password").fill(password)
    page.get_by_role("button", name="Add Member").click()
    page.get_by_text(email).wait_for()

    member_page = browser.new_context().new_page()
    log_in(member_page, live, email, password)
    member_page.wait_for_url("**/workspace/")
    assert name in member_page.content()

    member_page.goto(live.url + "/workspace/settings/")
    assert member_page.get_by_text("Plan & Billing").count() == 0
    assert member_page.goto(live.url + "/workspace/upgrade").status == 403
