"""Regression guard that build_scheduler_service accepts a real
EuScanPlannerImpl as the `eu_planner` argument."""

from __future__ import annotations

from _scheduler_fakes import (
    FakeAPScheduler,
    FakeBatchRunner,
    FakeMBBuilder,
    FakeMRBuilder,
    FakeMRCacheStore,
    FakeReportRunner,
    FakeReportStore,
)
from openlia.llm.runtime.messages import ReportRequest
from openlia_server.scheduler.settings import SchedulerSettings
from openlia_server.scheduler.wiring import build_scheduler_service
from openlia_server.services.eu_scan_planner import EuScanPlannerImpl


class _NoopAdapter:
    def latest_release(self, ticker, *, since):
        return None


def test_wiring_accepts_real_eu_planner(session_factory) -> None:
    planner = EuScanPlannerImpl(adapter=_NoopAdapter())
    svc = build_scheduler_service(
        session_factory=session_factory,
        settings=SchedulerSettings(enabled=True),
        scheduler=FakeAPScheduler(),
        report_runner=FakeReportRunner(events=[]),
        batch_runner=FakeBatchRunner(results=[]),
        mb_builder=FakeMBBuilder(request=ReportRequest(mode="stock_update", user_input="x")),
        eu_planner=planner,
        mr_builder=FakeMRBuilder(
            items=[], synth=ReportRequest(mode="mr_synthesis", user_input="x")
        ),
        report_store=FakeReportStore(),
        mr_cache_store=FakeMRCacheStore(),
    )
    assert svc is not None
