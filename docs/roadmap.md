# Roadmap

Direction, not delivery dates. See [CHANGELOG.md](https://github.com/level09/readykit/blob/master/CHANGELOG.md)
for release history. Version 1.5.1 focuses on reliable billing, workspace isolation,
and a smaller local setup for solo builders.

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
