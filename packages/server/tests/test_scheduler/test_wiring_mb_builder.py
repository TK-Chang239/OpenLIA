from __future__ import annotations

from _scheduler_fakes import FakeAPScheduler, FakeBatchRunner, FakeReportRunner
from openlia_server.scheduler.executors.mb import MBBriefingExecutor
from openlia_server.scheduler.registry import JobType
from openlia_server.scheduler.settings import SchedulerSettings
from openlia_server.scheduler.wiring import build_scheduler_service
from openlia_server.services.mb_request_builder import MbRequestBuilderImpl


def test_wiring_accepts_real_mb_builder(session_factory) -> None:
    builder = MbRequestBuilderImpl()
    svc = build_scheduler_service(
        session_factory=session_factory,
        settings=SchedulerSettings(enabled=True),
        scheduler=FakeAPScheduler(),
        report_runner=FakeReportRunner(events=[]),
        batch_runner=FakeBatchRunner(results=[]),
        mb_builder=builder,
    )
    mb_exec = svc.executors[JobType.MB_BRIEFING]
    assert isinstance(mb_exec, MBBriefingExecutor)
    assert mb_exec._mb_builder is builder
