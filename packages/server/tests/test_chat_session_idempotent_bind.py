"""POST /chat/sessions {attached_report_id} is idempotent for the same
(user, report) pair — returns the existing session id rather than
creating a duplicate.

TODO (plan 2026-05-17-report-chat-followup.md Task 5): add a second
multi-user test once company-mode client fixtures are available at this
test module level. The single-user idempotency case is covered below.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def _personal_client(db_session, monkeypatch):
    from openlia_server.app import create_app
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
    with TestClient(app) as client:
        yield client


@pytest.fixture
def seeded_report(db_session):
    from openlia_server.db.models.content import Report

    r = Report(
        id=str(uuid.uuid4()),
        user_id="local",
        department="equity_research",
        report_type="summary",
        title="Test Report",
        content_markdown="# Test",
        content_structured={},
        model_ref="gpt-4",
    )
    db_session.add(r)
    db_session.commit()
    return r


def test_creating_twice_with_same_report_returns_same_session_id(
    _personal_client: TestClient, seeded_report
) -> None:
    body = {
        "department": "equity_research",
        "title": "Bound session",
        "attached_report_id": seeded_report.id,
    }
    a = _personal_client.post("/chat/sessions", json=body).json()
    b = _personal_client.post("/chat/sessions", json=body).json()
    assert a["id"] == b["id"]


def test_different_users_get_different_sessions_for_same_report(db_session, monkeypatch) -> None:
    """Two distinct users posting the same report id each get their own session."""
    from openlia_server.app import create_app
    from openlia_server.db import session as session_mod
    from openlia_server.db.models.auth import User
    from openlia_server.db.models.content import Report
    from openlia_server.middleware.auth import COOKIE_NAME
    from openlia_server.services.auth import passwords, sessions, signup_policy

    monkeypatch.setenv("OPENLIA_MODE", "company")
    monkeypatch.setenv("OPENLIA_COOKIE_SECURE", "false")
    signup_policy.seed_signup_policy(db_session, mode_flag="company")

    # Seed a shared report owned by user_a (user_b's request won't attach
    # it, but the session row is still created with that report id).
    report = Report(
        id=str(uuid.uuid4()),
        user_id="user-a",
        department="equity_research",
        report_type="summary",
        title="Shared Report",
        content_markdown="# Test",
        content_structured={},
        model_ref="gpt-4",
    )

    for uid, email in (("user-a", "a@example.com"), ("user-b", "b@example.com")):
        u = User(
            id=uid,
            email=email,
            display_name=uid,
            password_hash=passwords.hash_password("TestPass1!"),
            is_admin=False,
            is_disabled=False,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        db_session.add(u)

    db_session.add(report)
    db_session.commit()

    app = create_app(db_session_factory=session_mod.SessionLocal)
    body = {
        "department": "equity_research",
        "title": "Bound session",
        "attached_report_id": report.id,
    }

    with TestClient(app) as client_a:
        with session_mod.SessionLocal() as s:
            tok_a = sessions.create_session(s, user_id="user-a", persistent=False)
        client_a.cookies.set(COOKIE_NAME, tok_a.raw_token)
        resp_a = client_a.post("/chat/sessions", json=body).json()

    with TestClient(app) as client_b:
        with session_mod.SessionLocal() as s:
            tok_b = sessions.create_session(s, user_id="user-b", persistent=False)
        client_b.cookies.set(COOKIE_NAME, tok_b.raw_token)
        resp_b = client_b.post("/chat/sessions", json=body).json()

    assert resp_a["id"] != resp_b["id"]
