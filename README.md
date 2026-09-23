# ReadyKit

**Production-ready Flask SaaS template**

Multi-tenant workspaces, subscription billing (Stripe or Chargebee), OAuth, and team collaboration out of the box. Build your product, not infrastructure.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Checks](https://github.com/level09/readykit/actions/workflows/checks.yml/badge.svg)](https://github.com/level09/readykit/actions/workflows/checks.yml)
[![Documentation](https://github.com/level09/readykit/actions/workflows/docs.yml/badge.svg)](https://github.com/level09/readykit/actions/workflows/docs.yml)
[![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://www.python.org/)

**[Documentation](https://level09.github.io/readykit/)** · **[Live Demo](https://try.readykit.dev)**

---



https://github.com/user-attachments/assets/c955e2a2-8f25-4430-98fe-5bbc95ffb4da



---

## What's Included

- **Multi-tenant workspaces** - Data isolation, scales from solo to teams
- **Subscription billing** - Stripe or Chargebee, hosted checkout, webhooks, customer portal
- **OAuth authentication** - Google & GitHub login
- **Team collaboration** - Roles (admin/member), member management
- **Modern stack** - Flask 3.1, Vue 3, Vuetify 3, PostgreSQL, Redis
- **Production ready** - Docker Compose, Celery background jobs

### Workspace Flow

New OAuth accounts receive a workspace. Non-superadmins with one workspace skip
the selection screen. Team, API key, and settings pages remain available according
to the user's role. Superadmins manage workspaces from the dashboard.

---

## Quick Start

```bash
# 1. Clone and setup
git clone git@github.com:level09/readykit.git
cd readykit
./setup.sh

# 2. Configure (edit .env)
GOOGLE_OAUTH_CLIENT_ID=your_id
GOOGLE_OAUTH_CLIENT_SECRET=your_secret

# Billing: choose stripe (default) or chargebee
BILLING_PROVIDER=stripe
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PRO_PRICE_ID=price_...

# 3. Run
uv run flask create-db
uv run flask install
uv run flask run
```

Visit http://localhost:5000 and sign in with the admin credentials from `flask install`.
Google login is available after configuring OAuth.

Local setup uses SQLite for data and sessions; Redis is not required. Use
`./setup.sh --full` for Redis sessions and Celery, or select Docker during setup
for the full production stack. See the [setup guide](docs/getting-started.md).

---

## Production Deploy

**Cloud Platforms:**

| Platform | Guide |
|----------|-------|
| Fly.io | [Setup Guide](docs/deployment/fly.md) |
| Railway | [Setup Guide](docs/deployment/railway.md) |

The platform guides cover PostgreSQL, Redis, and deployment workflows. Deployment
workflows run manually unless you enable their push triggers. Check provider
pricing for your chosen resources.

**Docker Compose** - Self-hosted:
```bash
./setup.sh  # Select Docker; review .env before starting
docker compose up --build
```

Includes PostgreSQL, Redis, Nginx, Celery.

**VPS Deploy** - One command for Ubuntu (Hetzner, DigitalOcean, etc.):
```bash
curl -sSL https://raw.githubusercontent.com/level09/ignite/main/ignite.sh | sudo DOMAIN=your-domain.com REPO=level09/readykit bash
```

Handles Caddy (auto SSL), Python 3.13, Redis, systemd. See [Ignite](https://github.com/level09/ignite).

---

## Customize

ReadyKit handles auth, billing, workspaces, and teams. You add your product features.

Example - workspace-scoped model:
```python
from enferno.extensions import db
from flask import render_template
from enferno.services.workspace import WorkspaceScoped, require_workspace_access

class Invoice(db.Model, WorkspaceScoped):
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspace.id'), nullable=False)
    # your fields here

@app.get("/workspace/<int:workspace_id>/invoices/")
@require_workspace_access("member")
def invoices(workspace_id):
    invoices = Invoice.for_current_workspace()
    return render_template("invoices.html", invoices=invoices)
```

The decorator checks membership; `for_current_workspace()` and `get_by_id()`
filter records to the selected workspace. Ordinary SQLAlchemy queries are not
automatically filtered. Use these helpers or an explicit `workspace_id` filter
for every query on workspace data. See the [workspace guide](docs/workspaces.md).

### Database Migrations

Schema changes are managed with Alembic. Autogenerate drafts the migration;
review and edit it before applying:

```bash
uv run flask db migrate -m "add invoice table"   # Draft from model changes
# Review migrations/versions/<revision>.py
uv run flask db upgrade                          # Apply
```

`create-db` stamps fresh databases automatically. Databases created before
migrations existed need `uv run flask db stamp head` once.

---

## AI-Assisted Development

Using Cursor, Claude Code, or GitHub Copilot? See [docs/agents.md](docs/agents.md) for patterns and conventions.

---

## Community

Questions and showcases belong in [GitHub Discussions](https://github.com/level09/readykit/discussions).
Reproducible bugs and scoped work belong in [GitHub Issues](https://github.com/level09/readykit/issues).
See [CONTRIBUTING.md](CONTRIBUTING.md) and the [roadmap](docs/roadmap.md) before opening a pull request.

---

## License

MIT - Build and sell products freely.
