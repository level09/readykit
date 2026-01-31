# AGENTS.md

This file provides comprehensive architectural patterns and coding standards for AI agents working with ReadyKit, a production-ready Flask SaaS template built on the Enferno framework.

## Framework Overview

**ReadyKit** is a Flask-based SaaS template with multi-tenant workspaces, billing, OAuth, and team collaboration:

- **Backend**: Flask 3.1+ with Blueprint organization
- **Frontend**: Vue 3 + Vuetify 3 (no build step required)
- **Database**: SQLAlchemy 2.x with modern statement-based queries
- **Auth**: Flask-Security-Too with 2FA, WebAuthn, OAuth support (Google, GitHub via Flask-Dance)
- **Tasks**: Celery + Redis (optional, via `full` extra)
- **Billing**: Stripe or Chargebee (configurable via `BILLING_PROVIDER`)
- **Package Manager**: uv for fast dependency management

## Project Structure

```
readykit/
├── enferno/                   # Main application package
│   ├── app.py                 # Application factory (create_app)
│   ├── settings.py            # Environment-based configuration (single Config class)
│   ├── extensions.py          # Flask extensions initialization
│   ├── commands.py            # Custom Flask CLI commands
│   ├── public/                # Public routes (no auth)
│   │   └── views.py
│   ├── user/                  # Superadmin user management (CMS)
│   │   ├── views.py           # bp_user blueprint (superadmin-only)
│   │   ├── models.py          # User, Role, Workspace, Membership, OAuth, APIKey, Activity, Session
│   │   └── forms.py
│   ├── portal/                # Protected dashboard/workspace routes
│   │   └── views.py
│   ├── api/                   # API endpoints
│   │   └── webhooks.py        # Stripe/Chargebee webhook handlers
│   ├── services/              # Business logic layer
│   │   ├── workspace.py       # Multi-tenant workspace management
│   │   ├── billing.py         # Stripe/Chargebee billing via hosted pages
│   │   └── auth.py            # Authorization decorators
│   ├── tasks/                 # Celery task definitions (optional)
│   ├── utils/                 # Utility functions
│   │   └── base.py            # BaseMixin (created_at, updated_at)
│   ├── static/                # CSS, JS, images
│   │   ├── css/               # layout.css, app.css, vuetify.min.css
│   │   ├── js/                # vue.min.js, vuetify.min.js, axios.min.js, config.js
│   │   ├── mdi/               # Material Design Icons (local)
│   │   └── img/
│   └── templates/             # All Jinja2 templates (single directory, not per-blueprint)
├── nginx/                     # Nginx configuration
├── instance/                  # Instance-specific files (gitignored)
├── pyproject.toml             # Dependencies and project metadata
├── uv.lock                    # Lock file for reproducible installs
├── .env                       # Environment variables (gitignored)
├── .env-sample                # Environment template
├── setup.sh                   # Setup script
├── run.py                     # Application entry point
├── Dockerfile                 # Docker configuration
└── docker-compose.yml         # Docker Compose orchestration
```

## Development Commands

### Setup & Installation
```bash
./setup.sh                        # Create virtual environment, install dependencies, generate .env
uv sync --extra dev               # Install dependencies with dev tools
uv sync --extra full              # Install Celery + Redis support
uv sync --extra wsgi              # For Unix deployments that need uWSGI
```

### Database Management
```bash
uv run flask create-db                            # Initialize database tables
uv run flask install                              # Create admin user (interactive, auto-generates password)
uv run flask install -e admin@x.com -p pass123    # Non-interactive admin setup
uv run flask create -e user@x.com -p pass123      # Create regular user
uv run flask create -e user@x.com -p pass123 --super-admin  # Create superadmin
uv run flask reset -e <email/username> -p <password>  # Reset user password
uv run flask add-role -e <email> -r <role>        # Add role to user
```

### Development Server
```bash
uv run flask run                     # Default http://localhost:5000
uv run flask run --port 5001         # Use 5001 locally if 5000 is busy (macOS)
```

### Code Quality
```bash
uv run ruff check .                  # Lint code with ruff
uv run ruff format .                 # Format code with ruff
uv run ruff check --fix .            # Auto-fix linting issues
uv run pre-commit install            # Install pre-commit hooks
```

### Docker Development
```bash
docker compose up --build            # Full stack with Redis, PostgreSQL, Nginx, Celery
```

### Internationalization
```bash
uv run flask i18n extract            # Extract translatable strings
uv run flask i18n init <lang>        # Initialize new language
uv run flask i18n update             # Update translations
uv run flask i18n compile            # Compile translations
```

## Flask Architecture Patterns

### Application Factory Pattern

The app is created using the factory pattern in `enferno/app.py`:

```python
from flask import Flask
from enferno.settings import Config

def create_app(config_object=Config):
    app = Flask(__name__)
    app.config.from_object(config_object)

    register_blueprints(app)
    register_extensions(app)
    register_errorhandlers(app)
    register_shellcontext(app)
    register_commands(app, commands)
    return app
```

### Extension Initialization

Extensions are initialized in `enferno/extensions.py`:

```python
from flask_babel import Babel
from flask_caching import Cache
from flask_mail import Mail
from flask_session import Session
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import DeclarativeBase

# Optional dev dependency
try:
    from flask_debugtoolbar import DebugToolbarExtension
    debug_toolbar = DebugToolbarExtension()
except ImportError:
    debug_toolbar = None

class BaseModel(DeclarativeBase):
    pass

db = SQLAlchemy(model_class=BaseModel)
cache = Cache()
mail = Mail()
session = Session()
babel = Babel()

# Import initialized extensions anywhere:
from enferno.extensions import db, cache, mail, babel
```

### Blueprint Organization

Features are organized into blueprints by functional area:

#### 1. Public Blueprint (`enferno/public/`)
Routes accessible without authentication:

```python
from flask import Blueprint, render_template

public = Blueprint("public", __name__, static_folder="../static")

@public.get("/")
def index():
    return render_template("index.html")
```

#### 2. User Blueprint (`enferno/user/`) — Superadmin Only
CMS-style user management restricted to superadmins via `before_request`:

```python
from flask import Blueprint, abort
from flask_security import auth_required, current_user

bp_user = Blueprint("users", __name__, static_folder="../static")

@bp_user.before_request
@auth_required("session")
def before_request():
    if not current_user.is_superadmin:
        abort(403)

@bp_user.get("/users/")
def users():
    return render_template("cms/users.html")
```

#### 3. Portal Blueprint (`enferno/portal/`)
Protected routes requiring authentication. Uses `before_request` to protect all routes:

```python
from flask import Blueprint
from flask_security import auth_required

portal = Blueprint("portal", __name__, static_folder="../static")

@portal.before_request
@auth_required("session")
def before_request():
    pass

@portal.get("/dashboard/")
def dashboard():
    return render_template("dashboard.html")
```

#### 4. Webhooks Blueprint (`enferno/api/`)
Billing provider webhook handlers:

```python
from flask import Blueprint

webhooks_bp = Blueprint("webhooks", __name__)
```

### Creating New Blueprints

1. Create directory: `enferno/feature_name/`
2. Add files: `views.py`, `models.py`, optionally `forms.py`
3. Create templates in: `enferno/templates/feature_name/`
4. Register in `app.py`:

```python
from enferno.feature_name.views import feature_bp
app.register_blueprint(feature_bp)
```

## Database Patterns (SQLAlchemy 2.x)

### Model Definition

Models inherit from `db.Model`. Use `BaseMixin` for automatic timestamps:

```python
from enferno.extensions import db
from enferno.utils.base import BaseMixin

class BaseMixin:
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now, nullable=False)

class Post(db.Model, BaseMixin):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    content = db.Column(db.Text)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspace.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"))

    # Relationships
    user = db.relationship("User", backref="posts")

    def to_dict(self):
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "created_at": self.created_at.isoformat()
        }

    def from_dict(self, data):
        self.title = data.get("title", self.title)
        self.content = data.get("content", self.content)
        return self
```

### Modern Query Patterns (SQLAlchemy 2.x)

Use statement-based queries with `db.select()`, `db.update()`, `db.delete()`:

```python
from enferno.extensions import db
from enferno.user.models import User

# Select all
stmt = db.select(User)
users = db.session.scalars(stmt).all()

# Select with filtering
stmt = db.select(User).where(User.active == True)
active_users = db.session.scalars(stmt).all()

# Select single item
stmt = db.select(User).where(User.id == user_id)
user = db.session.scalar(stmt)

# Or use session.get for primary key lookup
user = db.session.get(User, user_id)

# Ordering and limiting
stmt = (
    db.select(Post)
    .order_by(Post.created_at.desc())
    .limit(10)
)
recent_posts = db.session.scalars(stmt).all()

# Joins
stmt = (
    db.select(Post)
    .join(Post.user)
    .where(User.active == True)
)
posts = db.session.scalars(stmt).all()

# Pagination (built-in)
query = db.select(User)
pagination = db.paginate(query, page=page, per_page=per_page)
items = pagination.items
total = pagination.total

# Update
stmt = db.update(User).where(User.id == user_id).values(active=False)
db.session.execute(stmt)
db.session.commit()

# Delete
stmt = db.delete(Post).where(Post.id == post_id)
db.session.execute(stmt)
db.session.commit()
```

### CRUD Operations

```python
# Create
post = Post(title="New Post", content="Content here")
db.session.add(post)
db.session.commit()

# Read
post = db.session.get(Post, 1)

# Update
post.title = "Updated Title"
db.session.commit()

# Delete
db.session.delete(post)
db.session.commit()
```

## API Development Standards

### RESTful Endpoint Patterns

- **Collections**: `/api/resource` (GET for list, POST for create)
- **Items**: `/api/resource/<id>` (GET for retrieve, POST for update, DELETE for remove)
- **JSON responses** with consistent structure
- **Proper HTTP status codes**: 200 (success), 400 (bad request), 404 (not found), 500 (error)

### API Response Patterns

```python
from flask import Blueprint, jsonify, request
from enferno.extensions import db
from enferno.user.models import User

api = Blueprint("api", __name__)

# List with pagination
@api.get("/api/users")
def get_users():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", 25, type=int)

    query = db.select(User)
    pagination = db.paginate(query, page=page, per_page=per_page)

    return jsonify({
        "items": [user.to_dict() for user in pagination.items],
        "total": pagination.total,
        "perPage": pagination.per_page
    })

# Update with error handling
@api.post("/api/users/<int:user_id>")
def update_user(user_id):
    try:
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404

        data = request.get_json()
        user.from_dict(data)
        db.session.commit()

        return jsonify({
            "message": "User updated successfully",
            "data": user.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

# Delete
@api.delete("/api/users/<int:user_id>")
def delete_user(user_id):
    try:
        user = db.session.get(User, user_id)
        if not user:
            return jsonify({"error": "User not found"}), 404

        db.session.delete(user)
        db.session.commit()

        return jsonify({"message": "User deleted successfully"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500
```

## Security Patterns

### Authentication & Authorization

Flask-Security provides comprehensive auth with decorators:

```python
from flask_security import auth_required, roles_required, current_user

# Require authentication
@app.route("/protected")
@auth_required("session")
def protected_route():
    return render_template("protected.html")

# Access current user
@app.route("/profile")
@auth_required("session")
def profile():
    user_name = current_user.name
    return render_template("profile.html", user=current_user)

# Superadmin check
if not current_user.is_superadmin:
    abort(403)
```

### Input Validation with WTForms

```python
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, validators

class PostForm(FlaskForm):
    title = StringField("Title", [
        validators.DataRequired(),
        validators.Length(min=3, max=255)
    ])
    content = TextAreaField("Content", [
        validators.DataRequired(),
        validators.Length(min=10)
    ])
```

### CSRF Protection

CSRF is automatically enabled via Flask-WTF. For AJAX requests include the token:

```javascript
// Include CSRF token in AJAX requests
const csrfToken = document.querySelector('meta[name="csrf-token"]').content;

axios.post("/api/endpoint", data, {
    headers: {
        "X-CSRFToken": csrfToken
    }
});
```

## Frontend Architecture (Vue 3 + Vuetify 3)

### No Build Step Philosophy

- Vue 3 and Vuetify loaded from local static files (`enferno/static/`)
- Components defined using `Vue.defineComponent` with template strings
- Per-page Vue instances (not SPA architecture)
- Global configuration in `enferno/static/js/config.js`
- Axios loaded for HTTP requests

### CRITICAL: Custom Vue Delimiters

**IMPORTANT**: ReadyKit uses `${` and `}` for Vue expressions to avoid conflicts with Jinja's `{{ }}`:

```javascript
// In config.js
const config = {
    delimiters: ['${', '}'],
    vuetifyConfig: {
        defaults: { /* Vuetify component defaults */ },
        theme: {
            defaultTheme: 'light',
            themes: {
                light: {
                    colors: {
                        primary: '#18181B',
                        secondary: '#71717A',
                        accent: '#F97316',
                        // ... other colors
                    }
                }
            }
        },
        icons: { defaultSet: 'mdi' }
    }
};
```

```html
<!-- CORRECT: Vue expressions with custom delimiters -->
<v-card-title>${ user.name }</v-card-title>
<v-list-item v-for="item in items" :key="item.id">
    ${ item.title }
</v-list-item>

<!-- CORRECT: Jinja expressions (server-side) -->
{% if current_user.is_authenticated %}
    <v-btn href="/logout">Logout</v-btn>
{% endif %}

<!-- WRONG: Never use {{ }} for Vue expressions -->
<v-card-title>{{ user.name }}</v-card-title>
```

### Base Template Structure

All pages extend `layout.html` which provides the full app shell (app bar, sidebar navigation, footer) plus Vue/Vuetify setup:

```html
<!DOCTYPE html>
<html lang="en">
<head>
    <link rel="stylesheet" href="/static/css/vuetify.min.css">
    <link rel="stylesheet" href="/static/mdi/css/materialdesignicons.min.css">
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/@tabler/icons-webfont@latest/tabler-icons.min.css">
    <link rel="stylesheet" href="/static/css/layout.css">
    <link rel="stylesheet" href="/static/css/app.css">
    {% block css %}{% endblock %}
</head>
<body>
<v-app id="app" v-cloak>
    <v-layout>
        <!-- App bar with user profile menu -->
        <!-- Navigation drawer with workspace-aware sidebar -->
        <v-main>
            {% block content %}{% endblock %}
        </v-main>
        <!-- Footer -->
    </v-layout>
</v-app>

<!-- Scripts loaded in this order: -->
<script src="/static/js/vue.min.js"></script>
<script src="/static/js/config.js"></script>
<script src="/static/js/vuetify.min.js"></script>
<script src="/static/js/axios.min.js"></script>

<script>
    // layoutMixin — provides drawer state and mobile detection
    const layoutMixin = {
        data() {
            return {
                drawer: true,
                isMobile: window.innerWidth < 960
            };
        },
        methods: {
            handleResize() {
                this.isMobile = window.innerWidth < 960;
            }
        },
        mounted() {
            window.addEventListener('resize', this.handleResize);
        },
        beforeUnmount() {
            window.removeEventListener('resize', this.handleResize);
        }
    };
</script>

{% block js %}{% endblock %}
</body>
</html>
```

### Vue App Initialization Pattern

Every page that uses Vue must include `layoutMixin` and follow this pattern:

```html
{% extends 'layout.html' %}

{% block content %}
<v-container>
    <h1>${ pageTitle }</h1>
    <!-- Vue content here -->
</v-container>
{% endblock %}

{% block js %}
<script>
const {createApp} = Vue;
const {createVuetify} = Vuetify;
const vuetify = createVuetify(config.vuetifyConfig);

const app = createApp({
    mixins: [layoutMixin],  // REQUIRED: provides drawer, isMobile
    data() {
        return {
            config: config,
            pageTitle: 'My Page',
            items: []
        };
    },
    delimiters: config.delimiters,  // REQUIRED: Uses ${ }
    methods: {
        async loadData() {
            const response = await axios.get('/api/items');
            this.items = response.data.items;
        }
    },
    mounted() {
        this.loadData();
    }
});

app.use(vuetify).mount('#app');
</script>
{% endblock %}
```

### Passing Server Data to Vue

Use JSON script tags to safely pass data from Jinja to Vue:

```html
<!-- In template -->
<script type="application/json" id="server-data">
    {{ data|tojson|safe }}
</script>

<script>
// In Vue app initialization
const serverData = JSON.parse(
    document.getElementById('server-data').textContent
);

const app = createApp({
    mixins: [layoutMixin],
    data() {
        return {
            items: serverData.items || [],
            config: config
        };
    }
});
</script>
```

### Common Vue Patterns

#### Data Table with Pagination

```javascript
const app = createApp({
    mixins: [layoutMixin],
    data() {
        return {
            items: [],
            itemsLength: 0,
            loading: false,
            search: '',
            options: {
                page: 1,
                itemsPerPage: 25,
                sortBy: []
            },
            headers: [
                { title: 'ID', value: 'id', sortable: true },
                { title: 'Name', value: 'name', sortable: true },
                { title: 'Email', value: 'email', sortable: false },
                { title: 'Actions', value: 'actions', sortable: false }
            ]
        };
    },
    methods: {
        refresh(options) {
            if (options) {
                this.options = {...this.options, ...options};
            }
            this.loadItems();
        },

        async loadItems() {
            this.loading = true;
            try {
                const params = new URLSearchParams({
                    page: this.options.page,
                    per_page: this.options.itemsPerPage,
                    search: this.search
                });

                const response = await axios.get(`/api/items?${params}`);
                this.items = response.data.items;
                this.itemsLength = response.data.total;
            } catch (error) {
                console.error('Error loading data:', error);
                this.showSnack('Failed to load data');
            } finally {
                this.loading = false;
            }
        },

        showSnack(message, color = 'success') {
            this.snackMessage = message;
            this.snackColor = color;
            this.snackBar = true;
        }
    },
    mounted() {
        this.loadItems();
    }
});
```

#### Edit Dialog Pattern

```javascript
data() {
    return {
        edialog: false,
        eitem: {
            id: null,
            name: '',
            email: '',
            active: true
        },
        defaultItem: {
            id: null,
            name: '',
            email: '',
            active: true
        }
    };
},
methods: {
    editItem(item) {
        this.eitem = Object.assign({}, item);
        this.edialog = true;
    },

    newItem() {
        this.eitem = Object.assign({}, this.defaultItem);
        this.edialog = true;
    },

    async saveItem() {
        const endpoint = this.eitem.id ?
            `/api/items/${this.eitem.id}` :
            '/api/items';

        try {
            const response = await axios.post(endpoint, {item: this.eitem});
            this.showSnack(response.data.message || 'Saved successfully');
            this.edialog = false;
            this.refresh();
        } catch (error) {
            this.showSnack(error.response?.data?.error || 'Save failed', 'error');
        }
    },

    closeDialog() {
        this.edialog = false;
        this.eitem = Object.assign({}, this.defaultItem);
    }
}
```

### Vuetify Component Examples

```html
<!-- Data Table -->
<v-data-table
    :items="items"
    :headers="headers"
    :loading="loading"
    :items-length="itemsLength"
    :search="search"
    v-model:options="options"
    @update:options="refresh"
    class="elevation-1">

    <template v-slot:top>
        <v-toolbar flat>
            <v-toolbar-title>Users</v-toolbar-title>
            <v-spacer></v-spacer>
            <v-text-field
                v-model="search"
                append-icon="mdi-magnify"
                label="Search"
                single-line
                hide-details>
            </v-text-field>
            <v-btn color="primary" class="ml-2" @click="newItem">
                Add New
            </v-btn>
        </v-toolbar>
    </template>

    <template v-slot:item.actions="{ item }">
        <v-btn icon="mdi-pencil" size="small" @click="editItem(item)"></v-btn>
        <v-btn icon="mdi-delete" size="small" color="error" @click="deleteItem(item)"></v-btn>
    </template>
</v-data-table>

<!-- Edit Dialog -->
<v-dialog v-model="edialog" max-width="500px">
    <v-card>
        <v-card-title>
            <span>${ eitem.id ? 'Edit' : 'New' } Item</span>
        </v-card-title>

        <v-card-text>
            <v-text-field
                v-model="eitem.name"
                label="Name"
                required>
            </v-text-field>
            <v-text-field
                v-model="eitem.email"
                label="Email"
                type="email">
            </v-text-field>
            <v-switch
                v-model="eitem.active"
                label="Active">
            </v-switch>
        </v-card-text>

        <v-card-actions>
            <v-spacer></v-spacer>
            <v-btn variant="text" @click="closeDialog">Cancel</v-btn>
            <v-btn color="primary" @click="saveItem">Save</v-btn>
        </v-card-actions>
    </v-card>
</v-dialog>

<!-- Snackbar for notifications -->
<v-snackbar v-model="snackBar" :color="snackColor" timeout="3000">
    ${ snackMessage }
    <template v-slot:actions>
        <v-btn variant="text" @click="snackBar = false">Close</v-btn>
    </template>
</v-snackbar>
```

### Button & Card Patterns

```html
<!-- Buttons -->
<v-btn color="primary" variant="elevated" prepend-icon="mdi-plus" @click="newItem">
    Add New
</v-btn>
<v-btn variant="text" @click="closeDialog">Cancel</v-btn>
<v-btn icon="mdi-pencil" size="small" @click="editItem(item)"></v-btn>
<v-btn color="error" variant="outlined" prepend-icon="mdi-delete">Delete</v-btn>

<!-- Card Layout -->
<v-card class="ma-2">
    <v-card-title class="d-flex justify-space-between align-center">
        <span>Card Title</span>
        <v-btn icon="mdi-refresh" @click="refresh"></v-btn>
    </v-card-title>

    <v-card-text>
        <!-- Main content -->
    </v-card-text>

    <v-card-actions>
        <v-spacer></v-spacer>
        <v-btn variant="text">Cancel</v-btn>
        <v-btn color="primary">Save</v-btn>
    </v-card-actions>
</v-card>
```

### Template-Level Auth Checks

```html
<!-- Jinja auth checks (server-side) -->
{% if current_user.is_authenticated %}
    <v-btn href="/dashboard">Dashboard</v-btn>
{% else %}
    <v-btn href="/login">Login</v-btn>
{% endif %}

{% if current_user.is_superadmin %}
    <v-btn href="/users/">User Management</v-btn>
{% endif %}
```

## Background Tasks (Celery)

### Optional Dependency

Celery and Redis are optional dependencies installed via `uv sync --extra full`. The task system gracefully handles their absence:

```python
# enferno/tasks/__init__.py
import importlib.util

CELERY_AVAILABLE = importlib.util.find_spec("celery") is not None

celery = None

if CELERY_AVAILABLE:
    from celery import Celery
    from enferno.settings import Config as cfg

    if cfg.CELERY_BROKER_URL:
        celery = Celery(
            "enferno.tasks",
            broker=cfg.CELERY_BROKER_URL,
            backend=cfg.CELERY_RESULT_BACKEND,
            broker_connection_retry_on_startup=True,
        )
```

### Task Definition

Tasks are defined in `enferno/tasks/`:

```python
from enferno.tasks import celery

@celery.task
def send_welcome_email(user_id):
    from enferno.user.models import User
    from flask_mail import Message
    from enferno.extensions import mail

    user = db.session.get(User, user_id)
    if not user:
        return False

    msg = Message(
        subject="Welcome!",
        recipients=[user.email],
        body=f"Welcome {user.name}!"
    )
    mail.send(msg)
    return True
```

### Calling Tasks

```python
from enferno.tasks import send_welcome_email

# Call asynchronously
send_welcome_email.delay(user.id)

# Call with ETA
from datetime import datetime, timedelta
send_welcome_email.apply_async(
    args=[user.id],
    eta=datetime.now() + timedelta(hours=1)
)
```

### Running Celery Worker

```bash
celery -A enferno.tasks worker -l info
```

## Docker Deployment

### Dockerfile

```dockerfile
# syntax=docker/dockerfile:1.4
FROM python:3.12-slim AS builder
WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential python3-dev \
    && rm -rf /var/lib/apt/lists/* \
    && pip install --no-cache-dir uv

COPY pyproject.toml uv.lock ./
RUN uv sync --extra wsgi --frozen --no-install-project

FROM python:3.12-slim
WORKDIR /app
ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends curl libexpat1 \
    && rm -rf /var/lib/apt/lists/* \
    && useradd -m -u 1000 enferno

COPY --from=builder --chown=enferno:enferno /app/.venv ./.venv
COPY --chown=enferno:enferno . .

RUN mkdir -p /app/instance && chown enferno:enferno /app/instance

USER enferno

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:5000/ || exit 1

CMD ["uwsgi", "--http", "0.0.0.0:5000", "--master", "--wsgi", "run:app", "--processes", "2", "--threads", "2"]
```

### Docker Compose

```yaml
services:
  redis:
    image: redis:7-alpine
    command: redis-server --requirepass ${REDIS_PASSWORD:-verystrongpass}
    volumes:
      - redis-data:/data
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s

  postgres:
    image: postgres:15-alpine
    environment:
      - POSTGRES_USER=enferno
      - POSTGRES_PASSWORD=${DB_PASSWORD:-verystrongpass}
      - POSTGRES_DB=enferno
    volumes:
      - postgres-data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD", "pg_isready", "-U", "enferno"]
      interval: 5s

  website:
    build: .
    depends_on:
      - redis
      - postgres
    ports:
      - "8000:5000"
    env_file:
      - .env
    environment:
      - SQLALCHEMY_DATABASE_URI=postgresql://enferno:${DB_PASSWORD:-verystrongpass}@postgres/enferno
      - REDIS_SESSION=redis://:${REDIS_PASSWORD:-verystrongpass}@redis:6379/1
      - CELERY_BROKER_URL=redis://:${REDIS_PASSWORD:-verystrongpass}@redis:6379/2
      - CELERY_RESULT_BACKEND=redis://:${REDIS_PASSWORD:-verystrongpass}@redis:6379/3
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/"]
      interval: 30s

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
    volumes:
      - ./enferno/static/:/app/static/:ro
      - ./nginx/nginx.conf:/etc/nginx/nginx.conf:ro
      - ./nginx/enferno.conf:/etc/nginx/conf.d/default.conf:ro
    depends_on:
      - website
    healthcheck:
      test: ["CMD", "nginx", "-t"]
      interval: 30s

  celery:
    build: .
    command: celery -A enferno.tasks worker -l info
    depends_on:
      - redis
    env_file:
      - .env
    environment:
      - CELERY_BROKER_URL=redis://:${REDIS_PASSWORD:-verystrongpass}@redis:6379/2
      - CELERY_RESULT_BACKEND=redis://:${REDIS_PASSWORD:-verystrongpass}@redis:6379/3

volumes:
  redis-data:
  postgres-data:
```

## Error Handling

### Exception Management

```python
from flask import jsonify
from sqlalchemy.exc import IntegrityError

try:
    db.session.commit()
except IntegrityError:
    db.session.rollback()
    return jsonify({"error": "Data integrity violation"}), 400
except Exception as e:
    db.session.rollback()
    current_app.logger.error(f"Unexpected error: {str(e)}")
    return jsonify({"error": "Internal server error"}), 500
```

### Logging

```python
from flask import current_app

# Use Flask's logger
current_app.logger.info("User login successful")
current_app.logger.error(f"Failed login attempt: {email}")
current_app.logger.debug(f"Processing request: {request.url}")
```

## Configuration Management

### Single Config Class

Configuration in `enferno/settings.py` — there is only one `Config` class (no subclasses):

```python
import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY")
    if not SECRET_KEY:
        raise ValueError("SECRET_KEY environment variable is required")

    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "SQLALCHEMY_DATABASE_URI", "postgresql:///enferno"
    )

    SECURITY_PASSWORD_SALT = os.environ.get("SECURITY_PASSWORD_SALT")
    if not SECURITY_PASSWORD_SALT:
        raise ValueError("SECURITY_PASSWORD_SALT environment variable is required")

    SECURITY_PASSWORD_HASH = "argon2"
    SECURITY_PASSWORD_LENGTH_MIN = 12

    # Billing Provider: 'stripe' or 'chargebee'
    BILLING_PROVIDER = os.environ.get("BILLING_PROVIDER", "stripe")

    # Mail (SSL on port 465)
    MAIL_SERVER = os.environ.get("MAIL_SERVER")
    MAIL_PORT = 465
    MAIL_USE_SSL = True
```

### Environment Variables

Use `.env` file for local development (never commit):

```bash
SECRET_KEY=your-secret-key-here
SQLALCHEMY_DATABASE_URI=sqlite:///enferno.sqlite3  # Dev override (default is postgresql)
FLASK_ENV=development

# Mail settings (SSL on port 465)
MAIL_SERVER=smtp.gmail.com
MAIL_USERNAME=your-email@gmail.com
MAIL_PASSWORD=your-app-password

# Security
SECURITY_PASSWORD_SALT=your-salt-here
SECURITY_TOTP_SECRETS=secret1

# Optional: OAuth
GOOGLE_AUTH_ENABLED=true
GOOGLE_OAUTH_CLIENT_ID=your-client-id
GOOGLE_OAUTH_CLIENT_SECRET=your-client-secret

GITHUB_AUTH_ENABLED=true
GITHUB_OAUTH_CLIENT_ID=your-client-id
GITHUB_OAUTH_CLIENT_SECRET=your-client-secret

# Billing Provider: 'stripe' or 'chargebee'
BILLING_PROVIDER=stripe

# Stripe (if BILLING_PROVIDER=stripe)
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_PRO_PRICE_ID=price_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Chargebee (if BILLING_PROVIDER=chargebee)
CHARGEBEE_SITE=your-site
CHARGEBEE_API_KEY=your-api-key
CHARGEBEE_PRO_ITEM_PRICE_ID=your-item-price-id
CHARGEBEE_WEBHOOK_USERNAME=webhook-user
CHARGEBEE_WEBHOOK_PASSWORD=webhook-pass

# Display values
PRO_PRICE_DISPLAY=$29
PRO_PRICE_INTERVAL=month

# Redis (required for production sessions)
REDIS_SESSION=redis://localhost:6379/1
CELERY_BROKER_URL=redis://localhost:6379/2
CELERY_RESULT_BACKEND=redis://localhost:6379/3
```

## Code Style Standards

### Python Conventions
- Python 3.11+ required
- 4-space indentation
- 88-character line length (Ruff default)
- Double quotes for strings
- Imports ordered by Ruff/isort

### Naming Conventions
- Modules/functions: `snake_case`
- Classes: `PascalCase`
- Constants: `UPPER_CASE`
- Private attributes: `_leading_underscore`

### Import Organization
```python
# Standard library
import os
from datetime import datetime

# Third-party
from flask import Blueprint, jsonify
from flask_security import auth_required

# Local application
from enferno.extensions import db
from enferno.user.models import User
```

## Development Philosophy

Write code that's minimal, rock-solid, and production-ready. Focus on:

- **Simplicity First** - Fewest moving parts possible
- **Production Ready** - Code should work reliably in real use
- **Clear Purpose** - Every line solves one problem well
- **No Over-Engineering** - Avoid premature abstraction
- **Ship Fast** - Functional out-of-the-box with sensible defaults

## Verification Checklist

Before committing:
1. **Lint & Format**: `uv run ruff check --fix .` then `uv run ruff format .`
2. **Test Locally**: `uv run flask create-db && uv run flask install && uv run flask run`
3. **Smoke Test**: Visit `/`, `/login`, dashboard; verify no errors
4. **Pre-commit**: Run `uv run pre-commit run -a`

## Commit Guidelines

- Use imperative present tense: "Add feature" not "Added feature"
- Keep messages concise and descriptive
- Never mention AI/Claude in commits
- Never use `git add .` or `git add -A` - add files selectively
- Format: `Add Stripe webhook handler` or `Fix user login validation`

## Key Principles

1. **Blueprint Organization** - Features organized by functional area
2. **Modern SQLAlchemy** - Statement-based queries (`db.select()`, not legacy `.query`)
3. **Custom Vue Delimiters** - Always use `${}` for Vue expressions
4. **No Build Step** - Direct JavaScript without compilation
5. **Security First** - Use Flask-Security decorators, validate all inputs
6. **Consistent API** - RESTful patterns with standard JSON responses
7. **Environment Config** - Use `.env` files, never hardcode secrets
8. **Modern Tooling** - Use `uv` for package management, Ruff for linting
9. **Multi-Tenant** - All business data scoped to workspaces
10. **Provider Agnostic Billing** - Stripe or Chargebee via `BILLING_PROVIDER` config

This architecture ensures clean separation of concerns, maintainable code, and rapid development velocity.
