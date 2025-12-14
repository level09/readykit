# Railway Deployment

Deploy your SaaS to Railway with CI/CD. Push to deploy.

## Prerequisites

- Railway account (https://railway.app - sign in with GitHub)
- Railway CLI: `npm install -g @railway/cli`

## Quick Setup (CLI)

```bash
# 1. Login
railway login

# 2. Create project
railway init -n my-saas -w "Your Workspace Name"

# 3. Add services
railway add -d postgres
railway add -d redis
railway add -s app

# 4. Link to app service
railway link -p my-saas -s app

# 5. Set environment variables
railway variables --set "SECRET_KEY=$(openssl rand -hex 32)"
railway variables --set "SECURITY_PASSWORD_SALT=$(openssl rand -hex 32)"
railway variables --set "SECURITY_TOTP_SECRETS=$(openssl rand -hex 32)"
railway variables --set "FLASK_APP=run.py"
railway variables --set "FLASK_DEBUG=0"

# 6. Link database URLs (Railway auto-resolves these)
railway variables --set 'SQLALCHEMY_DATABASE_URI=${{Postgres.DATABASE_URL}}'
railway variables --set 'REDIS_SESSION=${{Redis.REDIS_URL}}'
railway variables --set 'CELERY_BROKER_URL=${{Redis.REDIS_URL}}'
railway variables --set 'CELERY_RESULT_BACKEND=${{Redis.REDIS_URL}}'

# 7. Get project token for GitHub Actions
# Go to: Railway Dashboard → Project Settings → Tokens → Create
```

## GitHub Actions Setup

1. Copy your Railway project token
2. Go to GitHub repo → Settings → Secrets and variables → Actions
3. Create new secret: `RAILWAY_TOKEN` = your token

**Important**: If updating an existing secret, delete it first and recreate. Updating sometimes doesn't work.

Push to `railway-deploy` branch (or `master` after testing) to trigger deployment.

## Verify Deployment

```bash
# Check status
railway status

# View logs
railway logs --tail 50

# Get public URL
railway domain
```

## Post-Deployment: Create Admin User

```bash
railway run flask create-db
railway run flask install
```

## File Structure

Your repo needs these files (already included):

**`railway.json`** - Build config:
```json
{
  "build": {
    "builder": "NIXPACKS"
  },
  "deploy": {
    "startCommand": "gunicorn run:app",
    "restartPolicyType": "ON_FAILURE",
    "restartPolicyMaxRetries": 10
  }
}
```

**`.github/workflows/deploy-railway.yml`** - CI/CD workflow:
```yaml
name: Deploy to Railway

on:
  workflow_dispatch:
  push:
    branches: [master]

jobs:
  deploy:
    runs-on: ubuntu-latest
    container: ghcr.io/railwayapp/cli:latest
    env:
      RAILWAY_TOKEN: ${{ secrets.RAILWAY_TOKEN }}
    steps:
      - uses: actions/checkout@v4
      - run: railway up --service app --detach
```

## Redis Databases

Railway Redis supports multiple logical databases. Append DB number to URL:

```
${{Redis.REDIS_URL}}/1  # DB 1 for sessions
${{Redis.REDIS_URL}}/2  # DB 2 for Celery broker
${{Redis.REDIS_URL}}/3  # DB 3 for Celery results
```

## Troubleshooting

**403 Forbidden on deploy**: Delete and recreate `RAILWAY_TOKEN` secret in GitHub.

**Database connection timeout**: Ensure Postgres service is deployed and running.

**Health check failed**: Check logs with `railway logs`. Usually a startup error.

## Cost (Hobby Plan)

~$5/month total:
- App: ~$2-3/month
- PostgreSQL: ~$1-2/month
- Redis: ~$0.50/month

## CLI Reference

```bash
railway login              # Authenticate
railway init -n NAME       # Create project
railway add -d postgres    # Add database
railway add -s NAME        # Add empty service
railway link -p PROJECT -s SERVICE  # Link to service
railway variables          # View variables
railway variables --set "KEY=value"  # Set variable
railway up                 # Deploy
railway logs               # View logs
railway domain             # Get/create public URL
railway run COMMAND        # Run command in service
```
