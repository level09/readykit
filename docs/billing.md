# Billing

Subscription billing with Stripe or Chargebee.

## Overview

ReadyKit uses hosted payment pages - no custom checkout UI to build or maintain. Users upgrade via the provider's checkout page and manage subscriptions through their portal.

::: warning Choose Your Provider First
Select your billing provider before going to production. Switching providers after users have subscribed requires manual migration of customer data. Set `BILLING_PROVIDER` in your environment and stick with it.
:::

## Supported Providers

| Provider | Best For |
|----------|----------|
| **Stripe** | Most SaaS apps, US/EU focus, extensive API |
| **Chargebee** | Complex billing needs, subscription management, international |

## Plans

Out of the box, ReadyKit supports two plans:

| Plan | Features |
|------|----------|
| **Free** | Basic access, limited features |
| **Pro** | Full access, all features |

Plans are stored on the `Workspace` model, not the user. This means the entire team shares the same plan.

## Stripe Setup

### 1. Get Your Keys

From [Stripe Dashboard](https://dashboard.stripe.com):

1. **API Keys** → Copy your secret key and publishable key
2. **Products** → Create a product with a recurring price
3. **Webhooks** → Add endpoint (see below)

### 2. Configure Environment

```bash
# .env
BILLING_PROVIDER=stripe

STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_PRO_PRICE_ID=price_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Display values (shown in UI)
PRO_PRICE_DISPLAY=$29
PRO_PRICE_INTERVAL=month
```

### 3. Set Up Webhook

In Stripe Dashboard → Webhooks → Add endpoint:

- **URL**: `https://yourdomain.com/stripe/webhook`
- **Events to listen for**:
  - `checkout.session.completed`
  - `checkout.session.async_payment_succeeded`
  - `customer.subscription.created`
  - `customer.subscription.updated`
  - `customer.subscription.deleted`
  - `customer.subscription.paused`
  - `customer.subscription.resumed`
  - `invoice.payment_failed`
  - `invoice.paid`

Copy the signing secret to `STRIPE_WEBHOOK_SECRET`.

## Chargebee Setup

### 1. Get Your Credentials

From [Chargebee Dashboard](https://app.chargebee.com):

1. **Settings → API Keys** → Copy your API key
2. **Product Catalog → Items** → Create an item with a price
3. **Settings → Webhooks** → Add endpoint (see below)

### 2. Configure Environment

```bash
# .env
BILLING_PROVIDER=chargebee

CHARGEBEE_SITE=your-site          # e.g., "acme" for acme.chargebee.com
CHARGEBEE_API_KEY=your_api_key
CHARGEBEE_PRO_ITEM_PRICE_ID=Pro-Plan-USD-Monthly

# Webhook authentication (required in production)
CHARGEBEE_WEBHOOK_USERNAME=webhook_user
CHARGEBEE_WEBHOOK_PASSWORD=your_secure_password

# Display values (shown in UI)
PRO_PRICE_DISPLAY=$29
PRO_PRICE_INTERVAL=month
```

### 3. Set Up Webhook

In Chargebee Dashboard → Settings → Webhooks → Add webhook:

- **URL**: `https://yourdomain.com/chargebee/webhook`
- **Authentication**: Basic Auth with your configured username/password
- **Events to listen for**:
  - `subscription_cancelled`
  - `subscription_created`
  - `subscription_started`
  - `subscription_activated`
  - `subscription_changed`
  - `subscription_reactivated`
  - `subscription_paused`
  - `subscription_resumed`
  - `subscription_renewed`
  - `subscription_cancellation_scheduled`
  - `subscription_scheduled_cancellation_removed`
  - `payment_failed`
  - `payment_succeeded`

::: info Chargebee Webhook Security
Chargebee uses HTTP Basic Auth for webhook verification (not HMAC signatures like Stripe). Always configure `CHARGEBEE_WEBHOOK_USERNAME` and `CHARGEBEE_WEBHOOK_PASSWORD` in production. Unauthenticated webhooks are only allowed in debug mode for local testing.
:::

## How Billing Works

### Upgrade Flow

```
User clicks "Upgrade"
    → Create checkout session
    → Redirect to provider's hosted page
    → User completes payment
    → Provider redirects to success URL
    → Validate session
    → Save the billing customer and read current subscriptions
    → Grant Pro if the configured price has an eligible subscription
```

```python
from enferno.services.billing import HostedBilling

@app.route("/workspace/<int:workspace_id>/upgrade/")
@require_workspace_access("admin")
def upgrade(workspace_id):
    session = HostedBilling.create_upgrade_session(
        workspace_id=workspace_id,
        user_email=current_user.email,
        base_url=request.host_url
    )
    return redirect(session.url)
```

### Success Callback

The existing `/billing/success` route requires login and accepts Stripe's
`session_id` or Chargebee's `id`. It calls
`HostedBilling.handle_successful_payment()` to validate the hosted checkout with
the provider, link the customer, and reconcile the current subscription state.
It renders a success page only when that state grants Pro access.

The checkout ID alone is not proof of entitlement. Revisiting an old successful
checkout must not restore a canceled subscription. Keep provider validation and
subscription reconciliation in the shared billing service.

### Manage Billing (Customer Portal)

Workspace admins with a linked billing customer can use the provider's portal,
including after losing Pro access. Both providers return to `/workspace/settings/`.

```python
@app.route("/workspace/<int:workspace_id>/billing/")
@require_workspace_access("admin")
def manage_billing(workspace_id):
    workspace = g.current_workspace

    if not workspace.billing_customer_id:
        return redirect(url_for("portal.upgrade_workspace"))

    session = HostedBilling.create_portal_session(
        customer_id=workspace.billing_customer_id,
        workspace_id=workspace_id,
        base_url=request.host_url
    )
    return redirect(session.url)
```

## Webhook Handlers

Webhooks read current subscriptions from the provider before changing a workspace's
plan. Event payloads can be old or arrive out of order. Access is based on the
current subscription state for the configured Pro price, not the event's old state.

### Stripe Events

| Event | Action |
|-------|--------|
| `checkout.session.completed`, `checkout.session.async_payment_succeeded` | Validate checkout, save customer ID, reconcile access |
| Subscription created, updated, deleted, paused, resumed | Reconcile access |
| `invoice.payment_failed`, `invoice.paid` | Reconcile access, including payment recovery |

Stripe subscriptions with status `active` or `trialing` grant Pro. Other states,
including `past_due`, `unpaid`, `paused`, and `canceled`, grant Free. Cancellation
scheduled for the end of a term keeps access while the subscription is active.

### Chargebee Events

| Event | Action |
|-------|--------|
| Subscription lifecycle events listed above | Reconcile access |
| `payment_failed`, `payment_succeeded` | Reconcile access, including payment recovery |

Chargebee subscriptions with status `active`, `in_trial`, or `non_renewing` grant
Pro. Other states grant Free. An active subscription keeps access during payment
retries until Chargebee changes its status. Configure Chargebee's dunning policy
to cancel or pause subscriptions when access should end.

::: tip Chargebee Upgrades
The first Chargebee checkout still requires the success redirect to link the
customer to the workspace. Once linked, webhooks handle recovery and later plan
changes. Initial checkout without a browser return is not covered by this flow.
:::

### Idempotency

The `BillingEvent` receipt and the plan update commit in one transaction. Provider
or database failures return HTTP 500 and roll back the receipt, so the provider can
retry the same event. Only events already committed are acknowledged as duplicates.
Handled events whose customer is not linked yet also return HTTP 500. This keeps
early events retryable until checkout commits the customer link, even if the
subscription changes price before that commit. Events for unrelated or deleted
customers also retry; use a provider account dedicated to this application, and
investigate persistent unlinked-customer errors. Linked customers without an
eligible subscription for the configured Pro price receive Free access.

PostgreSQL row locks serialize subscription reads and plan writes for each
workspace. SQLite remains suitable for local development, but does not provide
this row-lock behavior. Checkout redirects use the same reconciliation path, so
revisiting an old checkout cannot restore a cancelled subscription.

Existing customer IDs are reused for new checkouts. A checkout from a different
customer cannot replace the workspace's current customer mapping.

### Upgrading an Existing Installation

There is no database migration. Enable the additional events listed above in your
provider's webhook settings. Keep the Pro price configuration aligned with the
subscriptions that should grant access.

Receipts committed by the old handler cannot establish whether processing
succeeded. This fix does not repair those old events automatically; reconcile
affected workspaces against the provider before changing existing receipts.

## Gating Features

Use the `@requires_pro_plan` decorator to restrict features:

```python
from enferno.services.billing import requires_pro_plan

@app.route("/workspace/<int:workspace_id>/advanced-feature/")
@require_workspace_access("member")
@requires_pro_plan
def advanced_feature(workspace_id):
    # Only Pro workspaces can access this
    return render_template("advanced.html")
```

For API endpoints, it returns a `402 Payment Required` response:

```json
{"error": "Pro plan required"}
```

For web pages, it redirects to the upgrade page.

## Testing Locally

### Stripe

Use [Stripe CLI](https://stripe.com/docs/stripe-cli) to test webhooks locally:

```bash
# Install Stripe CLI
brew install stripe/stripe-cli/stripe

# Login
stripe login

# Forward webhooks to local server
stripe listen --forward-to localhost:5000/stripe/webhook

# Put the listener's whsec_... value in STRIPE_WEBHOOK_SECRET, then restart the app.
# Open /workspace/upgrade as a workspace admin and complete a sandbox checkout.
```

Use a sandbox price for `STRIPE_PRO_PRICE_ID` and credentials from the same sandbox.
Generic CLI fixture events do not carry ReadyKit's workspace mapping or necessarily
use its configured price, so they do not prove the full upgrade flow.

The Stripe sandbox flow has been checked for checkout, failed renewal, payment
recovery, cancellation, duplicate events, and portal return. Chargebee coverage
uses SDK fixtures; a real Chargebee sandbox run remains pending. Run the automated
suite for both providers as described in [Contributing](https://github.com/level09/readykit/blob/master/CONTRIBUTING.md).

### Chargebee

Use [ngrok](https://ngrok.com) to expose your local server:

```bash
# Start ngrok
ngrok http 5000

# In Chargebee Dashboard:
# 1. Add webhook URL: https://your-ngrok-url.ngrok.io/chargebee/webhook
# 2. Set Basic Auth credentials matching your .env
# 3. Trigger test events from the webhook settings page
```

For local testing without authentication, set `FLASK_DEBUG=1` - webhooks will be accepted without Basic Auth in debug mode.

## Checking Plan Status

```python
# In routes (after @require_workspace_access)
workspace = g.current_workspace
if workspace.is_pro:
    # Pro features
    pass
```

```html
<!-- In templates -->
{% if get_current_workspace().is_pro %}
  <span class="badge">Pro</span>
{% else %}
  <a href="{{ url_for('portal.upgrade_workspace') }}">
    Upgrade to Pro
  </a>
{% endif %}
```

## Workspace Model Fields

```python
class Workspace(db.Model):
    # Billing fields
    plan = db.Column(db.String(20), default="free")  # "free" or "pro"
    billing_customer_id = db.Column(db.String(255))  # Provider customer ID
    upgraded_at = db.Column(db.DateTime)             # When they upgraded

    @property
    def is_pro(self):
        return self.plan == "pro"
```

## Provider Comparison

| Feature | Stripe | Chargebee |
|---------|--------|-----------|
| Webhook auth | HMAC signature | Basic Auth |
| Upgrade via | Redirect + Webhook | Redirect only |
| Portal URL field | `.url` | `.access_url` (wrapped) |
| Session param | `session_id` | `id` |
| Customer ID location | `session.customer` | `hosted_page.content["customer"]["id"]` |
