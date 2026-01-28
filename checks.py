#!/usr/bin/env python
"""
Quick sanity checks - run before deploying.
No frameworks, no mocking, just real code paths.

Usage:
    uv run python checks.py
    uv run python checks.py -v  # verbose
"""

import sys
import warnings

# Suppress passlib pkg_resources deprecation warning
warnings.filterwarnings("ignore", message="pkg_resources is deprecated")

VERBOSE = "-v" in sys.argv
PASSED = 0
FAILED = 0


def check(name):
    """Decorator to register a check"""

    def decorator(f):
        def wrapper(app):
            global PASSED, FAILED
            try:
                f(app)
                PASSED += 1
                print(f"  \033[32m✓\033[0m {name}")
                return True
            except Exception as e:
                FAILED += 1
                print(f"  \033[31m✗\033[0m {name}")
                if VERBOSE:
                    print(f"    → {e}")
                return False

        wrapper._check_name = name
        return wrapper

    return decorator


# =============================================================================
# CHECKS
# =============================================================================


@check("App boots without errors")
def check_app_boots(app):
    assert app is not None
    assert app.config["SECRET_KEY"]


@check("Database connection works")
def check_database(app):
    from enferno.extensions import db

    with app.app_context():
        db.session.execute(db.text("SELECT 1"))


@check("User model loads")
def check_user_model(app):
    from enferno.user.models import User

    with app.app_context():
        User.query.limit(1).all()


@check("Workspace model and relationships")
def check_workspace_model(app):
    from enferno.user.models import Membership, Workspace

    with app.app_context():
        Workspace.query.limit(1).all()
        Membership.query.limit(1).all()


@check("Workspace service imports")
def check_workspace_service(app):
    from enferno.services.workspace import (
        WorkspaceScoped,
        WorkspaceService,
        require_workspace_access,
        workspace_query,
    )

    assert callable(require_workspace_access)
    assert callable(workspace_query)
    assert hasattr(WorkspaceService, "create_workspace")
    assert hasattr(WorkspaceScoped, "for_current_workspace")


@check("Billing service imports")
def check_billing_service(app):
    from enferno.services.billing import HostedBilling, requires_pro_plan

    assert callable(requires_pro_plan)
    assert hasattr(HostedBilling, "create_upgrade_session")
    assert hasattr(HostedBilling, "create_portal_session")
    assert hasattr(HostedBilling, "handle_successful_payment")


@check("BillingEvent model exists")
def check_billing_event_model(app):
    from enferno.user.models import BillingEvent

    with app.app_context():
        assert hasattr(BillingEvent, "provider")
        BillingEvent.query.limit(1).all()


@check("Auth decorators work")
def check_auth_decorators(app):
    from enferno.services.auth import require_superadmin, require_superadmin_api

    assert callable(require_superadmin)
    assert callable(require_superadmin_api)


@check("All blueprints register")
def check_blueprints(app):
    blueprints = list(app.blueprints.keys())
    required = ["users", "public", "portal", "webhooks"]
    for bp in required:
        assert bp in blueprints, f"Missing blueprint: {bp}"


@check("Critical routes exist")
def check_routes(app):
    rules = [r.rule for r in app.url_map.iter_rules()]

    critical_routes = [
        "/",
        "/login",
        "/dashboard/",
    ]

    for route in critical_routes:
        assert route in rules, f"Missing route: {route}"

    # Billing webhook - one of these must exist based on provider
    webhook_routes = ["/stripe/webhook", "/chargebee/webhook"]
    assert any(r in rules for r in webhook_routes), "Missing billing webhook route"


@check("Security config is sane")
def check_security_config(app):
    # Password security
    assert app.config["SECURITY_PASSWORD_LENGTH_MIN"] >= 8
    # Session security
    assert app.config["SESSION_COOKIE_HTTPONLY"] is True
    # Multi-tenant safety
    assert app.config["SECURITY_EMAIL_CHANGEABLE"] is False


# =============================================================================
# RUNNER
# =============================================================================


def run_checks():
    from enferno.app import create_app

    print("\n\033[1mRunning checks...\033[0m\n")

    app = create_app()
    checks = [v for v in globals().values() if hasattr(v, "_check_name")]

    for check_fn in checks:
        check_fn(app)

    print()
    if FAILED == 0:
        print(f"\033[32m\033[1m✓ All {PASSED} checks passed\033[0m\n")
        return 0
    else:
        print(f"\033[31m\033[1m✗ {FAILED}/{PASSED + FAILED} checks failed\033[0m\n")
        return 1


if __name__ == "__main__":
    sys.exit(run_checks())
