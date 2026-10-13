import json
from urllib.parse import parse_qs, urlsplit

import pytest
import requests

from enferno.extensions import db
from enferno.user.models import User


@pytest.fixture
def provider(app, monkeypatch):
    """Answer the provider's token and profile endpoints without network access."""
    routes = {
        "/o/oauth2/token": {"access_token": "t", "token_type": "Bearer"},
        "/login/oauth/access_token": {"access_token": "t", "token_type": "bearer"},
        "/oauth2/v2/userinfo": {"id": "g1", "email": "owner@example.com"},
        "/user": {"id": 7, "login": "owner"},
        "/user/emails": [],
    }

    def send(adapter, request, **kwargs):
        body = routes[urlsplit(request.url).path]
        response = requests.Response()
        response.status_code = 500 if body is None else 200
        response.headers["Content-Type"] = "application/json"
        response._content = json.dumps(body).encode()
        response.url = request.url
        response.request = request
        return response

    monkeypatch.setattr(requests.adapters.HTTPAdapter, "send", send)
    db.session.add(User(email="owner@example.com", password="unused", active=True))
    db.session.commit()
    return routes


def sign_in(app, name):
    client = app.test_client()
    start = client.get(f"/login/{name}")
    state = parse_qs(urlsplit(start.location).query)["state"][0]
    client.get(f"/login/{name}/authorized?code=c&state={state}")
    with client.session_transaction() as session:
        return session.get("_user_id")


def owner_id():
    return str(db.session.scalar(db.select(User.fs_uniquifier)))


@pytest.mark.parametrize("verified", [False, True])
def test_google_links_existing_account_only_for_verified_email(app, provider, verified):
    provider["/oauth2/v2/userinfo"]["verified_email"] = verified

    signed_in = sign_in(app, "google")

    assert (signed_in == owner_id()) is verified


@pytest.mark.parametrize("verified", [False, True])
def test_github_links_existing_account_only_for_verified_primary_email(
    app, provider, verified
):
    provider["/user/emails"] = [
        {"email": "owner@example.com", "primary": True, "verified": verified}
    ]

    signed_in = sign_in(app, "github")

    assert (signed_in == owner_id()) is verified


def link(name, provider_user_id):
    from enferno.user.models import OAuth

    owner = db.session.scalar(db.select(User))
    db.session.add(
        OAuth(
            provider=name,
            provider_user_id=provider_user_id,
            token={"access_token": "old"},
            user=owner,
        )
    )
    db.session.commit()


@pytest.mark.parametrize("linked", [False, True])
def test_github_email_lookup_failure_only_blocks_linking(app, provider, linked):
    provider["/user/emails"] = None  # GitHub answers 500
    if linked:
        link("github", "7")

    signed_in = sign_in(app, "github")

    assert (signed_in == owner_id()) is linked
    assert db.session.scalar(db.select(db.func.count()).select_from(User)) == 1


def test_provider_email_links_case_insensitively(app, provider):
    provider["/oauth2/v2/userinfo"].update(
        email="Owner@Example.COM", verified_email=True
    )

    assert sign_in(app, "google") == owner_id()
    assert db.session.scalar(db.select(db.func.count()).select_from(User)) == 1


@pytest.mark.parametrize("name,provider_user_id", [("google", "g1"), ("github", "7")])
def test_linked_account_signs_in_without_a_verified_email(
    app, provider, name, provider_user_id
):
    link(name, provider_user_id)

    assert sign_in(app, name) == owner_id()
