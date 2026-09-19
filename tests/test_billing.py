import hashlib
import hmac
import json
import time
from concurrent.futures import ThreadPoolExecutor
from threading import Event, Lock
from types import SimpleNamespace

import pytest
from sqlalchemy import event

from enferno.extensions import db
from enferno.services import billing
from enferno.user.models import BillingEvent, User, Workspace

PROVIDER = billing.PROVIDER


@pytest.fixture
def workspace(app):
    user = User(email="billing@example.com", password="unused", active=True)
    db.session.add(user)
    db.session.flush()
    workspace = Workspace(
        name="Billing",
        slug="billing",
        owner_id=user.id,
        billing_customer_id="cus_test",
        plan="pro",
    )
    db.session.add(workspace)
    db.session.commit()
    return workspace


@pytest.fixture
def provider(app, monkeypatch):
    app.config.update(
        STRIPE_SECRET_KEY="sk_test_readykit",
        STRIPE_PRO_PRICE_ID="price_pro",
        CHARGEBEE_API_KEY="test_readykit",
        CHARGEBEE_SITE="readykit-test",
        CHARGEBEE_PRO_ITEM_PRICE_ID="price_pro",
        CHARGEBEE_WEBHOOK_USERNAME="test",
        CHARGEBEE_WEBHOOK_PASSWORD="test-secret",
    )
    state = SimpleNamespace(status="active", price="price_pro", error=None)
    if PROVIDER == "stripe":
        import stripe

        def subscriptions(**params):
            assert params["price"] == "price_pro"
            if state.error:
                raise state.error
            return stripe.ListObject.construct_from(
                {
                    "object": "list",
                    "has_more": False,
                    "data": [
                        {
                            "id": "sub_test",
                            "object": "subscription",
                            "customer": "cus_test",
                            "status": state.status,
                            "items": {"data": [{"price": {"id": state.price}}]},
                        }
                    ]
                    if state.price == params["price"]
                    and params["customer"] == "cus_test"
                    else [],
                },
                "sk_test_readykit",
            )

        monkeypatch.setattr(stripe.Subscription, "list", subscriptions)
        monkeypatch.setattr(
            stripe.checkout.Session,
            "retrieve",
            lambda session_id: stripe.checkout.Session.construct_from(
                {
                    "id": session_id,
                    "object": "checkout.session",
                    "status": "complete",
                    "payment_status": "paid",
                    "customer": "cus_test",
                    "metadata": {"workspace_id": "1"},
                },
                "sk_test_readykit",
            ),
        )
    else:
        from chargebee.models.subscription.responses import (
            ListResponse,
            ListSubscriptionResponse,
            SubscriptionItemResponse,
            SubscriptionResponse,
        )

        def subscriptions(params):
            assert params["item_price_id"] == {"is": "price_pro"}
            if state.error:
                raise state.error
            return ListResponse(
                http_status_code=200,
                headers={},
                list=[
                    ListSubscriptionResponse(
                        customer=None,
                        subscription=SubscriptionResponse(
                            id="sub_test",
                            customer_id="cus_test",
                            status=state.status,
                            subscription_items=[
                                SubscriptionItemResponse(
                                    item_price_id=state.price,
                                )
                            ],
                        ),
                    )
                ]
                if state.price == params["item_price_id"]["is"]
                and params["customer_id"] == {"is": "cus_test"}
                else [],
            )

        monkeypatch.setattr(
            billing,
            "_cb_client",
            SimpleNamespace(
                Subscription=SimpleNamespace(list=subscriptions),
                HostedPage=SimpleNamespace(
                    retrieve=lambda page_id: SimpleNamespace(
                        hosted_page=SimpleNamespace(
                            id=page_id,
                            state="succeeded",
                            pass_thru_content='{"workspace_id": "1"}',
                            content={"customer": {"id": "cus_test"}},
                        ),
                    )
                ),
            ),
        )
    return state


def deliver(app, kind, event_id="evt_test", customer="cus_test"):
    if PROVIDER == "stripe":
        types = {
            "failed": "invoice.payment_failed",
            "paid": "invoice.paid",
            "cancelled": "customer.subscription.deleted",
            "changed": "customer.subscription.updated",
            "checkout": "checkout.session.completed",
        }
        payload = json.dumps(
            {
                "id": event_id,
                "object": "event",
                "type": types[kind],
                "data": {"object": {"id": "sub_test", "customer": customer}},
            }
        )
        timestamp = int(time.time())
        signature = hmac.new(
            app.config["STRIPE_WEBHOOK_SECRET"].encode(),
            f"{timestamp}.{payload}".encode(),
            hashlib.sha256,
        ).hexdigest()
        return app.test_client().post(
            "/stripe/webhook",
            data=payload,
            content_type="application/json",
            headers={"Stripe-Signature": f"t={timestamp},v1={signature}"},
        )
    types = {
        "failed": "payment_failed",
        "paid": "payment_succeeded",
        "cancelled": "subscription_cancelled",
        "changed": "subscription_changed",
    }
    return app.test_client().post(
        "/chargebee/webhook",
        json={
            "id": event_id,
            "event_type": types[kind],
            "content": {"customer": {"id": customer}},
        },
        auth=("test", "test-secret"),
    )


def receipt_count():
    return db.session.scalar(db.select(db.func.count()).select_from(BillingEvent))


def test_payment_recovery_restores_access(app, workspace, provider):
    workspace.plan = "free"
    db.session.commit()
    response = deliver(app, "paid")
    assert response.status_code == 200
    db.session.refresh(workspace)
    assert workspace.plan == "pro"
    assert receipt_count() == 1


@pytest.mark.parametrize("kind", ["failed", "cancelled"])
def test_late_event_cannot_revoke_recovered_access(app, workspace, provider, kind):
    response = deliver(app, kind)
    assert response.status_code == 200
    db.session.refresh(workspace)
    assert workspace.plan == "pro"


@pytest.mark.parametrize(
    "status,expected",
    [
        ("active", "pro"),
        ("trialing" if PROVIDER == "stripe" else "in_trial", "pro"),
        ("past_due" if PROVIDER == "stripe" else "paused", "free"),
        ("canceled" if PROVIDER == "stripe" else "cancelled", "free"),
    ],
)
def test_subscription_state_controls_access(app, workspace, provider, status, expected):
    provider.status = status
    workspace.plan = "free" if expected == "pro" else "pro"
    db.session.commit()
    assert deliver(app, "changed").status_code == 200
    db.session.refresh(workspace)
    assert workspace.plan == expected


def test_other_product_does_not_grant_pro(app, workspace, provider):
    provider.price = "price_other"
    assert deliver(app, "paid").status_code == 200
    db.session.refresh(workspace)
    assert workspace.plan == "free"


def test_active_subscription_on_later_page_grants_access(
    app, workspace, provider, monkeypatch
):
    workspace.plan = "free"
    db.session.commit()
    api = (
        billing.stripe.Subscription
        if PROVIDER == "stripe"
        else billing._cb_client.Subscription
    )
    original_list = api.list
    if PROVIDER == "stripe":

        def first_page(**params):
            provider.status = "canceled"
            page = original_list(**params)
            page["has_more"] = True
            return page

        def next_page(page, **params):
            provider.status = "active"
            return original_list(customer="cus_test", price="price_pro")

        monkeypatch.setattr(api, "list", first_page)
        monkeypatch.setattr(billing.stripe.ListObject, "next_page", next_page)
    else:

        def page(params):
            provider.status = (
                "active" if params.get("offset") == "next" else "cancelled"
            )
            result = original_list(params)
            result.next_offset = "next" if provider.status == "cancelled" else None
            return result

        monkeypatch.setattr(api, "list", page)
    assert deliver(app, "paid").status_code == 200
    db.session.refresh(workspace)
    assert workspace.plan == "pro"


@pytest.mark.skipif(PROVIDER != "chargebee", reason="Chargebee subscription state")
def test_chargebee_scheduled_cancellation_keeps_access(app, workspace, provider):
    provider.status = "non_renewing"
    assert deliver(app, "changed").status_code == 200
    db.session.refresh(workspace)
    assert workspace.plan == "pro"


def test_provider_failure_leaves_event_retryable(app, workspace, provider):
    workspace.plan = "free"
    db.session.commit()
    provider.error = RuntimeError("provider unavailable")
    assert deliver(app, "paid").status_code == 500
    assert receipt_count() == 0
    db.session.refresh(workspace)
    assert workspace.plan == "free"
    provider.error = None
    assert deliver(app, "paid").status_code == 200
    db.session.refresh(workspace)
    assert workspace.plan == "pro"
    assert receipt_count() == 1


def test_database_failure_rolls_back_receipt_and_plan(app, workspace, provider):
    provider.status = "canceled" if PROVIDER == "stripe" else "cancelled"

    def fail_update(mapper, connection, target):
        raise RuntimeError("database write failed")

    event.listen(Workspace, "before_update", fail_update)
    try:
        assert deliver(app, "cancelled").status_code == 500
    finally:
        event.remove(Workspace, "before_update", fail_update)
    db.session.rollback()
    assert receipt_count() == 0
    db.session.refresh(workspace)
    assert workspace.plan == "pro"
    assert deliver(app, "cancelled").status_code == 200
    db.session.refresh(workspace)
    assert workspace.plan == "free"


def test_duplicate_is_acknowledged_without_processing(app, workspace, provider):
    assert deliver(app, "paid").status_code == 200
    provider.error = AssertionError("duplicate must not call provider")
    assert deliver(app, "paid").status_code == 200
    assert receipt_count() == 1


def test_unrelated_customer_does_not_change_workspace(app, workspace, provider):
    assert deliver(app, "cancelled", customer="cus_other").status_code == 500
    db.session.refresh(workspace)
    assert workspace.plan == "pro"


def test_ambiguous_customer_does_not_change_either_workspace(app, workspace, provider):
    other = Workspace(
        name="Other",
        slug="other",
        owner_id=workspace.owner_id,
        billing_customer_id="cus_test",
        plan="pro",
    )
    db.session.add(other)
    db.session.commit()
    provider.status = "canceled" if PROVIDER == "stripe" else "cancelled"
    assert deliver(app, "cancelled").status_code == 500
    db.session.refresh(workspace)
    db.session.refresh(other)
    assert workspace.plan == other.plan == "pro"
    assert receipt_count() == 0


@pytest.mark.parametrize("price", ["price_pro", "price_other"])
def test_event_before_customer_link_remains_retryable(app, workspace, provider, price):
    workspace.billing_customer_id = None
    db.session.commit()
    provider.status = "canceled" if PROVIDER == "stripe" else "cancelled"
    provider.price = price
    assert deliver(app, "cancelled").status_code == 500
    assert receipt_count() == 0
    workspace.billing_customer_id = "cus_test"
    db.session.commit()
    assert deliver(app, "cancelled").status_code == 200
    db.session.refresh(workspace)
    assert workspace.plan == "free"
    assert receipt_count() == 1


def test_missing_event_id_is_rejected(app, workspace, provider):
    assert deliver(app, "cancelled", event_id=None).status_code == 400
    assert receipt_count() == 0


@pytest.mark.parametrize("active", [True, False])
def test_checkout_checks_current_subscription(app, workspace, provider, active):
    workspace.plan = "free"
    workspace.billing_customer_id = None
    db.session.commit()
    if not active:
        provider.status = "canceled" if PROVIDER == "stripe" else "cancelled"
    result = billing.HostedBilling.handle_successful_payment("checkout_test")
    db.session.refresh(workspace)
    assert result == (workspace.id if active else None)
    assert workspace.plan == ("pro" if active else "free")
    assert workspace.billing_customer_id == "cus_test"


def test_old_checkout_cannot_replace_customer(app, workspace, provider):
    workspace.billing_customer_id = "cus_new"
    db.session.commit()
    with pytest.raises(ValueError, match="customer"):
        billing.HostedBilling.handle_successful_payment("checkout_old")
    db.session.rollback()
    db.session.refresh(workspace)
    assert workspace.billing_customer_id == "cus_new"


def test_checkout_failure_does_not_leave_pending_customer(app, workspace, provider):
    workspace.billing_customer_id = None
    workspace.plan = "free"
    db.session.commit()
    provider.error = RuntimeError("provider unavailable")
    with pytest.raises(RuntimeError, match="provider unavailable"):
        billing.HostedBilling.handle_successful_payment("checkout_test")
    # Saving a server-side session must not commit a failed checkout's changes.
    db.session.commit()
    db.session.refresh(workspace)
    assert workspace.billing_customer_id is None
    assert workspace.plan == "free"


def test_checkout_reuses_customer(app, workspace, provider, monkeypatch):
    if PROVIDER == "stripe":
        import stripe

        def create(**params):
            assert params["customer"] == "cus_test"
            assert "customer_email" not in params
            return SimpleNamespace(id="checkout_test", url="https://checkout.example")

        monkeypatch.setattr(stripe.checkout.Session, "create", create)
    else:

        def create(params):
            assert params["customer"] == {"id": "cus_test"}
            return SimpleNamespace(
                hosted_page=SimpleNamespace(
                    id="checkout_test",
                    url="https://checkout.example",
                )
            )

        monkeypatch.setattr(
            billing._cb_client.HostedPage,
            "checkout_new_for_items",
            create,
            raising=False,
        )
    result = billing.HostedBilling.create_upgrade_session(
        workspace.id,
        "billing@example.com",
        "https://app.example/",
    )
    assert result.url == "https://checkout.example"


@pytest.mark.skipif(PROVIDER != "stripe", reason="Stripe checkout webhook")
def test_checkout_failure_rolls_back_customer_and_receipt(app, workspace, provider):
    workspace.billing_customer_id = None
    workspace.plan = "free"
    db.session.commit()
    provider.error = RuntimeError("provider unavailable")
    assert deliver(app, "checkout").status_code == 500
    db.session.refresh(workspace)
    assert workspace.billing_customer_id is None
    assert workspace.plan == "free"
    assert receipt_count() == 0
    provider.error = None
    assert deliver(app, "checkout").status_code == 200
    db.session.refresh(workspace)
    assert workspace.billing_customer_id == "cus_test"
    assert workspace.plan == "pro"
    assert receipt_count() == 1


@pytest.mark.skipif(PROVIDER != "chargebee", reason="Chargebee webhook auth")
def test_chargebee_rejects_invalid_auth(app, workspace, provider):
    response = app.test_client().post(
        "/chargebee/webhook",
        json={
            "id": "evt_test",
            "event_type": "subscription_cancelled",
        },
        auth=("wrong", "wrong"),
    )
    assert response.status_code == 401
    assert receipt_count() == 0


@pytest.mark.parametrize("duplicate", [False, True])
def test_concurrent_events_serialize_provider_reads(
    app, workspace, provider, monkeypatch, duplicate
):
    if db.engine.dialect.name != "postgresql":
        pytest.skip("Requires PostgreSQL row locks")
    first_read, release, second_read = Event(), Event(), Event()
    counter_lock = Lock()
    calls = 0
    api = (
        billing.stripe.Subscription
        if PROVIDER == "stripe"
        else billing._cb_client.Subscription
    )
    original_list = api.list

    def subscriptions(*args, **kwargs):
        nonlocal calls
        with counter_lock:
            calls += 1
            first = calls == 1
        snapshot = original_list(*args, **kwargs)
        if first:
            first_read.set()
            assert release.wait(5), "Timed out releasing provider response"
        else:
            second_read.set()
        return snapshot

    monkeypatch.setattr(api, "list", subscriptions)
    provider.status = "canceled" if PROVIDER == "stripe" else "cancelled"
    db.session.remove()
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(deliver, app, "cancelled", "evt_first")
        try:
            assert first_read.wait(5), "First event did not reach the provider"
            provider.status = "active"
            second = pool.submit(
                deliver, app, "paid", "evt_first" if duplicate else "evt_second"
            )
            assert not second_read.wait(0.3), "Provider read escaped the workspace lock"
        finally:
            release.set()
        assert first.result(timeout=5).status_code == 200
        assert second.result(timeout=5).status_code == 200
    assert db.session.get(Workspace, 1).plan == ("free" if duplicate else "pro")
    assert receipt_count() == (1 if duplicate else 2)
