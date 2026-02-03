# AGENTS.md

Context for AI agents working with ReadyKit, a Flask SaaS template with multi-tenant workspaces.

## Stack

- **Backend**: Flask 3.1, SQLAlchemy 2.x, Flask-Security-Too
- **Frontend**: Vue 3 + Vuetify 3 (no build step, loaded from static/)
- **Database**: PostgreSQL (production), SQLite (dev)
- **Auth**: Email/password, OAuth (Google, GitHub), 2FA, WebAuthn
- **Billing**: Stripe or Chargebee (via `BILLING_PROVIDER` env var)
- **Package Manager**: uv

## Commands

```bash
./setup.sh                    # First-time setup
uv run flask create-db        # Initialize database
uv run flask install          # Create admin user
uv run flask run              # Dev server on :5000
uv run ruff check --fix .     # Lint
uv run ruff format .          # Format
docker compose up --build     # Production stack
```

## Project Structure

```
enferno/
├── app.py              # Application factory
├── settings.py         # Single Config class (env-based)
├── extensions.py       # Flask extensions (db, cache, mail, session)
├── public/views.py     # Landing, login, register (no auth)
├── portal/views.py     # Dashboard, workspace routes (authenticated)
├── user/
│   ├── views.py        # Superadmin CMS (user management)
│   └── models.py       # User, Workspace, Membership, etc.
├── api/webhooks.py     # Stripe/Chargebee webhooks
├── services/
│   ├── workspace.py    # Multi-tenant: WorkspaceService, require_workspace_access
│   ├── billing.py      # HostedBilling, requires_pro_plan
│   └── auth.py         # OAuth handlers
├── static/js/config.js # Vue config with custom delimiters
└── templates/          # All Jinja2 templates (single directory)
```

## Critical: Vue Delimiters

Uses `${` `}` for Vue (not `{{ }}`):

```html
<!-- Vue expressions -->
<v-card-title>${ user.name }</v-card-title>

<!-- Jinja (server-side) -->
{% if current_user.is_authenticated %}
```

## Vue App Pattern

```html
{% extends 'layout.html' %}

{% block content %}
<v-container>
    <h1>${ title }</h1>
</v-container>
{% endblock %}

{% block js %}
<script>
const {createApp} = Vue;
const {createVuetify} = Vuetify;
const vuetify = createVuetify(config.vuetifyConfig);

const app = createApp({
    mixins: [layoutMixin],  // Required: provides drawer, isMobile
    delimiters: config.delimiters,  // Required: ${ }
    data() {
        return {
            title: 'Page Title',
            items: []
        };
    },
    methods: {
        async loadData() {
            const response = await axios.get('/api/items');
            this.items = response.data.items;
        }
    },
    mounted() {
        this.loadData();
    }
});

app.use(vuetify).mount('#app');
</script>
{% endblock %}
```

## SQLAlchemy 2.x Queries

Use statement-based queries, not legacy `.query`:

```python
from enferno.extensions import db

# Select
stmt = db.select(User).where(User.active == True)
users = db.session.scalars(stmt).all()

# Single item
user = db.session.get(User, user_id)

# Pagination
query = db.select(User)
pagination = db.paginate(query, page=page, per_page=per_page)

# Update
stmt = db.update(User).where(User.id == user_id).values(active=False)
db.session.execute(stmt)
db.session.commit()
```

## Multi-Tenant Workspaces

All business data belongs to a workspace. Use `WorkspaceScoped` mixin:

```python
from enferno.services.workspace import WorkspaceScoped
from enferno.extensions import db

class Invoice(db.Model, WorkspaceScoped):
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspace.id"), nullable=False)

# Query within current workspace
invoices = Invoice.for_current_workspace()
invoice = Invoice.get_by_id(invoice_id)
```

### Route Protection

```python
from enferno.services.workspace import require_workspace_access
from flask import g

@portal.get("/workspace/<int:workspace_id>/data/")
@require_workspace_access("member")  # or "admin"
def view_data(workspace_id):
    # g.current_workspace and g.user_workspace_role are set
    return render_template("data.html", workspace=g.current_workspace)
```

### WorkspaceService

```python
from enferno.services.workspace import WorkspaceService

WorkspaceService.create_workspace(name="Acme", owner_user=user)
WorkspaceService.add_member(workspace_id, user, role="member")
WorkspaceService.remove_member(workspace_id, user_id)
WorkspaceService.update_member_role(workspace_id, user_id, "admin")
```

## Billing

Hosted checkout only (no custom UI):

```python
from enferno.services.billing import HostedBilling, requires_pro_plan

# Upgrade
session = HostedBilling.create_upgrade_session(
    workspace_id=ws.id, user_email=user.email, base_url=request.host_url
)
return redirect(session.url)

# Portal (manage subscription)
session = HostedBilling.create_portal_session(
    customer_id=workspace.billing_customer_id,
    workspace_id=workspace.id,
    base_url=request.host_url
)
return redirect(session.url)

# Gate pro features
@require_workspace_access("member")
@requires_pro_plan
def pro_feature(workspace_id):
    pass
```

## API Pattern

```python
@api.get("/api/items")
def get_items():
    page = request.args.get("page", 1, type=int)
    query = db.select(Item)
    pagination = db.paginate(query, page=page, per_page=25)
    return jsonify({
        "items": [i.to_dict() for i in pagination.items],
        "total": pagination.total
    })

@api.post("/api/items/<int:item_id>")
def update_item(item_id):
    item = db.session.get(Item, item_id)
    if not item:
        return jsonify({"error": "Not found"}), 404
    item.from_dict(request.get_json())
    db.session.commit()
    return jsonify({"message": "Updated", "data": item.to_dict()})
```

## Blueprint Protection

```python
# Require auth for all routes in blueprint
@portal.before_request
@auth_required("session")
def before_request():
    pass

# Superadmin only (user management CMS)
@bp_user.before_request
@auth_required("session")
def before_request():
    if not current_user.is_superadmin:
        abort(403)
```

## Security

- Always use `@require_workspace_access()` on workspace routes
- Never query business data without workspace scope
- Webhook signature verification required (STRIPE_WEBHOOK_SECRET or Chargebee auth)
- `requires_pro_plan` must come AFTER `require_workspace_access`

## Code Style

- Python 3.11+, 88-char lines, double quotes
- Modern SQLAlchemy (`db.select()`, not `.query`)
- Ruff for linting/formatting
- Selective git add (never `git add .`)
- No AI mentions in commits

## Key Files

- `enferno/services/workspace.py` - Multi-tenant core
- `enferno/services/billing.py` - Stripe/Chargebee
- `enferno/user/models.py` - User, Workspace, Membership
- `enferno/static/js/config.js` - Vue delimiters and theme
- `enferno/templates/layout.html` - Base template with app shell
