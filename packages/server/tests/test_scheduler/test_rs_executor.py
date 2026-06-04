"""Tests for RSSnapshotExecutor — repointed to report_dash_rs engine.

Covers:
  - scheduled fan-out: one run_to_cache call per watchlist ticker.
  - manual single-ticker refresh: one call for exactly that ticker.
  - ASSESSMENT_READY notification emitted in both cases.
"""

from __future__ import annotations

import pytest
from openlia_server.db.models.auth import User
from openlia_server.db.models.departments import EuWatchlistEntry
from openlia_server.db.models.scheduler import JobRun, RsSchedule, UserNotification
from openlia_server.scheduler.executors.rs import RSSnapshotExecutor
from openlia_server.scheduler.registry import JobStatus, NotificationType
from sqlalchemy.orm import Session


def _seed(
    session: Session,
    *,
    tickers: tuple[str, ...] = ("AAPL", "MSFT"),
    schedule_id: str = "sched-rs-uuid",
) -> str:
    """Seed a user, watchlist entries, and an RS schedule. Returns schedule id."""
    session.add(
        User(
            id="u_1",
            email="u@e.com",
            display_name="u",
            password_hash="h",
            is_admin=False,
            is_disabled=False,
        )
    )
    for t in tickers:
        session.add(
            EuWatchlistEntry(
                id=f"w_{t}",
                user_id="u_1",
                ticker=t,
                company_name=f"{t} Inc",
            )
        )
    session.add(
        RsSchedule(
            id=schedule_id,
            user_id="u_1",
            time="08:00",
            timezone="UTC",
            days_of_week='["mon","tue","wed","thu","fri"]',
            label="Daily RS",
            is_enabled=True,
        )
    )
    session.commit()
    return schedule_id


def _make_executor(session_factory, monkeypatch) -> tuple[RSSnapshotExecutor, list[dict]]:
    """Build executor with run_to_cache stubbed; return (executor, call_log)."""
    from openlia_server.scheduler.executors import rs as rs_module

    call_log: list[dict] = []

    async def _fake_run_to_cache(db, *, user_id: str, ticker: str, **kwargs) -> str:
        call_log.append({"user_id": user_id, "ticker": ticker})
        return ticker

    monkeypatch.setattr(rs_module.rs_dash_run_service, "run_to_cache", _fake_run_to_cache)

    ex = RSSnapshotExecutor(session_factory=session_factory)
    return ex, call_log


@pytest.mark.asyncio
async def test_rs_executor_scheduled_fanout(session_factory, monkeypatch) -> None:
    """Scheduled fire fans out to all watchlist tickers."""
    sched_id = "sched-rs-uuid"
    with session_factory() as s:
        _seed(s, schedule_id=sched_id)

    ex, call_log = _make_executor(session_factory, monkeypatch)

    run_id = await ex.execute(user_id="u_1", schedule_id=sched_id)

    # Both watchlist tickers processed.
    assert len(call_log) == 2
    tickers_called = {c["ticker"] for c in call_log}
    assert tickers_called == {"AAPL", "MSFT"}

    with session_factory() as s:
        row = s.get(JobRun, run_id)
        assert row.status == JobStatus.COMPLETED.value
        assert row.user_id == "u_1"

        notifs = s.query(UserNotification).all()
        assert len(notifs) == 1
        assert notifs[0].type == NotificationType.ASSESSMENT_READY.value
        assert notifs[0].department == "retail_sentiment"
        assert "2 ticker" in notifs[0].message


@pytest.mark.asyncio
async def test_rs_executor_manual_single_ticker(session_factory, monkeypatch) -> None:
    """Manual refresh with schedule_id=ticker symbol targets only that ticker."""
    sched_id = "sched-rs-uuid"
    with session_factory() as s:
        _seed(s, schedule_id=sched_id)

    ex, call_log = _make_executor(session_factory, monkeypatch)

    # "AAPL" is a ticker symbol, not the schedule uuid — triggers single-ticker path.
    run_id = await ex.execute(user_id="u_1", schedule_id="AAPL")

    assert len(call_log) == 1
    assert call_log[0]["ticker"] == "AAPL"

    with session_factory() as s:
        row = s.get(JobRun, run_id)
        assert row.status == JobStatus.COMPLETED.value

        notifs = s.query(UserNotification).all()
        assert len(notifs) == 1
        assert notifs[0].type == NotificationType.ASSESSMENT_READY.value
        assert "1 ticker" in notifs[0].message
