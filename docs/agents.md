# AI Agents

Using AI tools effectively with ReadyKit.

## Overview

ReadyKit is designed to work seamlessly with AI-powered development tools like Cursor, Claude Code, and GitHub Copilot. The codebase follows consistent patterns that AI assistants can understand and replicate.

## Project Instructions

The repository includes `AGENTS.md` with shared project patterns. `CLAUDE.md` is
ignored by Git; if you use one locally, point it to `AGENTS.md` instead of maintaining
a second copy. Update the shared instructions when the architecture changes.

The shared instructions cover:

- Project architecture overview
- Multi-tenant patterns and conventions
- Workspace-scoped model examples
- Route protection patterns
- Database query conventions
- Billing integration details

::: tip
AI assistants that support project context (like Claude Code) will automatically read `CLAUDE.md` to understand your codebase and follow your project's patterns.
:::

## Key Patterns for AI Prompts

When asking AI assistants to help with ReadyKit, reference these patterns:

### Creating Workspace-Scoped Features

```
"Create a new [Feature] model that belongs to workspaces,
with CRUD routes using @require_workspace_access decorator"
```

The AI should generate:
- Model with `WorkspaceScoped` mixin
- Routes with workspace_id parameter
- Proper decorator usage
- Workspace-scoped queries

### Route Protection

```
"Add a route for [action] that only workspace admins can access"
```

Expected pattern:
```python
@app.route('/workspace/<int:workspace_id>/admin-action/')
@require_workspace_access('admin')
def admin_action(workspace_id):
    workspace = g.current_workspace
    # ...
```

### Database Queries

```
"Query [Model] filtered by current workspace"
```

Expected pattern:
```python
from enferno.services.workspace import workspace_query

stmt = workspace_query(Model).where(Model.status == 'active')
results = db.session.scalars(stmt).all()
```

## Project Conventions

When working with AI assistants, these conventions should be followed:

### File Organization

| Type | Location |
|------|----------|
| Models | `enferno/user/models.py` or new `enferno/[feature]/models.py` |
| Routes | `enferno/portal/views.py` or `enferno/api/` |
| Services | `enferno/services/` |
| Templates | `enferno/templates/` |
| Static files | `enferno/static/` |

### Naming Conventions

- Routes: `snake_case` (`list_projects`, `create_project`)
- Models: `PascalCase` (`Project`, `ProjectComment`)
- Templates: `snake_case` directories and files (`projects/list.html`)
- URL patterns: `/workspace/<int:workspace_id>/[resource]/`

### Import Patterns

```python
# Extensions
from enferno.extensions import db

# Services
from enferno.services.workspace import require_workspace_access, WorkspaceScoped
from enferno.services.billing import requires_pro_plan

# Models
from enferno.user.models import User, Workspace, Membership

# Flask utilities
from flask import g, render_template, redirect, url_for, flash, abort
from flask_security import current_user, auth_required
```

## Tips for AI Assistants

If you're an AI assistant working with ReadyKit:

1. **Always scope data to workspaces** - Use scoped helpers or explicit workspace filters. A foreign key and mixin alone do not filter ordinary queries.
2. **Use the decorator** - `@require_workspace_access('member')` or `@require_workspace_access('admin')`
3. **Access workspace via `g`** - After the decorator, use `g.current_workspace`
4. **SQLAlchemy 2.0 style** - Use `db.select()`, `db.session.scalars()`, not legacy Query API
5. **Commit explicitly** - Call `db.session.commit()` after mutations
