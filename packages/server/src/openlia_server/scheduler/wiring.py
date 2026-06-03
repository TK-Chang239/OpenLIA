"""Construct the SchedulerService executor graph.

Every scheduled job type must be wired with its real builder/store
collaborator. The wiring entry point is strict — omitting any
dependency raises TypeError at boot. Test-only fakes live in
`tests/test_scheduler/_scheduler_fakes.py`.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from openlia_server.scheduler.executors.base import SessionFactory
from openlia_server.scheduler.executors.eu import EUScanExecutor
from openlia_server.scheduler.executors.eu_v2 import (
    EuV2DispatchExecutor,
    EuV2SyncExecutor,
)
from openlia_server.scheduler.executors.graph_extraction import (
    GraphExtractionExecutor,
)
from openlia_server.scheduler.executors.maintenance import MaintenanceExecutor
from openlia_server.scheduler.executors.mb import MBBriefingExecutor
from openlia_server.scheduler.executors.mr_dash import MrDashExecutor
from openlia_server.scheduler.executors.portfolio_prices import (
    production_executor as portfolio_executor_factory,
)
from openlia_server.scheduler.executors.rs import RSSnapshotExecutor
from openlia_server.scheduler.payloads import (
    EUScanPlanner,
    EuV2CalendarSyncer,
    EuV2Dispatcher,
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
    eu_planner: EUScanPlanner,
    report_store: ReportStore,
    rs_runner: RSSnapshotRunner | None = None,
    financial_adapter_provider: Callable[[], Any] | None = None,
    eu_v2_syncer: EuV2CalendarSyncer | None = None,
    eu_v2_dispatcher: EuV2Dispatcher | None = None,
) -> SchedulerService:
    executors: dict[JobType, Any] = {
        # The MB executor runs the report_mb engine inline via mb_v2_run_service
        # (its module-default collaborator). `report_runner` / `report_store`
        # stay — the EU scan executor below still uses them.
        JobType.MB_BRIEFING: MBBriefingExecutor(
            session_factory=session_factory,
        ),
        JobType.EU_SCAN: EUScanExecutor(
            session_factory=session_factory,
            eu_planner=eu_planner,
            report_runner=report_runner,
            report_store=report_store,
        ),
        JobType.MR_DASH: MrDashExecutor(session_factory=session_factory),
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

    if financial_adapter_provider is not None:
        executors[JobType.PORTFOLIO_PRICE_REFRESH] = portfolio_executor_factory(
            session_factory=session_factory,
            financial_adapter_provider=financial_adapter_provider,
        )

    if eu_v2_syncer is not None:
        executors[JobType.EU_V2_SYNC] = EuV2SyncExecutor(
            session_factory=session_factory,
            syncer=eu_v2_syncer,
        )

    if eu_v2_dispatcher is not None:
        executors[JobType.EU_V2_DISPATCH] = EuV2DispatchExecutor(
            session_factory=session_factory,
            dispatcher=eu_v2_dispatcher,
        )

    return SchedulerService(
        session_factory=session_factory,
        scheduler=scheduler,
        settings=settings,
        executors=executors,
    )
