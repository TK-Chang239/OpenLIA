"""NEW-6-04 — When the user updates department config (e.g. adds a
ticker to the EU watchlist), the next scheduled fire must see the new
ticker. Today this works because EuScanPlanner reads the watchlist at
fire time; this test pins the invariant."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime

import pytest
from _scheduler_fakes import (
    FakeAPScheduler,
    FakeReportRunner,
    FakeReportStore,
)
from openlia.llm.runtime.events import ReportComplete
from openlia_server.db.models.auth import User
from openlia_server.db.models.departments import EuWatchlistEntry
from openlia_server.db.models.scheduler import EuSchedule
from openlia_server.scheduler.registry import JobType, job_key
from openlia_server.scheduler.settings import SchedulerSettings
from openlia_server.scheduler.wiring import build_scheduler_service
from openlia_server.services.eu_scan_planner import EuScanPlannerImpl


class _RecordingAdapter:
    """Always returns a release for any ticker — captures call list."""

    def __init__(self) -> None:
        self.queries: list[str] = []

    def latest_release(self, ticker: str, *, since: datetime | None) -> datetime | None:
        self.queries.append(ticker)
        return datetime.now(UTC)

    def next_earnings(self, ticker: str) -> dict | None:
        return {
            "ticker": ticker,
            "company_name": ticker,
            "date": None,
            "release_timing": None,
        }


@pytest.mark.asyncio
async def test_added_ticker_picked_up_on_next_fire(session_factory) -> None:
    with session_factory() as s:
        s.add(
            User(
                id="u_1",
                email="u@e.com",
                display_name="u",
                password_hash="h",
                is_admin=False,
                is_disabled=False,
            )
        )
        s.add(
            EuSchedule(
                id="sch_eu",
                user_id="u_1",
                time="16:30",
                timezone="UTC",
                days_of_week='["mon","tue","wed","thu","fri"]',
                label="Post-Market",
                is_enabled=True,
                created_at=datetime.now(UTC),
                last_run_at=None,
            )
        )
        # Initial watchlist: a single ticker.
        s.add(
            EuWatchlistEntry(
                id="w_1",
                user_id="u_1",
                ticker="AAPL",
                company_name="Apple",
            )
        )
        s.commit()

    adapter = _RecordingAdapter()
    planner = EuScanPlannerImpl(adapter=adapter)
    fake_scheduler = FakeAPScheduler()

    svc = build_scheduler_service(
        session_factory=session_factory,
        settings=SchedulerSettings(enabled=True),
        scheduler=fake_scheduler,
        report_runner=FakeReportRunner(
            events=[
                ReportComplete(
                    report_id="r_1",
                    schema={
                        "cover": {"title": "EU"},
                        "sections": [],
                        "report_type": "stock_update",
                        "generated_at": datetime.now(UTC).isoformat(),
                    },
                ),
            ]
        ),
        eu_planner=planner,
        report_store=FakeReportStore(),
    )
    await svc.start()

    # Add a new ticker AFTER the schedule was registered. The schedule
    # row didn't change — the contract under test is that the planner
    # reads the watchlist on every fire.
    with session_factory() as s:
        s.add(
            EuWatchlistEntry(
                id="w_2",
                user_id="u_1",
                ticker="MSFT",
                company_name="Microsoft",
            )
        )
        s.commit()

    key = job_key(JobType.EU_SCAN, "u_1")

    # Fire the schedule callback. Don't actually wait for the executor
    # to finish (the FakeReportStore happily returns), but give the
    # planner.plan() call a chance to land.
    try:
        await asyncio.wait_for(fake_scheduler.fire(key), timeout=5.0)
    except Exception:
        # We don't care about downstream failures from the fakes; the
        # only thing under test is that planner saw both tickers.
        pass

    assert "AAPL" in adapter.queries
    assert "MSFT" in adapter.queries
