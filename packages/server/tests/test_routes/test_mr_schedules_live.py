"""Live-scheduler integration for the MR schedule routes (P0-05).

Asserts the route handlers reach the scheduler-bound MRScheduleService
stashed on `app.state.mr_schedule_service` rather than a factory-time
instance with `scheduler=None`."""

from __future__ import annotations

import sys
from contextlib import asynccontextmanager
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openlia_server.db.base import Base
from openlia_server.db.models.auth import User
from openlia_server.routes.mr_schedules import build_mr_schedule_router
from openlia_server.scheduler.registry import JobType, job_key
from openlia_server.scheduler.settings import SchedulerSettings
from openlia_server.services.mr_schedules import MRScheduleService
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

# Make the scheduler-fakes directory importable.
sys.path.insert(
    0,
    str(Path(__file__).parents[1] / "test_scheduler"),
)

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
from openlia_server.scheduler.wiring import build_scheduler_service


@pytest.fixture
def live_app():
    """Boot a minimal FastAPI app with a real SchedulerService backed by
    a FakeAPScheduler so we can assert add_schedule / remove_schedule
    actually reach the scheduler from PUT/DELETE handlers."""
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(eng)
    factory = sessionmaker(bind=eng, future=True, expire_on_commit=False, autoflush=False)

    with factory() as s:
        s.add(
            User(
                id="local",
                email="u@e.com",
                display_name="u",
                password_hash="h",
                is_admin=False,
                is_disabled=False,
            )
        )
        s.commit()

    fake_scheduler = FakeAPScheduler()
    svc = build_scheduler_service(
        session_factory=factory,
        settings=SchedulerSettings(enabled=True),
        scheduler=fake_scheduler,
        report_runner=FakeReportRunner(events=[]),
        batch_runner=FakeBatchRunner(results=[]),
        mb_builder=FakeMBBuilder(request=ReportRequest(mode="stock_update", user_input="x")),
        eu_planner=StubEUScanPlanner(),
        mr_builder=FakeMRBuilder(
            items=[], synth=ReportRequest(mode="mr_synthesis", user_input="x")
        ),
        report_store=FakeReportStore(),
        mr_cache_store=FakeMRCacheStore(),
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await svc.start()
        app.state.scheduler = svc
        app.state.mr_schedule_service = MRScheduleService(session_factory=factory, scheduler=svc)
        yield
        await svc.shutdown()

    app = FastAPI(lifespan=lifespan)

    # Factory-time MR schedule service deliberately built with no scheduler
    # — the live test confirms the route reads from app.state instead.
    factory_time_svc = MagicMock()
    app.include_router(
        build_mr_schedule_router(
            db_session_factory=factory,
            mode="personal",
            mr_schedule_service=factory_time_svc,
            require_auth_override=lambda: User(
                id="local",
                email="u@e.com",
                display_name="u",
                password_hash="h",
                is_admin=False,
                is_disabled=False,
            ),
        )
    )

    with TestClient(app) as client:
        yield client, fake_scheduler, factory_time_svc, svc


def test_upsert_registers_with_live_scheduler(live_app):
    client, fake_scheduler, factory_time_svc, _svc = live_app
    r = client.put(
        "/departments/macro_research/schedule",
        json={"cron_expression": "0 0 * * 0"},
    )
    assert r.status_code == 200, r.text
    # Live scheduler received the registration.
    assert job_key(JobType.MR_ASSESSMENT, "local") in fake_scheduler.jobs
    # Factory-time stub was *not* called (route reads from app.state).
    factory_time_svc.upsert.assert_not_called()


def test_delete_unregisters_from_live_scheduler(live_app):
    client, fake_scheduler, _factory_time_svc, _svc = live_app
    # First register so there's something to delete.
    r = client.put(
        "/departments/macro_research/schedule",
        json={"cron_expression": "0 0 * * 0"},
    )
    assert r.status_code == 200
    assert job_key(JobType.MR_ASSESSMENT, "local") in fake_scheduler.jobs

    r = client.delete("/departments/macro_research/schedule")
    assert r.status_code == 204
    assert job_key(JobType.MR_ASSESSMENT, "local") not in fake_scheduler.jobs
