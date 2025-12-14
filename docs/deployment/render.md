# Render Deployment

Deploy your SaaS to Render with CI/CD. Dashboard-friendly with Blueprint infrastructure-as-code.

## Prerequisites

- Render account (https://render.com - sign in with GitHub)
- GitHub repository connected to Render

## Quick Setup (Dashboard)

### 1. Create Blueprint from render.yaml

1. Go to https://dashboard.render.com
2. Click "New" → "Blueprint"
3. Connect your GitHub repo
4. Render detects `render.yaml` automatically
5. Fill in the prompted secrets (Stripe keys)
6. Click "Apply" to create all services

This creates:
- **readykit** - Flask web service
- **readykit-db** - PostgreSQL database
- **readykit-redis** - Redis for sessions/Celery

### 2. Get Deploy Hook URL

1. Go to your web service in Render Dashboard
2. Click "Settings" → scroll to "Deploy Hook"
3. Copy the deploy hook URL

### 3. Add GitHub Secret

1. Go to your GitHub repo → Settings → Secrets and variables → Actions
2. Create new secret: `RENDER_DEPLOY_HOOK_URL` = your deploy hook URL

### 4. Deploy

Go to Actions tab → "Deploy to Render" → "Run workflow"

Your app will be live at: `https://readykit.onrender.com`

## Manual Setup (Without Blueprint)

If you prefer manual setup:

### 1. Create PostgreSQL Database

1. Dashboard → New → PostgreSQL
2. Name: `readykit-db`
3. Plan: Starter ($7/month)
4. Create database

### 2. Create Redis

1. Dashboard → New → Redis
2. Name: `readykit-redis`
3. Plan: Starter ($10/month)
4. Create instance

### 3. Create Web Service

1. Dashboard → New → Web Service
2. Connect your GitHub repo
3. Configure:
   - Name: `readykit`
   - Runtime: Python
   - Build Command: `pip install uv && uv sync --extra wsgi --frozen`
   - Start Command: `gunicorn run:app`

### 4. Set Environment Variables

In Web Service → Environment:

```bash
FLASK_APP=run.py
FLASK_DEBUG=0
SECRET_KEY=<generate: openssl rand -hex 32>
SECURITY_PASSWORD_SALT=<generate: openssl rand -hex 32>
SECURITY_TOTP_SECRETS=<generate: openssl rand -hex 32>

# Database (from readykit-db Internal Connection String)
SQLALCHEMY_DATABASE_URI=<copy from PostgreSQL service>

# Redis (from readykit-redis Internal Connection String)
REDIS_SESSION=<copy from Redis service>
CELERY_BROKER_URL=<copy from Redis service>
CELERY_RESULT_BACKEND=<copy from Redis service>

# Stripe
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PUBLISHABLE_KEY=pk_live_...
STRIPE_PRO_PRICE_ID=price_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

## GitHub Actions Setup

The workflow triggers deployment via Deploy Hook (simplest, official method):

**`.github/workflows/deploy-render.yml`**:
```yaml
name: Deploy to Render

on:
  workflow_dispatch:
  # Uncomment to auto-deploy on push:
  # push:
  #   branches: [master]

jobs:
  deploy:
    name: Deploy app
    runs-on: ubuntu-latest
    concurrency: deploy-group
    steps:
      - name: Trigger Render Deploy
        run: curl -s "${{ secrets.RENDER_DEPLOY_HOOK_URL }}"
```

## Post-Deployment: Create Admin User

Use Render's Shell feature:

1. Go to your web service → Shell
2. Run:
   ```bash
   flask create-db
   flask install
   ```

Or use the Render CLI:
```bash
render ssh --service readykit
flask create-db
flask install
```

## File Structure

Your repo needs these files (already included):

**`render.yaml`** - Blueprint config (optional but recommended):
```yaml
services:
  - type: web
    name: readykit
    runtime: python
    buildCommand: pip install uv && uv sync --extra wsgi --frozen
    startCommand: gunicorn run:app
    healthCheckPath: /
    envVars:
      - key: SQLALCHEMY_DATABASE_URI
        fromDatabase:
          name: readykit-db
          property: connectionString
      # ... more vars

databases:
  - name: readykit-db
    plan: starter
```

## Verify Deployment

- Check service status in Dashboard
- View logs: Service → Logs
- Check health: Service → Events

## Troubleshooting

**Deploy Hook returns error**: Regenerate deploy hook in Settings.

**Build fails**: Check logs. Common issues:
- Missing Python version specification
- uv not installing properly

**Database connection timeout**:
- Ensure PostgreSQL service is running
- Use Internal Connection String (not External)

**Health check failed**:
- Check logs for startup errors
- Verify `healthCheckPath: /` returns 200

## Cost (Starter Plans)

~$24/month total:
- Web Service: $7/month
- PostgreSQL: $7/month
- Redis: $10/month

Free tier available for testing (with limitations).

## Render vs Railway vs Fly.io

| Aspect | Render | Railway | Fly.io |
|--------|--------|---------|--------|
| **Setup** | Dashboard-first | CLI-first | CLI-first |
| **Config** | render.yaml | railway.json | fly.toml |
| **Build** | Native Python | NIXPACKS | Dockerfile |
| **Deploy** | Deploy Hook | API Token | API Token |
| **Cost** | ~$24/mo | ~$5/mo | Pay-as-you-go |
| **Free Tier** | Yes (limited) | Yes (limited) | Yes (limited) |

**Choose Render if**: You prefer dashboard UI, want Blueprint IaC, need managed services.

## CLI Reference (Optional)

Install Render CLI:
```bash
npm install -g @render/cli
```

Commands:
```bash
render login              # Authenticate
render services           # List services
render deploys            # View deployments
render logs --service readykit --tail  # Stream logs
render ssh --service readykit          # SSH access
```
