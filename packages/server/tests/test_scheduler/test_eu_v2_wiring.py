from __future__ import annotations

from datetime import datetime

import pytest
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
from openlia_server.scheduler.registry import JobType
from openlia_server.scheduler.settings import SchedulerSettings
from openlia_server.scheduler.wiring import build_scheduler_service


class _FakeSyncer:
    def sync_all(self, *, session) -> int:
        return 0


class _FakeDispatcher:
    def dispatch_due(self, *, session, now: datetime) -> int:
        return 0


def _builders():
    return dict(
        eu_planner=StubEUScanPlanner(),
        mr_builder=FakeMRBuilder(
            items=[], synth=ReportRequest(mode="mr_synthesis", user_input="x")
        ),
        report_store=FakeReportStore(),
        mr_cache_store=FakeMRCacheStore(),
    )


def _common(session_factory):
    return dict(
        session_factory=session_factory,
        settings=SchedulerSettings(enabled=True),
        scheduler=FakeAPScheduler(),
        report_runner=FakeReportRunner(events=[]),
        batch_runner=FakeBatchRunner(results=[]),
        **_builders(),
    )


@pytest.mark.asyncio
async def test_eu_v2_executors_registered(session_factory):
    svc = build_scheduler_service(
        **_common(session_factory),
        eu_v2_syncer=_FakeSyncer(),
        eu_v2_dispatcher=_FakeDispatcher(),
    )
    assert JobType.EU_V2_SYNC in svc.executors
    assert JobType.EU_V2_DISPATCH in svc.executors


@pytest.mark.asyncio
async def test_eu_v2_executors_absent_when_not_supplied(session_factory):
    svc = build_scheduler_service(**_common(session_factory))
    assert JobType.EU_V2_SYNC not in svc.executors
    assert JobType.EU_V2_DISPATCH not in svc.executors


@pytest.mark.asyncio
async def test_start_registers_eu_v2_cadences(session_factory):
    from openlia_server.scheduler.registry import (
        EU_V2_DISPATCH_KEY,
        EU_V2_SYNC_KEY,
    )

    scheduler = FakeAPScheduler()
    svc = build_scheduler_service(
        **{**_common(session_factory), "scheduler": scheduler},
        eu_v2_syncer=_FakeSyncer(),
        eu_v2_dispatcher=_FakeDispatcher(),
    )
    await svc.start()
    assert EU_V2_SYNC_KEY in scheduler.jobs
    assert EU_V2_DISPATCH_KEY in scheduler.jobs
