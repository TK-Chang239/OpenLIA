from __future__ import annotations

from _scheduler_fakes import (
    FakeAPScheduler,
    FakeBatchRunner,
    FakeMRBuilder,
    FakeMRCacheStore,
    FakeReportRunner,
    FakeReportStore,
    StubEUScanPlanner,
)
from openlia.llm.runtime.messages import ReportRequest
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
        eu_planner=StubEUScanPlanner(),
        mr_builder=FakeMRBuilder(
            items=[], synth=ReportRequest(mode="mr_synthesis", user_input="x")
        ),
        report_store=FakeReportStore(),
        mr_cache_store=FakeMRCacheStore(),
    )
    # MB rework Phase 3: the MB executor no longer consumes the legacy
    # mb_builder; build_scheduler_service still accepts it (the EU executor +
    # app wiring depend on the shared signature) but the MB executor runs the
    # report_mb engine inline via its module-default run-service collaborator.
    mb_exec = svc.executors[JobType.MB_BRIEFING]
    assert isinstance(mb_exec, MBBriefingExecutor)
    from openlia_server.services import mb_v2_run_service

    assert mb_exec._run_service is mb_v2_run_service
