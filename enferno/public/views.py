import datetime

from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    request,
    send_from_directory,
    url_for,
)
from flask.templating import render_template
from flask_dance.consumer import oauth_authorized, oauth_error
from flask_security import current_user, login_user, logout_user
from oauthlib.oauth2.rfc6749.errors import OAuth2Error
from sqlalchemy.orm.exc import NoResultFound

from enferno.extensions import db
from enferno.services.workspace import WorkspaceService
from enferno.user.models import OAuth, User

public = Blueprint("public", __name__, static_folder="../static")


def get_real_ip():
    """Get real IP address with Cloudflare and proxy support."""
    # First check for Cloudflare
    cf_connecting_ip = request.headers.get("CF-Connecting-IP")
    if cf_connecting_ip:
        return cf_connecting_ip

    # Then check X-Forwarded-For
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        # Get the first IP in the list
        return x_forwarded_for.split(",")[0].strip()

    # Then check X-Real-IP
    x_real_ip = request.headers.get("X-Real-IP")
    if x_real_ip:
        return x_real_ip

    # Finally fall back to remote_addr
    return request.remote_addr


def update_user_login_info(user, ip_address):
    """Update user login tracking information."""
    now = datetime.datetime.now()
    user.last_login_at = user.current_login_at
    user.current_login_at = now
    user.last_login_ip = user.current_login_ip
    user.current_login_ip = ip_address
    user.login_count = (user.login_count or 0) + 1
    db.session.add(user)
    db.session.commit()


def create_oauth_user(provider_data, oauth_token, ip_address):
    """Create a new user from OAuth data."""
    now = datetime.datetime.now()
    user = User(
        email=provider_data.get("email"),
        username=provider_data.get("email"),
        name=provider_data.get("name", ""),
        password=User.random_password(),
        password_set=False,  # OAuth users don't know their random password
        active=True,
        confirmed_at=now,
        current_login_at=now,
        current_login_ip=ip_address,
        login_count=1,
    )
    return user


def get_oauth_user_data(blueprint):
    """Return the provider's user data; email is None unless the provider verified it.

    New logins are linked to accounts by email, so an unverified address would
    let anyone who registers it at the provider sign in as the matching user.
    """
    if not blueprint:
        return None

    if blueprint.name == "google":
        resp = blueprint.session.get("/oauth2/v2/userinfo")
        if not resp.ok:
            current_app.logger.error(f"Failed to fetch user info: {resp.text}")
            return None
        data = resp.json()
        if not data.get("verified_email"):
            data["email"] = None
        return data
    elif blueprint.name == "github":
        resp = blueprint.session.get("/user")
        if not resp.ok:
            current_app.logger.error(f"Failed to fetch GitHub user info: {resp.text}")
            return None
        data = resp.json()
        # Linked users sign in by provider ID, so a failed email lookup only blocks linking.
        email = None
        email_resp = blueprint.session.get("/user/emails")
        if email_resp.ok:
            email = next(
                (
                    e["email"]
                    for e in email_resp.json()
                    if e["primary"] and e["verified"]
                ),
                None,
            )
        else:
            current_app.logger.warning(
                f"Failed to fetch GitHub emails ({email_resp.status_code}): {email_resp.text}"
            )
        return {
            "id": str(data["id"]),  # Convert to string to match Google's ID format
            "email": email,
            "name": data.get("name") or data.get("login"),
        }
    return None


@public.get("/")
def index():
    return render_template("index.html")


@public.get("/robots.txt")
def static_from_root():
    return send_from_directory(public.static_folder, request.path[1:])


# Handle pre-OAuth login check
def before_oauth_login():
    if (
        request.endpoint in ["google.login", "github.login"]
        and current_user.is_authenticated
    ):
        flash("Please sign out before proceeding.", category="warning")
        return redirect(url_for("portal.dashboard"))


# Register the check for all OAuth routes
public.before_app_request(before_oauth_login)


@oauth_authorized.connect
def oauth_logged_in(blueprint, token):
    if not token:
        current_app.logger.error(
            f"OAuth login failed: No token received for {blueprint.name}"
        )
        flash("Authentication failed.", category="error")
        return False

    try:
        # Get user info from provider
        provider_data = get_oauth_user_data(blueprint)
        if not provider_data:
            flash("Authentication failed.", category="error")
            return False

        user_id = provider_data["id"]
        real_ip = get_real_ip()

        # First check if we already have OAuth entry
        query = OAuth.query.filter_by(provider=blueprint.name, provider_user_id=user_id)
        try:
            oauth = query.one()
        except NoResultFound:
            oauth = OAuth(
                provider=blueprint.name, provider_user_id=user_id, token=token
            )

        if not oauth.user and not provider_data.get("email"):
            flash(
                f"Could not confirm a verified {blueprint.name.title()} email.",
                category="error",
            )
            return False

        if oauth.user:
            if current_user.is_authenticated and current_user.id != oauth.user.id:
                logout_user()
            update_user_login_info(oauth.user, real_ip)
            login_user(oauth.user)
        else:
            # Check if user exists with this email
            # Password login matches emails case-insensitively; linking must agree.
            existing_user = User.query.filter(
                db.func.lower(User.email) == provider_data["email"].lower()
            ).first()
            if existing_user:
                # Link OAuth to existing user
                oauth.user = existing_user
                db.session.add(oauth)
                db.session.commit()
                update_user_login_info(existing_user, real_ip)
                login_user(existing_user)
                flash("Account linked successfully.", category="success")
            else:
                # Create new user with workspace
                user = create_oauth_user(provider_data, token, real_ip)
                oauth.user = user
                db.session.add_all([user, oauth])
                db.session.flush()  # Get user ID before creating workspace

                # Only create workspace if user doesn't already have one
                # (handles edge case of orphaned data from deleted users)
                if not user.get_workspaces():
                    WorkspaceService.create_workspace(
                        name="", owner_user=user, auto_name=True
                    )
                login_user(user)
                flash("Welcome! Your workspace has been created.")

        return redirect(url_for("portal.dashboard"))

    except OAuth2Error as e:
        current_app.logger.error(f"OAuth2Error during {blueprint.name} login: {str(e)}")
        flash("Authentication failed.", category="error")
        return False


@oauth_error.connect
def oauth_error(blueprint, message, response):
    current_app.logger.error(
        f"OAuth error from {blueprint.name}: {message}, Response: {response}"
    )
    flash("Authentication failed.", category="error")
