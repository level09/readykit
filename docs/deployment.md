# Deployment

Deploy ReadyKit to production.

## Overview

ReadyKit provides multiple deployment options:

1. **Docker Compose** - Full stack on any server
2. **Fly.io** - Quick cloud deployment with CI/CD
3. **Railway** - Simple cloud deployment with CI/CD
4. **Traditional** - Manual setup on Ubuntu/Debian

## Docker Compose (Recommended)

The simplest way to deploy. One command starts everything:

```bash
docker compose up --build -d
```

This starts:
- **Flask app** via uWSGI
- **PostgreSQL** database
- **Redis** for sessions and Celery
- **Nginx** reverse proxy with SSL
- **Celery** worker for background tasks

### Configuration

1. Copy and edit environment file:
```bash
cp .env-sample .env
# Edit .env with production values
```

2. Key production settings:
```bash
FLASK_DEBUG=0
SECRET_KEY=your_secure_random_key
SQLALCHEMY_DATABASE_URI=postgresql://user:pass@postgres:5432/readykit

# Billing (Stripe or Chargebee)
BILLING_PROVIDER=stripe  # or chargebee
STRIPE_SECRET_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

3. Start the stack:
```bash
docker compose up --build -d
```

4. Create admin user:
```bash
docker compose exec web flask create-db
docker compose exec web flask install
```

## Fly.io Deployment

Quick cloud deployment with automatic CI/CD. See [Fly.io Guide](/deployment/fly) for detailed setup.

### Quick Start

```bash
# Install Fly CLI
brew install flyctl  # or curl -L https://fly.io/install.sh | sh

# Login and create app
flyctl auth login
flyctl apps create your-app-name

# Create database
flyctl postgres create --name your-app-db

# Set secrets
flyctl secrets set SECRET_KEY="$(openssl rand -hex 32)"

# Deploy
flyctl deploy
```

Your app will be live at `https://your-app-name.fly.dev`

## Railway Deployment

Simple cloud deployment with automatic CI/CD. See [Railway Guide](/deployment/railway) for detailed setup.

### Quick Start

```bash
# Create project at railway.app
# Add PostgreSQL and Redis services
# Set environment variables in dashboard

# Add GitHub secret: RAILWAY_TOKEN
# Push to deploy branch - auto-deploys
```

Your app will be live at the URL shown in Railway dashboard.

## Traditional Deployment

For manual setup on Ubuntu/Debian servers.

### Prerequisites

- Python 3.11+
- PostgreSQL
- Redis
- Nginx
- Systemd

### Server Setup

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install dependencies
sudo apt install -y python3-pip python3-venv nginx redis-server postgresql

# Install uv
pip install uv
```

### Application Setup

```bash
# Clone repository
git clone https://github.com/level09/readykit.git
cd readykit

# Setup environment
./setup.sh

# Configure production settings
nano .env  # Update with production values

# Initialize database
source .venv/bin/activate
flask create-db
flask install
```

### Systemd Service

Create `/etc/systemd/system/readykit.service`:

```ini
[Unit]
Description=ReadyKit Web Application
After=network.target

[Service]
User=www-data
WorkingDirectory=/path/to/readykit
Environment="PATH=/path/to/readykit/.venv/bin"
ExecStart=/path/to/readykit/.venv/bin/gunicorn -w 4 -b 127.0.0.1:5000 wsgi:app

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable readykit
sudo systemctl start readykit
```

### Celery Worker

Create `/etc/systemd/system/readykit-celery.service`:

```ini
[Unit]
Description=ReadyKit Celery Worker
After=network.target

[Service]
User=www-data
WorkingDirectory=/path/to/readykit
Environment="PATH=/path/to/readykit/.venv/bin"
ExecStart=/path/to/readykit/.venv/bin/celery -A enferno.tasks worker --loglevel=info

[Install]
WantedBy=multi-user.target
```

### Nginx Configuration

```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /static {
        alias /path/to/readykit/enferno/static;
        expires 30d;
    }
}
```

### SSL with Let's Encrypt

```bash
sudo apt install certbot python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

## Production Checklist

::: details Security
- [ ] Set `FLASK_DEBUG=0`
- [ ] Use strong `SECRET_KEY`
- [ ] Enable HTTPS only
- [ ] Set secure cookie flags
- [ ] Configure firewall (allow 80, 443, 22)
:::

::: details Billing (Stripe/Chargebee)
- [ ] Use live API keys (not test)
- [ ] Configure webhook endpoint
- [ ] Test webhook authentication
- [ ] Verify pricing displays correctly
:::

::: details Database
- [ ] Use PostgreSQL (not SQLite)
- [ ] Set up automated backups
- [ ] Configure connection pooling
:::

::: details Monitoring
- [ ] Set up error tracking (Sentry)
- [ ] Configure logging
- [ ] Set up uptime monitoring
- [ ] Monitor billing webhooks
:::

## Environment Variables

Essential production variables:

```bash
# Core
FLASK_DEBUG=0
SECRET_KEY=your_64_char_hex_key
SECURITY_PASSWORD_SALT=your_secure_salt

# Database
SQLALCHEMY_DATABASE_URI=postgresql://user:pass@localhost/readykit

# Redis
REDIS_SESSION=redis://localhost:6379/1
CELERY_BROKER_URL=redis://localhost:6379/2

# Billing (Stripe or Chargebee)
BILLING_PROVIDER=stripe  # or chargebee
STRIPE_SECRET_KEY=sk_live_...
STRIPE_PRO_PRICE_ID=price_...
STRIPE_WEBHOOK_SECRET=whsec_...

# OAuth (if using)
GOOGLE_AUTH_ENABLED=true
GOOGLE_OAUTH_CLIENT_ID=...
GOOGLE_OAUTH_CLIENT_SECRET=...
```

## Troubleshooting

### Application Not Starting

```bash
# Check service status
sudo systemctl status readykit

# View logs
sudo journalctl -u readykit -f
```

### Database Connection Issues

```bash
# Test PostgreSQL connection
psql -U user -h localhost -d readykit

# Check environment variable
echo $SQLALCHEMY_DATABASE_URI
```

### Billing Webhooks Not Working

```bash
# Check webhook logs in your billing provider's dashboard
# Verify webhook secrets are set correctly
# For Stripe, test locally with:
stripe listen --forward-to localhost:5000/stripe/webhook
```
