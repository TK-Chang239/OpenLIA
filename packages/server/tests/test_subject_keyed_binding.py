"""When OPENLIA_REVISION_PASS_ENABLED=1, the chat-followup §4 routing
checks SUBJECT equality (lowercased + trimmed) instead of just
attached_report_id-is-None. Same ticker re-anchors; different ticker
spawns a new thread."""

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
    monkeypatch.setenv("OPENLIA_REPORT_CHAT_ENABLED", "1")
    app = create_app(db_session_factory=session_mod.SessionLocal)
    with TestClient(app) as client:
        yield client


@pytest.fixture
def seeded_bound_chat_session_msft(db_session):
    """A chat session already bound to a report for ticker MSFT."""
    from openlia_server.db.models.content import ChatSession, Report

    report = Report(
        id=f"r_{uuid.uuid4().hex[:12]}",
        user_id="local",
        department="equity_research",
        report_type="stock_initiation",
        title="equity_research — MSFT",
        content_markdown="",
        content_structured={},
        model_ref="",
        status="generating",
        original_request={
            "department_id": "equity_research",
            "mode": "stock_initiation",
            "user_input": "MSFT",
            "enabled_sections": [],
            "length": "standard",
            "source_session_id": None,
        },
        started_at=datetime.now(UTC),
    )
    db_session.add(report)
    db_session.flush()

    sess = ChatSession(
        id=str(uuid.uuid4()),
        user_id="local",
        department="equity_research",
        title="MSFT session",
        attached_report_id=report.id,
    )
    db_session.add(sess)
    db_session.commit()
    return sess


def test_same_ticker_in_bound_chat_re_anchors(
    monkeypatch: pytest.MonkeyPatch,
    test_client: TestClient,
    seeded_bound_chat_session_msft,
) -> None:
    monkeypatch.setenv("OPENLIA_REVISION_PASS_ENABLED", "1")
    src_id = seeded_bound_chat_session_msft.id
    original_attached = seeded_bound_chat_session_msft.attached_report_id
    resp = test_client.post(
        "/reports/generate",
        json={
            "source_session_id": src_id,
            "department_id": "equity_research",
            "mode": "stock_initiation",
            "user_input": "msft",  # same ticker, different case
        },
    )
    assert resp.status_code == 200
    assert resp.json()["redirect"] is False
    sess = test_client.get(f"/chat/sessions/{src_id}")
    new_attached = sess.json()["attached_report_id"]
    assert new_attached != original_attached  # re-anchored to new report
    assert new_attached == resp.json()["report_id"]


def test_different_ticker_in_bound_chat_spawns_new_thread(
    monkeypatch: pytest.MonkeyPatch,
    test_client: TestClient,
    seeded_bound_chat_session_msft,
) -> None:
    monkeypatch.setenv("OPENLIA_REVISION_PASS_ENABLED", "1")
    src_id = seeded_bound_chat_session_msft.id
    original_attached = seeded_bound_chat_session_msft.attached_report_id
    resp = test_client.post(
        "/reports/generate",
        json={
            "source_session_id": src_id,
            "department_id": "equity_research",
            "mode": "stock_initiation",
            "user_input": "AAPL",  # different ticker
        },
    )
    assert resp.status_code == 200
    assert resp.json()["redirect"] is True
    assert resp.json()["session_id"] != src_id
    # Source session attached_report_id unchanged (strict).
    sess = test_client.get(f"/chat/sessions/{src_id}")
    assert sess.json()["attached_report_id"] == original_attached


def test_flag_off_preserves_strict_immutability(
    monkeypatch: pytest.MonkeyPatch,
    test_client: TestClient,
    seeded_bound_chat_session_msft,
) -> None:
    monkeypatch.delenv("OPENLIA_REVISION_PASS_ENABLED", raising=False)
    src_id = seeded_bound_chat_session_msft.id
    resp = test_client.post(
        "/reports/generate",
        json={
            "source_session_id": src_id,
            "department_id": "equity_research",
            "mode": "stock_initiation",
            "user_input": "msft",  # same ticker
        },
    )
    # When flag is off, chat-followup §4's original "immutable" rule applies
    # and same-ticker still spawns a new thread.
    assert resp.json()["redirect"] is True
