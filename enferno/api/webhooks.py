import os

from flask import Blueprint, current_app, request
from sqlalchemy.exc import IntegrityError

from enferno.extensions import db
from enferno.services.billing import HostedBilling
from enferno.user.models import BillingEvent

webhooks_bp = Blueprint("webhooks", __name__)

PROVIDER = os.environ.get("BILLING_PROVIDER", "stripe")


def _process_event(event_id, event_type, process):
    if not isinstance(event_id, str) or not event_id or not isinstance(event_type, str):
        return "Invalid event", 400

    try:
        db.session.add(
            BillingEvent(event_id=event_id, event_type=event_type, provider=PROVIDER)
        )
        db.session.flush()
    except IntegrityError:
        db.session.rollback()
        if db.session.scalar(
            db.select(BillingEvent.id).where(
                BillingEvent.event_id == event_id, BillingEvent.provider == PROVIDER
            )
        ):
            return "OK", 200
        current_app.logger.exception("Failed to record billing event %s", event_id)
        return "Processing failed", 500

    try:
        process()
        # A receipt must not survive a failed plan update.
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Failed to process billing event %s", event_id)
        return "Processing failed", 500
    return "OK", 200


if PROVIDER == "stripe":
    import stripe

    @webhooks_bp.route("/stripe/webhook", methods=["POST"])
    def stripe_webhook():
        payload = request.get_data()
        sig_header = request.headers.get("Stripe-Signature")
        secret = current_app.config.get("STRIPE_WEBHOOK_SECRET")

        if not secret:
            current_app.logger.error("Stripe webhook secret not configured")
            return "Webhook secret not configured", 500

        try:
            event = stripe.Webhook.construct_event(
                payload, sig_header, secret
            ).to_dict()
        except (ValueError, stripe.SignatureVerificationError) as e:
            current_app.logger.error(f"Webhook error: {e}")
            return "Invalid request", 400

        def process():
            if event["type"] in {
                "checkout.session.completed",
                "checkout.session.async_payment_succeeded",
            }:
                HostedBilling.handle_successful_payment(
                    event["data"]["object"]["id"], commit=False
                )
            elif event["type"] in {
                "customer.subscription.created",
                "customer.subscription.updated",
                "customer.subscription.deleted",
                "customer.subscription.paused",
                "customer.subscription.resumed",
                "invoice.payment_failed",
                "invoice.paid",
            }:
                HostedBilling.sync_customer(event["data"]["object"]["customer"])

        return _process_event(event.get("id"), event.get("type"), process)

elif PROVIDER == "chargebee":

    def _verify_chargebee_auth():
        """Verify Chargebee webhook using Basic Auth (required in production)."""
        username = current_app.config.get("CHARGEBEE_WEBHOOK_USERNAME")
        password = current_app.config.get("CHARGEBEE_WEBHOOK_PASSWORD")

        if not username or not password:
            if not current_app.debug:
                current_app.logger.error("Chargebee webhook credentials not configured")
                return False
            return True  # Allow in debug mode for local testing

        auth = request.authorization
        if not auth or auth.username != username or auth.password != password:
            return False
        return True

    @webhooks_bp.route("/chargebee/webhook", methods=["POST"])
    def chargebee_webhook():
        if not _verify_chargebee_auth():
            current_app.logger.error("Chargebee webhook auth failed")
            return "Unauthorized", 401

        event = request.get_json()
        if not isinstance(event, dict) or not event:
            return "Invalid request", 400

        def process():
            if event["event_type"] in {
                "subscription_created",
                "subscription_started",
                "subscription_activated",
                "subscription_changed",
                "subscription_cancelled",
                "subscription_reactivated",
                "subscription_paused",
                "subscription_resumed",
                "subscription_renewed",
                "subscription_cancellation_scheduled",
                "subscription_scheduled_cancellation_removed",
                "payment_failed",
                "payment_succeeded",
            }:
                HostedBilling.sync_customer(event["content"]["customer"]["id"])

        return _process_event(event.get("id"), event.get("event_type"), process)
