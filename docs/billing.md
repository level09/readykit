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
  - `customer.subscription.deleted`
  - `invoice.payment_failed`

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
  - `payment_failed`

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
    → Upgrade workspace to Pro
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

The success URL includes a session ID that's validated server-side:

```python
@app.route("/billing/success")
def billing_success():
    # Works with both Stripe (session_id) and Chargebee (id)
    session_id = request.args.get("session_id") or request.args.get("id")
    workspace_id = HostedBilling.handle_successful_payment(session_id)

    if workspace_id:
        flash("Welcome to Pro!")
        return redirect(url_for("portal.workspace_settings", workspace_id=workspace_id))

    flash("Payment processing failed")
    return redirect(url_for("portal.dashboard"))
```

::: info
The session ID is the security token. Always validate it via the provider's API before upgrading - never trust URL parameters directly.
:::

### Manage Billing (Customer Portal)

Existing Pro users can manage their subscription through the provider's portal:

```python
@app.route("/workspace/<int:workspace_id>/billing/")
@require_workspace_access("admin")
def manage_billing(workspace_id):
    workspace = g.current_workspace

    if not workspace.billing_customer_id:
        return redirect(url_for("portal.upgrade", workspace_id=workspace_id))

    session = HostedBilling.create_portal_session(
        customer_id=workspace.billing_customer_id,
        workspace_id=workspace_id,
        base_url=request.host_url
    )
    return redirect(session.url)
```

## Webhook Handlers

Webhooks update workspace status automatically when billing changes:

### Stripe Events

| Event | Action |
|-------|--------|
| `checkout.session.completed` | Upgrade workspace to Pro, save customer_id |
| `customer.subscription.deleted` | Downgrade workspace to Free |
| `invoice.payment_failed` | Downgrade workspace to Free |

### Chargebee Events

| Event | Action |
|-------|--------|
| `subscription_cancelled` | Downgrade workspace to Free |
| `payment_failed` | Downgrade workspace to Free |

::: tip Chargebee Upgrades
Chargebee upgrades are handled via the redirect flow only (not webhooks). This is intentional - the webhook would arrive after the redirect in most cases anyway.
:::

### Idempotency

Webhooks are idempotent - duplicate events are safely ignored using the `BillingEvent` model:

```python
# Duplicate events are caught by unique constraint
try:
    db.session.add(BillingEvent(
        event_id=event_id,
        event_type=event_type,
        provider="stripe"  # or "chargebee"
    ))
    db.session.commit()
except IntegrityError:
    db.session.rollback()
    return "OK", 200  # Already processed
```

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

# In another terminal, trigger test events
stripe trigger checkout.session.completed
stripe trigger customer.subscription.deleted
```

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
  <a href="{{ url_for('portal.upgrade', workspace_id=workspace.id) }}">
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
