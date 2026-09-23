# Teams

Workspace admins manage accounts and roles through `/workspace/team/`.

## Current Behavior

The Add Member form creates a new account with a name, username, email, password,
and workspace role. Login uses email, though the form still requires a username.
The form rejects an email or username that already exists. It does not send an
invitation email or offer an invitation acceptance flow.

To attach an existing account from application code, use `WorkspaceService.add_member`
inside an authorized admin operation and commit the transaction.

## Roles

| Role | Built-in access |
|------|-----------------|
| Admin | Manage members, change workspace settings, manage billing, create and revoke API keys |
| Member | View the workspace, settings, member list API, and active API keys |

New product routes define their own required role. Workspace ownership always
requires admin membership; owners cannot be removed or demoted. The member removal
API also prevents an admin from removing themselves.

## Member API

All routes require login and membership in the URL's workspace.

| Method | Route | Role | Behavior |
|--------|-------|------|----------|
| POST | `/api/workspace/<workspace_id>/members` | Member | Paginated member list; body accepts `options.page` and `options.itemsPerPage` |
| POST | `/api/workspace/<workspace_id>/members/add` | Admin | Create an account; requires `name`, `username`, `email`, `password`; `role` defaults to `member` |
| PUT | `/api/workspace/<workspace_id>/members/<user_id>` | Admin | Change `role` to `admin` or `member` |
| DELETE | `/api/workspace/<workspace_id>/members/<user_id>` | Admin | Remove membership, keeping the user account |

The Team page itself requires admin access. The list API permits any member.

## Service Methods

These methods do not authorize the caller. Protect the calling route with
`@require_workspace_access("admin")` and use the authorized workspace ID.

```python
from enferno.services.workspace import WorkspaceService
from enferno.extensions import db
from flask import render_template

# Attach an existing User object to the authorized workspace.
WorkspaceService.add_member(g.current_workspace.id, user, role="member")
db.session.commit()

# These methods commit on success and return False if membership is absent.
WorkspaceService.update_member_role(g.current_workspace.id, user.id, "admin")
WorkspaceService.remove_member(g.current_workspace.id, user.id)
```

Invalid roles, duplicate membership, and attempts to remove or demote the owner
raise `ValueError`. After removal, protected workspace routes reject that user on
their next request, even if their session still selects the workspace.

## Checking Access

```python
from flask import g
from enferno.services.workspace import require_workspace_access

@portal.get("/workspace/<int:workspace_id>/projects/")
@require_workspace_access("member")
def list_projects(workspace_id):
    projects = Project.for_current_workspace()
    return render_template("projects.html", projects=projects)
```

`g.user_workspace_role` contains the checked role. Query helpers still need an
explicit call; ordinary SQLAlchemy queries are not automatically filtered.
See [Workspaces](/workspaces) for the full contract.
