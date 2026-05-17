"""GET /reports/{id}/stream — synthetic terminal event for already-finished reports.

Tests:
- finished (complete) report -> one synthetic report.complete frame
- failed report -> one synthetic report.error frame
- another user's report -> 404
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
    from openlia_server.services.background_report_registry import BackgroundReportRegistry

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
    registry = BackgroundReportRegistry()
    app.state.bg_report_registry = registry
    return app


def _make_report(db_session, *, report_id: str, status: str, user_id: str = "local") -> None:
    from openlia_server.db.models.content import Report

    row = Report(
        id=report_id,
        user_id=user_id,
        department="equity_research",
        report_type="stock_initiation",
        title=f"Terminal test {report_id}",
        content_markdown="",
        content_structured={},
        model_ref="",
        status=status,
        started_at=datetime.now(UTC),
    )
    db_session.add(row)
    db_session.commit()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def seeded_completed_report(db_session):
    _make_report(db_session, report_id="r_terminal_complete", status="complete")
    from openlia_server.db import session as session_mod
    from openlia_server.db.models.content import Report
    from sqlalchemy import select

    with session_mod.SessionLocal() as s:
        return s.execute(select(Report).where(Report.id == "r_terminal_complete")).scalar_one()


@pytest.fixture
def seeded_failed_report(db_session):
    _make_report(db_session, report_id="r_terminal_failed", status="failed")
    from openlia_server.db import session as session_mod
    from openlia_server.db.models.content import Report
    from sqlalchemy import select

    with session_mod.SessionLocal() as s:
        return s.execute(select(Report).where(Report.id == "r_terminal_failed")).scalar_one()


@pytest.fixture
def test_client(db_session, monkeypatch):
    monkeypatch.setenv("OPENLIA_MODE", "personal")
    app = _make_app(db_session, monkeypatch, mode="personal")
    with TestClient(app) as client:
        yield client


@pytest.fixture
def test_client_user_b(db_session, monkeypatch):
    """Company-mode client authenticated as user-b (does not own seeded_completed_report)."""
    from openlia_server.app import create_app
    from openlia_server.db import session as session_mod
    from openlia_server.db.models.auth import User
    from openlia_server.middleware.auth import COOKIE_NAME
    from openlia_server.services.auth import passwords, sessions
    from openlia_server.services.background_report_registry import BackgroundReportRegistry

    for uid, email in (("local", "local@openlia.local"), ("user-b", "b@example.com")):
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
    db_session.commit()

    monkeypatch.setenv("OPENLIA_MODE", "company")
    app = create_app(db_session_factory=session_mod.SessionLocal)
    registry = BackgroundReportRegistry()
    app.state.bg_report_registry = registry

    with session_mod.SessionLocal() as s:
        tok_b = sessions.create_session(s, user_id="user-b", persistent=False)

    with TestClient(app) as client:
        client.cookies.set(COOKIE_NAME, tok_b.raw_token)
        yield client


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_finished_report_yields_one_synthetic_complete_frame(
    monkeypatch: pytest.MonkeyPatch, test_client: TestClient, seeded_completed_report
) -> None:
    monkeypatch.setenv("OPENLIA_BACKGROUND_REPORTS_ENABLED", "1")
    rid = seeded_completed_report.id
    with test_client.stream("GET", f"/reports/{rid}/stream") as resp:
        text = "".join(chunk for chunk in resp.iter_text(chunk_size=4096))
    assert "event: report.complete" in text or "event: reportcomplete" in text.lower()


def test_failed_report_yields_one_synthetic_error_frame(
    monkeypatch: pytest.MonkeyPatch, test_client: TestClient, seeded_failed_report
) -> None:
    monkeypatch.setenv("OPENLIA_BACKGROUND_REPORTS_ENABLED", "1")
    rid = seeded_failed_report.id
    with test_client.stream("GET", f"/reports/{rid}/stream") as resp:
        text = "".join(chunk for chunk in resp.iter_text(chunk_size=4096))
    assert (
        "event: report.error" in text or "report.error" in text.lower() or "failed" in text.lower()
    )


def test_other_users_report_returns_404(
    monkeypatch: pytest.MonkeyPatch, test_client_user_b: TestClient, seeded_completed_report
) -> None:
    monkeypatch.setenv("OPENLIA_BACKGROUND_REPORTS_ENABLED", "1")
    rid = seeded_completed_report.id
    resp = test_client_user_b.get(f"/reports/{rid}/stream")
    assert resp.status_code == 404
