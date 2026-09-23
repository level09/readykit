# Fly.io Deployment

The supplied GitHub Actions workflow deploys manually. Enable its commented push
trigger if you want deployments on `master` changes. `fly.toml` configures a web
process only; it does not start a Celery worker.

## One-Time Setup

### 1. Create Fly.io Account

Sign up at https://fly.io and install the CLI:

```bash
# macOS
brew install flyctl

# Linux/WSL
curl -L https://fly.io/install.sh | sh
```

Login:
```bash
flyctl auth login
```

### 2. Create Your App

```bash
flyctl apps create your-app-name
```

### 3. Create Postgres Database

Provision PostgreSQL for your app and obtain its connection URI from the database
setup. ReadyKit reads `SQLALCHEMY_DATABASE_URI`, not `DATABASE_URL`; set it explicitly
using the `postgresql://` scheme. Keep the database provider's required TLS options.

### 4. Set Secrets

```bash
# Required secrets
flyctl secrets set -a your-app-name \
  SECRET_KEY="$(openssl rand -hex 32)" \
  SECURITY_PASSWORD_SALT="$(openssl rand -hex 32)" \
  SECURITY_TOTP_SECRETS="$(openssl rand -hex 32)" \
  SESSION_COOKIE_SECURE=True

# Use the actual connection URI from your database setup:
flyctl secrets set -a your-app-name \
  SQLALCHEMY_DATABASE_URI="postgresql://user:pass@database-host/database-name"
```

`flyctl secrets list` shows names and digests, not secret values. See the
[Fly secrets reference](https://fly.io/docs/flyctl/secrets-list/).

### 5. Update fly.toml

Edit `fly.toml` and change the app name:

```toml
app = 'your-app-name'  # Change this
```

### 6. Add GitHub Secret

1. Create deploy token:
   ```bash
   flyctl tokens create deploy -x 999h -a your-app-name
   ```

2. Add to GitHub:
   - Go to your repo → Settings → Secrets and variables → Actions
   - New repository secret: `FLY_API_TOKEN` = (paste token)

### 7. Deploy

Go to Actions tab in your GitHub repo → "Deploy to Fly.io" → "Run workflow"

Your app will be live at: `https://your-app-name.fly.dev`

**Optional: Auto-deploy on push**

Edit `.github/workflows/deploy-fly.yml` and uncomment the push trigger:
```yaml
on:
  workflow_dispatch:
  push:
    branches: [master]
```

## Post-Deployment

### Create Admin User

SSH into your app and create the admin:

```bash
flyctl ssh console -a your-app-name
# Inside the deployed container, for a fresh database:
flask create-db
flask install
```

For existing databases, run `flask db upgrade` instead of `flask create-db`.

### Optional: Add Redis

Provision a Redis service reachable from the app for Redis sessions. Without
Redis, sessions use the configured SQLAlchemy database. Background jobs also need
a separate Celery worker; setting broker variables does not start one.

Then set the Redis secrets:
```bash
flyctl secrets set -a your-app-name \
  REDIS_URL="redis://..." \
  CELERY_BROKER_URL="redis://..." \
  CELERY_RESULT_BACKEND="redis://..."
```

## Troubleshooting

### View Logs
```bash
flyctl logs -a your-app-name
```

### SSH into Container
```bash
flyctl ssh console -a your-app-name
```

### Check App Status
```bash
flyctl status -a your-app-name
```

### Redeploy Manually
```bash
flyctl deploy -a your-app-name
```
