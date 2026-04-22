"""Fixtures for HTTP-level route tests (company mode app)."""

from __future__ import annotations

from datetime import UTC

import pytest
from fastapi.testclient import TestClient
from openlia_server.app import create_app
from openlia_server.middleware.rate_limit import limiter


@pytest.fixture(autouse=True)
def _clear_rate_limiter():
    limiter().clear()
    yield
    limiter().clear()


@pytest.fixture
def wizard_personal_client(db_session):
    """App for wizard route tests — no pre-existing local user, no OPENLIA_MODE override."""
    from openlia_server.db import session as session_mod

    app = create_app(
        db_session_factory=session_mod.SessionLocal,
        is_loopback_request=lambda _: True,
    )
    return TestClient(app)


@pytest.fixture
def wizard_company_client(db_session):
    """App for wizard company route tests — no pre-existing users, no OPENLIA_MODE override."""
    from openlia_server.db import session as session_mod

    app = create_app(
        db_session_factory=session_mod.SessionLocal,
        is_loopback_request=lambda _: True,
    )
    return TestClient(app)


@pytest.fixture
def company_client(db_session, monkeypatch):
    monkeypatch.setenv("OPENLIA_MODE", "company")
    # TestClient speaks http://testserver, so Secure cookies would be dropped
    # by httpx. Override the production-safe default to keep tests plain-http.
    monkeypatch.setenv("OPENLIA_COOKIE_SECURE", "false")
    from openlia_server.db import session as session_mod
    from openlia_server.services.auth import signup_policy

    signup_policy.seed_signup_policy(db_session, mode_flag="company")
    app = create_app(db_session_factory=session_mod.SessionLocal)
    return TestClient(app)


@pytest.fixture
def personal_client(db_session, make_user, monkeypatch):
    from datetime import datetime

    from openlia_server.db import session as session_mod
    from openlia_server.db.models.auth import User

    user = User(
        id="local",
        email="local@openlia.local",
        display_name="Local",
        is_admin=True,
        is_disabled=False,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(user)
    db_session.commit()
    monkeypatch.setenv("OPENLIA_MODE", "personal")
    app = create_app(db_session_factory=session_mod.SessionLocal)
    return TestClient(app)
