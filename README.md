# ReadyKit

**Production-ready Flask SaaS template**

Multi-tenant workspaces, Stripe billing, OAuth, and team collaboration out of the box. Build your product, not infrastructure.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**[Documentation](https://level09.github.io/readykit/)** · **[Live Demo](https://try.readykit.dev)**

---



https://github.com/user-attachments/assets/c955e2a2-8f25-4430-98fe-5bbc95ffb4da



---

## What's Included

- **Multi-tenant workspaces** - Data isolation, scales from solo to teams
- **Stripe billing** - Checkout, webhooks, customer portal
- **OAuth authentication** - Google & GitHub login
- **Team collaboration** - Roles (admin/member), member management
- **Modern stack** - Flask 3.1, Vue 3, Vuetify 3, PostgreSQL, Redis
- **Production ready** - Docker Compose, Celery background jobs

### The Smart Part

Workspaces are **invisible to solo users**:
- Sign in → Auto workspace created → Straight to your app
- No "select workspace" screens for single users
- Team features appear when you add members
- Multi-tenant infrastructure works behind the scenes

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
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PRO_PRICE_ID=price_...

# 3. Run
uv run flask create-db
uv run flask install
uv run flask run
```

Visit http://localhost:5000 and sign in with Google.

---

## Production Deploy

**One-Click Cloud Platforms:**

| Platform | Cost | Guide |
|----------|------|-------|
| [Fly.io](https://fly.io) | ~$5/month | [Setup Guide](docs/deployment/fly.md) |
| [Railway](https://railway.app) | ~$5/month | [Setup Guide](docs/deployment/railway.md) |

All platforms include PostgreSQL, Redis, and CI/CD (push to deploy).

**Docker Compose** - Self-hosted:
```bash
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
from enferno.services.workspace import WorkspaceScoped, require_workspace_access

class Invoice(db.Model, WorkspaceScoped):
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspace.id'))
    # your fields here

@app.get("/workspace/<int:workspace_id>/invoices/")
@require_workspace_access("member")
def invoices(workspace_id):
    invoices = Invoice.for_current_workspace()
    return render_template("invoices.html", invoices=invoices)
```

All queries are automatically scoped to the current workspace.

---

## AI-Assisted Development

Using Cursor, Claude Code, or GitHub Copilot? See [docs/agents.md](docs/agents.md) for patterns and conventions.

---

## License

MIT - Build and sell products freely.

---

Built for indie makers who ship. 🚀
