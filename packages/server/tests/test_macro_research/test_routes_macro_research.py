from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import openlia_server.db.models.register_all  # noqa: F401 — register all tables
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openlia_server.db.base import Base
from openlia_server.db.models.auth import User
from openlia_server.db.models.dashboard import MrDashboardCache
from openlia_server.db.models.scheduler import JobRun
from openlia_server.routes.departments.macro_research import build_macro_research_router
from openlia_server.scheduler.registry import JobStatus, JobType
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def session_factory():
    # StaticPool keeps a single connection so the in-memory schema persists
    # across separate sessions opened by the route handler and the test.
    engine = create_engine(
        "sqlite+pysqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)
    with SessionLocal() as s:
        s.add(User(id="u-1", email="a@b", password_hash="x", display_name="A"))
        s.commit()
    return SessionLocal


@pytest.fixture
def fake_scheduler():
    sched = MagicMock()
    sched.run_now = AsyncMock()
    return sched


@pytest.fixture
def client(session_factory, fake_scheduler) -> TestClient:
    app = FastAPI()

    def _override_auth():
        return MagicMock(id="u-1", email="a@b", is_admin=False)

    router = build_macro_research_router(
        db_session_factory=session_factory,
        mode="personal",
        require_auth_override=_override_auth,
    )
    app.include_router(router)
    app.state.scheduler = fake_scheduler
    return TestClient(app)


def test_list_dashboards(client: TestClient) -> None:
    r = client.get("/departments/macro_research/dashboards")
    assert r.status_code == 200
    body = r.json()
    assert "dashboards" in body
    assert len(body["dashboards"]) == 6


def test_get_dashboard(client: TestClient, session_factory) -> None:
    # Seed a cache row for the _override_auth user (id="u-1") + debt_cycle.
    # The route opens its own session via the same StaticPool-backed factory,
    # so the seed must be committed (not merely flushed) to be visible.
    with session_factory() as s:
        s.add(
            MrDashboardCache(
                user_id="u-1",
                dashboard="debt_cycle",
                payload_json='{"phaseBox": {"title": "Late Plateau"}}',
                provenance="live",
                model_ref="anthropic:claude",
                generated_at=datetime.now(UTC),
            )
        )
        s.commit()

    r = client.get("/departments/macro_research/dashboards/debt_cycle")
    assert r.status_code == 200
    body = r.json()
    assert body["payload"]["phaseBox"]["title"] == "Late Plateau"
    assert body["is_stale"] is False
    assert body["provenance"] == "live"
    assert body["generated_at"] is not None


def test_get_dashboard_missing_returns_null(client: TestClient) -> None:
    r = client.get("/departments/macro_research/dashboards/world_order")
    assert r.status_code == 200
    body = r.json()
    assert body["payload"] is None
    assert body["is_stale"] is True
    assert body["generated_at"] is None
    assert body["provenance"] is None


def test_get_dashboard_404_for_unknown(client: TestClient) -> None:
    r = client.get("/departments/macro_research/dashboards/not_real")
    assert r.status_code == 404


def test_refresh_enqueues(client: TestClient, session_factory, fake_scheduler) -> None:
    r = client.post("/departments/macro_research/dashboards/debt_cycle/refresh")
    assert r.status_code == 202
    body = r.json()
    assert "job_run_id" in body
    assert body["status"] == "queued"
    # JobRun row persisted with running status + scheduler dispatched MR_DASH.
    with session_factory() as s:
        row = s.get(JobRun, body["job_run_id"])
        assert row is not None
        assert row.status == JobStatus.RUNNING.value
        assert row.job_type == JobType.MR_DASH.value
        assert row.schedule_id == "debt_cycle"
        assert row.user_id == "u-1"
    fake_scheduler.run_now.assert_awaited_once()
    kwargs = fake_scheduler.run_now.await_args.kwargs
    assert kwargs["job_type"] == JobType.MR_DASH
    assert kwargs["user_id"] == "u-1"
    assert kwargs["schedule_id"] == "debt_cycle"
    assert kwargs["run_id"] == body["job_run_id"]


def test_refresh_without_scheduler_marks_cancelled(
    session_factory,
) -> None:
    app = FastAPI()

    def _override_auth():
        return MagicMock(id="u-1", email="a@b", is_admin=False)

    router = build_macro_research_router(
        db_session_factory=session_factory,
        mode="personal",
        require_auth_override=_override_auth,
    )
    app.include_router(router)
    # No scheduler on app.state.
    client = TestClient(app)
    # debt_cycle is the implemented dashboard; world_order would now hit the
    # 409 implemented-gate before reaching the scheduler-disabled branch.
    r = client.post("/departments/macro_research/dashboards/debt_cycle/refresh")
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "cancelled"
    with session_factory() as s:
        row = s.get(JobRun, body["job_run_id"])
        assert row.status == JobStatus.CANCELLED.value
        assert row.job_type == JobType.MR_DASH.value


def test_refresh_409_when_run_in_progress(
    client: TestClient, session_factory, fake_scheduler
) -> None:
    # A fresh RUNNING mr_dash run for (u-1, debt_cycle) is already in flight.
    with session_factory() as s:
        s.add(
            JobRun(
                id="existing-run",
                user_id="u-1",
                job_type=JobType.MR_DASH.value,
                schedule_id="debt_cycle",
                status=JobStatus.RUNNING.value,
                started_at=datetime.now(UTC),
            )
        )
        s.commit()

    r = client.post("/departments/macro_research/dashboards/debt_cycle/refresh")
    assert r.status_code == 409
    assert "in progress" in r.json()["detail"]
    # No second row was pre-allocated and the scheduler was not dispatched.
    with session_factory() as s:
        rows = s.query(JobRun).filter_by(schedule_id="debt_cycle").all()
        assert len(rows) == 1
    fake_scheduler.run_now.assert_not_awaited()


def test_refresh_allows_after_stale_running(
    client: TestClient, session_factory, fake_scheduler
) -> None:
    # A RUNNING row older than the staleness window is a dead orphan (e.g. a
    # process killed mid-run) and must not permanently block a re-trigger.
    with session_factory() as s:
        s.add(
            JobRun(
                id="stale-run",
                user_id="u-1",
                job_type=JobType.MR_DASH.value,
                schedule_id="debt_cycle",
                status=JobStatus.RUNNING.value,
                started_at=datetime.now(UTC) - timedelta(hours=2),
            )
        )
        s.commit()

    r = client.post("/departments/macro_research/dashboards/debt_cycle/refresh")
    assert r.status_code == 202
    assert r.json()["status"] == "queued"
    with session_factory() as s:
        rows = s.query(JobRun).filter_by(schedule_id="debt_cycle").all()
        assert len(rows) == 2  # the stale orphan + the freshly enqueued run
    fake_scheduler.run_now.assert_awaited_once()


def test_refresh_404_for_unknown(client: TestClient) -> None:
    r = client.post("/departments/macro_research/dashboards/not_real/refresh")
    assert r.status_code == 404


def test_refresh_409_for_unimplemented(
    client: TestClient, session_factory, fake_scheduler, monkeypatch
) -> None:
    # All five dashboards now have engine support, so simulate an
    # unimplemented-but-known dashboard by trimming the implemented set the
    # route gates against. five_forces stays a known DASHBOARDS slug (passes
    # the 404 gate) but is reported as not-yet-generatable (hits the 409 gate).
    import openlia_server.routes.departments.macro_research as mr_route

    monkeypatch.setattr(
        mr_route,
        "implemented_dashboard_slugs",
        lambda: frozenset({"debt_cycle", "world_order", "four_seasons", "all_weather"}),
    )
    r = client.post("/departments/macro_research/dashboards/five_forces/refresh")
    assert r.status_code == 409
    assert "not yet available" in r.json()["detail"]
    # No JobRun was pre-allocated and the scheduler was not dispatched.
    with session_factory() as s:
        rows = s.query(JobRun).filter_by(schedule_id="five_forces").all()
        assert rows == []
    fake_scheduler.run_now.assert_not_awaited()
