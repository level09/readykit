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
