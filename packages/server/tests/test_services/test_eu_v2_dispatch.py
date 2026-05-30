# packages/server/tests/test_services/test_eu_v2_dispatch.py
import uuid
from datetime import UTC, datetime

from openlia_server.db.models.report_eu import EuV2EarningsSchedule
from openlia_server.services.eu_v2_dispatch import (
    mark_failed,
    mark_reported,
    select_due_rows,
)


def seed_schedule(
    db,
    user_id: str,
    ticker: str,
    fiscal_date: str,
    *,
    run_at: datetime,
    status: str = "pending",
) -> EuV2EarningsSchedule:
    now = datetime.now(UTC)
    row = EuV2EarningsSchedule(
        id=str(uuid.uuid4()),
        user_id=user_id,
        ticker=ticker,
        fiscal_date=fiscal_date,
        release_timing="post_market",
        eps_estimate=None,
        revenue_estimate=None,
        scheduled_run_at=run_at,
        status=status,
        attempts=0,
        report_id=None,
        synced_at=now,
        created_at=now,
    )
    db.add(row)
    db.commit()
    return row


def test_select_due_returns_only_past_pending(db_session):
    seed_schedule(
        db_session,
        "u-1",
        "MSFT.US",
        "2026-06-15",
        run_at=datetime(2026, 6, 15, 23, tzinfo=UTC),
    )
    seed_schedule(
        db_session,
        "u-1",
        "AAPL.US",
        "2026-07-30",
        run_at=datetime(2026, 7, 30, 23, tzinfo=UTC),
    )
    due = select_due_rows(db_session, now=datetime(2026, 6, 16, tzinfo=UTC))
    assert [r.ticker for r in due] == ["MSFT.US"]


def test_select_due_orders_by_run_at(db_session):
    seed_schedule(db_session, "u-1", "B.US", "2026-06-15", run_at=datetime(2026, 6, 15, tzinfo=UTC))
    seed_schedule(db_session, "u-1", "A.US", "2026-06-10", run_at=datetime(2026, 6, 10, tzinfo=UTC))
    due = select_due_rows(db_session, now=datetime(2026, 6, 20, tzinfo=UTC))
    assert [r.ticker for r in due] == ["A.US", "B.US"]


def test_mark_reported_sets_status_and_report_id(db_session):
    row = seed_schedule(
        db_session,
        "u-1",
        "MSFT.US",
        "2026-06-15",
        run_at=datetime(2026, 6, 15, 23, tzinfo=UTC),
    )
    mark_reported(db_session, row_id=row.id, report_id="r123")
    db_session.refresh(row)
    assert row.status == "reported"
    assert row.report_id == "r123"


def test_mark_failed_keeps_pending_before_max(db_session):
    row = seed_schedule(
        db_session,
        "u-1",
        "MSFT.US",
        "2026-06-15",
        run_at=datetime(2026, 6, 15, 23, tzinfo=UTC),
    )
    mark_failed(db_session, row_id=row.id, max_attempts=3)
    db_session.refresh(row)
    assert row.status == "pending"
    assert row.attempts == 1


def test_mark_failed_skips_after_max_attempts(db_session):
    row = seed_schedule(
        db_session,
        "u-1",
        "MSFT.US",
        "2026-06-15",
        run_at=datetime(2026, 6, 15, 23, tzinfo=UTC),
    )
    for _ in range(3):
        mark_failed(db_session, row_id=row.id, max_attempts=3)
    db_session.refresh(row)
    assert row.status == "skipped"
    assert row.attempts == 3
