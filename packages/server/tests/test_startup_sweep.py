from __future__ import annotations

from datetime import UTC, datetime

import pytest
from openlia_server.db.models.auth import User
from openlia_server.db.models.content import Report


@pytest.fixture
def seeded_user(db_session):
    now = datetime.now(UTC)
    user = User(
        id="u-sweep-1",
        email="sweep@test.example",
        display_name="sweep",
        password_hash=None,
        is_admin=False,
        is_disabled=False,
        created_at=now,
        updated_at=now,
    )
    db_session.add(user)
    db_session.commit()
    return db_session.get(User, "u-sweep-1")


def _make_report(session, *, report_id: str, user_id: str, status: str) -> Report:
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
    )
    session.add(row)
    session.commit()
    return row


def test_startup_sweep_marks_orphans_failed(db_session_factory, seeded_user) -> None:
    from openlia_server.app import sweep_orphaned_generating_reports

    with db_session_factory() as session:
        _make_report(session, report_id="r_orphan", user_id=seeded_user.id, status="generating")
    sweep_orphaned_generating_reports(db_session_factory)
    with db_session_factory() as session:
        row = session.get(Report, "r_orphan")
        assert row.status == "failed"
        assert row.failure_reason == "server_restart_interrupted"


def test_startup_sweep_leaves_complete_rows_alone(db_session_factory, seeded_user) -> None:
    from openlia_server.app import sweep_orphaned_generating_reports

    with db_session_factory() as session:
        _make_report(session, report_id="r_done", user_id=seeded_user.id, status="complete")
    sweep_orphaned_generating_reports(db_session_factory)
    with db_session_factory() as session:
        row = session.get(Report, "r_done")
        assert row.status == "complete"
