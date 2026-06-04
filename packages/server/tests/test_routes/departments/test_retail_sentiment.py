"""HTTP tests for /departments/retail_sentiment/* (MR-shaped dashboard routes)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import openlia_server.db.models.register_all  # noqa: F401 — register all tables
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openlia.departments.health import DepartmentHealth
from openlia_server.db.base import Base
from openlia_server.db.models.auth import User
from openlia_server.db.models.dashboard import RsDashboardCache
from openlia_server.db.models.scheduler import JobRun
from openlia_server.routes.departments.retail_sentiment import build_retail_sentiment_router
from openlia_server.scheduler.registry import JobStatus, JobType
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool


@pytest.fixture
def session_factory():
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

    router = build_retail_sentiment_router(
        db_session_factory=session_factory,
        mode="personal",
        require_auth_override=_override_auth,
    )
    app.include_router(router)
    app.state.scheduler = fake_scheduler
    return TestClient(app)


# ---------------------------------------------------------------------------
# GET /dashboard/{ticker}
# ---------------------------------------------------------------------------


def test_get_dashboard_no_cache_returns_null(client: TestClient) -> None:
    r = client.get("/departments/retail_sentiment/dashboard/AAPL")
    assert r.status_code == 200
    body = r.json()
    assert body["payload"] is None
    assert body["generated_at"] is None
    assert body["is_stale"] is True
    assert body["provenance"] is None


def test_get_dashboard_with_cache_row(client: TestClient, session_factory) -> None:
    with session_factory() as s:
        s.add(
            RsDashboardCache(
                user_id="u-1",
                ticker="AAPL",
                payload_json=json.dumps({"sentiment_score": 0.7}),
                provenance="live",
                model_ref="anthropic:claude-sonnet-4-6",
                generated_at=datetime.now(UTC),
            )
        )
        s.commit()

    r = client.get("/departments/retail_sentiment/dashboard/AAPL")
    assert r.status_code == 200
    body = r.json()
    assert body["payload"]["sentiment_score"] == 0.7
    assert body["is_stale"] is False
    assert body["provenance"] == "live"
    assert body["generated_at"] is not None


def test_get_dashboard_stale_when_old(client: TestClient, session_factory) -> None:
    old_time = datetime.now(UTC) - timedelta(hours=25)
    with session_factory() as s:
        s.add(
            RsDashboardCache(
                user_id="u-1",
                ticker="AAPL",
                payload_json=json.dumps({"sentiment_score": 0.5}),
                provenance="live",
                model_ref="anthropic:claude-sonnet-4-6",
                generated_at=old_time,
            )
        )
        s.commit()

    r = client.get("/departments/retail_sentiment/dashboard/AAPL")
    assert r.status_code == 200
    assert r.json()["is_stale"] is True


# ---------------------------------------------------------------------------
# GET /dashboard/{ticker}/history
# ---------------------------------------------------------------------------


def test_get_history_no_cache_returns_empty(client: TestClient) -> None:
    r = client.get("/departments/retail_sentiment/dashboard/AAPL/history")
    assert r.status_code == 200
    body = r.json()
    assert body == []


def test_get_history_with_cache_row(client: TestClient, session_factory) -> None:
    with session_factory() as s:
        s.add(
            RsDashboardCache(
                user_id="u-1",
                ticker="AAPL",
                payload_json=json.dumps({"sentiment_score": 0.6}),
                provenance="live",
                model_ref="anthropic:claude-sonnet-4-6",
                generated_at=datetime.now(UTC),
            )
        )
        s.commit()

    r = client.get("/departments/retail_sentiment/dashboard/AAPL/history?days=7")
    assert r.status_code == 200
    body = r.json()
    assert len(body) == 1
    assert body[0]["payload"]["sentiment_score"] == 0.6
    assert body[0]["generated_at"] is not None


def test_get_history_excludes_old_rows(client: TestClient, session_factory) -> None:
    old_time = datetime.now(UTC) - timedelta(days=10)
    with session_factory() as s:
        s.add(
            RsDashboardCache(
                user_id="u-1",
                ticker="AAPL",
                payload_json=json.dumps({"sentiment_score": 0.3}),
                provenance="live",
                model_ref="anthropic:claude-sonnet-4-6",
                generated_at=old_time,
            )
        )
        s.commit()

    r = client.get("/departments/retail_sentiment/dashboard/AAPL/history?days=7")
    assert r.status_code == 200
    assert r.json() == []


# ---------------------------------------------------------------------------
# GET/PUT /config
# ---------------------------------------------------------------------------


def test_get_config_creates_default(client: TestClient) -> None:
    r = client.get("/departments/retail_sentiment/config")
    assert r.status_code == 200
    body = r.json()
    assert body["refresh_interval_minutes"] == 60


def test_put_config_round_trip(client: TestClient) -> None:
    r = client.put(
        "/departments/retail_sentiment/config",
        json={"refresh_interval_minutes": 30},
    )
    assert r.status_code == 200
    assert r.json()["refresh_interval_minutes"] == 30

    reread = client.get("/departments/retail_sentiment/config").json()
    assert reread["refresh_interval_minutes"] == 30


def test_put_config_rejects_too_small_interval(client: TestClient) -> None:
    r = client.put(
        "/departments/retail_sentiment/config",
        json={"refresh_interval_minutes": 1},
    )
    assert r.status_code == 400


# ---------------------------------------------------------------------------
# POST /dashboard/{ticker}/refresh
# ---------------------------------------------------------------------------


def test_refresh_enqueues(client: TestClient, session_factory, fake_scheduler) -> None:
    r = client.post("/departments/retail_sentiment/dashboard/AAPL/refresh")
    assert r.status_code == 202
    body = r.json()
    assert "job_run_id" in body
    assert body["status"] == "queued"

    with session_factory() as s:
        row = s.get(JobRun, body["job_run_id"])
        assert row is not None
        assert row.status == JobStatus.RUNNING.value
        assert row.job_type == JobType.RS_SNAPSHOT.value
        assert row.schedule_id == "AAPL"
        assert row.user_id == "u-1"

    fake_scheduler.run_now.assert_awaited_once()
    kwargs = fake_scheduler.run_now.await_args.kwargs
    assert kwargs["job_type"] == JobType.RS_SNAPSHOT
    assert kwargs["user_id"] == "u-1"
    assert kwargs["schedule_id"] == "AAPL"
    assert kwargs["run_id"] == body["job_run_id"]


def test_refresh_409_when_run_in_progress(
    client: TestClient, session_factory, fake_scheduler
) -> None:
    with session_factory() as s:
        s.add(
            JobRun(
                id="existing-run",
                user_id="u-1",
                job_type=JobType.RS_SNAPSHOT.value,
                schedule_id="AAPL",
                status=JobStatus.RUNNING.value,
                started_at=datetime.now(UTC),
            )
        )
        s.commit()

    r = client.post("/departments/retail_sentiment/dashboard/AAPL/refresh")
    assert r.status_code == 409
    assert "in progress" in r.json()["detail"]

    with session_factory() as s:
        rows = s.query(JobRun).filter_by(schedule_id="AAPL").all()
        assert len(rows) == 1
    fake_scheduler.run_now.assert_not_awaited()


def test_refresh_different_tickers_not_blocked(
    client: TestClient, session_factory, fake_scheduler
) -> None:
    # AAPL in progress — MSFT refresh must not be blocked.
    with session_factory() as s:
        s.add(
            JobRun(
                id="aapl-run",
                user_id="u-1",
                job_type=JobType.RS_SNAPSHOT.value,
                schedule_id="AAPL",
                status=JobStatus.RUNNING.value,
                started_at=datetime.now(UTC),
            )
        )
        s.commit()

    r = client.post("/departments/retail_sentiment/dashboard/MSFT/refresh")
    assert r.status_code == 202


def test_refresh_allows_after_stale_running(
    client: TestClient, session_factory, fake_scheduler
) -> None:
    with session_factory() as s:
        s.add(
            JobRun(
                id="stale-run",
                user_id="u-1",
                job_type=JobType.RS_SNAPSHOT.value,
                schedule_id="AAPL",
                status=JobStatus.RUNNING.value,
                started_at=datetime.now(UTC) - timedelta(hours=2),
            )
        )
        s.commit()

    r = client.post("/departments/retail_sentiment/dashboard/AAPL/refresh")
    assert r.status_code == 202
    assert r.json()["status"] == "queued"
    with session_factory() as s:
        rows = s.query(JobRun).filter_by(schedule_id="AAPL").all()
        assert len(rows) == 2
    fake_scheduler.run_now.assert_awaited_once()


def test_refresh_without_scheduler_marks_cancelled(session_factory) -> None:
    app = FastAPI()

    def _override_auth():
        return MagicMock(id="u-1", email="a@b", is_admin=False)

    router = build_retail_sentiment_router(
        db_session_factory=session_factory,
        mode="personal",
        require_auth_override=_override_auth,
    )
    app.include_router(router)
    # No scheduler on app.state.
    client = TestClient(app)
    r = client.post("/departments/retail_sentiment/dashboard/AAPL/refresh")
    assert r.status_code == 202
    body = r.json()
    assert body["status"] == "cancelled"
    with session_factory() as s:
        row = s.get(JobRun, body["job_run_id"])
        assert row.status == JobStatus.CANCELLED.value
        assert row.job_type == JobType.RS_SNAPSHOT.value


def test_refresh_409_when_dept_disabled(session_factory, fake_scheduler) -> None:
    app = FastAPI()

    def _override_auth():
        return MagicMock(id="u-1", email="a@b", is_admin=False)

    router = build_retail_sentiment_router(
        db_session_factory=session_factory,
        mode="personal",
        require_auth_override=_override_auth,
    )
    app.include_router(router)
    app.state.scheduler = fake_scheduler
    app.state.dept_health = {
        "retail_sentiment": DepartmentHealth(
            department_id="retail_sentiment",
            status="disabled",
            reason="no WEB_SEARCH connector",
            missing_categories=frozenset(),
            satisfied_categories=frozenset(),
            unsatisfied_any_of=(),
            unresolved_needs=frozenset(),
        )
    }
    client = TestClient(app)
    r = client.post("/departments/retail_sentiment/dashboard/AAPL/refresh")
    assert r.status_code == 409
    assert r.json()["detail"]["error"] == "dept_disabled"
    fake_scheduler.run_now.assert_not_awaited()
