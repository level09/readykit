# Development Guide

Development guide and best practices for ReadyKit.

## Project Structure

```
readykit/
├── enferno/                # Main application package
│   ├── app.py             # Application factory
│   ├── settings.py        # Configuration from .env
│   ├── extensions.py      # Flask extensions
│   ├── commands.py        # CLI commands
│   ├── api/               # API endpoints
│   │   └── webhooks.py    # Billing webhooks
│   ├── portal/            # Authenticated routes
│   ├── public/            # Public routes
│   ├── user/              # User models and auth
│   ├── services/          # Business logic
│   │   ├── workspace.py   # Multi-tenant core
│   │   ├── billing.py     # Stripe/Chargebee billing
│   │   └── auth.py        # Authorization
│   ├── tasks/             # Celery tasks
│   ├── static/            # CSS, JS, images
│   └── templates/         # Jinja2 templates
├── docs/                  # Documentation
├── .env                   # Environment config
├── setup.sh              # Setup script
└── run.py                # Entry point
```

## Blueprints

ReadyKit uses three main blueprints:

### Portal (Authenticated)

All routes require authentication via `before_request`:

```python
from flask import Blueprint
from flask_security import auth_required

portal = Blueprint('portal', __name__)

@portal.before_request
@auth_required()
def before_request():
    pass

@portal.route('/dashboard/')
def dashboard():
    return render_template('portal/dashboard.html')
```

### Public (Unauthenticated)

Landing pages, login, registration:

```python
from flask import Blueprint

public = Blueprint('public', __name__)

@public.route('/')
def index():
    return render_template('public/index.html')
```

### User

Profile and account management:

```python
from flask import Blueprint
from flask_security import auth_required

user = Blueprint('user', __name__)

@user.route('/profile/')
@auth_required()
def profile():
    return render_template('user/profile.html')
```

## Creating Workspace-Scoped Features

### 1. Define the Model

```python
from enferno.extensions import db
from enferno.services.workspace import WorkspaceScoped

class Project(db.Model, WorkspaceScoped):
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey('workspace.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=db.func.now())

    workspace = db.relationship('Workspace', backref='projects')
```

### 2. Create the Route

```python
from enferno.services.workspace import require_workspace_access
from flask import g, render_template

@portal.route('/workspace/<int:workspace_id>/projects/')
@require_workspace_access('member')
def list_projects(workspace_id):
    projects = Project.for_current_workspace()
    return render_template('projects/list.html', projects=projects)

@portal.route('/workspace/<int:workspace_id>/projects/<int:project_id>/')
@require_workspace_access('member')
def view_project(workspace_id, project_id):
    project = Project.get_by_id(project_id)  # Auto-scoped to workspace
    if not project:
        abort(404)
    return render_template('projects/detail.html', project=project)
```

### 3. Create Form and Template

```python
# forms.py
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField
from wtforms.validators import DataRequired, Length

class ProjectForm(FlaskForm):
    name = StringField('Name', validators=[DataRequired(), Length(max=100)])
    description = TextAreaField('Description')
```

```html
<!-- templates/projects/list.html -->
{% extends "layout.html" %}
{% block content %}
<h1>Projects</h1>
<ul>
{% for project in projects %}
  <li>
    <a href="{{ url_for('portal.view_project', workspace_id=workspace.id, project_id=project.id) }}">
      {{ project.name }}
    </a>
  </li>
{% endfor %}
</ul>
{% endblock %}
```

## Database Operations

ReadyKit uses SQLAlchemy 2.0 style queries:

```python
from enferno.extensions import db
from enferno.user.models import User

# Select all
stmt = db.select(User)
users = db.session.scalars(stmt).all()

# Get by ID
user = db.session.get(User, user_id)

# Filtered query
stmt = db.select(User).where(User.email.like('%@example.com'))
users = db.session.scalars(stmt).all()

# Workspace-scoped query
from enferno.services.workspace import workspace_query
stmt = workspace_query(Project).where(Project.status == 'active')
projects = db.session.scalars(stmt).all()

# Create
project = Project(workspace_id=workspace_id, name='New Project')
db.session.add(project)
db.session.commit()

# Update
project.name = 'Updated Name'
db.session.commit()

# Delete
db.session.delete(project)
db.session.commit()
```

## Background Tasks

Define tasks in `enferno/tasks/__init__.py`:

```python
from enferno.tasks import celery

@celery.task
def send_welcome_email(user_id):
    from enferno.extensions import db
    from enferno.user.models import User

    user = db.session.get(User, user_id)
    if user:
        # Send email logic
        pass
    return True
```

Call tasks asynchronously:

```python
from enferno.tasks import send_welcome_email

# Queue task for background execution
send_welcome_email.delay(user.id)
```

Run the worker:

```bash
uv run celery -A enferno.tasks worker --loglevel=info
```

## Code Quality

### Linting and Formatting

```bash
# Lint and auto-fix
uv run ruff check --fix .

# Format code
uv run ruff format .

# Install pre-commit hooks
uv run pre-commit install
```

### Style Guidelines

- Line length: 88 characters
- Python 3.11+ syntax
- SQLAlchemy 2.0 query style
- Type hints optional (use where they add clarity)

## Development Server

```bash
# Start Flask dev server
uv run flask run

# With debug mode (auto-reload)
FLASK_DEBUG=1 uv run flask run

# Run Celery worker
uv run celery -A enferno.tasks worker --loglevel=info
```

## Common Patterns

### Flash Messages

```python
from flask import flash, redirect, url_for

@portal.route('/workspace/<int:workspace_id>/project/create/', methods=['POST'])
@require_workspace_access('member')
def create_project(workspace_id):
    form = ProjectForm()
    if form.validate_on_submit():
        project = Project(
            workspace_id=workspace_id,
            name=form.name.data,
            description=form.description.data
        )
        db.session.add(project)
        db.session.commit()
        flash('Project created successfully')
        return redirect(url_for('portal.list_projects', workspace_id=workspace_id))
    flash('Please fix the errors below')
    return render_template('projects/create.html', form=form)
```

### API Responses

```python
from flask import jsonify

@api.route('/projects/')
@require_workspace_access('member')
def api_list_projects(workspace_id):
    projects = Project.for_current_workspace()
    return jsonify([{
        'id': p.id,
        'name': p.name,
        'description': p.description
    } for p in projects])
```

### Error Handling

```python
from flask import abort

@portal.route('/workspace/<int:workspace_id>/project/<int:project_id>/delete/', methods=['POST'])
@require_workspace_access('admin')  # Admin only
def delete_project(workspace_id, project_id):
    project = Project.get_by_id(project_id)
    if not project:
        abort(404)

    db.session.delete(project)
    db.session.commit()
    flash('Project deleted')
    return redirect(url_for('portal.list_projects', workspace_id=workspace_id))
```

## Template Context

Available in all templates:

```html
<!-- Current workspace -->
{{ get_current_workspace().name }}

<!-- Current user -->
{{ current_user.email }}

<!-- User's role in workspace -->
{{ g.user_workspace_role }}
```
