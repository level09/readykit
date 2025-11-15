# ReadyKit

**Production-ready Flask SaaS template for indie makers**

Ship your SaaS in days, not months. ReadyKit gives you multi-tenant workspaces, Stripe billing, team collaboration, and authentication out of the box—so you can focus on building features customers will pay for.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

---

## Why ReadyKit?

Building a SaaS from scratch means weeks of infrastructure work before you write a single feature. ReadyKit eliminates that.

**You get:**
- ✅ **Multi-tenant workspaces** - Scales from solo users to enterprise teams
- ✅ **Stripe billing** - Checkout, webhooks, and customer portal ready
- ✅ **OAuth authentication** - Google & GitHub login built-in
- ✅ **Team collaboration** - Invite members, assign roles (admin/member)
- ✅ **Modern stack** - Flask + Vue 3 + Vuetify (no build step)
- ✅ **Production-ready** - Docker, Redis sessions, PostgreSQL

**Instead of building infrastructure, you build your product.**

---

## The Smart Part: Invisible Workspaces

Most SaaS templates force workspace complexity on all users. ReadyKit hides it for solo users and reveals it when needed:

**Solo user (Day 1):**
- Signs in with Google → Auto workspace created
- Goes directly to your app (no "select workspace" screen)
- Just works like a single-user product ✨

**Growing team (Month 3):**
- Adds teammates via simple admin panel
- Everyone collaborates in same workspace
- No migration, no rebuild—it just works

**Power user (Year 1):**
- Creates multiple workspaces or joins teams
- Workspace switcher appears automatically
- Full multi-tenant SaaS ready

**This is the secret:** Multi-tenancy without the complexity.

---

## What's Included

### Authentication & Users
- OAuth (Google, GitHub) for instant signup
- Email/password for team invites
- 2FA & WebAuthn support
- Session management with Redis

### Multi-Tenancy & Teams
- Workspace isolation (each tenant gets own data)
- Automatic workspace creation on signup
- Role-based access (admin/member)
- Team member management

### Billing & Payments
- Stripe Checkout integration
- Customer Portal (manage subscriptions)
- Webhook handlers (auto-downgrade on cancellation/failure)
- Free & Pro tier ready

### Tech Stack
- **Backend:** Flask 3.1, SQLAlchemy 2.x, Python 3.11+
- **Frontend:** Vue 3, Vuetify 3 (Material Design, no build step)
- **Database:** PostgreSQL (SQLite for dev)
- **Cache:** Redis
- **Background Jobs:** Celery
- **Production:** Docker Compose, Nginx

---

## Quick Start

### 1. Clone and Setup

```bash
git clone git@github.com:level09/readykit.git
cd readykit
./setup.sh  # Creates environment, installs dependencies, generates .env
```

### 2. Configure OAuth & Stripe

Edit `.env`:
```bash
# Google OAuth (get from console.cloud.google.com)
GOOGLE_OAUTH_CLIENT_ID=your_client_id
GOOGLE_OAUTH_CLIENT_SECRET=your_client_secret

# Stripe (get from dashboard.stripe.com)
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PRO_PRICE_ID=price_...
PRO_PRICE_DISPLAY=$29
PRO_PRICE_INTERVAL=month
```

### 3. Initialize & Run

```bash
uv run flask create-db  # Create database tables
uv run flask install    # Create super admin user
uv run flask run        # Start dev server → http://localhost:5000
```

### 4. Test the Flow

1. Sign in with Google → Workspace auto-created
2. You land directly in your workspace (no selection screen)
3. Try Settings → See billing/upgrade options
4. Try Team (if admin) → Add teammates

**That's it. You're building your product now.**

---

## Production Deployment

### Docker (Recommended)

```bash
docker compose up --build
```

Includes: Flask, PostgreSQL, Redis, Nginx, Celery—ready to deploy.

### Manual Deploy

Works on any VPS, Render, Railway, Fly.io:

1. Set production environment variables
2. Use PostgreSQL (not SQLite)
3. Enable Redis for sessions
4. Set `FLASK_ENV=production`
5. Configure Stripe webhooks

See `docs/` for detailed deployment guides.

---

## Who Is This For?

**Perfect for:**
- 🚀 Indie makers launching their first SaaS
- 💼 Freelancers building client products
- 🏗️ Startups validating ideas quickly
- 👨‍💻 Developers tired of boilerplate

**Not ideal for:**
- Pure B2C social apps (no teams needed)
- Real-time chat/collaborative editing (needs WebSockets)
- Mobile-first apps (web-focused, though API exists)

---

## Customize for Your Product

ReadyKit is a **foundation**, not a finished product. You add:

1. **Your core feature** - Invoices, projects, analytics, whatever you're building
2. **Your data models** - Extend with workspace-scoped tables
3. **Your business logic** - The unique value customers pay for
4. **Your branding** - Replace logo, colors, copy

**Example: Building an invoice tool?**

```python
# Your model (workspace-scoped)
from enferno.services.workspace import WorkspaceScoped

class Invoice(db.Model, WorkspaceScoped):
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspace.id'))
    # ... your invoice fields

# Your protected route
from enferno.services.workspace import require_workspace_access

@app.get("/workspace/<int:workspace_id>/invoices/")
@require_workspace_access("member")
def invoices(workspace_id):
    invoices = Invoice.for_current_workspace()  # Auto-scoped!
    return render_template("invoices.html", invoices=invoices)
```

**ReadyKit handles:** Auth, billing, teams, workspaces
**You handle:** Making invoices awesome

---

## Time Saved

Setting this up from scratch:
- Multi-tenant architecture: 1-2 weeks
- Stripe integration: 3-5 days
- OAuth setup: 2-3 days
- Team features: 1 week
- Production Docker: 2-3 days

**Total: 3-4 weeks of infrastructure work**

With ReadyKit: **10 minutes to running app**

---

## Documentation

- [Architecture Guide](docs/multi-tenant-implementation.md) - How multi-tenancy works
- [Quick Start](docs/TEMPLATE-QUICK-START.md) - Detailed setup guide
- [Deployment](docs/LEAN-LAUNCH.md) - Production deployment
- [Development](CLAUDE.md) - Development patterns

---

## Support & Community

- **Issues:** [GitHub Issues](https://github.com/level09/readykit/issues)
- **Discussions:** [GitHub Discussions](https://github.com/level09/readykit/discussions)
- **Updates:** Watch this repo for updates

---

## License

MIT License - Use it to build profitable products. No strings attached.

---

## Built With

ReadyKit is built on [Enferno](https://github.com/level09/enferno), a modern Flask framework optimized for rapid development.

**Ready to ship?** Clone, configure, and start building your product today. 🚀
