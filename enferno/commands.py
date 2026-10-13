"""Click commands."""

import os
import secrets
import string
import subprocess
import sys

import click
from flask import current_app
from flask.cli import AppGroup, with_appcontext
from flask_security.utils import hash_password
from rich.console import Console

from enferno.extensions import db
from enferno.user.models import User

console = Console()


@click.command()
@with_appcontext
def create_db():
    """creates db tables - import your models within commands.py to create the models."""
    from flask_migrate import stamp

    db.create_all()
    stamp()
    print("Database structure created successfully")


@click.command()
@click.option("--email", "-e", help="Admin email (default: admin@example.com)")
@click.option(
    "--password", "-p", help="Admin password (auto-generated if not provided)"
)
@click.option("--non-interactive", "-n", is_flag=True, help="Non-interactive mode")
@click.option("--yes", "-y", is_flag=True, help="Assume yes; non-interactive")
@with_appcontext
def install(email=None, password=None, non_interactive=False, yes=False):
    """Install a default admin user and add an admin role to it."""
    # check if admin exists
    from enferno.user.models import Role

    # Determine effective non-interactive mode
    env_email = os.environ.get("ADMIN_EMAIL") or os.environ.get("ENFERNO_ADMIN_EMAIL")
    env_password = os.environ.get("ADMIN_PASSWORD") or os.environ.get(
        "ENFERNO_ADMIN_PASSWORD"
    )
    non_interactive = non_interactive or yes or (not sys.stdin.isatty())

    # create admin role if it doesn't exist
    admin_role = db.session.execute(
        db.select(Role).where(Role.name == "admin")
    ).scalar_one_or_none()
    if not admin_role:
        admin_role = Role(name="admin")
        db.session.add(admin_role)
        db.session.commit()

    # If email is explicitly provided (via arg or env), prefer operating on that user
    if email is None:
        email = env_email

    # Get email
    if email is None:
        if non_interactive:
            email = "admin@example.com"
        else:
            email = click.prompt("Admin email", default="admin@example.com")

    # Get or generate password (env has priority)
    if password is None:
        password = env_password

    if password is None:
        if non_interactive:
            # Generate a secure password for non-interactive mode
            password = "".join(
                secrets.choice(string.ascii_letters + string.digits + "@#$%^&*")
                for _ in range(32)
            )
        else:
            # Interactive mode - ask user if they want to generate or provide password
            generate_password = click.confirm(
                "Generate a secure random password?", default=True
            )
            if generate_password:
                password = "".join(
                    secrets.choice(string.ascii_letters + string.digits + "@#$%^&*")
                    for _ in range(32)
                )
            else:
                password = click.prompt("Enter admin password", hide_input=True)

    # Extract username from email for backwards compatibility
    username = email.split("@")[0]

    # If a user with this email exists, ensure admin role and optionally reset password
    existing_user = db.session.execute(
        db.select(User).where(User.email == email)
    ).scalar_one_or_none()
    if existing_user:
        if not any(getattr(r, "name", None) == "admin" for r in existing_user.roles):
            existing_user.roles.append(admin_role)
        # Only reset password if it was explicitly provided
        if env_password is not None or (not non_interactive):
            # In non-interactive with no env password we avoid silently changing
            if password:
                existing_user.password = hash_password(password)
        db.session.commit()
        console.print("\n[green]✓[/] Admin setup verified for existing user")
        console.print(f"[blue]Email:[/] {existing_user.email}")
        if env_password:
            console.print("[yellow]Password was updated from provided value[/]")
        return

    # Otherwise, if any admin already exists, don't create another implicitly
    admin_user = db.session.execute(
        db.select(User).where(User.roles.any(Role.name == "admin"))
    ).scalar_one_or_none()
    if admin_user:
        console.print(
            f"[yellow]An admin user already exists:[/] [blue]{admin_user.email}[/]"
        )
        return

    user = User(
        username=username,
        email=email,
        name="Super Admin",
        password=hash_password(password),
        active=True,
    )
    # Try to enable superadmin if supported by model
    if hasattr(user, "is_superadmin"):
        try:
            user.is_superadmin = True
        except Exception:
            pass
    user.roles.append(admin_role)
    db.session.add(user)
    db.session.commit()

    console.print("\n[green]✓[/] Super Admin user created successfully!")
    console.print(f"[blue]Email:[/] {email}")
    console.print(f"[blue]Password:[/] [red]{password}[/]")
    console.print(
        "\n[yellow]⚠️  Please save this password securely - you will not see it again![/]"
    )


@click.command()
@click.option("-e", "--email", prompt=True, default=None)
@click.option("-p", "--password", prompt=True, default=None)
@click.option(
    "--super-admin",
    is_flag=True,
    help="Create as super admin (bypasses UI restrictions)",
)
@with_appcontext
def create(email, password, super_admin):
    """Creates a user using an email."""
    a = db.session.execute(
        db.select(User).where(User.email == email)
    ).scalar_one_or_none()
    if a is not None:
        print("User already exists!")
    else:
        username = email.split("@")[0]
        user = User(
            username=username,
            email=email,
            password=hash_password(password),
            active=True,
            is_superadmin=super_admin,
        )
        db.session.add(user)
        db.session.commit()

        if super_admin:
            console.print(f"[green]✓[/] Super Admin user created: {email}")
            console.print("[yellow]⚠️  This user has full platform access![/]")
        else:
            console.print(f"[green]✓[/] User created: {email}")


@click.command()
@click.option("-e", "--email", prompt=True, default=None)
@click.option("-r", "--role", prompt=True, default="admin")
@with_appcontext
def add_role(email, role):
    """Adds a role to the specified user."""
    from enferno.user.models import Role

    u = db.session.execute(
        db.select(User).where(User.email == email)
    ).scalar_one_or_none()

    if u is None:
        print("Sorry, this user does not exist!")
    else:
        r = db.session.execute(db.select(Role).filter_by(name=role)).scalar_one()
        if r is None:
            print("Sorry, this role does not exist!")
            u = click.prompt("Would you like to create one? Y/N", default="N")
            if u.lower() == "y":
                r = Role(name=role)
                try:
                    db.session.add(r)
                    db.session.commit()
                    print("Role created successfully, you may add it now to the user")
                except Exception:
                    db.session.rollback()
        # add role to user
        u.roles.append(r)
        db.session.commit()


@click.command()
@click.option("-e", "--email", prompt="Email or username", default=None)
@click.option("-p", "--password", hide_input=True, prompt=True, default=None)
@with_appcontext
def reset(email, password):
    """Reset a user password using email or username"""
    try:
        pwd = hash_password(password)
        # Check if user exists with provided email or username
        u = db.session.execute(
            db.select(User).where((User.email == email) | (User.username == email))
        ).scalar_one_or_none()
        if not u:
            print(f'User with email or username "{email}" not found.')
            return

        u.password = pwd
        try:
            db.session.commit()
            print("User password has been reset successfully.")
        except Exception:
            db.session.rollback()
            print("Error committing to database.")
    except Exception as e:
        print(f"Error resetting user password: {e}")


PRO_PRICE_LOOKUP_KEY = "readykit_pro"


def _stripe_cli(*args, api_key=None):
    # STRIPE_API_KEY keeps the key out of the process list.
    env = {**os.environ, "STRIPE_API_KEY": api_key} if api_key else None
    try:
        return subprocess.run(
            ["stripe", *args], capture_output=True, text=True, check=True, env=env
        ).stdout
    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        raise click.ClickException(
            f"`stripe {args[0]}` failed. Install the Stripe CLI and run `stripe login`."
        ) from e


@click.command("stripe-setup")
@click.option("--amount", default=2900, show_default=True, help="Pro price in cents.")
@with_appcontext
def stripe_setup(amount):
    """Create the Stripe Pro price and local webhook secret, then save them to .env."""
    import stripe
    from dotenv import set_key

    config = current_app.config
    if config["BILLING_PROVIDER"] != "stripe":
        raise click.ClickException("stripe-setup requires BILLING_PROVIDER=stripe.")

    def missing(name):
        value = config.get(name)
        return not value or "your_" in value

    env_file = os.path.join(config["PROJECT_ROOT"], ".env")
    stripe.api_key = config["STRIPE_SECRET_KEY"]
    # The Stripe CLI keeps its own keys in the system keychain, so the app key is required.
    if missing("STRIPE_SECRET_KEY") or not stripe.api_key.startswith("sk_test_"):
        raise click.ClickException("Set STRIPE_SECRET_KEY to an sk_test_ key first.")

    if missing("STRIPE_PRO_PRICE_ID"):
        # The lookup key makes reruns reuse the price instead of creating another.
        existing = stripe.Price.list(lookup_keys=[PRO_PRICE_LOOKUP_KEY], active=True)
        price = (
            existing.data[0]
            if existing.data
            else stripe.Price.create(
                unit_amount=amount,
                currency="usd",
                recurring={"interval": config["PRO_PRICE_INTERVAL"]},
                product_data={"name": "Pro"},
                lookup_key=PRO_PRICE_LOOKUP_KEY,
            )
        )
        display = "$" + f"{price.unit_amount / 100:.2f}".removesuffix(".00")
        set_key(env_file, "STRIPE_PRO_PRICE_ID", price.id)
        set_key(env_file, "PRO_PRICE_DISPLAY", display)
        set_key(env_file, "PRO_PRICE_INTERVAL", price.recurring.interval)
        print(f"STRIPE_PRO_PRICE_ID: {price.id} ({display}/{price.recurring.interval})")

    if missing("STRIPE_WEBHOOK_SECRET"):
        # Valid for `stripe listen` forwarding only; production needs a Dashboard endpoint secret.
        secret = _stripe_cli("listen", "--print-secret", api_key=stripe.api_key)
        set_key(env_file, "STRIPE_WEBHOOK_SECRET", secret.strip())
        print("STRIPE_WEBHOOK_SECRET: local `stripe listen` secret")

    print(f"Stripe is configured in {env_file}.")


i18n_cli = AppGroup("i18n")


@i18n_cli.command()
@click.argument("lang")
def init(lang):
    """Initialize a new language"""
    if os.system("pybabel init -i messages.pot -d enferno/translations -l " + lang):
        raise RuntimeError("init command failed")


@i18n_cli.command()
def extract():
    """Extract messages from code"""
    if os.system("pybabel extract -F babel.cfg -k _l -o messages.pot ."):
        raise RuntimeError("Extract command failed")


@i18n_cli.command()
def update():
    """Update translations"""
    if os.system("pybabel update -i messages.pot -d enferno/translations"):
        raise RuntimeError("Update command failed")


@i18n_cli.command()
def compile():
    """Compile translations"""
    if os.system("pybabel compile -d enferno/translations"):
        raise RuntimeError("Compile command failed")
