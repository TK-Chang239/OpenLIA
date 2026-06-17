"""Phase 1b — insert/update mr_dashboard_state with the schedule columns."""

from __future__ import annotations

from datetime import UTC, datetime

from openlia_server.db.models.auth import User
from openlia_server.db.models.dashboard import MrDashboardState
from sqlalchemy.orm import Session


def test_insert_row_with_schedule_columns(create_tables, db_session: Session) -> None:
    db_session.add(User(id="u-sch", email="sch@example.com", display_name="Sch"))
    db_session.flush()

    now = datetime.now(UTC)
    row = MrDashboardState(
        id="mrs-1",
        user_id="u-sch",
        dashboard="debt_cycle",
        assessment_schedule="0 0 * * 0",
        last_assessment_at=now,
    )
    db_session.add(row)
    db_session.commit()
    db_session.expire_all()

    reloaded = db_session.get(MrDashboardState, "mrs-1")
    assert reloaded is not None
    assert reloaded.assessment_schedule == "0 0 * * 0"
    assert reloaded.last_assessment_at is not None


def test_schedule_columns_nullable(create_tables, db_session: Session) -> None:
    db_session.add(User(id="u-null", email="null@example.com", display_name="Null"))
    db_session.flush()

    row = MrDashboardState(
        id="mrs-2",
        user_id="u-null",
        dashboard="four_seasons",
    )
    db_session.add(row)
    db_session.commit()
    db_session.expire_all()

    reloaded = db_session.get(MrDashboardState, "mrs-2")
    assert reloaded is not None
    assert reloaded.assessment_schedule is None
    assert reloaded.last_assessment_at is None
