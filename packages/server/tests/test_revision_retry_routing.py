# packages/server/tests/test_revision_retry_routing.py
"""When the failed report's original_request.kind == 'revision', the
Retry button POSTs to /revise (with the persisted source_report_id and
revision_brief) instead of /generate."""

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
def seeded_failed_revision_report(db_session):
    """A failed report whose original_request carries kind='revision'.

    Also seeds the source report and a chat session bound to that source
    report, so the /revise re-route can satisfy its ownership + binding checks.
    """
    from openlia_server.db.models.content import ChatSession, Report

    source_id = f"r_{uuid.uuid4().hex[:12]}"
    source = Report(
        id=source_id,
        user_id="local",
        department="equity_research",
        report_type="stock_initiation",
        title="Source Report",
        content_markdown="# Source",
        content_structured={"cover": {"title": "Source"}, "sections": []},
        model_ref="gpt-4",
        status="complete",
    )
    db_session.add(source)
    db_session.flush()

    session_id = str(uuid.uuid4())
    chat = ChatSession(
        id=session_id,
        user_id="local",
        department="equity_research",
        title="Bound chat",
        attached_report_id=source_id,
    )
    db_session.add(chat)
    db_session.flush()

    failed_id = f"r_{uuid.uuid4().hex[:12]}"
    failed = Report(
        id=failed_id,
        user_id="local",
        department="equity_research",
        report_type="stock_initiation",
        title="Failed Revision",
        content_markdown="",
        content_structured={},
        model_ref="",
        status="failed",
        started_at=datetime.now(UTC),
        original_request={
            "kind": "revision",
            "source_report_id": source_id,
            "chat_session_id": session_id,
            "revision_brief": "Fix Q4 capex",
            "sections_to_focus": None,
        },
    )
    db_session.add(failed)
    db_session.commit()
    return failed


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_retry_for_revision_kind_uses_revise_endpoint(
    monkeypatch: pytest.MonkeyPatch,
    test_client: TestClient,
    seeded_failed_revision_report,
) -> None:
    monkeypatch.setenv("OPENLIA_REVISION_PASS_ENABLED", "1")
    failed_id = seeded_failed_revision_report.id
    resp = test_client.post(f"/reports/{failed_id}/retry")
    assert resp.status_code == 200
    body = resp.json()
    # New report exists in generating status.
    new = test_client.get(f"/reports/{body['report_id']}")
    new_body = new.json()
    assert new_body["status"] == "generating"
    assert new_body["original_request"]["kind"] == "revision"
    assert (
        new_body["original_request"]["source_report_id"]
        == seeded_failed_revision_report.original_request["source_report_id"]
    )
