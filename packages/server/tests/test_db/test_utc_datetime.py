"""UTCDateTime TypeDecorator round-trip tests (Phase 1a P0-1a-02)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

from openlia_server.db.models.auth import User
from openlia_server.db.models.dashboard import MrDashboardState
from openlia_server.db.models.infrastructure import ConfigStore
from sqlalchemy.orm import Session


def _make_mr_row(db_session: Session, *, last_assessment_at: datetime | None) -> MrDashboardState:
    db_session.add(User(id="u-utc", email="utc@example.com", display_name="U"))
    db_session.flush()
    row = MrDashboardState(
        id="mr-utc",
        user_id="u-utc",
        dashboard="debt_cycle",
        view_config={},
        threshold_overrides={},
        last_assessment_at=last_assessment_at,
    )
    db_session.add(row)
    db_session.commit()
    db_session.expire_all()
    return row


def test_utc_datetime_round_trip_preserves_utc(create_tables, db_session: Session) -> None:
    aware_utc = datetime(2026, 4, 24, 18, 30, 0, tzinfo=UTC)
    _make_mr_row(db_session, last_assessment_at=aware_utc)

    reloaded = db_session.get(MrDashboardState, "mr-utc")
    assert reloaded is not None
    assert reloaded.last_assessment_at == aware_utc
    assert reloaded.last_assessment_at.tzinfo is not None
    assert reloaded.last_assessment_at.utcoffset() == timedelta(0)


def test_utc_datetime_converts_non_utc_aware_to_utc(create_tables, db_session: Session) -> None:
    pacific = timezone(timedelta(hours=-7))
    aware_pst = datetime(2026, 4, 24, 11, 30, 0, tzinfo=pacific)
    _make_mr_row(db_session, last_assessment_at=aware_pst)

    reloaded = db_session.get(MrDashboardState, "mr-utc")
    assert reloaded is not None
    assert reloaded.last_assessment_at == aware_pst
    assert reloaded.last_assessment_at.utcoffset() == timedelta(0)


def test_utc_datetime_naive_input_read_as_utc(create_tables, db_session: Session) -> None:
    naive = datetime(2026, 4, 24, 18, 30, 0)
    _make_mr_row(db_session, last_assessment_at=naive)

    reloaded = db_session.get(MrDashboardState, "mr-utc")
    assert reloaded is not None
    assert reloaded.last_assessment_at is not None
    assert reloaded.last_assessment_at.utcoffset() == timedelta(0)


def test_utc_datetime_handles_none(create_tables, db_session: Session) -> None:
    _make_mr_row(db_session, last_assessment_at=None)

    reloaded = db_session.get(MrDashboardState, "mr-utc")
    assert reloaded is not None
    assert reloaded.last_assessment_at is None


def test_config_store_updated_at_has_utc_offset(create_tables, db_session: Session) -> None:
    row = ConfigStore(key="test.key", value="test-value")
    db_session.add(row)
    db_session.commit()
    db_session.expire_all()

    reloaded = db_session.get(ConfigStore, "test.key")
    assert reloaded is not None
    assert reloaded.updated_at is not None
    assert reloaded.updated_at.utcoffset() == timedelta(0)
