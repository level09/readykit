# Railway Deployment

Automated CI/CD deployment to Railway. Push to your deploy branch and your app deploys automatically.

## One-Time Setup (5 minutes)

### 1. Create Railway Account

Sign up at https://railway.app (sign in with GitHub recommended).

### 2. Create Project with Services

1. Click **"New Project"** → **"Empty Project"**
2. Name it (e.g., `my-saas`)

**Add the app service:**
1. Click **"New"** → **"Empty Service"**
2. Click on the new service → **Settings** → rename it to **`app`** (important!)

**Add databases:**
1. Click **"New"** → **"Database"** → **"PostgreSQL"**
2. Click **"New"** → **"Database"** → **"Redis"**

Your project should now have 3 services: `app`, `Postgres`, `Redis`

### 3. Get Project Token

1. Click on **project name** (top left) → **Settings**
2. Go to **"Tokens"** tab
3. Click **"Create Token"** → name it `github-deploy`
4. Copy the token

### 4. Add GitHub Secret

1. Go to your GitHub repo → **Settings** → **Secrets and variables** → **Actions**
2. Click **"New repository secret"**
3. Name: `RAILWAY_TOKEN`
4. Value: (paste the token)

### 5. Configure Environment Variables

In Railway dashboard, click on your **`app`** service and add variables:

```bash
# Required
SECRET_KEY=your_64_char_hex_key
SECURITY_PASSWORD_SALT=your_secure_salt
SECURITY_TOTP_SECRETS=your_totp_secret

# Database (Railway sets DATABASE_URL, but Flask needs this format)
SQLALCHEMY_DATABASE_URI=${{DATABASE_URL}}

# Redis (reference Railway's Redis service)
REDIS_SESSION=${{REDIS_URL}}
CELERY_BROKER_URL=${{REDIS_URL}}
CELERY_RESULT_BACKEND=${{REDIS_URL}}

# App
FLASK_APP=run.py
FLASK_DEBUG=0
```

Generate secure keys:
```bash
openssl rand -hex 32  # Run 3 times for each secret
```

### 6. Deploy

Push to `master` (or your deploy branch) and GitHub Actions deploys automatically.

Or trigger manually: **Actions** → **"Deploy to Railway"** → **"Run workflow"**

Your app will be live at the URL shown in Railway dashboard (click on `app` service → **Settings** → **Domains**).

## Post-Deployment

### Create Admin User

1. In Railway dashboard, click on your app service
2. Go to "Settings" → "Railway Shell" (or use Railway CLI)
3. Run:

```bash
flask create-db
flask install
```

Or via Railway CLI:
```bash
npm install -g @railway/cli
railway login
railway link  # Select your project
railway run flask create-db
railway run flask install
```

## Connecting Services

Railway uses service references. In your app's variables:

| Variable | Value |
|----------|-------|
| `SQLALCHEMY_DATABASE_URI` | `${{Postgres.DATABASE_URL}}` |
| `REDIS_SESSION` | `${{Redis.REDIS_URL}}` |
| `CELERY_BROKER_URL` | `${{Redis.REDIS_URL}}` |

The `${{ServiceName.VAR}}` syntax auto-links to other services in your project.

## Troubleshooting

### View Logs

In Railway dashboard → Your service → "Deployments" → Click on deployment → "View Logs"

Or via CLI:
```bash
railway logs
```

### Redeploy Manually

```bash
railway up
```

### Check Service Status

Railway dashboard shows real-time status, metrics, and logs for each service.

### Database Connection Issues

1. Verify PostgreSQL service is running
2. Check `SQLALCHEMY_DATABASE_URI` references the correct service
3. Railway uses `postgres://` - SQLAlchemy accepts both `postgres://` and `postgresql://`

## Cost Estimate (Hobby Plan - $5/month)

- **App**: ~$2-3/month (shared CPU, 512MB RAM)
- **PostgreSQL**: ~$1-2/month (minimal usage)
- **Redis**: ~$0.50/month (minimal usage)

Total: Usually under $5/month for a small SaaS.

## Differences from Fly.io

| Feature | Railway | Fly.io |
|---------|---------|--------|
| Database | Add as service | Separate `flyctl postgres create` |
| Secrets | Dashboard or CLI | `flyctl secrets set` |
| Logs | Dashboard | `flyctl logs` |
| Shell | Dashboard + CLI | `flyctl ssh console` |
| Pricing | Usage-based | Fixed + usage |
