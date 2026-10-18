# Roadmap

Direction, not delivery dates. See [CHANGELOG.md](https://github.com/level09/readykit/blob/master/CHANGELOG.md)
for release history. Version 1.7.4 makes `AGENTS.md` the single agent instruction file;
1.7.3 adds `flask stripe-listen` and moves the dev server to port 5050.

## In 1.7.4

- One instruction file, `AGENTS.md`, read by every coding agent including Claude Code.

## In 1.7.3

- `flask stripe-listen` forwards exactly the handled Stripe events with the app's test key.
- Dev server on port 5050, clear of macOS AirPlay Receiver on 5000.

## In 1.7.2

- `FLASK_APP` lives in a committed `.flaskenv`, so `flask` commands work with any `.env`.

A full `stripe projects build` of the ReadyKit template passed setup, database, billing
and app checks on a provisioned Neon database.

## In 1.7.1

- Rerunning `./setup.sh` edits `.env` in place and no longer rotates password and 2FA secrets.
- `NEON_POSTGRES_CONNECTION_STRING` from Stripe Projects is used as the database URL.
- `checks.py --config` fails when the SQLite default hides a provisioned database.
- Docker setup uses the host user ID and secure cookies.

Stripe Projects provisioning, setup and reruns were verified on a live account.

## In 1.7.0

- Verified provider email required before OAuth links or creates an account.
- Unpaid subscriptions route to the billing portal instead of a second checkout.
- A per-customer lock orders checkout with webhook events on PostgreSQL.
- SQLAlchemy 2.1 with psycopg 3, Flask-Security-Too 5.9, Stripe 16, Python 3.14 in CI.
- Browser journeys against a Stripe sandbox, including a failed renewal on a test clock.
- One page header, form, dialog and error page design across the app.

## In 1.6.0

- `flask stripe-setup` creates the Pro price and local webhook secret from an `sk_test_` key.
- `./setup.sh --yes` for non-interactive setup that keeps a provisioned `DATABASE_URL`.
- `DATABASE_URL` fallback for Stripe Projects, Fly.io, and Railway databases.
- OAuth providers enabled by their credentials; a fresh install passes `checks.py --config`.

The Stripe sandbox flow was rerun end to end with `stripe-setup`. A Stripe Projects
template listing is pending a live-account test of provisioning order and
`stripe projects env --pull`.

## In 1.5.1

- Retry-safe billing webhooks and plan reconciliation from current subscriptions.
- Billing portal return to workspace settings.
- Workspace isolation tests and explicit query-scoping guidance.
- Docker runtime dependencies and a worker-specific Celery health check.
- SQLite sessions for local setup; Redis and Celery through `--full` or Docker setup.
- Configuration checks before app startup with `checks.py --config` and optional billing checks.
- PostgreSQL test matrix for both providers across Python 3.11, 3.12, and 3.13.

Stripe checkout and recovery flows have been exercised in a sandbox. Chargebee has
automated SDK fixture coverage; a real sandbox run is still pending.

## Possible Follow-ups

These are options to evaluate against user needs, not release requirements:

- Email invitations for products that need teams.
- A workspace-scoped CRUD recipe if the existing examples are insufficient.
- A template update workflow if maintaining derived projects becomes a recurring problem.

## Further Verification

- Run the Chargebee checkout and recovery flow in a real sandbox.
- Verify deployment on Fly.io and Railway; local configuration checks are not a
  substitute for deployed tests.
- Improve accessibility and keyboard navigation in the application shell.

Proposals belong in [GitHub Discussions](https://github.com/level09/readykit/discussions).
