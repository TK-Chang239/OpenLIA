"""GET /api/admin/guardrail-events with filtering and admin gating."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from openlia_server.db.models.safety import LiaGuardrailEvent


def _seed(db_session, **overrides) -> None:
    base = {
        "id": str(uuid.uuid4()),
        "session_id": "s",
        "user_id": "u",
        "department_id": "equity_research",
        "event_type": "tripwire_flag",
        "category": "leaked_prompt",
        "action_taken": "replaced",
        "user_input_hash": "a" * 64,
        "response_excerpt": "x",
        "created_at": datetime.now(UTC),
    }
    base.update(overrides)
    db_session.add(LiaGuardrailEvent(**base))


def test_list_events_filters_category(db_session, personal_client) -> None:
    _seed(db_session, category="leaked_prompt")
    _seed(db_session, category="advice_phrasing", action_taken="warned")
    db_session.commit()

    r = personal_client.get("/api/admin/guardrail-events?since_days=7&category=leaked_prompt")
    assert r.status_code == 200
    rows = r.json()["items"]
    assert all(row["category"] == "leaked_prompt" for row in rows)


def test_list_events_filters_since(db_session, personal_client) -> None:
    _seed(db_session, created_at=datetime.now(UTC) - timedelta(days=30))
    _seed(db_session, created_at=datetime.now(UTC) - timedelta(days=2))
    db_session.commit()

    r = personal_client.get("/api/admin/guardrail-events?since_days=7")
    rows = r.json()["items"]
    assert len(rows) == 1


@pytest.fixture
def company_client(db_session, monkeypatch) -> TestClient:
    monkeypatch.setenv("OPENLIA_MODE", "company")
    monkeypatch.setenv("OPENLIA_COOKIE_SECURE", "false")
    from openlia_server.app import create_app
    from openlia_server.db import session as session_mod
    from openlia_server.services.auth import signup_policy

    signup_policy.seed_signup_policy(db_session, mode_flag="company")
    app = create_app(db_session_factory=session_mod.SessionLocal)
    return TestClient(app)


def _login(company_client: TestClient, db_session, user) -> None:
    from openlia_server.middleware.auth import COOKIE_NAME
    from openlia_server.services.auth import sessions

    created = sessions.create_session(db_session, user_id=user.id, persistent=False)
    company_client.cookies.set(COOKIE_NAME, created.raw_token)


def test_non_admin_gets_403_on_get_and_delete(company_client, db_session, make_user) -> None:
    _seed(db_session)
    db_session.commit()
    user = make_user(email="pleb@example.com", is_admin=False)
    _login(company_client, db_session, user)

    r = company_client.get("/api/admin/guardrail-events")
    assert r.status_code == 403

    r = company_client.delete("/api/admin/guardrail-events")
    assert r.status_code == 403
    assert db_session.query(LiaGuardrailEvent).count() == 1


def test_admin_can_get_and_delete(company_client, db_session, make_user) -> None:
    _seed(db_session)
    db_session.commit()
    admin = make_user(email="admin@example.com", is_admin=True)
    _login(company_client, db_session, admin)

    r = company_client.get("/api/admin/guardrail-events")
    assert r.status_code == 200
    assert len(r.json()["items"]) == 1

    r = company_client.delete("/api/admin/guardrail-events")
    assert r.status_code == 200
    assert r.json() == {"deleted": 1}
    assert db_session.query(LiaGuardrailEvent).count() == 0
