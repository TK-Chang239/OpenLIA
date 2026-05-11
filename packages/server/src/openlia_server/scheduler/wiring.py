"""Construct the SchedulerService executor graph.

Every scheduled job type must be wired with its real builder/store
collaborator. The wiring entry point is strict — omitting any
dependency raises TypeError at boot. Test-only fakes live in
`tests/test_scheduler/_scheduler_fakes.py`.
"""

from __future__ import annotations

from typing import Any

from openlia_server.scheduler.executors.base import SessionFactory
from openlia_server.scheduler.executors.eu import EUScanExecutor
from openlia_server.scheduler.executors.graph_extraction import (
    GraphExtractionExecutor,
)
from openlia_server.scheduler.executors.maintenance import MaintenanceExecutor
from openlia_server.scheduler.executors.mb import MBBriefingExecutor
from openlia_server.scheduler.executors.mr import MRAssessmentExecutor
from openlia_server.scheduler.executors.rs import RSSnapshotExecutor
from openlia_server.scheduler.payloads import (
    EUScanPlanner,
    MBRequestBuilder,
    MRAssessmentBuilder,
    MRCacheStore,
    ReportStore,
    RSSnapshotRunner,
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
    mb_builder: MBRequestBuilder,
    eu_planner: EUScanPlanner,
    mr_builder: MRAssessmentBuilder,
    report_store: ReportStore,
    mr_cache_store: MRCacheStore,
    rs_runner: RSSnapshotRunner | None = None,
) -> SchedulerService:
    if batch_runner is None:
        raise TypeError("batch_runner is required (got None)")

    executors: dict[JobType, Any] = {
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
        JobType.GRAPH_EXTRACTION: GraphExtractionExecutor(
            session_factory=session_factory,
        ),
    }

    if rs_runner is not None:
        executors[JobType.RS_SNAPSHOT] = RSSnapshotExecutor(
            session_factory=session_factory,
            rs_runner=rs_runner,
        )

    return SchedulerService(
        session_factory=session_factory,
        scheduler=scheduler,
        settings=settings,
        executors=executors,
    )
