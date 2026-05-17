"""POST /reports/{report_id}/retry creates a new generation from
original_request (Task 10).

Tests:
- retry on a failed report returns 200, new report_id, original row stays failed,
  new row is generating with same original_request.
- retry on a non-failed report returns 400/409.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_app(db_session, monkeypatch, *, mode: str = "personal"):
    from openlia_server.app import create_app
    from openlia_server.db import session as session_mod
    from openlia_server.db.models.auth import User

    if mode == "personal":
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

    monkeypatch.setenv("OPENLIA_MODE", mode)
    app = create_app(db_session_factory=session_mod.SessionLocal)
    return app


def _make_report(
    db_session,
    *,
    report_id: str,
    user_id: str = "local",
    status: str,
    original_request: dict | None = None,
):
    from openlia_server.db.models.content import Report

    row = Report(
        id=report_id,
        user_id=user_id,
        department="equity_research",
        report_type="stock_initiation",
        title=f"Report {report_id}",
        content_markdown="",
        content_structured={},
        model_ref="",
        status=status,
        original_request=original_request,
        started_at=datetime.now(UTC),
    )
    db_session.add(row)
    db_session.commit()
    return row


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def seeded_failed_report(db_session):
    return _make_report(
        db_session,
        report_id="r_retry_failed_1",
        status="failed",
        original_request={
            "department_id": "equity_research",
            "mode": "stock_initiation",
            "user_input": "AAPL",
            "enabled_sections": [],
            "length": "standard",
            "source_session_id": None,
        },
    )


@pytest.fixture
def seeded_completed_report(db_session):
    return _make_report(
        db_session,
        report_id="r_retry_complete_1",
        status="complete",
        original_request={
            "department_id": "equity_research",
            "mode": "stock_initiation",
            "user_input": "MSFT",
            "enabled_sections": [],
            "length": "standard",
            "source_session_id": None,
        },
    )


@pytest.fixture
def test_client(db_session, monkeypatch):
    monkeypatch.setenv("OPENLIA_MODE", "personal")
    app = _make_app(db_session, monkeypatch, mode="personal")
    with TestClient(app) as client:
        yield client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_retry_creates_new_generation_with_original_request(
    monkeypatch: pytest.MonkeyPatch, test_client: TestClient, seeded_failed_report
) -> None:
    monkeypatch.setenv("OPENLIA_BACKGROUND_REPORTS_ENABLED", "1")
    failed_id = seeded_failed_report.id
    resp = test_client.post(f"/reports/{failed_id}/retry")
    assert resp.status_code == 200
    new_id = resp.json()["report_id"]
    assert new_id != failed_id
    # Original row retained for audit.
    old = test_client.get(f"/reports/{failed_id}")
    assert old.json()["status"] == "failed"
    # New row exists with status generating + same original_request.
    new = test_client.get(f"/reports/{new_id}")
    assert new.json()["status"] == "generating"
    assert new.json()["original_request"] == seeded_failed_report.original_request


def test_retry_404_for_non_failed_report(
    monkeypatch: pytest.MonkeyPatch, test_client: TestClient, seeded_completed_report
) -> None:
    monkeypatch.setenv("OPENLIA_BACKGROUND_REPORTS_ENABLED", "1")
    rid = seeded_completed_report.id
    resp = test_client.post(f"/reports/{rid}/retry")
    # Only failed/cancelled rows can be retried.
    assert resp.status_code in (400, 409)
