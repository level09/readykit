import os

from flask import Blueprint, current_app, request
from sqlalchemy.exc import IntegrityError

from enferno.extensions import db
from enferno.user.models import BillingEvent, Workspace

webhooks_bp = Blueprint("webhooks", __name__)

PROVIDER = os.environ.get("BILLING_PROVIDER", "stripe")

if PROVIDER == "stripe":
    import stripe

    from enferno.services.billing import HostedBilling

    @webhooks_bp.route("/stripe/webhook", methods=["POST"])
    def stripe_webhook():
        payload = request.get_data()
        sig_header = request.headers.get("Stripe-Signature")
        secret = current_app.config.get("STRIPE_WEBHOOK_SECRET")

        if not secret:
            current_app.logger.error("Stripe webhook secret not configured")
            return "Webhook secret not configured", 500

        try:
            event = stripe.Webhook.construct_event(payload, sig_header, secret)
        except (ValueError, stripe.error.SignatureVerificationError) as e:
            current_app.logger.error(f"Webhook error: {e}")
            return "Invalid request", 400

        # Skip duplicate events
        event_id = event.get("id")
        try:
            db.session.add(
                BillingEvent(
                    event_id=event_id, event_type=event.get("type"), provider="stripe"
                )
            )
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return "OK", 200

        # Handle checkout completion
        if event["type"] == "checkout.session.completed":
            session = event["data"]["object"]
            session_id = session.get("id")

            HostedBilling.handle_successful_payment(session_id)
            current_app.logger.info(f"Processed checkout: {session_id}")

        # Handle subscription cancellation (downgrade to free)
        elif event["type"] == "customer.subscription.deleted":
            subscription = event["data"]["object"]
            customer_id = subscription.get("customer")

            workspace = db.session.execute(
                db.select(Workspace).where(Workspace.billing_customer_id == customer_id)
            ).scalar_one_or_none()

            if workspace:
                workspace.plan = "free"
                db.session.commit()
                current_app.logger.info(
                    f"Downgraded workspace {workspace.id} to free (subscription cancelled)"
                )

        # Handle payment failure (downgrade to free)
        elif event["type"] == "invoice.payment_failed":
            invoice = event["data"]["object"]
            customer_id = invoice.get("customer")

            workspace = db.session.execute(
                db.select(Workspace).where(Workspace.billing_customer_id == customer_id)
            ).scalar_one_or_none()

            if workspace and workspace.plan == "pro":
                workspace.plan = "free"
                db.session.commit()
                current_app.logger.warning(
                    f"Downgraded workspace {workspace.id} to free (payment failed)"
                )

        return "OK", 200

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
        if not event:
            return "Invalid request", 400

        event_type = event.get("event_type")
        event_id = event.get("id")

        # Skip duplicate events
        try:
            db.session.add(
                BillingEvent(
                    event_id=event_id, event_type=event_type, provider="chargebee"
                )
            )
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            return "OK", 200

        content = event.get("content", {})

        # Handle subscription cancellation (downgrade to free)
        # Note: Upgrades handled via redirect flow, not webhook
        if event_type == "subscription_cancelled":
            customer = content.get("customer", {})
            customer_id = customer.get("id")

            workspace = db.session.execute(
                db.select(Workspace).where(Workspace.billing_customer_id == customer_id)
            ).scalar_one_or_none()

            if workspace:
                workspace.plan = "free"
                db.session.commit()
                current_app.logger.info(
                    f"Downgraded workspace {workspace.id} to free (subscription cancelled)"
                )

        # Handle payment failure (downgrade to free)
        elif event_type == "payment_failed":
            customer = content.get("customer", {})
            customer_id = customer.get("id")

            workspace = db.session.execute(
                db.select(Workspace).where(Workspace.billing_customer_id == customer_id)
            ).scalar_one_or_none()

            if workspace and workspace.plan == "pro":
                workspace.plan = "free"
                db.session.commit()
                current_app.logger.warning(
                    f"Downgraded workspace {workspace.id} to free (payment failed)"
                )

        return "OK", 200
