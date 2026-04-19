"""Construct the SchedulerService executor graph.

Each Plan that ships a real department builder will update this module
to inject its real implementation. Until then, stubs raise
DepartmentPayloadBuilderNotWired when fired — which the executor logs
as a failed job_runs row but does NOT treat as a crash."""
from __future__ import annotations

from typing import Any

from openlia_server.scheduler.executors.base import SessionFactory
from openlia_server.scheduler.executors.eu import EUScanExecutor
from openlia_server.scheduler.executors.maintenance import MaintenanceExecutor
from openlia_server.scheduler.executors.mb import MBBriefingExecutor
from openlia_server.scheduler.executors.mr import MRAssessmentExecutor
from openlia_server.scheduler.payloads import (
    EUScanPlanner,
    MBRequestBuilder,
    MRAssessmentBuilder,
    MRCacheStore,
    ReportStore,
    StubEUScanPlanner,
    StubMBRequestBuilder,
    StubMRAssessmentBuilder,
    StubMRCacheStore,
    StubReportStore,
)
from openlia_server.scheduler.registry import JobType
from openlia_server.scheduler.service import SchedulerService
from openlia_server.scheduler.settings import SchedulerSettings


def build_scheduler_service(
    *,
    session_factory: SessionFactory,
    settings: SchedulerSettings,
    scheduler: Any,
    report_runner: Any,
    batch_runner: Any,
    mb_builder: MBRequestBuilder | None = None,
    eu_planner: EUScanPlanner | None = None,
    mr_builder: MRAssessmentBuilder | None = None,
    report_store: ReportStore | None = None,
    mr_cache_store: MRCacheStore | None = None,
) -> SchedulerService:
    mb_builder = mb_builder or StubMBRequestBuilder()
    eu_planner = eu_planner or StubEUScanPlanner()
    mr_builder = mr_builder or StubMRAssessmentBuilder()
    report_store = report_store or StubReportStore()
    mr_cache_store = mr_cache_store or StubMRCacheStore()

    executors = {
        JobType.MB_BRIEFING: MBBriefingExecutor(
            session_factory=session_factory,
            mb_builder=mb_builder,
            report_runner=report_runner,
            report_store=report_store,
        ),
        JobType.EU_SCAN: EUScanExecutor(
            session_factory=session_factory,
            eu_planner=eu_planner,
            report_runner=report_runner,
            report_store=report_store,
        ),
        JobType.MR_ASSESSMENT: MRAssessmentExecutor(
            session_factory=session_factory,
            mr_builder=mr_builder,
            batch_runner=batch_runner,
            report_runner=report_runner,
            mr_cache_store=mr_cache_store,
        ),
        JobType.SYSTEM_MAINTENANCE: MaintenanceExecutor(
            session_factory=session_factory,
        ),
    }

    return SchedulerService(
        session_factory=session_factory,
        scheduler=scheduler,
        settings=settings,
        executors=executors,
    )
