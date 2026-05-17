"""GET /reports — list endpoint exposes status field on each row.

Task 11: verify that the reports list includes `status`, `failure_reason`,
`original_request`, and `started_at` for each report.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

# ---------------------------------------------------------------------------
# App + client fixture
# ---------------------------------------------------------------------------


@pytest.fixture
def _personal_app(db_session, monkeypatch):
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
    return create_app(db_session_factory=session_mod.SessionLocal)


@pytest.fixture
def test_client(_personal_app) -> TestClient:
    with TestClient(_personal_app) as c:
        yield c


# ---------------------------------------------------------------------------
# Seed fixture
# ---------------------------------------------------------------------------


def _make_report(db_session, *, report_id: str, status: str) -> None:
    from openlia_server.db.models.content import Report

    row = Report(
        id=report_id,
        user_id="local",
        department="equity_research",
        report_type="stock_initiation",
        title=f"Status test {status}",
        content_markdown="",
        content_structured={},
        model_ref="",
        status=status,
        original_request={
            "department_id": "equity_research",
            "mode": "stock_initiation",
            "user_input": "AAPL",
            "enabled_sections": [],
            "length": "standard",
        },
        started_at=datetime.now(UTC),
    )
    db_session.add(row)


@pytest.fixture
def seeded_reports_of_each_status(db_session):
    """Insert one report per status value into the DB."""
    for s in ("generating", "complete", "failed", "cancelled"):
        _make_report(db_session, report_id=f"r_status_{s}", status=s)
    db_session.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_list_returns_status_for_each_report(
    test_client: TestClient, seeded_reports_of_each_status
) -> None:
    resp = test_client.get("/reports")
    assert resp.status_code == 200
    rows = resp.json()["items"]
    statuses = {r["status"] for r in rows}
    assert {"generating", "complete", "failed", "cancelled"}.issubset(statuses)


def test_list_returns_failure_reason(
    test_client: TestClient, seeded_reports_of_each_status
) -> None:
    resp = test_client.get("/reports")
    assert resp.status_code == 200
    rows = resp.json()["items"]
    assert all("failure_reason" in r for r in rows)


def test_list_returns_original_request(
    test_client: TestClient, seeded_reports_of_each_status
) -> None:
    resp = test_client.get("/reports")
    assert resp.status_code == 200
    rows = resp.json()["items"]
    assert all("original_request" in r for r in rows)


def test_list_returns_started_at(test_client: TestClient, seeded_reports_of_each_status) -> None:
    resp = test_client.get("/reports")
    assert resp.status_code == 200
    rows = resp.json()["items"]
    assert all("started_at" in r for r in rows)
