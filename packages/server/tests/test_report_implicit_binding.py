"""When a report is generated from a chat session whose
attached_report_id is NULL, the session's attached_report_id is set to
the new report's id on ReportComplete. If the column was already set
(race), the conditional UPDATE leaves it alone."""

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
    monkeypatch.setenv("OPENLIA_BACKGROUND_REPORTS_ENABLED", "1")
    monkeypatch.setenv("OPENLIA_REPORT_CHAT_ENABLED", "1")
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


@pytest.fixture
def seeded_existing_report(db_session):
    """A completed report that the bound session points at."""
    from openlia_server.db.models.content import Report

    r = Report(
        id=str(uuid.uuid4()),
        user_id="local",
        department="equity_research",
        report_type="stock_initiation",
        title="Existing Report",
        content_markdown="# Existing",
        content_structured={},
        model_ref="gpt-4",
    )
    db_session.add(r)
    db_session.commit()
    return r


@pytest.fixture
def seeded_bound_chat_session(db_session, seeded_existing_report):
    """A chat session already pointing at a report."""
    from openlia_server.db.models.content import ChatSession

    sess = ChatSession(
        id=str(uuid.uuid4()),
        user_id="local",
        department="equity_research",
        title="Bound session",
        attached_report_id=seeded_existing_report.id,
    )
    db_session.add(sess)
    db_session.commit()
    # Expose original_report_id for assertions.
    sess.original_report_id = seeded_existing_report.id  # type: ignore[attr-defined]
    return sess


def test_report_from_unbound_chat_implicitly_binds_session(
    _personal_client: TestClient, seeded_unbound_chat_session, db_session
) -> None:
    source_id = seeded_unbound_chat_session.id
    resp = _personal_client.post(
        "/reports/generate",
        json={
            "source_session_id": source_id,
            "department_id": "equity_research",
            "mode": "stock_initiation",
            "user_input": "MSFT",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    new_report_id = body["report_id"]

    # Source session is now bound to the new report.
    sess_get = _personal_client.get(f"/chat/sessions/{source_id}")
    assert sess_get.status_code == 200
    assert sess_get.json()["attached_report_id"] == new_report_id

    # Response carries the source session id (no redirect needed).
    assert body["session_id"] == source_id
    assert body.get("redirect") is False


def test_implicit_binding_skipped_when_column_already_set(
    _personal_client: TestClient, seeded_bound_chat_session, db_session
) -> None:
    source_id = seeded_bound_chat_session.id
    original_report_id = seeded_bound_chat_session.original_report_id
    resp = _personal_client.post(
        "/reports/generate",
        json={
            "source_session_id": source_id,
            "department_id": "equity_research",
            "mode": "stock_initiation",
            "user_input": "AAPL",
        },
    )
    assert resp.status_code == 200
    body = resp.json()

    # Source session column is unchanged (still points at original report).
    sess_get = _personal_client.get(f"/chat/sessions/{source_id}")
    assert sess_get.status_code == 200
    assert sess_get.json()["attached_report_id"] == original_report_id

    # The response carries a different session id for the new report.
    assert body.get("session_id") and body["session_id"] != source_id
    assert body.get("redirect") is True
