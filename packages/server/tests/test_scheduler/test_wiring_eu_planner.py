"""Regression guard that build_scheduler_service accepts a real
EuScanPlannerImpl as the `eu_planner` argument."""

from __future__ import annotations

from dataclasses import dataclass, field

from openlia_server.scheduler.settings import SchedulerSettings
from openlia_server.scheduler.wiring import build_scheduler_service
from openlia_server.services.eu_scan_planner import EuScanPlannerImpl


@dataclass
class _StubRunner:
    async def run(self, **kwargs):
        if False:
            yield


@dataclass
class _StubStore:
    saved: list[dict] = field(default_factory=list)

    def save_from_event(self, **kwargs):
        self.saved.append(kwargs)


@dataclass
class _StubBatch:
    async def run_batch(self, **kwargs):
        return []


class _NoopAdapter:
    def latest_release(self, ticker, *, since):
        return None


def test_wiring_accepts_real_eu_planner(db_session_factory) -> None:
    planner = EuScanPlannerImpl(adapter=_NoopAdapter())
    svc = build_scheduler_service(
        session_factory=db_session_factory,
        settings=SchedulerSettings(enabled=True),
        scheduler=object(),
        report_runner=_StubRunner(),
        batch_runner=_StubBatch(),
        eu_planner=planner,
    )
    assert svc is not None
