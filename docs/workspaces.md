# Workspaces

Multi-tenant architecture for data isolation.

## Overview

ReadyKit groups business data by workspace. Isolation depends on two explicit
steps: check the user's membership with `require_workspace_access`, then filter
every data query to that workspace. The model mixin does not add global query filters.

## How It Works

```
User → Membership → Workspace
         ↓
    role: admin | member
```

- Users can belong to multiple workspaces
- Each workspace has one owner (the creator)
- Members have either `admin` or `member` role
- Business data must be queried and written within its workspace

## Automatic Workspace Creation

The OAuth flow creates a workspace for a new account. Linking OAuth to an existing
account does not create one. Email/password self-registration is disabled;
`flask install` creates a superadmin who can create workspaces from the dashboard.

```python
# Used when creating a new OAuth account
workspace = WorkspaceService.create_workspace(
    name="",           # Ignored when auto_name=True
    owner_user=user,
    auto_name=True     # Generates "John's Workspace" from user data
)
```

The auto-generated name uses:
1. User's name if available → `"John's Workspace"`
2. Email prefix as fallback → `"john's Workspace"`
3. Default → `"My Workspace"`

## Workspace Selection

Non-superadmins with one workspace skip the selection screen:

```python
workspaces = current_user.get_workspaces()
if len(workspaces) == 1 and not current_user.is_superadmin:
    return redirect(url_for("portal.switch_workspace", workspace_id=workspaces[0].id))
```

Team management is available to workspace admins. Settings and API key pages are
available to members; billing changes and key creation require admin access.
These pages do not depend on the number of members.

## Route Protection

**Always** use the `@require_workspace_access()` decorator on workspace routes:

```python
from enferno.services.workspace import require_workspace_access
from flask import g

@app.get("/workspace/<int:workspace_id>/projects/")
@require_workspace_access("member")  # or "admin" for admin-only routes
def list_projects(workspace_id):
    # Security checks already performed:
    # ✓ User is authenticated
    # ✓ Workspace exists
    # ✓ User is a member
    # ✓ User has required role

    # Access workspace context:
    workspace = g.current_workspace
    role = g.user_workspace_role

    return render_template("projects.html", workspace=workspace)
```

### What the Decorator Does

1. Verifies user is authenticated
2. Fetches the workspace from the URL parameter, or the session when the URL has none
3. Checks user has membership in workspace
4. Validates role requirement (`admin` or `member`)
5. Sets session and context:
   - `session["current_workspace_id"]`
   - `g.current_workspace`
   - `g.user_workspace_role`

## Creating Workspace-Scoped Models

All business data should inherit from `WorkspaceScoped` mixin:

```python
from enferno.services.workspace import WorkspaceScoped
from enferno.extensions import db

class Project(db.Model, WorkspaceScoped):
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspace.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)

    # Relationship to workspace
    workspace = db.relationship('Workspace', backref='projects')
```

::: warning
Always include `workspace_id` as a non-nullable foreign key to identify the record's
workspace. This does not restrict which rows a query can read or change. ReadyKit
does not configure database row-level security.
:::

## Querying Workspace Data

The `WorkspaceScoped` mixin provides query methods that filter by the selected
workspace. Call them from a route protected by `require_workspace_access`; they
read the session context and do not check membership themselves.

```python
# Get all records for current workspace
projects = Project.for_current_workspace()

# Get specific record (workspace-scoped)
project = Project.get_by_id(project_id)  # Returns None if not in current workspace
```

For custom queries, use the helper function:

```python
from enferno.services.workspace import workspace_query

# Build workspace-scoped query
stmt = workspace_query(Project).where(Project.name.ilike("Acme%"))
projects = db.session.execute(stmt).scalars().all()
```

`db.select(Project)`, `db.session.get(Project, id)`, bulk updates, and bulk deletes
do not gain workspace filters from the mixin. Add an explicit filter when you do
not use the helpers:

```python
stmt = db.select(Project).where(Project.workspace_id == g.current_workspace.id)
```

Without a workspace selected, `workspace_query()` and `for_current_workspace()`
raise `ValueError`; `get_by_id()` returns `None`.

## Workspace Service Methods

```python
from enferno.services.workspace import WorkspaceService

# Create workspace
ws = WorkspaceService.create_workspace(
    name="Acme Corp",
    owner_user=user,
    auto_name=False
)

# Add member
WorkspaceService.add_member(workspace_id, user, role="member")
db.session.commit()  # Caller must commit

# Remove member (cannot remove owner)
WorkspaceService.remove_member(workspace_id, user_id)

# Change role (cannot change owner's role)
WorkspaceService.update_member_role(workspace_id, user_id, "admin")
```

## User Model Methods

```python
# Get all workspaces user belongs to
workspaces = current_user.get_workspaces()

# Get user's role in a specific workspace
role = current_user.get_workspace_role(workspace_id)  # Returns "admin" or "member"
```

## Template Context

`get_current_workspace()` is globally available in all templates:

It reads the selected workspace from the session; it does not check membership.
Render workspace data only after the route's access check.

```html
{% if get_current_workspace() %}
  <h1>{{ get_current_workspace().name }}</h1>
  <p>Plan: {{ get_current_workspace().plan }}</p>
{% endif %}
```

## Security Best Practices

::: details Always use the decorator
Use `@require_workspace_access()` on workspace routes. It validates membership
and the required role. Each query must still filter records by workspace.
:::

::: details Don't trust session alone
`session["current_workspace_id"]` can be stale. The decorator re-validates membership on every request.
:::

::: details Include workspace_id in queries
Use the scoped helpers or filter by `g.current_workspace.id`. A foreign key and
the mixin alone do not filter ordinary SQLAlchemy queries.
:::

::: details Validate ownership for destructive actions
For updates and deletes, fetch the record with `get_by_id()` or an explicit
workspace filter before changing it. Return 404 when that lookup finds no record.
For creation, set `workspace_id` from `g.current_workspace.id`, not the request
body. Do not let a general field-update method move a record to another workspace.
:::
