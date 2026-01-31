import secrets
import string
from datetime import datetime
from uuid import uuid4

from flask_dance.consumer.storage.sqla import OAuthConsumerMixin
from flask_security import AsaList
from flask_security.core import RoleMixin, UserMixin
from flask_security.utils import hash_password
from sluggi import slugify
from sqlalchemy import Column, ForeignKey, Integer, Table, select, update
from sqlalchemy.ext.mutable import MutableList
from sqlalchemy.orm import declared_attr, relationship

from enferno.extensions import db
from enferno.utils.base import BaseMixin

roles_users: Table = db.Table(
    "roles_users",
    Column("user_id", Integer, ForeignKey("user.id"), primary_key=True),
    Column("role_id", Integer, ForeignKey("role.id"), primary_key=True),
)


class Role(db.Model, RoleMixin, BaseMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), unique=True, nullable=True)
    description = db.Column(db.String(255), nullable=True)

    def to_dict(self) -> dict:
        return {"id": self.id, "name": self.name, "description": self.description}

    def from_dict(self, json_dict):
        self.name = json_dict.get("name", self.name)
        self.description = json_dict.get("description", self.description)
        return self


class User(UserMixin, db.Model, BaseMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(255), unique=True, nullable=True)
    fs_uniquifier = db.Column(
        db.String(255), unique=True, nullable=False, default=(lambda _: uuid4().hex)
    )
    name = db.Column(db.String(255), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    password_set = db.Column(db.Boolean, default=True, nullable=False)
    active = db.Column(db.Boolean, default=False, nullable=True)
    is_superadmin = db.Column(db.Boolean, default=False, nullable=False)

    roles = relationship("Role", secondary=roles_users, backref="users")

    confirmed_at = db.Column(db.DateTime, nullable=True)
    last_login_at = db.Column(db.DateTime, nullable=True)
    current_login_at = db.Column(db.DateTime, nullable=True)
    last_login_ip = db.Column(db.String(255), nullable=True)
    current_login_ip = db.Column(db.String(255), nullable=True)
    login_count = db.Column(db.Integer, nullable=True)

    # web authn
    fs_webauthn_user_handle = db.Column(db.String(64), unique=True, nullable=True)
    tf_phone_number = db.Column(db.String(64), nullable=True)
    tf_primary_method = db.Column(db.String(140), nullable=True)
    tf_totp_secret = db.Column(db.String(255), nullable=True)
    mf_recovery_codes = db.Column(db.JSON, nullable=True)

    @declared_attr
    def webauthn(cls):
        return relationship("WebAuthn", backref="users", cascade="all, delete")

    @property
    def display_name(self):
        """Return best available display name for UI."""
        return self.name or self.email

    @property
    def has_usable_password(self):
        """Check if user has a password they actually know.

        OAuth users are created with password_set=False. Once they set
        a password via the change password form, password_set becomes True.
        """
        return self.password_set

    def to_dict(self):
        return {
            "id": self.id,
            "active": self.active,
            "name": self.name,
            "email": self.email,
            "is_superadmin": self.is_superadmin,
        }

    def from_dict(self, json_dict):
        self.name = json_dict.get("name", self.name)
        self.username = json_dict.get("username", self.username)
        if "password" in json_dict:
            self.password = hash_password(json_dict["password"])
        self.active = json_dict.get("active", self.active)
        return self

    def __str__(self) -> str:
        """
        Return the string representation of the object, typically using its ID.
        """
        return f"{self.id}"

    def __repr__(self) -> str:
        """
        Return an unambiguous string representation of the object.
        """
        return f"<User {self.id}: {self.email}>"

    @staticmethod
    def random_password(length=32):
        alphabet = string.ascii_letters + string.digits + string.punctuation
        password = "".join(secrets.choice(alphabet) for i in range(length))
        return hash_password(password)

    def get_workspaces(self):
        """Get all workspaces user has access to"""

        return (
            db.session.execute(
                select(Workspace)
                .join(Membership)
                .where(Membership.user_id == self.id)
                .order_by(Workspace.created_at.desc())
            )
            .scalars()
            .all()
        )

    def get_workspace_role(self, workspace_id):
        """Get user's role in a specific workspace"""
        membership = db.session.execute(
            db.select(Membership).where(
                Membership.user_id == self.id, Membership.workspace_id == workspace_id
            )
        ).scalar_one_or_none()
        return membership.role if membership else None

    def logout_other_sessions(self, current_session_token=None):
        """Logout all other sessions for this user."""
        Session.deactivate_user_sessions(self.id, exclude_token=current_session_token)

    def get_active_sessions(self):
        """Get all active sessions for this user."""
        return [s for s in self.sessions if s.is_active]

    @property
    def two_factor_devices(self):
        """Get a unified list of all 2FA methods/devices."""
        devices = []
        if self.tf_primary_method:
            devices.append(
                {"type": self.tf_primary_method, "name": "Authenticator App"}
            )
        if self.webauthn:
            for wan in self.webauthn:
                devices.append(
                    {"type": "webauthn", "name": wan.name, "usage": wan.usage}
                )
        return devices


class WebAuthn(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    credential_id = db.Column(
        db.LargeBinary(1024), index=True, nullable=False, unique=True
    )
    public_key = db.Column(db.LargeBinary(1024), nullable=False)
    sign_count = db.Column(db.Integer, default=0, nullable=False)
    transports = db.Column(MutableList.as_mutable(AsaList()), nullable=True)
    extensions = db.Column(db.String(255), nullable=True)
    lastuse_datetime = db.Column(db.DateTime, nullable=False)
    name = db.Column(db.String(64), nullable=False)
    usage = db.Column(db.String(64), nullable=False)
    backup_state = db.Column(db.Boolean, nullable=False)
    device_type = db.Column(db.String(64), nullable=False)

    @declared_attr
    def user_id(cls):
        return db.Column(
            db.String(64),
            db.ForeignKey("user.fs_webauthn_user_handle", ondelete="CASCADE"),
            nullable=False,
        )

    def get_user_mapping(self):
        """
        Return the mapping from webauthn back to User.
        Since user_id is fs_webauthn_user_handle, we need to map it correctly.
        """
        return {"fs_webauthn_user_handle": self.user_id}


class OAuth(OAuthConsumerMixin, db.Model):
    __tablename__ = "oauth"
    provider_user_id = db.Column(db.String(256), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey(User.id), nullable=False)
    user = db.relationship(
        User,
        backref=db.backref(
            "oauth_accounts", cascade="all, delete-orphan", lazy="dynamic"
        ),
    )


class Activity(db.Model, BaseMixin):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    workspace_id = db.Column(
        db.Integer, db.ForeignKey("workspace.id", ondelete="CASCADE"), nullable=True
    )
    action = db.Column(db.String(255), nullable=False)
    data = db.Column(db.JSON, nullable=True)

    # Optional relationships for convenience
    user = relationship("User", lazy="joined")
    workspace = relationship("Workspace", lazy="joined")

    @classmethod
    def register(cls, user_id, action, data=None, workspace_id=None):
        """Register an activity for audit purposes (optionally workspace-scoped)."""
        activity = cls(
            user_id=user_id, action=action, data=data, workspace_id=workspace_id
        )
        db.session.add(activity)
        db.session.commit()
        return activity


class BillingEvent(db.Model, BaseMixin):
    """Durable store for processed billing webhook events (idempotency)."""

    id = db.Column(db.Integer, primary_key=True)
    event_id = db.Column(db.String(255), unique=True, nullable=False)
    event_type = db.Column(db.String(128), nullable=True)
    provider = db.Column(db.String(20), nullable=True)  # 'stripe' or 'chargebee'


class Workspace(db.Model, BaseMixin):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    owner_id = db.Column(
        db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )

    # Billing fields
    plan = db.Column(db.String(10), default="free")  # 'free' or 'pro'
    billing_customer_id = db.Column(db.String(100), nullable=True)
    upgraded_at = db.Column(db.DateTime, nullable=True)

    owner = relationship(
        "User",
        backref=db.backref(
            "owned_workspaces", cascade="all, delete-orphan", passive_deletes=True
        ),
    )

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "slug": self.slug,
            "owner_id": self.owner_id,
            "plan": self.plan,
            "is_pro": self.is_pro,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "upgraded_at": self.upgraded_at.isoformat() if self.upgraded_at else None,
        }

    @property
    def is_pro(self):
        """Check if workspace is on pro plan."""
        return self.plan == "pro"

    @staticmethod
    def generate_slug(name):
        """Generate URL-safe slug from name"""

        return slugify(name)


class Membership(db.Model, BaseMixin):
    workspace_id = db.Column(
        db.Integer, db.ForeignKey("workspace.id", ondelete="CASCADE"), primary_key=True
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), primary_key=True
    )
    role = db.Column(
        db.String(20), nullable=False, default="member"
    )  # 'admin' or 'member'

    workspace = relationship(
        "Workspace",
        backref=db.backref(
            "memberships", cascade="all, delete-orphan", passive_deletes=True
        ),
    )
    user = relationship(
        "User",
        backref=db.backref(
            "memberships", cascade="all, delete-orphan", passive_deletes=True
        ),
    )

    def to_dict(self):
        return {
            "workspace_id": self.workspace_id,
            "user_id": self.user_id,
            "role": self.role,
            "user": self.user.to_dict() if self.user else None,
            "workspace": self.workspace.to_dict() if self.workspace else None,
        }


class APIKey(db.Model, BaseMixin):
    """API keys scoped to a workspace."""

    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(
        db.Integer, db.ForeignKey("workspace.id", ondelete="CASCADE"), nullable=False
    )
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    name = db.Column(db.String(100), nullable=False)
    prefix = db.Column(db.String(8), nullable=False)
    key_hash = db.Column(db.String(255), nullable=False)
    last_used_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True, nullable=False)

    workspace = relationship("Workspace", backref=db.backref("api_keys", cascade="all, delete-orphan"))
    user = relationship("User", backref=db.backref("api_keys", cascade="all, delete-orphan"))

    @staticmethod
    def generate_key():
        """Generate a new API key. Returns (full_key, prefix, key_hash)."""
        import hashlib

        full_key = f"rk_{secrets.token_hex(24)}"
        prefix = full_key[:7]
        key_hash = hashlib.sha256(full_key.encode()).hexdigest()
        return full_key, prefix, key_hash

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "prefix": self.prefix,
            "is_active": self.is_active,
            "last_used_at": self.last_used_at.isoformat() if self.last_used_at else None,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class Session(db.Model, BaseMixin):
    """Track active user sessions for session management."""

    __tablename__ = "user_sessions"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("user.id", ondelete="CASCADE"), nullable=False
    )
    user = db.relationship(
        "User",
        backref=db.backref(
            "sessions", lazy=True, cascade="all, delete-orphan", passive_deletes=True
        ),
    )

    session_token = db.Column(db.String(255), unique=True, nullable=False)
    last_active = db.Column(db.DateTime, default=datetime.now)
    expires_at = db.Column(db.DateTime, nullable=True)
    ip_address = db.Column(db.String(255), nullable=True)

    # Browser, OS, device metadata
    meta = db.Column(db.JSON, nullable=True)

    is_active = db.Column(db.Boolean, default=True)

    def to_dict(self):
        return {
            "id": self.id,
            "user_id": self.user_id,
            "last_active": self.last_active.isoformat() if self.last_active else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "ip_address": self.ip_address,
            "meta": self.meta,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    @classmethod
    def create_session(cls, user_id, session_token, ip_address=None, meta=None):
        """Create or update a session for a user.

        Uses get-or-create pattern to avoid unique constraint violations
        that would rollback other pending changes (like password updates).
        """
        # Try to find existing session first
        existing = db.session.execute(
            db.select(cls).where(cls.session_token == session_token)
        ).scalar_one_or_none()
        if existing:
            # Update existing session
            existing.user_id = user_id
            existing.ip_address = ip_address
            existing.meta = meta
            existing.is_active = True
            existing.last_active = datetime.now()
            db.session.add(existing)
            return existing

        # Create new session
        session_record = cls(
            user_id=user_id,
            session_token=session_token,
            ip_address=ip_address,
            meta=meta,
            is_active=True,
        )
        db.session.add(session_record)
        return session_record

    @classmethod
    def deactivate_user_sessions(cls, user_id, exclude_token=None):
        """Deactivate all sessions for a user, optionally excluding current."""
        conditions = [cls.user_id == user_id, cls.is_active.is_(True)]
        if exclude_token:
            conditions.append(cls.session_token != exclude_token)
        db.session.execute(
            update(cls).where(*conditions).values(is_active=False)
        )
        db.session.commit()
