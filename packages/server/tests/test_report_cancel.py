"""DELETE /reports/{id} cancels the background task (Task 9).

Tests:
- DELETE on a 'generating' report calls registry.cancel and marks it cancelled.
- DELETE from another user returns 404.
"""

from __future__ import annotations

import time
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
    return app, registry


def _make_running_report(db_session, *, report_id: str, user_id: str = "local"):
    from openlia_server.db.models.content import Report

    row = Report(
        id=report_id,
        user_id=user_id,
        department="equity_research",
        report_type="stock_initiation",
        title=f"Running report {report_id}",
        content_markdown="",
        content_structured={},
        model_ref="",
        status="generating",
        started_at=datetime.now(UTC),
    )
    db_session.add(row)
    db_session.commit()
    return row


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def seeded_running_report(db_session):
    return _make_running_report(db_session, report_id="r_cancel_test_1")


@pytest.fixture
def test_client(db_session, monkeypatch):
    monkeypatch.setenv("OPENLIA_MODE", "personal")
    app, registry = _make_app(db_session, monkeypatch, mode="personal")
    with TestClient(app) as client:
        client._registry = registry  # type: ignore[attr-defined]
        yield client


@pytest.fixture
def test_client_user_b(db_session, monkeypatch):
    """Company-mode client authenticated as user-b (does not own seeded_running_report)."""
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


def test_delete_cancels_running_task_and_marks_cancelled(
    monkeypatch: pytest.MonkeyPatch, test_client: TestClient, seeded_running_report
) -> None:
    monkeypatch.setenv("OPENLIA_BACKGROUND_REPORTS_ENABLED", "1")
    rid = seeded_running_report.id
    resp = test_client.delete(f"/reports/{rid}")
    assert resp.status_code == 200
    # Allow async cancellation to propagate.
    time.sleep(0.2)
    get_resp = test_client.get(f"/reports/{rid}")
    assert get_resp.json()["status"] == "cancelled"
    assert get_resp.json()["failure_reason"] in ("user_cancelled", "session_disconnected")


def test_delete_404_for_other_users_report(
    monkeypatch: pytest.MonkeyPatch, test_client_user_b: TestClient, seeded_running_report
) -> None:
    monkeypatch.setenv("OPENLIA_BACKGROUND_REPORTS_ENABLED", "1")
    rid = seeded_running_report.id
    resp = test_client_user_b.delete(f"/reports/{rid}")
    assert resp.status_code == 404
