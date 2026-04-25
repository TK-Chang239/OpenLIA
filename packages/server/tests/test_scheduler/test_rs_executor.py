"""Tests for RSSnapshotExecutor — JobRun + UserNotification wiring.

Covers:
  - happy path: writes JobRun.completed and one assessment_ready notif.
  - empty watchlist: returns 0 snapshots, JobRun still completes.
  - idempotent under repeat fire (two executions → two JobRun rows).
"""

from __future__ import annotations

from collections.abc import Sequence

import pytest
from openlia_server.db.models.auth import User
from openlia_server.db.models.departments import EuWatchlistEntry
from openlia_server.db.models.scheduler import JobRun, UserNotification
from openlia_server.scheduler.executors.rs import RSSnapshotExecutor
from openlia_server.scheduler.registry import JobStatus, NotificationType
from sqlalchemy.orm import Session


class _FakeRsRunner:
    def __init__(self) -> None:
        self.calls: list[Sequence[str]] = []

    def run_many(self, tickers: Sequence[str]) -> list[dict]:
        self.calls.append(tuple(tickers))
        return [{"ticker": t} for t in tickers]


def _seed(session: Session, *, tickers: Sequence[str] = ("AAPL", "MSFT")) -> None:
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
    session.commit()


@pytest.mark.asyncio
async def test_rs_executor_writes_job_run_and_notification(session_factory) -> None:
    with session_factory() as s:
        _seed(s)

    runner = _FakeRsRunner()
    ex = RSSnapshotExecutor(session_factory=session_factory, rs_runner=runner)

    run_id = await ex.execute(user_id="u_1", schedule_id="sch_rs")

    with session_factory() as s:
        row = s.get(JobRun, run_id)
        assert row.status == JobStatus.COMPLETED.value
        assert row.user_id == "u_1"
        notifs = s.query(UserNotification).all()
        assert len(notifs) == 1
        assert notifs[0].type == NotificationType.ASSESSMENT_READY.value
        assert notifs[0].department == "retail_sentiment"
        assert "2 tickers" in notifs[0].message

    assert runner.calls == [("AAPL", "MSFT")]


@pytest.mark.asyncio
async def test_rs_executor_handles_empty_watchlist(session_factory) -> None:
    with session_factory() as s:
        _seed(s, tickers=())

    runner = _FakeRsRunner()
    ex = RSSnapshotExecutor(session_factory=session_factory, rs_runner=runner)

    run_id = await ex.execute(user_id="u_1", schedule_id="sch_rs")

    with session_factory() as s:
        row = s.get(JobRun, run_id)
        assert row.status == JobStatus.COMPLETED.value

    assert runner.calls == []


@pytest.mark.asyncio
async def test_rs_executor_is_idempotent_under_repeat_fire(session_factory) -> None:
    with session_factory() as s:
        _seed(s)

    runner = _FakeRsRunner()
    ex = RSSnapshotExecutor(session_factory=session_factory, rs_runner=runner)

    run_id_a = await ex.execute(user_id="u_1", schedule_id="sch_rs")
    run_id_b = await ex.execute(user_id="u_1", schedule_id="sch_rs")

    assert run_id_a != run_id_b
    with session_factory() as s:
        rows = s.query(JobRun).filter_by(user_id="u_1").all()
        assert len(rows) == 2
        assert all(r.status == JobStatus.COMPLETED.value for r in rows)
    # runner ran for each fire
    assert runner.calls == [("AAPL", "MSFT"), ("AAPL", "MSFT")]
