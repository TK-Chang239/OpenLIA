"""When OPENLIA_REPORT_CHAT_ENABLED=0 (the default), the feature is
inert: no implicit binding fires, attached_report_id is never set
implicitly, locked-chat behavior does not trigger. When =1, it
activates."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def test_client(db_session, monkeypatch):
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
    monkeypatch.setenv("OPENLIA_BACKGROUND_REPORTS_ENABLED", "1")
    app = create_app(db_session_factory=session_mod.SessionLocal)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def seeded_unbound_chat_session(db_session):
    """A chat session with attached_report_id = NULL."""
    from openlia_server.db.models.content import ChatSession

    sess = ChatSession(
        id=str(uuid.uuid4()),
        user_id="local",
        department="equity_research",
        title="Unbound session",
    )
    db_session.add(sess)
    db_session.commit()
    return sess


def test_flag_off_does_not_implicit_bind(
    monkeypatch: pytest.MonkeyPatch,
    test_client: TestClient,
    seeded_unbound_chat_session,
) -> None:
    monkeypatch.setenv("OPENLIA_REPORT_CHAT_ENABLED", "0")
    source_id = seeded_unbound_chat_session.id
    resp = test_client.post(
        "/reports/generate",
        json={
            "source_session_id": source_id,
            "department_id": "equity_research",
            "mode": "stock_initiation",
            "user_input": "MSFT",
        },
    )
    assert resp.status_code == 200
    sess = test_client.get(f"/chat/sessions/{source_id}")
    # Column remains NULL because the flag is off.
    assert sess.json().get("attached_report_id") is None


def test_flag_on_does_implicit_bind(
    monkeypatch: pytest.MonkeyPatch,
    test_client: TestClient,
    seeded_unbound_chat_session,
) -> None:
    monkeypatch.setenv("OPENLIA_REPORT_CHAT_ENABLED", "1")
    source_id = seeded_unbound_chat_session.id
    resp = test_client.post(
        "/reports/generate",
        json={
            "source_session_id": source_id,
            "department_id": "equity_research",
            "mode": "stock_initiation",
            "user_input": "MSFT",
        },
    )
    assert resp.status_code == 200
    sess = test_client.get(f"/chat/sessions/{source_id}")
    assert sess.json()["attached_report_id"] == resp.json()["report_id"]
