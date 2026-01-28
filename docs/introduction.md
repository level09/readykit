# Introduction

ReadyKit is a production-ready Flask SaaS template that gives you everything you need to build and ship a multi-tenant SaaS application. Instead of spending weeks setting up authentication, billing, and team management, you can focus on building your actual product.

Built on the [Enferno framework](https://github.com/level09/enferno), ReadyKit adds the essential SaaS features that every subscription business needs.

## Key Features

### Multi-Tenant Workspaces

Every user gets their own workspace. Data is automatically scoped to workspaces, ensuring complete isolation between customers.

- Automatic workspace creation on signup
- Workspace-scoped data models
- Session-based workspace context
- Solo users never see workspace UI (invisible until they need teams)

### Subscription Billing

Stripe or Chargebee - your choice. Hosted pages, no custom checkout UI to maintain.

- Hosted checkout for upgrades
- Customer portal for subscription management
- Webhook handlers for plan changes
- Free and Pro plan support out of the box

### Team Collaboration

Invite team members to your workspace with role-based access control.

- Admin and Member roles
- Email invitations
- Member management UI
- Owner protection (can't be removed or demoted)

### Authentication

Comprehensive auth system with modern security features.

- Email/password with Argon2 hashing
- OAuth (Google, GitHub)
- Two-factor authentication (TOTP)
- WebAuthn/Passkeys support
- Password recovery

### Modern Stack

- **Backend**: Python 3.11+, Flask 3.1, SQLAlchemy 2.0
- **Frontend**: Vue 3, Vuetify 3 (Material Design)
- **Database**: PostgreSQL (production), SQLite (development)
- **Task Queue**: Celery with Redis
- **Deployment**: Docker Compose ready

## Documentation

| Section | Description |
|---------|-------------|
| [Quick Start](/getting-started) | Get up and running in 5 minutes |
| [Workspaces](/workspaces) | Multi-tenant architecture guide |
| [Billing](/billing) | Stripe/Chargebee integration and plans |
| [Teams](/teams) | Member management and roles |

## Who is ReadyKit For?

- **Solo developers** building their first SaaS
- **Startups** that need to ship fast without reinventing the wheel
- **Agencies** looking for a solid foundation for client projects
- **Teams** that want a battle-tested Flask architecture

## Source Code

The source code is available on [GitHub](https://github.com/level09/readykit).
