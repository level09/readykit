#!/bin/bash
set -e  # Exit on error

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m'

FULL_CONFIG=false
ASSUME_YES=false
for arg in "$@"; do
    case "$arg" in
        --full) FULL_CONFIG=true ;;
        --yes) ASSUME_YES=true ;;
        -h|--help)
            echo "Usage: ./setup.sh [--full] [--yes]"
            echo "Default: SQLite data and sessions, no Redis required."
            echo "--full: Install and configure Redis sessions and Celery."
            echo "--yes: Skip prompts; no Docker, regenerate .env keeping a provisioned database URL."
            echo "Choosing Docker also enables the full stack."
            exit 0
            ;;
        *) echo "Unknown option: $arg"; exit 1 ;;
    esac
done

# Find a supported Python version
PYTHON_CMD=""
for cmd in python3.14 python3.13 python3.12 python3.11 python3; do
    if command -v "$cmd" &> /dev/null && \
       "$cmd" -c 'import sys; raise SystemExit(sys.version_info < (3, 11))'; then
        PYTHON_CMD=$(command -v "$cmd")
        break
    fi
done

if [ -z "$PYTHON_CMD" ]; then
    echo -e "${RED}Error: Python 3.11 or newer is required${NC}"
    exit 1
fi

echo -e "${GREEN}Using Python: $($PYTHON_CMD --version)${NC}"

# Check if uv is installed
if ! command -v uv &> /dev/null; then
    echo -e "${RED}Error: uv is not installed. Please install uv using: 'pip install uv' or 'curl -sSf https://astral.sh/uv/install.sh | bash'${NC}"
    exit 1
fi

# Modern uv workflow doesn't require manual venv creation
# uv sync will automatically create and manage the virtual environment
echo -e "${GREEN}uv will automatically manage virtual environment...${NC}"

# Note: uv sync creates .venv automatically, activation happens via 'uv run'
# For manual activation after setup:
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    ACTIVATE_CMD="source .venv/Scripts/activate"
else
    ACTIVATE_CMD="source .venv/bin/activate"
fi
echo -e "${GREEN}Virtual environment will be available at .venv${NC}"

# Check for required commands
for cmd in tr openssl awk; do
    if ! command -v $cmd &> /dev/null; then
        echo -e "${RED}Error: $cmd is required but not installed.${NC}"
        exit 1
    fi
done

# Function to generate secure random string
generate_secure_string() {
    local length=$1
    if command -v openssl &> /dev/null; then
        openssl rand -base64 $length | tr -dc 'A-Za-z0-9@#$%^&*' | head -c $length
    else
        LC_ALL=C tr -dc 'A-Za-z0-9@#$%^&*' < /dev/urandom | head -c $length
    fi
}

# Check if .env-sample exists
if [ ! -f .env-sample ]; then
    echo -e "${RED}Error: .env-sample file not found${NC}"
    exit 1
fi

# Ask about Docker configuration
REPLY=n
if [ "$ASSUME_YES" = false ]; then
    read -p "Would you like to configure Docker settings? (y/N) " -n 1 -r
    echo
fi
DOCKER_CONFIG=false
if [[ $REPLY =~ ^[Yy]$ ]]; then
    DOCKER_CONFIG=true
    FULL_CONFIG=true
    echo -e "${GREEN}Docker configuration will be included.${NC}"
else
    echo -e "${YELLOW}Skipping Docker configuration.${NC}"
fi

# Check if .env already exists
BACKUP_FILE=""
if [ -f .env ]; then
    REPLY=y
    if [ "$ASSUME_YES" = false ]; then
        read -p "A .env file already exists. Do you want to overwrite it? (y/N) " -n 1 -r
        echo
    fi
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
    # Backup existing .env (owner-only: it holds secrets)
    BACKUP_FILE=".env.backup.$(date +%Y%m%d_%H%M%S)"
    if ! (umask 077 && cp .env "$BACKUP_FILE"); then
        echo -e "${RED}Error: Failed to create backup file${NC}"
        exit 1
    fi
    echo -e "${GREEN}Created backup of existing .env at $BACKUP_FILE${NC}"
fi

# Install only the dependencies needed for the selected setup.
echo -e "${GREEN}Installing dependencies from pyproject.toml...${NC}"
if [ "$FULL_CONFIG" = true ]; then
    uv sync --python "$PYTHON_CMD" --extra dev --extra full
else
    uv sync --python "$PYTHON_CMD" --extra dev
fi

# .env and its temporary file hold secrets: owner-only, and never left behind.
umask 077
trap 'rm -f .env.new' EXIT

# Print KEY's raw value from the previous .env, unless blank or the sample placeholder.
previous() {
    [ -n "$BACKUP_FILE" ] || return 0
    local value sample
    value=$(grep -m1 "^$1=" "$BACKUP_FILE" | cut -d= -f2-)
    sample=$(grep -m1 "^$1=" .env-sample | cut -d= -f2-)
    if [ -n "$value" ] && [ "$value" != '""' ] && [ "$value" != "$sample" ]; then
        printf '%s' "$value"
    fi
}

# Copy the sample file
if ! cp .env-sample .env; then
    echo -e "${RED}Error: Failed to copy .env-sample to .env${NC}"
    exit 1
fi

# Generate secure random values
SECRET_KEY=$(generate_secure_string 32)
TOTP_SECRET1=$(generate_secure_string 32)
TOTP_SECRET2=$(generate_secure_string 32)
PASSWORD_SALT=$(generate_secure_string 32)
# A running Docker volume keeps its old passwords, so reuse them too.
REDIS_PASSWORD=$(previous REDIS_PASSWORD)
[ -n "$REDIS_PASSWORD" ] || REDIS_PASSWORD=$(generate_secure_string 20)
DB_PASSWORD=$(previous DB_PASSWORD)
[ -n "$DB_PASSWORD" ] || DB_PASSWORD=$(generate_secure_string 20)
DOCKER_UID=$(id -u)

# Validate generated values
if [ -z "$SECRET_KEY" ] || [ -z "$TOTP_SECRET1" ] || [ -z "$TOTP_SECRET2" ] || [ -z "$PASSWORD_SALT" ]; then
    echo -e "${RED}Error: Failed to generate secure values${NC}"
    exit 1
fi

# Keep the previous database with the app's precedence (enferno/settings.py). The SQLite
# default this script writes never outranks a provisioned URL (Fly.io, Railway, Neon).
DATABASE_URL_LINE=""
if [ "$DOCKER_CONFIG" = false ]; then
    for key in SQLALCHEMY_DATABASE_URI DATABASE_URL NEON_POSTGRES_CONNECTION_STRING; do
        value=$(previous "$key")
        if [ -n "$value" ] && [ "$value" != "sqlite:///enferno.sqlite3" ]; then
            DATABASE_URL_LINE="$key=$value"
            break
        fi
    done
fi
export DATABASE_URL_LINE

# Process the .env file. A rerun keeps every previous value: secrets (new ones would
# invalidate stored passwords and 2FA secrets), billing and OAuth settings, and keys the
# sample lacks. Only the settings the selected mode controls are rewritten.
ENV_INPUTS=(.env)
[ -n "$BACKUP_FILE" ] && ENV_INPUTS=("$BACKUP_FILE" .env)
if ! awk -v sk="$SECRET_KEY" -v ts1="$TOTP_SECRET1" -v ts2="$TOTP_SECRET2" -v ps="$PASSWORD_SALT" \
       -v docker="$DOCKER_CONFIG" -v full="$FULL_CONFIG" -v rpass="$REDIS_PASSWORD" -v dbpass="$DB_PASSWORD" -v uid="$DOCKER_UID" \
       -v prevfile="$BACKUP_FILE" '
BEGIN {
    split("SQLALCHEMY_DATABASE_URI SESSION_COOKIE_SECURE REDIS_SESSION CELERY_BROKER_URL CELERY_RESULT_BACKEND DOCKER_UID REDIS_PASSWORD DB_PASSWORD", owned, " ")
    for (i in owned) modal[owned[i]] = 1
    dbkey = ENVIRON["DATABASE_URL_LINE"]
    sub(/=.*/, "", dbkey)
}
FILENAME == prevfile {
    if (match($0, /^[A-Z_][A-Z0-9_]*=/)) {
        k = substr($0, 1, RLENGTH - 1)
        if (!(k in prev)) { prev[k] = substr($0, RLENGTH + 1); order[++n] = k }
    }
    next
}
{
    key = ""
    if (match($0, /^#?[A-Z_][A-Z0-9_]*=/)) {
        key = substr($0, 1, RLENGTH - 1)
        sub(/^#/, "", key)
        known[key] = 1
    }
    if (key != "" && $0 !~ /^#/ && !(key in modal) && (key in prev) \
        && prev[key] != "" && prev[key] != "\"\"" && prev[key] != substr($0, length(key) + 2)) {
        print key "=" prev[key]
        next
    }
    if ($0 ~ /^SECRET_KEY=/) {
        print "SECRET_KEY=\"" sk "\""
    }
    else if ($0 ~ /^SECURITY_TOTP_SECRETS=/) {
        print "SECURITY_TOTP_SECRETS=\"" ts1 "," ts2 "\""
    }
    else if ($0 ~ /^SECURITY_PASSWORD_SALT=/) {
        print "SECURITY_PASSWORD_SALT=\"" ps "\""
    }
    else if (ENVIRON["DATABASE_URL_LINE"] != "" && $0 ~ /^SQLALCHEMY_DATABASE_URI=/) {
        print ENVIRON["DATABASE_URL_LINE"]
    }
    else if ($0 ~ /^SQLALCHEMY_DATABASE_URI=/) {
        print "SQLALCHEMY_DATABASE_URI=sqlite:///enferno.sqlite3"
        print "# PostgreSQL alternative:"
        print "# SQLALCHEMY_DATABASE_URI=postgresql://postgres:pass@localhost/dbname"
    }
    else if (docker != "true" && $0 ~ /^SESSION_COOKIE_SECURE=/) {
        print "SESSION_COOKIE_SECURE=False"
    }
    else if (full != "true" && $0 ~ /^(REDIS_SESSION|CELERY_BROKER_URL|CELERY_RESULT_BACKEND)=/) {
        print "#" $0
    }
    else if (docker == "true" && $0 ~ /^#REDIS_PASSWORD=/) {
        print "REDIS_PASSWORD=" rpass
    }
    else if (docker == "true" && $0 ~ /^#DB_PASSWORD=/) {
        print "DB_PASSWORD=" dbpass
    }
    else if (docker == "true" && $0 ~ /^#SQLALCHEMY_DATABASE_URI=postgresql:/) {
        print "SQLALCHEMY_DATABASE_URI=postgresql://enferno:${DB_PASSWORD}@postgres/enferno"
    }
    else if (docker == "true" && $0 ~ /^#REDIS_SESSION=/) {
        print "REDIS_SESSION=redis://:${REDIS_PASSWORD}@redis:6379/1"
    }
    else if (docker == "true" && $0 ~ /^#CELERY_BROKER_URL=redis:\/\/:/) {
        print "CELERY_BROKER_URL=redis://:${REDIS_PASSWORD}@redis:6379/2"
    }
    else if (docker == "true" && $0 ~ /^#CELERY_RESULT_BACKEND=redis:\/\/:/) {
        print "CELERY_RESULT_BACKEND=redis://:${REDIS_PASSWORD}@redis:6379/3"
    }
    else if (docker == "true" && $0 ~ /^# Docker-specific settings/) {
        print "# Docker-specific settings"
        print "DOCKER_UID=" uid
        print
    }
    else {
        print $0
    }
}
END {
    # Keys the sample does not define (provider ids, custom settings) carry over.
    for (i = 1; i <= n; i++) {
        k = order[i]
        if (!(k in known) && k != dbkey && prev[k] != "") {
            if (!carried++) print "\n# Kept from the previous .env"
            print k "=" prev[k]
        }
    }
}' "${ENV_INPUTS[@]}" > .env.new; then
    echo -e "${RED}Error: Failed to process .env file${NC}"
    exit 1
fi

if ! mv .env.new .env; then
    echo -e "${RED}Error: Failed to save .env file${NC}"
    rm -f .env.new
    exit 1
fi

# Verify the file was created
if [ ! -f .env ]; then
    echo -e "${RED}Error: .env file was not created${NC}"
    exit 1
fi

echo -e "${GREEN}Successfully generated .env file with secure keys${NC}"
if [ -n "$BACKUP_FILE" ]; then
    echo -e "${GREEN}Kept existing values and secrets; generated any secrets that were missing${NC}"
else
    echo -e "${GREEN}Generated secure values for: SECRET_KEY, SECURITY_TOTP_SECRETS, SECURITY_PASSWORD_SALT${NC}"
fi
if [ "$DOCKER_CONFIG" = true ]; then
    echo -e "${GREEN}Docker configuration enabled with secure passwords for Redis and PostgreSQL${NC}"
else
    if [ -n "$DATABASE_URL_LINE" ]; then
        echo -e "${GREEN}Database: kept ${DATABASE_URL_LINE%%=*} from the previous .env${NC}"
    else
        echo -e "${GREEN}SQLite database configured at: enferno.sqlite3${NC}"
    fi
    if [ "$FULL_CONFIG" = true ]; then
        echo -e "${YELLOW}Redis is required at localhost:6379 for sessions and Celery.${NC}"
    else
        echo -e "${GREEN}Sessions use the database. Redis and Celery are disabled.${NC}"
    fi
fi
echo
echo -e "${GREEN}Next steps:${NC}"
echo -e "1. Update the remaining values in your .env file (mail settings, etc.)"
echo -e "2. Modern uv workflow - use these commands:"
echo -e "   ${GREEN}uv run flask create-db${NC}   # Initialize database"
echo -e "   ${GREEN}uv run flask install${NC}     # Create admin user"
echo -e "   ${GREEN}uv run flask run${NC}         # Start development server"
echo -e "   ${GREEN}uv run ruff check --fix .${NC} # Lint and auto-fix code"
echo -e "   ${GREEN}uv run ruff format .${NC}      # Format code"
echo -e "   ${GREEN}uv run pre-commit install${NC} # Install pre-commit hooks"
echo -e ""
echo -e "3. Or activate manually: ${GREEN}$ACTIVATE_CMD${NC}"
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "cygwin" ]]; then
    echo -e "${YELLOW}Note: On Windows, uWSGI is automatically excluded${NC}"
fi
if [ "$DOCKER_CONFIG" = true ]; then
    echo -e "4. For Docker: ${GREEN}docker compose up -d${NC}"
fi
