import datetime

import orjson as json
from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    jsonify,
    render_template,
    request,
    session,
)
from flask_login import user_logged_out
from flask_security import auth_required, current_user
from flask_security.signals import (
    password_changed,
    tf_profile_changed,
    user_authenticated,
)

from enferno.extensions import db
from enferno.user.models import Activity, Membership, Session, User, Workspace

bp_user = Blueprint("users", __name__, static_folder="../static")

PER_PAGE = 25


def validate_super_admin_change(user, new_status):
    """Validate super admin status changes - enforce single super admin rule"""
    # Trying to add super admin
    if new_status and not user.is_superadmin:
        existing = db.session.execute(
            db.select(User).where(User.is_superadmin)
        ).scalar_one_or_none()
        if existing:
            return (
                "Only one super admin is allowed. Use CLI command to create additional super admins if needed.",
                400,
            )

    # Trying to remove super admin
    if not new_status and user.is_superadmin:
        count = db.session.execute(
            db.select(db.func.count(User.id)).where(User.is_superadmin)
        ).scalar()
        if count <= 1:
            return (
                "Cannot remove the last super admin. Create another super admin first.",
                400,
            )

    return None


@bp_user.before_request
@auth_required("session")
def before_request():
    # Ensure only super admins can access user management
    if not current_user.is_superadmin:
        abort(403)


@bp_user.get("/users/")
def users():
    # Get all workspaces for assignment
    workspaces = db.session.execute(db.select(Workspace)).scalars().all()
    workspace_list = [{"id": w.id, "name": w.name} for w in workspaces]

    return render_template("cms/users.html", workspaces=workspace_list)


@bp_user.get("/api/users")
def api_user():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", PER_PAGE, type=int)

    query = db.select(User)
    pagination = db.paginate(query, page=page, per_page=per_page)

    def user_with_workspaces(user):
        """Add workspace info to user dict"""
        workspaces = user.get_workspaces()
        owned_count = db.session.execute(
            db.select(db.func.count(Workspace.id)).where(Workspace.owner_id == user.id)
        ).scalar()
        return {
            **user.to_dict(),
            "workspace_count": len(workspaces),
            "owned_workspace_count": owned_count,
            "workspaces": [
                {"id": w.id, "name": w.name, "role": user.get_workspace_role(w.id)}
                for w in workspaces[:3]  # Show first 3
            ],
        }

    items = [user_with_workspaces(user) for user in pagination.items]

    return Response(
        json.dumps(
            {"items": items, "total": pagination.total, "perPage": pagination.per_page}
        ),
        content_type="application/json",
    )


@bp_user.post("/api/user/")
def api_user_create():
    user_data = request.get_json(silent=True) or {}
    user_data = user_data.get("item", {})

    user = User()
    user.from_dict(user_data)

    # Validate super admin changes
    if "is_superadmin" in user_data and user_data["is_superadmin"]:
        error = validate_super_admin_change(user, True)
        if error:
            return jsonify({"error": error[0]}), error[1]
        user.is_superadmin = True

    user.confirmed_at = datetime.datetime.now()
    db.session.add(user)
    db.session.flush()

    # Handle workspace assignments
    if "workspace_ids" in user_data and not user.is_superadmin:
        for workspace_id in user_data.get("workspace_ids", []):
            db.session.add(
                Membership(user_id=user.id, workspace_id=workspace_id, role="member")
            )

    try:
        db.session.commit()
        Activity.register(current_user.id, "User Create", user.to_dict())
        return jsonify({"message": "User successfully created!"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400


@bp_user.post("/api/user/<int:id>")
def api_user_update(id):
    user = db.get_or_404(User, id)
    user_data = request.get_json(silent=True) or {}
    user_data = user_data.get("item", {})

    old_user_data = user.to_dict()
    user.from_dict(user_data)

    # Validate super admin changes
    if "is_superadmin" in user_data:
        error = validate_super_admin_change(user, user_data["is_superadmin"])
        if error:
            return jsonify({"error": error[0]}), error[1]
        user.is_superadmin = user_data["is_superadmin"]

    # Handle workspace assignments
    if "workspace_ids" in user_data and not user.is_superadmin:
        db.session.execute(db.delete(Membership).where(Membership.user_id == user.id))
        for workspace_id in user_data.get("workspace_ids", []):
            db.session.add(
                Membership(user_id=user.id, workspace_id=workspace_id, role="member")
            )

    try:
        db.session.commit()
        Activity.register(
            current_user.id,
            "User Update",
            {"old": old_user_data, "new": user.to_dict()},
        )
        return jsonify({"message": "User successfully updated!"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400


@bp_user.delete("/api/user/<int:id>")
def api_user_delete(id):
    user = db.get_or_404(User, id)
    user_data = user.to_dict()

    try:
        # Explicitly clean up owned workspaces and their memberships
        owned_workspaces = db.session.execute(
            db.select(Workspace).where(Workspace.owner_id == user.id)
        ).scalars().all()

        for ws in owned_workspaces:
            # Delete all memberships for this workspace
            db.session.execute(
                db.delete(Membership).where(Membership.workspace_id == ws.id)
            )
            db.session.delete(ws)

        # Delete user's memberships in other workspaces
        db.session.execute(
            db.delete(Membership).where(Membership.user_id == user.id)
        )

        db.session.delete(user)
        db.session.commit()
        Activity.register(current_user.id, "User Delete", user_data)
        return jsonify({"message": "User successfully deleted!"})
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 400


@bp_user.get("/activities/")
def activities():
    return render_template("cms/activities.html")


@bp_user.get("/api/activities")
def api_activities():
    page = request.args.get("page", 1, type=int)
    per_page = request.args.get("per_page", PER_PAGE, type=int)

    query = db.select(Activity).order_by(Activity.created_at.desc())
    pagination = db.paginate(query, page=page, per_page=per_page)

    def activity_to_dict(activity):
        """Convert activity to dict with user info"""
        user = db.session.get(User, activity.user_id)
        return {
            "id": activity.id,
            "user": user.display_name if user else f"User ID: {activity.user_id}",
            "action": activity.action,
            "data": activity.data,
            "created_at": activity.created_at.strftime("%Y-%m-%d %H:%M:%S"),
        }

    items = [activity_to_dict(activity) for activity in pagination.items]

    return Response(
        json.dumps(
            {"items": items, "total": pagination.total, "perPage": pagination.per_page}
        ),
        content_type="application/json",
    )


# --- Flask-Security Signal Handlers ---


@user_authenticated.connect
def user_authenticated_handler(app, user, authn_via, **extra_args):
    """Handle user authentication - create session record and check for new IP."""
    session_data = {
        "user_id": user.id,
        "session_token": session.sid if hasattr(session, "sid") else str(id(session)),
        "ip_address": request.remote_addr,
        "meta": {
            "browser": request.user_agent.browser,
            "browser_version": request.user_agent.version,
            "os": request.user_agent.platform,
            "device": request.user_agent.string,
        },
    }

    # Create session record
    Session.create_session(**session_data)

    # Log if logged in from a different IP
    if user.last_login_ip and user.current_login_ip != user.last_login_ip:
        Activity.register(
            user.id,
            "Login from new IP",
            {"old_ip": user.last_login_ip, "new_ip": user.current_login_ip},
        )

    # Enforce single session if configured
    if current_app.config.get("DISABLE_MULTIPLE_SESSIONS", False):
        user.logout_other_sessions(session_data["session_token"])


@password_changed.connect
def after_password_change(sender, user, **extra_args):
    """Log password change and mark password as user-set."""
    user.password_set = True
    db.session.add(user)
    Activity.register(user.id, "Password Changed", {"email": user.email})


@tf_profile_changed.connect
def after_tf_profile_change(sender, user, **extra_args):
    """Log 2FA profile changes."""
    Activity.register(
        user.id,
        "Two-Factor Profile Changed",
        {"email": user.email, "method": user.tf_primary_method},
    )


@user_logged_out.connect
def user_logged_out_handler(app, user, **extra_args):
    """Clear session on logout."""
    if hasattr(session, "sid"):
        # Deactivate the session record
        Session.query.filter_by(session_token=session.sid, is_active=True).update(
            {"is_active": False}
        )
        db.session.commit()
    session.clear()
