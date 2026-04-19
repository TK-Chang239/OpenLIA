from __future__ import annotations

import pytest

from _fakes import (
    FakeAPScheduler,
    FakeBatchRunner,
    FakeReportRunner,
)
from openlia_server.scheduler.registry import JobType
from openlia_server.scheduler.settings import SchedulerSettings
from openlia_server.scheduler.wiring import build_scheduler_service


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
    )

    assert JobType.MB_BRIEFING in svc.executors
    assert JobType.EU_SCAN in svc.executors
    assert JobType.MR_ASSESSMENT in svc.executors
    assert JobType.SYSTEM_MAINTENANCE in svc.executors


def test_build_scheduler_service_uses_stubs_when_builders_unprovided(
    session_factory,
) -> None:
    """If a department's builder isn't provided, the executor fires but its
    stub raises DepartmentPayloadBuilderNotWired on first call. The
    scheduler layer treats that as a normal failed run, not a crash."""
    from openlia_server.scheduler.payloads import (
        DepartmentPayloadBuilderNotWired,
    )

    svc = build_scheduler_service(
        session_factory=session_factory,
        settings=SchedulerSettings(enabled=True),
        scheduler=FakeAPScheduler(),
        report_runner=FakeReportRunner(events=[]),
        batch_runner=FakeBatchRunner(results=[]),
    )

    mb_exec = svc.executors[JobType.MB_BRIEFING]
    with pytest.raises(DepartmentPayloadBuilderNotWired, match="Plan 16"):
        # MBBriefingExecutor grabs the builder on _do_work; call directly.
        mb_exec._mb_builder.build(
            session=None, user_id="u_1", schedule_id="s_1"
        )
