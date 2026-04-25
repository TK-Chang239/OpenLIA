from __future__ import annotations

import pytest
from _scheduler_fakes import (
    FakeAPScheduler,
    FakeBatchRunner,
    FakeMBBuilder,
    FakeMRBuilder,
    FakeMRCacheStore,
    FakeReportRunner,
    FakeReportStore,
    StubEUScanPlanner,
)
from openlia.llm.runtime.messages import ReportRequest
from openlia_server.scheduler.registry import JobType
from openlia_server.scheduler.settings import SchedulerSettings
from openlia_server.scheduler.wiring import build_scheduler_service


def _builders():
    """Return a fresh kwargs dict of real-shaped fakes for wiring tests."""
    return dict(
        mb_builder=FakeMBBuilder(request=ReportRequest(mode="stock_update", user_input="x")),
        eu_planner=StubEUScanPlanner(),
        mr_builder=FakeMRBuilder(
            items=[], synth=ReportRequest(mode="mr_synthesis", user_input="x")
        ),
        report_store=FakeReportStore(),
        mr_cache_store=FakeMRCacheStore(),
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
        batch_runner=FakeBatchRunner(results=[]),
        **_builders(),
    )

    assert JobType.MB_BRIEFING in svc.executors
    assert JobType.EU_SCAN in svc.executors
    assert JobType.MR_ASSESSMENT in svc.executors
    assert JobType.SYSTEM_MAINTENANCE in svc.executors


def test_build_requires_real_builders(session_factory) -> None:
    """Omitting any required builder must raise TypeError at boot — no
    silent stub fallbacks remain in the production wiring path."""
    common = dict(
        session_factory=session_factory,
        settings=SchedulerSettings(enabled=True),
        scheduler=FakeAPScheduler(),
        report_runner=FakeReportRunner(events=[]),
        batch_runner=FakeBatchRunner(results=[]),
    )
    base = _builders()
    for missing in (
        "mb_builder",
        "eu_planner",
        "mr_builder",
        "report_store",
        "mr_cache_store",
    ):
        kwargs = {k: v for k, v in base.items() if k != missing}
        with pytest.raises(TypeError):
            build_scheduler_service(**common, **kwargs)


def test_build_requires_batch_runner(session_factory) -> None:
    """batch_runner must not be None — MR executor unconditionally calls
    .run() on it at fire time."""
    with pytest.raises(TypeError):
        build_scheduler_service(
            session_factory=session_factory,
            settings=SchedulerSettings(enabled=True),
            scheduler=FakeAPScheduler(),
            report_runner=FakeReportRunner(events=[]),
            batch_runner=None,
            **_builders(),
        )


@pytest.mark.asyncio
async def test_build_scheduler_service_with_real_report_runner(
    session_factory,
) -> None:
    from openlia_server.services.runtime import build_batch_runner, build_report_runner

    svc = build_scheduler_service(
        session_factory=session_factory,
        settings=SchedulerSettings(enabled=True),
        scheduler=FakeAPScheduler(),
        report_runner=build_report_runner(session_factory),
        batch_runner=build_batch_runner(session_factory),
        **_builders(),
    )

    assert JobType.MB_BRIEFING in svc.executors
    assert JobType.EU_SCAN in svc.executors
    assert JobType.MR_ASSESSMENT in svc.executors
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
        batch_runner=FakeBatchRunner(results=[]),
        rs_runner=_RsRunner(),
        **_builders(),
    )

    assert JobType.RS_SNAPSHOT in svc.executors
