from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import datetime, timezone

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from openlia_server.auth.deps import get_current_user
from openlia_server.db.base import Base
import openlia_server.db.models  # noqa: F401 — register all models
from openlia_server.db.models.auth import User
from openlia_server.db.models.scheduler import JobRun
from openlia_server.routes.jobs import router as jobs_router
from openlia_server.routes.notifications import router as notifications_router
from openlia_server.scheduler.registry import JobStatus, JobType


@pytest.fixture
def route_engine():
    """In-memory SQLite using StaticPool so all threads share one connection."""
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(eng)
    try:
        yield eng
    finally:
        eng.dispose()


@pytest.fixture
def route_session_factory(route_engine):
    return sessionmaker(
        bind=route_engine,
        future=True,
        expire_on_commit=False,
        autoflush=False,
    )


@pytest.fixture
def client_with_user(route_session_factory):
    """Stand up a minimal app with stubbed scheduler and a logged-in user."""
    from _fakes import FakeAPScheduler, FakeBatchRunner, FakeReportRunner
    from openlia_server.scheduler import wiring as wiring_mod
    from openlia_server.scheduler.settings import SchedulerSettings

    with route_session_factory() as s:
        s.add(
            User(
                id="u_1", email="u@e.com", display_name="u",
                password_hash="h", is_admin=False, is_disabled=False,
            )
        )
        s.commit()

    scheduler = FakeAPScheduler()
    svc = wiring_mod.build_scheduler_service(
        session_factory=route_session_factory,
        settings=SchedulerSettings(enabled=True),
        scheduler=scheduler,
        report_runner=FakeReportRunner(events=[]),
        batch_runner=FakeBatchRunner(results=[]),
    )

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        await svc.start()
        app.state.scheduler = svc
        yield
        await svc.shutdown()

    app = FastAPI(lifespan=lifespan)
    app.include_router(jobs_router)
    app.include_router(notifications_router)

    def _fake_user():
        with route_session_factory() as s:
            return s.get(User, "u_1")

    app.dependency_overrides[get_current_user] = _fake_user

    with TestClient(app) as client:
        yield client


def _seed_run(
    session,
    *,
    id: str,
    status: JobStatus,
    job_type: JobType = JobType.MB_BRIEFING,
    user_id: str = "u_1",
) -> None:
    now = datetime.now(timezone.utc)
    session.add(
        JobRun(
            id=id,
            job_type=job_type.value,
            user_id=user_id,
            schedule_id="sch_mb",
            attempt=1,
            status=status.value,
            started_at=now,
            completed_at=now if status is not JobStatus.RUNNING else None,
            result_summary=json.dumps({"ok": True}) if status is JobStatus.COMPLETED else None,
            error_message="429" if status is JobStatus.FAILED else None,
        )
    )


def test_jobs_history_returns_current_users_runs_newest_first(
    client_with_user, route_session_factory
) -> None:
    with route_session_factory() as s:
        _seed_run(s, id="run_1", status=JobStatus.COMPLETED)
        _seed_run(s, id="run_2", status=JobStatus.FAILED)
        _seed_run(s, id="run_3", status=JobStatus.COMPLETED)
        s.add(
            User(
                id="u_other", email="x@e.com", display_name="x",
                password_hash="h", is_admin=False, is_disabled=False,
            )
        )
        _seed_run(s, id="run_other", status=JobStatus.COMPLETED, user_id="u_other")
        s.commit()

    r = client_with_user.get("/jobs/history")
    assert r.status_code == 200
    body = r.json()
    ids = [row["id"] for row in body["runs"]]
    assert "run_other" not in ids
    assert set(ids) == {"run_1", "run_2", "run_3"}
    assert body["total"] == 3


def test_jobs_history_pagination(client_with_user, route_session_factory) -> None:
    with route_session_factory() as s:
        for i in range(5):
            _seed_run(s, id=f"r{i}", status=JobStatus.COMPLETED)
        s.commit()

    r = client_with_user.get("/jobs/history?limit=2&offset=0")
    assert r.status_code == 200
    assert len(r.json()["runs"]) == 2
    assert r.json()["total"] == 5


def test_retry_endpoint_schedules_new_run(
    client_with_user, route_session_factory
) -> None:
    with route_session_factory() as s:
        _seed_run(s, id="run_fail", status=JobStatus.FAILED)
        s.commit()

    r = client_with_user.post("/jobs/run_fail/retry")
    assert r.status_code == 202
    body = r.json()
    assert body["run_id"] == "run_fail"
    assert body["retry_scheduled"] is True


def test_retry_refuses_someone_elses_run(
    client_with_user, route_session_factory
) -> None:
    with route_session_factory() as s:
        s.add(
            User(
                id="u_other", email="x@e.com", display_name="x",
                password_hash="h", is_admin=False, is_disabled=False,
            )
        )
        _seed_run(s, id="run_other", status=JobStatus.FAILED, user_id="u_other")
        s.commit()

    r = client_with_user.post("/jobs/run_other/retry")
    assert r.status_code == 404
