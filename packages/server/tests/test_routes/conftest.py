"""Fixtures for HTTP-level route tests (company mode app)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

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
def auth_user(company_client: TestClient, db_session, make_user):
    from openlia_server.middleware.auth import COOKIE_NAME
    from openlia_server.services.auth import sessions

    user = make_user(password="CorrectHorseBattery9!")
    created = sessions.create_session(db_session, user_id=user.id, persistent=False)
    company_client.cookies.set(COOKIE_NAME, created.raw_token)
    return user


@pytest.fixture
def company_client_anon(db_session, monkeypatch):
    monkeypatch.setenv("OPENLIA_MODE", "company")
    monkeypatch.setenv("OPENLIA_COOKIE_SECURE", "false")
    from openlia_server.app import create_app
    from openlia_server.db import session as session_mod
    from openlia_server.services.auth import signup_policy

    signup_policy.seed_signup_policy(db_session, mode_flag="company")
    app = create_app(db_session_factory=session_mod.SessionLocal)
    return TestClient(app)


@pytest.fixture
def seed_admin_roster(db_session, create_tables):
    import uuid
    from datetime import UTC, datetime

    from openlia_server.db.models.config import LLMModel, LLMProvider

    provider = LLMProvider(
        id=str(uuid.uuid4()),
        kind="openai",
        label="OpenAI",
        is_enabled=True,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(provider)
    db_session.flush()

    tiers = {}
    for tier in ("thinking", "everyday", "quick"):
        model = LLMModel(
            id=str(uuid.uuid4()),
            provider_id=provider.id,
            tier=tier,
            model_ref=f"gpt-4-{tier}",
            display_name=f"GPT-4 {tier.title()}",
            is_tier_default=True,
            is_enabled=True,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db_session.add(model)
        tiers[tier] = [model]

    db_session.commit()
    return tiers


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


@pytest.fixture
def client(db_session, monkeypatch):
    """Company-mode client for multi-user route tests."""
    monkeypatch.setenv("OPENLIA_MODE", "company")
    monkeypatch.setenv("OPENLIA_COOKIE_SECURE", "false")
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


@pytest.fixture
def report_factory(db_session):
    """Creates Report rows for testing (no file_path — reports are content in DB)."""

    def _make(user_id: str, **kwargs):
        from openlia_server.db.models.content import Report

        r = Report(
            id=str(uuid.uuid4()),
            user_id=user_id,
            department=kwargs.get("department", "secretary"),
            report_type=kwargs.get("report_type", "summary"),
            title=kwargs.get("title", "Test Report"),
            content_markdown=kwargs.get("content_markdown", "# Test"),
            content_structured=kwargs.get("content_structured", {}),
            model_ref=kwargs.get("model_ref", "gpt-4"),
        )
        db_session.add(r)
        db_session.commit()
        return r

    return _make


@pytest.fixture
def seed_message(db_session):
    """Inserts a ChatMessage directly into the DB for route tests."""

    def _seed(session_id: str, role: str, content: str):
        from openlia_server.db.models.content import ChatMessage

        m = ChatMessage(
            id=str(uuid.uuid4()),
            session_id=session_id,
            role=role,
            content=content,
        )
        db_session.add(m)
        db_session.commit()
        return m

    return _seed
