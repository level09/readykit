# Contributing

ReadyKit welcomes focused fixes, documentation improvements, and small,
well-defined features.

## Start here

1. Check existing issues and Discussions before opening duplicate work.
2. For a bug, include reproduction steps, expected behavior, and actual behavior.
3. For a feature, describe the user problem before proposing an implementation.
4. Keep each pull request limited to one change.

## Local development

```bash
./setup.sh
uv run flask create-db
uv run pytest
uv run ruff check .
```

The default setup needs no Redis service. For the full test environment, install
the optional dependencies and run each provider in a separate process:

```bash
uv sync --extra dev --extra full
BILLING_PROVIDER=stripe uv run pytest
BILLING_PROVIDER=chargebee uv run pytest
```

Tests use a disposable SQLite database by default. PostgreSQL locking tests require
`TEST_DATABASE_URI` pointing to a dedicated test database: the test fixture creates
and drops its tables. CI runs PostgreSQL 15 with Python 3.11, 3.12, and 3.13 for both
providers. Provider-specific tests skip in the other provider's run.

Build the documentation with:

```bash
cd docs
npm ci
npm run build
```

## Pull requests

- Add or update tests for behavior changes.
- Keep workspace data scoped and protect workspace routes with
  `require_workspace_access`.
- Review generated migrations before committing them.
- Update documentation when behavior or configuration changes.
- Do not include unrelated cleanup.

Security reports must follow [SECURITY.md](SECURITY.md), not public issues.
