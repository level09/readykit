"""
Billing service with provider support (Stripe or Chargebee).
Uses hosted pages - no custom checkout UI.
"""

import json
import os
from datetime import datetime
from functools import wraps
from typing import Any

from flask import current_app, jsonify, redirect, request, url_for

from enferno.extensions import db
from enferno.services.workspace import get_current_workspace
from enferno.user.models import Workspace

PROVIDER = os.environ.get("BILLING_PROVIDER", "stripe")

if PROVIDER == "stripe":
    import stripe

    def _init_stripe():
        """Initialize Stripe API key from config"""
        secret = current_app.config.get("STRIPE_SECRET_KEY")
        if not secret:
            raise RuntimeError("Stripe is not configured")
        stripe.api_key = secret

    class HostedBilling:
        """Billing service using Stripe's hosted pages."""

        @staticmethod
        def create_upgrade_session(
            workspace_id: int, user_email: str, base_url: str
        ) -> Any:
            """Create Stripe Checkout session for workspace upgrade."""
            _init_stripe()
            price_id = current_app.config.get("STRIPE_PRO_PRICE_ID")
            if not price_id:
                raise RuntimeError("Stripe price not configured")

            session = stripe.checkout.Session.create(
                customer_email=user_email,
                line_items=[{"price": price_id, "quantity": 1}],
                mode="subscription",
                success_url=f"{base_url}billing/success?session_id={{CHECKOUT_SESSION_ID}}",
                cancel_url=f"{base_url}dashboard",
                metadata={"workspace_id": str(workspace_id)},
            )
            current_app.logger.info(f"Created Stripe Checkout session: {session.id}")
            return session

        @staticmethod
        def create_portal_session(
            customer_id: str, workspace_id: int, base_url: str
        ) -> Any:
            """Create Stripe Customer Portal session for billing management."""
            _init_stripe()
            session = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=f"{base_url}workspace/{workspace_id}/settings",
            )
            current_app.logger.info(f"Created Stripe Portal session: {session.id}")
            return session

        @staticmethod
        def handle_successful_payment(session_id: str) -> int:
            """Handle successful Stripe payment by upgrading the workspace."""
            _init_stripe()
            session = stripe.checkout.Session.retrieve(session_id)
            current_app.logger.info(
                f"Processing checkout: {session.id} status={session.status} payment={session.payment_status}"
            )

            if session.status != "complete":
                current_app.logger.warning(
                    f"Checkout session not complete: {session.id} status={session.status}"
                )
                return None

            if session.payment_status not in {"paid", "no_payment_required"}:
                current_app.logger.warning(
                    f"Payment not confirmed: {session.id} payment_status={session.payment_status}"
                )
                return None

            workspace_id = session.metadata.get("workspace_id")
            if not workspace_id:
                return None

            workspace = db.session.get(Workspace, int(workspace_id))
            if not workspace:
                return None

            if workspace.is_pro:
                return workspace.id

            try:
                workspace.plan = "pro"
                workspace.billing_customer_id = session.customer
                workspace.upgraded_at = datetime.utcnow()
                db.session.commit()
                return workspace.id
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(
                    f"Failed to upgrade workspace {workspace_id}: {e}"
                )
                return None

elif PROVIDER == "chargebee":
    from chargebee import Chargebee

    _cb_client = None

    def _init_chargebee():
        """Initialize Chargebee client from config"""
        global _cb_client
        if _cb_client is None:
            api_key = current_app.config.get("CHARGEBEE_API_KEY")
            site = current_app.config.get("CHARGEBEE_SITE")
            if not api_key or not site:
                raise RuntimeError("Chargebee is not configured")
            _cb_client = Chargebee(api_key=api_key, site=site)
        return _cb_client

    class HostedBilling:
        """Billing service using Chargebee's hosted pages."""

        @staticmethod
        def create_upgrade_session(
            workspace_id: int, user_email: str, base_url: str
        ) -> Any:
            """Create Chargebee Checkout session for workspace upgrade."""
            cb = _init_chargebee()
            item_price_id = current_app.config.get("CHARGEBEE_PRO_ITEM_PRICE_ID")
            if not item_price_id:
                raise RuntimeError("Chargebee item price not configured")

            result = cb.HostedPage.checkout_new_for_items(
                {
                    "subscription_items": [{"item_price_id": item_price_id}],
                    "customer": {"email": user_email},
                    "redirect_url": f"{base_url}billing/success",
                    "cancel_url": f"{base_url}dashboard",
                    "pass_thru_content": json.dumps({"workspace_id": str(workspace_id)}),
                }
            )
            hosted_page = result.hosted_page
            current_app.logger.info(f"Created Chargebee Checkout: {hosted_page.id}")
            return hosted_page

        @staticmethod
        def create_portal_session(
            customer_id: str, workspace_id: int, base_url: str
        ) -> Any:
            """Create Chargebee Portal session for billing management."""
            cb = _init_chargebee()
            result = cb.PortalSession.create(
                {
                    "customer": {"id": customer_id},
                    "redirect_url": f"{base_url}workspace/{workspace_id}/settings",
                }
            )
            portal_session = result.portal_session
            current_app.logger.info(
                f"Created Chargebee Portal session: {portal_session.id}"
            )

            # Wrap to provide consistent .url interface (Chargebee uses access_url)
            class PortalSessionWrapper:
                def __init__(self, session):
                    self.id = session.id
                    self.url = session.access_url

            return PortalSessionWrapper(portal_session)

        @staticmethod
        def handle_successful_payment(hosted_page_id: str) -> int:
            """Handle successful Chargebee payment by upgrading the workspace."""
            cb = _init_chargebee()
            result = cb.HostedPage.retrieve(hosted_page_id)
            hosted_page = result.hosted_page
            current_app.logger.info(
                f"Processing Chargebee checkout: {hosted_page.id} state={hosted_page.state}"
            )

            if hosted_page.state != "succeeded":
                current_app.logger.warning(
                    f"Checkout not succeeded: {hosted_page.id} state={hosted_page.state}"
                )
                return None

            pass_thru = json.loads(hosted_page.pass_thru_content or "{}")
            workspace_id = pass_thru.get("workspace_id")
            if not workspace_id:
                return None

            workspace = db.session.get(Workspace, int(workspace_id))
            if not workspace:
                return None

            if workspace.is_pro:
                return workspace.id

            try:
                workspace.plan = "pro"
                # Chargebee content is dict-like: content["customer"]["id"]
                workspace.billing_customer_id = hosted_page.content["customer"]["id"]
                workspace.upgraded_at = datetime.utcnow()
                db.session.commit()
                return workspace.id
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(
                    f"Failed to upgrade workspace {workspace_id}: {e}"
                )
                return None

else:
    raise RuntimeError(f"Unknown BILLING_PROVIDER: {PROVIDER}")


def requires_pro_plan(f):
    """Require Pro plan - assumes workspace context already set by require_workspace_access"""

    @wraps(f)
    def decorated(*args, **kwargs):
        workspace = get_current_workspace()
        if not workspace:
            return jsonify({"error": "Workspace not found"}), 404
        if not workspace.is_pro:
            if request.is_json or request.path.startswith("/api/"):
                return jsonify({"error": "Pro plan required"}), 402
            return redirect(
                url_for("portal.upgrade_workspace", workspace_id=workspace.id)
            )
        return f(*args, **kwargs)

    return decorated
