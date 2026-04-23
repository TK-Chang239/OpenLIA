from __future__ import annotations

import json
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import openlia_server.db.models  # noqa: F401 — register all models
import pytest
from _scheduler_fakes import FakeAPScheduler, FakeBatchRunner, FakeReportRunner
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openlia_server.db.base import Base
from openlia_server.db.models.auth import User
from openlia_server.routes.eu_schedules import build_eu_schedules_router
from openlia_server.scheduler import wiring as wiring_mod
from openlia_server.scheduler.registry import JobType, job_key
from openlia_server.scheduler.settings import SchedulerSettings
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def eu_engine():
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
def eu_session_factory(eu_engine):
    return sessionmaker(
        bind=eu_engine,
        future=True,
        expire_on_commit=False,
        autoflush=False,
    )


@pytest.fixture
def eu_fixtures(eu_session_factory):
    """Returns (TestClient, FakeAPScheduler) with EU schedules router mounted."""
    with eu_session_factory() as s:
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
    svc = wiring_mod.build_scheduler_service(
        session_factory=eu_session_factory,
        settings=SchedulerSettings(enabled=True),
        scheduler=fake_scheduler,
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
    app.include_router(
        build_eu_schedules_router(db_session_factory=eu_session_factory, mode="personal")
    )

    with TestClient(app) as client:
        yield client, fake_scheduler


@pytest.fixture
def client_no_scheduler(eu_session_factory):
    """App with scheduler disabled (app.state.scheduler is None)."""
    with eu_session_factory() as s:
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

    app = FastAPI()
    app.state.scheduler = None
    app.include_router(
        build_eu_schedules_router(db_session_factory=eu_session_factory, mode="personal")
    )
    with TestClient(app) as client:
        yield client


def test_post_creates_schedule_and_registers_job(eu_fixtures) -> None:
    client, fake_scheduler = eu_fixtures
    r = client.post(
        "/departments/earnings-update/schedules",
        json={
            "time": "07:00",
            "timezone": "America/New_York",
            "days_of_week": [0, 1, 2, 3, 4],
            "label": "Weekday scan",
            "is_enabled": True,
        },
    )
    assert r.status_code == 201
    body = r.json()
    assert body["time"] == "07:00"
    assert body["days_of_week"] == [0, 1, 2, 3, 4]
    assert job_key(JobType.EU_SCAN, "local") in fake_scheduler.jobs


def test_patch_updates_schedule_and_reregisters_job(eu_fixtures) -> None:
    client, fake_scheduler = eu_fixtures
    # Create first
    r = client.post(
        "/departments/earnings-update/schedules",
        json={
            "time": "07:00",
            "timezone": "America/New_York",
            "days_of_week": [0, 1, 2, 3, 4],
            "is_enabled": True,
        },
    )
    assert r.status_code == 201
    schedule_id = r.json()["id"]

    # Update
    r = client.patch(
        f"/departments/earnings-update/schedules/{schedule_id}",
        json={
            "time": "09:00",
            "timezone": "America/Chicago",
            "days_of_week": [0, 2, 4],
            "is_enabled": True,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["time"] == "09:00"
    assert body["days_of_week"] == [0, 2, 4]
    # Job key still registered after modify
    assert job_key(JobType.EU_SCAN, "local") in fake_scheduler.jobs


def test_delete_removes_schedule_and_unregisters_job(eu_fixtures) -> None:
    client, fake_scheduler = eu_fixtures
    r = client.post(
        "/departments/earnings-update/schedules",
        json={
            "time": "07:00",
            "timezone": "America/New_York",
            "days_of_week": [1, 3, 5],
            "is_enabled": True,
        },
    )
    assert r.status_code == 201
    schedule_id = r.json()["id"]

    r = client.delete(f"/departments/earnings-update/schedules/{schedule_id}")
    assert r.status_code == 200
    assert r.json() == {"deleted": schedule_id}
    assert job_key(JobType.EU_SCAN, "local") not in fake_scheduler.jobs


def test_get_lists_user_schedules(eu_fixtures) -> None:
    client, _ = eu_fixtures
    client.post(
        "/departments/earnings-update/schedules",
        json={"time": "07:00", "timezone": "UTC", "days_of_week": [0], "is_enabled": False},
    )
    client.post(
        "/departments/earnings-update/schedules",
        json={"time": "08:00", "timezone": "UTC", "days_of_week": [1], "is_enabled": False},
    )
    r = client.get("/departments/earnings-update/schedules")
    assert r.status_code == 200
    items = r.json()
    assert len(items) == 2
    times = {item["time"] for item in items}
    assert times == {"07:00", "08:00"}


def test_post_with_scheduler_disabled_returns_503(client_no_scheduler) -> None:
    r = client_no_scheduler.post(
        "/departments/earnings-update/schedules",
        json={"time": "07:00", "timezone": "UTC", "days_of_week": [0], "is_enabled": True},
    )
    assert r.status_code == 503
