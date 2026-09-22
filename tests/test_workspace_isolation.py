from types import SimpleNamespace

import pytest
from flask import session
from flask.testing import FlaskClient
from flask_security.utils import hash_password

from enferno.extensions import db
from enferno.services.workspace import (
    WorkspaceScoped,
    WorkspaceService,
    workspace_query,
)
from enferno.user.models import APIKey, User


class WorkspaceRecord(db.Model, WorkspaceScoped):
    __tablename__ = "test_workspace_record"
    id = db.Column(db.Integer, primary_key=True)
    workspace_id = db.Column(db.Integer, db.ForeignKey("workspace.id"), nullable=False)


@pytest.fixture
def tenants(app, monkeypatch):
    class RequestClient(FlaskClient):
        def open(self, *args, **kwargs):
            # The database fixture holds an app context; real requests get a fresh one.
            with self.application.app_context():
                return super().open(*args, **kwargs)

    monkeypatch.setattr(app, "test_client_class", RequestClient)
    password = "correct horse battery staple"
    password_hash = hash_password(password)
    users = [
        User(email=f"{name}@example.com", password=password_hash, active=True)
        for name in ("owner", "other-owner", "member", "other-member")
    ]
    db.session.add_all(users)
    db.session.commit()
    owner, other_owner, member, other_member = users
    own = WorkspaceService.create_workspace("Own", owner)
    other = WorkspaceService.create_workspace("Other", other_owner)
    WorkspaceService.add_member(own.id, member)
    WorkspaceService.add_member(other.id, other_member)
    db.session.commit()

    def login(user):
        client = app.test_client()
        response = client.post(
            "/login", data={"email": user.email, "password": password}
        )
        assert response.status_code == 302
        assert response.location == "/dashboard", response.location
        return client

    client = login(owner)
    other_client = login(other_owner)
    keys = []
    for user_client, workspace in ((client, own), (other_client, other)):
        response = user_client.get(f"/api/workspace/{workspace.id}/stats")
        assert response.json == {"member_count": 2}, (
            response.status_code,
            response.location,
        )
        response = user_client.post(
            f"/api/workspace/{workspace.id}/keys", json={"name": workspace.name}
        )
        assert response.status_code == 200
        keys.append(response.json["id"])
    return SimpleNamespace(
        own=own,
        other=other,
        owner=owner,
        member=member,
        other_member=other_member,
        client=client,
        login=login,
        own_key=keys[0],
        other_key=keys[1],
    )


@pytest.mark.parametrize(
    "method,suffix,payload",
    [
        ("GET", "/stats", None),
        ("GET", "/keys", None),
        ("POST", "/members", {}),
        ("PUT", "", {"name": "Changed"}),
        ("POST", "/keys", {"name": "Intruder"}),
        ("POST", "/members/add", {}),
        ("PUT", "/members/{member_id}", {"role": "admin"}),
        ("DELETE", "/members/{member_id}", None),
        ("DELETE", "/keys/{key_id}", None),
    ],
)
def test_other_workspace_routes_reject_access(tenants, method, suffix, payload):
    suffix = suffix.format(member_id=tenants.other_member.id, key_id=tenants.other_key)
    response = tenants.client.open(
        f"/api/workspace/{tenants.other.id}{suffix}", method=method, json=payload
    )
    assert response.status_code == 403
    with tenants.client.session_transaction() as stored_session:
        assert stored_session["current_workspace_id"] == tenants.own.id
    db.session.expire_all()
    assert tenants.other.name == "Other"
    assert db.session.get(APIKey, tenants.other_key).is_active
    assert tenants.other_member.get_workspace_role(tenants.other.id) == "member"


@pytest.mark.parametrize("action", ["revoke_key", "change_role", "remove_member"])
def test_foreign_record_id_cannot_be_used_in_own_workspace(tenants, action):
    prefix = f"/api/workspace/{tenants.own.id}"
    if action == "revoke_key":
        response = tenants.client.delete(f"{prefix}/keys/{tenants.other_key}")
        assert response.status_code == 404
    elif action == "change_role":
        response = tenants.client.put(
            f"{prefix}/members/{tenants.other_member.id}", json={"role": "admin"}
        )
        assert response.status_code == 400
    else:
        response = tenants.client.delete(f"{prefix}/members/{tenants.other_member.id}")
        assert response.status_code == 400
    db.session.expire_all()
    assert db.session.get(APIKey, tenants.other_key).is_active
    assert tenants.other_member.get_workspace_role(tenants.other.id) == "member"


def test_member_can_read_own_data_but_cannot_write(tenants):
    client = tenants.login(tenants.member)
    prefix = f"/api/workspace/{tenants.own.id}"
    assert [key["id"] for key in client.get(prefix + "/keys").json["keys"]] == [
        tenants.own_key
    ]
    members = client.post(prefix + "/members", json={}).json["items"]
    assert {member["user_id"] for member in members} == {
        tenants.owner.id,
        tenants.member.id,
    }
    assert client.put(prefix, json={"name": "Changed"}).status_code == 403
    assert client.post(prefix + "/keys", json={"name": "Denied"}).status_code == 403
    assert client.delete(f"{prefix}/keys/{tenants.own_key}").status_code == 403
    assert client.post(prefix + "/members/add", json={}).status_code == 403
    assert (
        client.put(
            f"{prefix}/members/{tenants.owner.id}", json={"role": "member"}
        ).status_code
        == 403
    )
    assert client.delete(f"{prefix}/members/{tenants.owner.id}").status_code == 403


def test_revoked_membership_blocks_existing_session(tenants):
    client = tenants.login(tenants.member)
    prefix = f"/api/workspace/{tenants.own.id}"
    assert client.get(prefix + "/keys").status_code == 200
    WorkspaceService.remove_member(tenants.own.id, tenants.member.id)
    assert client.get(prefix + "/keys").status_code == 403
    assert client.post(prefix + "/members", json={}).status_code == 403
    for path in (
        "/workspace/",
        "/workspace/settings/",
        "/workspace/keys/",
        "/workspace/upgrade",
        "/workspace/billing",
    ):
        assert client.get(path).status_code == 403


def test_key_creation_uses_authorized_workspace_not_request_body(tenants):
    response = tenants.client.post(
        f"/api/workspace/{tenants.own.id}/keys",
        json={"name": "New key", "workspace_id": tenants.other.id},
    )
    assert response.status_code == 200
    key = db.session.get(APIKey, response.json["id"])
    assert key.workspace_id == tenants.own.id
    keys = tenants.client.get(f"/api/workspace/{tenants.own.id}/keys").json["keys"]
    assert {item["id"] for item in keys} == {tenants.own_key, key.id}


def test_authorized_url_workspace_overrides_previous_selection(tenants):
    WorkspaceService.add_member(tenants.other.id, tenants.owner)
    db.session.commit()
    response = tenants.client.get(f"/api/workspace/{tenants.other.id}/keys")
    assert response.status_code == 200
    assert [key["id"] for key in response.json["keys"]] == [tenants.other_key]
    with tenants.client.session_transaction() as stored_session:
        assert stored_session["current_workspace_id"] == tenants.other.id


def test_scoped_helpers_exclude_other_workspace_records(app, tenants):
    own_record = WorkspaceRecord(workspace_id=tenants.own.id)
    other_record = WorkspaceRecord(workspace_id=tenants.other.id)
    db.session.add_all([own_record, other_record])
    db.session.commit()
    with app.test_request_context():
        session["current_workspace_id"] = tenants.own.id
        assert WorkspaceRecord.for_current_workspace() == [own_record]
        assert WorkspaceRecord.get_by_id(own_record.id) is own_record
        assert WorkspaceRecord.get_by_id(other_record.id) is None
        assert db.session.scalars(workspace_query(WorkspaceRecord)).all() == [
            own_record
        ]


def test_scoped_helpers_do_not_return_data_without_workspace_context(app, tenants):
    record = WorkspaceRecord(workspace_id=tenants.own.id)
    db.session.add(record)
    db.session.commit()
    with app.test_request_context():
        assert WorkspaceRecord.get_by_id(record.id) is None
        with pytest.raises(ValueError, match="No workspace context"):
            WorkspaceRecord.for_current_workspace()
