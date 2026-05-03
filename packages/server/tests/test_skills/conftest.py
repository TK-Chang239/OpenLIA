"""Fixtures for test_skills — re-export the standard route test fixtures."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient
from openlia_server.middleware.rate_limit import limiter


@pytest.fixture(autouse=True)
def _clear_rate_limiter():
    limiter().clear()
    yield
    limiter().clear()


@pytest.fixture
def client(db_session, monkeypatch):
    """Company-mode client for multi-user route tests."""
    monkeypatch.setenv("OPENLIA_MODE", "company")
    monkeypatch.setenv("OPENLIA_COOKIE_SECURE", "false")
    from openlia_server.app import create_app
    from openlia_server.db import session as session_mod
    from openlia_server.services.auth import signup_policy

    signup_policy.seed_signup_policy(db_session, mode_flag="company")
    app = create_app(db_session_factory=session_mod.SessionLocal)
    return TestClient(app)


@pytest.fixture
def user_factory(db_session):
    """Creates unique User rows; call with no args to get a new user each time."""
    counter = [0]

    def _make():
        counter[0] += 1
        from openlia_server.db.models.auth import User
        from openlia_server.services.auth import passwords

        u = User(
            id=str(uuid.uuid4()),
            email=f"testuser{counter[0]}@example.com",
            display_name=f"User{counter[0]}",
            password_hash=passwords.hash_password("TestPass1!"),
            is_admin=False,
            is_disabled=False,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db_session.add(u)
        db_session.commit()
        return u

    return _make


@pytest.fixture
def login_as(client):
    """Authenticates the client as a given user via session cookie."""

    def _login(user):
        from openlia_server.db import session as session_mod
        from openlia_server.middleware.auth import COOKIE_NAME
        from openlia_server.services.auth import sessions

        with session_mod.SessionLocal() as s:
            created = sessions.create_session(s, user_id=user.id, persistent=False)
        client.cookies.set(COOKIE_NAME, created.raw_token)

    return _login
