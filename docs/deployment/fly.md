# Deploy to Fly.io

Automated CI/CD deployment to Fly.io. Push to `master` and your app deploys in ~2 minutes.

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

```bash
# Create database
flyctl postgres create --name your-app-name-db --region iad --initial-cluster-size 1 --vm-size shared-cpu-1x --volume-size 1

# Attach to your app (sets DATABASE_URL automatically)
flyctl postgres attach your-app-name-db -a your-app-name
```

### 4. Set Secrets

```bash
# Required secrets
flyctl secrets set -a your-app-name \
  SECRET_KEY="$(openssl rand -hex 32)" \
  SECURITY_PASSWORD_SALT="$(openssl rand -hex 32)" \
  SECURITY_TOTP_SECRETS="$(openssl rand -hex 32)"

# Fix database URL (Fly uses postgres://, SQLAlchemy needs postgresql://)
# Get the DATABASE_URL from: flyctl secrets list -a your-app-name
# Then set SQLALCHEMY_DATABASE_URI with postgresql:// prefix:
flyctl secrets set -a your-app-name \
  SQLALCHEMY_DATABASE_URI="postgresql://user:pass@your-app-name-db.flycast:5432/your-app-name?sslmode=disable"
```

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

Push to `master`:

```bash
git push origin master
```

Watch deployment: https://github.com/YOUR_USERNAME/YOUR_REPO/actions

Your app will be live at: `https://your-app-name.fly.dev`

## Post-Deployment

### Create Admin User

SSH into your app and create the admin:

```bash
flyctl ssh console -a your-app-name
python -c "from run import app; from enferno.commands import create_db, install; app.app_context().push(); create_db(); install()"
```

Or run interactively:
```bash
flyctl ssh console -a your-app-name -C "flask create-db && flask install"
```

### Optional: Add Redis

For sessions and Celery background tasks:

```bash
flyctl redis create --name your-app-name-redis --region iad --no-replicas
```

Then set the Redis secrets:
```bash
flyctl secrets set -a your-app-name \
  REDIS_URL="redis://..." \
  CELERY_BROKER_URL="redis://..." \
  CELERY_RESULT_BACKEND="redis://..."
```

## Configuration

### fly.toml Options

```toml
app = 'your-app-name'
primary_region = 'iad'  # Change to your preferred region

[http_service]
  internal_port = 5000
  auto_stop_machines = 'stop'      # Stop when idle (saves money)
  auto_start_machines = true       # Start on request
  min_machines_running = 0         # Allow all machines to stop

[[vm]]
  memory = '512mb'                 # Increase for larger apps
  cpu_kind = 'shared'
  cpus = 1
```

### Regions

Common regions:
- `iad` - Virginia, USA
- `lax` - Los Angeles, USA
- `lhr` - London, UK
- `fra` - Frankfurt, Germany
- `sin` - Singapore
- `syd` - Sydney, Australia

Full list: https://fly.io/docs/reference/regions/

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

