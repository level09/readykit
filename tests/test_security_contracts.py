import pytest
from flask import g, session
from flask_login import login_user
from flask_security.utils import hash_password, verify_password
from werkzeug.exceptions import Forbidden

from enferno.extensions import db
from enferno.services.billing import PROVIDER
from enferno.services.workspace import require_workspace_access
from enferno.user.models import Membership, User, Workspace


def _create_user(email):
    user = User(
        email=email,
        password=hash_password("correct horse battery staple"),
        active=True,
    )
    db.session.add(user)
    db.session.flush()
    return user


def _create_workspace(name, owner):
    workspace = Workspace(name=name, slug=name.lower(), owner_id=owner.id)
    db.session.add(workspace)
    db.session.flush()
    db.session.add(
        Membership(workspace_id=workspace.id, user_id=owner.id, role="admin")
    )
    db.session.commit()
    return workspace


def test_password_hash_round_trip_uses_supported_backend(app):
    with app.app_context():
        password_hash = hash_password("correct horse battery staple")

        assert verify_password("correct horse battery staple", password_hash)
        assert not verify_password("wrong password", password_hash)


def test_member_cannot_access_another_workspace(app):
    with app.app_context():
        member = _create_user("member@example.com")
        member_workspace = _create_workspace("Member", member)
        other_owner = _create_user("other@example.com")
        other_workspace = _create_workspace("Other", other_owner)

        @require_workspace_access("member")
        def endpoint(workspace_id):
            return g.current_workspace.id

        with app.test_request_context(
            f"/api/workspace/{other_workspace.id}",
            method="GET",
        ):
            login_user(member)
            session["current_workspace_id"] = member_workspace.id

            with pytest.raises(Forbidden):
                endpoint(workspace_id=other_workspace.id)


def test_member_cannot_use_admin_route(app):
    with app.app_context():
        owner = _create_user("owner@example.com")
        workspace = _create_workspace("Team", owner)
        member = _create_user("member@example.com")
        db.session.add(
            Membership(
                workspace_id=workspace.id,
                user_id=member.id,
                role="member",
            )
        )
        db.session.commit()

        @require_workspace_access("admin")
        def endpoint(workspace_id):
            return g.current_workspace.id

        with app.test_request_context(
            f"/api/workspace/{workspace.id}",
            method="POST",
        ):
            login_user(member)

            with pytest.raises(Forbidden):
                endpoint(workspace_id=workspace.id)


@pytest.mark.skipif(PROVIDER != "stripe", reason="Stripe provider only")
def test_stripe_webhook_rejects_invalid_signature(app):
    response = app.test_client().post(
        "/stripe/webhook",
        data=b"{}",
        headers={"Stripe-Signature": "invalid"},
    )

    assert response.status_code == 400
