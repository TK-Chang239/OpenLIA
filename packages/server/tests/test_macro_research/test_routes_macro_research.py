from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock

import openlia_server.db.models.register_all  # noqa: F401 — register all tables
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openlia.macro_research.schemas import DashboardResult
from openlia_server.db.base import Base
from openlia_server.db.models.auth import User
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
    runner = MagicMock()
    runner.run = AsyncMock(
        return_value=DashboardResult(
            slug="debt_cycle",
            display_name="Debt Cycle",
            severity="amber",
            tiers=[],
            headline="Plateau",
            generated_at=datetime.now(UTC),
            smart_mode_active=False,
        )
    )
    dashboard_svc = MagicMock()
    dashboard_svc.list_for_user.return_value = []
    dashboard_svc.get_or_create.return_value = MagicMock(view_config={}, threshold_overrides={})
    dashboard_svc.update_config.return_value = MagicMock(
        view_config={"auto_refresh": "5m"},
        threshold_overrides={"debt_gdp_warn": 95},
    )

    def _override_auth():
        return MagicMock(id="u-1", email="a@b", is_admin=False)

    router = build_macro_research_router(
        db_session_factory=session_factory,
        mode="personal",
        mr_runner=runner,
        dashboard_service=dashboard_svc,
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
    assert len(body["dashboards"]) == 5


def test_get_dashboard(client: TestClient) -> None:
    r = client.get("/departments/macro_research/dashboards/debt_cycle")
    assert r.status_code == 200
    assert r.json()["slug"] == "debt_cycle"


def test_get_dashboard_404_for_unknown(client: TestClient) -> None:
    r = client.get("/departments/macro_research/dashboards/not_real")
    assert r.status_code == 404


def test_update_config(client: TestClient) -> None:
    r = client.put(
        "/departments/macro_research/dashboards/debt_cycle/config",
        json={
            "view_config": {"auto_refresh": "5m"},
            "threshold_overrides": {"debt_gdp_warn": 95},
        },
    )
    assert r.status_code == 200


def test_run_assessment(client: TestClient, session_factory, fake_scheduler) -> None:
    r = client.post(
        "/departments/macro_research/dashboards/world_order/assessment/run",
        json={},
    )
    assert r.status_code == 202
    body = r.json()
    assert "job_run_id" in body
    assert body["status"] == "queued"
    # JobRun row persisted with running status + scheduler dispatched.
    with session_factory() as s:
        row = s.get(JobRun, body["job_run_id"])
        assert row is not None
        assert row.status == JobStatus.RUNNING.value
        assert row.job_type == JobType.MR_ASSESSMENT.value
        assert row.schedule_id == "world_order"
        assert row.user_id == "u-1"
    fake_scheduler.run_now.assert_awaited_once()
    kwargs = fake_scheduler.run_now.await_args.kwargs
    assert kwargs["job_type"] == JobType.MR_ASSESSMENT
    assert kwargs["user_id"] == "u-1"
    assert kwargs["schedule_id"] == "world_order"
    assert kwargs["run_id"] == body["job_run_id"]


def test_run_assessment_without_scheduler_marks_cancelled(
    session_factory,
) -> None:
    app = FastAPI()
    runner = MagicMock()
    dashboard_svc = MagicMock()
    dashboard_svc.get_or_create.return_value = MagicMock(view_config={}, threshold_overrides={})

    def _override_auth():
        return MagicMock(id="u-1", email="a@b", is_admin=False)

    router = build_macro_research_router(
        db_session_factory=session_factory,
        mode="personal",
        mr_runner=runner,
        dashboard_service=dashboard_svc,
        require_auth_override=_override_auth,
    )
    app.include_router(router)
    # No scheduler on app.state.
    client = TestClient(app)
    r = client.post(
        "/departments/macro_research/dashboards/world_order/assessment/run",
        json={},
    )
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "cancelled"
    with session_factory() as s:
        row = s.get(JobRun, body["job_run_id"])
        assert row.status == JobStatus.CANCELLED.value


def test_run_assessment_404_for_unknown(client: TestClient) -> None:
    r = client.post(
        "/departments/macro_research/dashboards/not_real/assessment/run",
        json={},
    )
    assert r.status_code == 404


def test_get_dashboard_smart_mode_plumbed(client: TestClient) -> None:
    r = client.get("/departments/macro_research/dashboards/debt_cycle?smart_mode=true")
    assert r.status_code == 200


def test_put_threshold_overrides(client: TestClient) -> None:
    r = client.put(
        "/departments/macro_research/dashboards/debt_cycle/threshold-overrides",
        json={"threshold_overrides": {"debt_gdp_warn": 95}},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["threshold_overrides"] == {"debt_gdp_warn": 95}


def test_put_threshold_overrides_404_unknown(client: TestClient) -> None:
    r = client.put(
        "/departments/macro_research/dashboards/not_real/threshold-overrides",
        json={"threshold_overrides": {}},
    )
    assert r.status_code == 404
