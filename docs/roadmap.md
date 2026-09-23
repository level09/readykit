# Roadmap

Direction, not delivery dates. See [CHANGELOG.md](https://github.com/level09/readykit/blob/master/CHANGELOG.md)
for release history. Version 1.5.1 remains unreleased.

## Implemented for 1.5.1

- Retry-safe billing webhooks and plan reconciliation from current subscriptions.
- Billing portal return to workspace settings.
- Workspace isolation tests and explicit query-scoping guidance.
- Docker runtime dependencies and a worker-specific Celery health check.
- SQLite sessions for local setup; Redis and Celery through `--full` or Docker setup.
- PostgreSQL test matrix for both providers across Python 3.11, 3.12, and 3.13.

Stripe checkout and recovery flows have been exercised in a sandbox. Chargebee has
automated SDK fixture coverage; a real sandbox run is still pending.

## Next

1. Add a configuration check command with clear first-run errors.
2. Replace admin-assigned team passwords with email invitations.
3. Publish a tested workspace-scoped CRUD recipe.
4. Evaluate a template update workflow for projects built from ReadyKit.

## Further Verification

- Run the Chargebee checkout and recovery flow in a real sandbox.
- Verify deployment on Fly.io and Railway; local configuration checks are not a
  substitute for deployed tests.
- Improve accessibility and keyboard navigation in the application shell.

Proposals belong in [GitHub Discussions](https://github.com/level09/readykit/discussions).
