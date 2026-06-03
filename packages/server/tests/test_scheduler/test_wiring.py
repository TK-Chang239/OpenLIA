from __future__ import annotations

import pytest
from _scheduler_fakes import (
    FakeAPScheduler,
    FakeReportRunner,
    FakeReportStore,
    StubEUScanPlanner,
)
from openlia_server.scheduler.registry import JobType
from openlia_server.scheduler.settings import SchedulerSettings
from openlia_server.scheduler.wiring import build_scheduler_service


def _builders():
    """Return a fresh kwargs dict of real-shaped fakes for wiring tests."""
    return dict(
        eu_planner=StubEUScanPlanner(),
        report_store=FakeReportStore(),
    )


@pytest.mark.asyncio
async def test_build_scheduler_service_wires_all_executors(
    session_factory,
) -> None:
    svc = build_scheduler_service(
        session_factory=session_factory,
        settings=SchedulerSettings(enabled=True),
        scheduler=FakeAPScheduler(),
        report_runner=FakeReportRunner(events=[]),
        **_builders(),
    )

    assert JobType.MB_BRIEFING in svc.executors
    assert JobType.EU_SCAN in svc.executors
    assert JobType.MR_DASH in svc.executors
    assert JobType.SYSTEM_MAINTENANCE in svc.executors
    assert JobType.GRAPH_EXTRACTION in svc.executors


def test_build_requires_real_builders(session_factory) -> None:
    """Omitting any required builder must raise TypeError at boot — no
    silent stub fallbacks remain in the production wiring path."""
    common = dict(
        session_factory=session_factory,
        settings=SchedulerSettings(enabled=True),
        scheduler=FakeAPScheduler(),
        report_runner=FakeReportRunner(events=[]),
    )
    base = _builders()
    for missing in (
        "eu_planner",
        "report_store",
    ):
        kwargs = {k: v for k, v in base.items() if k != missing}
        with pytest.raises(TypeError):
            build_scheduler_service(**common, **kwargs)


@pytest.mark.asyncio
async def test_build_scheduler_service_with_real_report_runner(
    session_factory,
) -> None:
    from openlia_server.services.runtime import build_report_runner

    svc = build_scheduler_service(
        session_factory=session_factory,
        settings=SchedulerSettings(enabled=True),
        scheduler=FakeAPScheduler(),
        report_runner=build_report_runner(session_factory),
        **_builders(),
    )

    assert JobType.MB_BRIEFING in svc.executors
    assert JobType.EU_SCAN in svc.executors
    assert JobType.MR_DASH in svc.executors
    assert JobType.SYSTEM_MAINTENANCE in svc.executors


@pytest.mark.asyncio
async def test_build_includes_rs_executor_when_runner_provided(
    session_factory,
) -> None:
    from collections.abc import Sequence

    class _RsRunner:
        def run_many(self, tickers: Sequence[str]) -> list[dict]:
            return []

    svc = build_scheduler_service(
        session_factory=session_factory,
        settings=SchedulerSettings(enabled=True),
        scheduler=FakeAPScheduler(),
        report_runner=FakeReportRunner(events=[]),
        rs_runner=_RsRunner(),
        **_builders(),
    )

    assert JobType.RS_SNAPSHOT in svc.executors
