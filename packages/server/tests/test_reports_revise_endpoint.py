# packages/server/tests/test_reports_revise_endpoint.py
from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# App + client fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def _personal_app(db_session, monkeypatch, tmp_path):
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
    bundle_dir = tmp_path / "bundles"
    bundle_dir.mkdir()
    monkeypatch.setenv("OPENLIA_REPORT_BUNDLE_DIR", str(bundle_dir))
    return create_app(db_session_factory=session_mod.SessionLocal)


@pytest.fixture
def test_client(_personal_app) -> TestClient:
    with TestClient(_personal_app) as c:
        yield c


# ---------------------------------------------------------------------------
# Seed fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def seeded_source_report(db_session) -> str:
    """A completed report owned by the local user. Returns the report id."""
    from openlia_server.db.models.content import Report

    report_id = f"r_{uuid.uuid4().hex[:12]}"
    r = Report(
        id=report_id,
        user_id="local",
        department="equity_research",
        report_type="stock_initiation",
        title="Source Report",
        content_markdown="# Source",
        content_structured={"cover": {"title": "Source"}, "sections": []},
        model_ref="gpt-4",
        status="complete",
    )
    db_session.add(r)
    db_session.commit()
    return report_id


@pytest.fixture
def seeded_chat_with_messages(db_session, seeded_source_report) -> str:
    """A chat session bound to the source report. Returns the session id."""
    from openlia_server.db.models.content import ChatMessage, ChatSession

    session_id = str(uuid.uuid4())
    sess = ChatSession(
        id=session_id,
        user_id="local",
        department="equity_research",
        title="Bound chat",
        attached_report_id=seeded_source_report,
    )
    db_session.add(sess)
    db_session.flush()

    msg = ChatMessage(
        id=str(uuid.uuid4()),
        session_id=session_id,
        role="user",
        content="Fix Q4 capex",
        created_at=datetime.now(UTC),
    )
    db_session.add(msg)
    db_session.commit()
    return session_id


@pytest.fixture
def seeded_unbound_chat(db_session):
    """A chat session NOT bound to any report."""
    from openlia_server.db.models.content import ChatSession

    sess = ChatSession(
        id=str(uuid.uuid4()),
        user_id="local",
        department="equity_research",
        title="Unbound chat",
    )
    db_session.add(sess)
    db_session.commit()
    return sess


# ---------------------------------------------------------------------------
# Body fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def revision_body(seeded_chat_with_messages, seeded_source_report) -> dict:
    return {
        "chat_session_id": seeded_chat_with_messages,
        "revision_brief": "Fix Q4 capex",
        "sections_to_focus": None,
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_revise_endpoint_returns_new_report_id_fast(
    monkeypatch: pytest.MonkeyPatch,
    test_client: TestClient,
    seeded_source_report: str,
    revision_body: dict,
) -> None:
    monkeypatch.setenv("OPENLIA_REVISION_PASS_ENABLED", "1")
    import time

    start = time.monotonic()
    resp = test_client.post(f"/reports/{seeded_source_report}/revise", json=revision_body)
    elapsed = time.monotonic() - start
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["status"] == "generating"
    assert body["report_id"].startswith("r_")
    assert elapsed < 2.0


def test_revise_endpoint_404_for_unknown_source(
    monkeypatch: pytest.MonkeyPatch,
    test_client: TestClient,
    seeded_chat_with_messages: str,
) -> None:
    monkeypatch.setenv("OPENLIA_REVISION_PASS_ENABLED", "1")
    resp = test_client.post(
        "/reports/r_unknown/revise",
        json={
            "chat_session_id": seeded_chat_with_messages,
            "revision_brief": "x",
            "sections_to_focus": None,
        },
    )
    assert resp.status_code == 404


def test_revise_endpoint_400_when_chat_not_bound_to_source(
    monkeypatch: pytest.MonkeyPatch,
    test_client: TestClient,
    seeded_source_report: str,
    seeded_unbound_chat,
) -> None:
    monkeypatch.setenv("OPENLIA_REVISION_PASS_ENABLED", "1")
    resp = test_client.post(
        f"/reports/{seeded_source_report}/revise",
        json={
            "chat_session_id": seeded_unbound_chat.id,
            "revision_brief": "x",
            "sections_to_focus": None,
        },
    )
    assert resp.status_code == 400


def test_revise_endpoint_rejects_when_flag_off(
    monkeypatch: pytest.MonkeyPatch,
    test_client: TestClient,
    seeded_source_report: str,
    revision_body: dict,
) -> None:
    monkeypatch.delenv("OPENLIA_REVISION_PASS_ENABLED", raising=False)
    resp = test_client.post(f"/reports/{seeded_source_report}/revise", json=revision_body)
    assert resp.status_code in (403, 404, 503)
