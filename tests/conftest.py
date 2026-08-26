import os

import pytest

os.environ.setdefault("SECRET_KEY", "test-secret-key")
os.environ.setdefault("SECURITY_PASSWORD_SALT", "test-password-salt")
os.environ.setdefault("SECURITY_TOTP_SECRETS", "test-totp-secret")

from enferno.app import create_app
from enferno.extensions import db
from enferno.settings import Config


class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite://"
    SESSION_TYPE = "sqlalchemy"
    SESSION_REDIS = None
    STRIPE_WEBHOOK_SECRET = "whsec_test"
    WTF_CSRF_ENABLED = False


@pytest.fixture(scope="session")
def app():
    return create_app(TestConfig)


@pytest.fixture(autouse=True)
def database(app):
    with app.app_context():
        db.create_all()
        yield
        db.session.remove()
        db.drop_all()
