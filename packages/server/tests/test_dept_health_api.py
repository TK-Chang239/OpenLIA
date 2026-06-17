"""Tests for the dept-health API surface (Phase 10 Task 10.3).

Covers:
- GET /api/dept-health returns the serialized list.
- 409 gate on a known mutating dept endpoint (MR run-assessment).
- Scheduler `_run_job` skips when the corresponding dept is disabled.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openlia.connectors.types import Category
from openlia.departments.health import DepartmentHealth

# ---------------------------------------------------------------------------
# GET /dept-health
# ---------------------------------------------------------------------------


@pytest.fixture
def health_client() -> Iterator[TestClient]:
    from openlia_server.routes.dept_health import build_dept_health_router

    app = FastAPI()
    app.include_router(build_dept_health_router(), prefix="/api")
    yield TestClient(app)


def test_get_dept_health_returns_list_shape(health_client: TestClient) -> None:
    health_client.app.state.dept_health = {
        "equity_research": DepartmentHealth(
            department_id="equity_research",
            status="active",
            reason=None,
            missing_categories=[],
        ),
        "macro_research": DepartmentHealth(
            department_id="macro_research",
            status="disabled",
            reason="Missing required categories: financial",
            missing_categories=[Category.FINANCIAL],
        ),
    }
    resp = health_client.get("/api/dept-health")
    assert resp.status_code == 200
    body = resp.json()
    by_id = {row["department_id"]: row for row in body}
    assert by_id["equity_research"]["status"] == "active"
    assert by_id["equity_research"]["missing_categories"] == []
    assert by_id["macro_research"]["status"] == "disabled"
    assert by_id["macro_research"]["missing_categories"] == ["financial"]


def test_get_dept_health_empty_when_cache_unset(health_client: TestClient) -> None:
    health_client.app.state.dept_health = {}
    resp = health_client.get("/api/dept-health")
    assert resp.status_code == 200
    assert resp.json() == []


def test_post_dept_health_refresh_recomputes_and_returns(db_session_factory) -> None:
    """POST /dept-health/refresh recomputes from current DB state and updates the cache."""
    from openlia_server.routes.dept_health import build_dept_health_router

    app = FastAPI()
    app.include_router(
        build_dept_health_router(db_session_factory=db_session_factory),
        prefix="/api",
    )
    # Seed a stale cache entry the recompute should overwrite.
    app.state.dept_health = {
        "stale": DepartmentHealth(
            department_id="stale",
            status="disabled",
            reason="stale",
            missing_categories=[],
        )
    }
    client = TestClient(app)
    resp = client.post("/api/dept-health/refresh")
    assert resp.status_code == 200
    body = resp.json()
    ids = {row["department_id"] for row in body}
    # Real registered depts are returned; the stale entry is gone.
    assert "stale" not in ids
    # Cache mutated in place.
    assert "stale" not in app.state.dept_health


def test_post_dept_health_refresh_404_when_factory_not_wired() -> None:
    """Without a session factory, the refresh route is not registered (404 not 405)."""
    from openlia_server.routes.dept_health import build_dept_health_router

    app = FastAPI()
    app.include_router(build_dept_health_router(), prefix="/api")
    client = TestClient(app)
    resp = client.post("/api/dept-health/refresh")
    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# 409 gate
# ---------------------------------------------------------------------------


def test_gate_dept_or_409_raises_when_disabled() -> None:
    from fastapi import HTTPException, Request
    from openlia_server.routes.dept_health import gate_dept_or_409

    class _StubApp:
        class state:
            dept_health: dict = {  # noqa: RUF012
                "equity_research": DepartmentHealth(
                    department_id="equity_research",
                    status="disabled",
                    reason="Missing required categories: financial",
                    missing_categories=[Category.FINANCIAL],
                )
            }

    request = Request(
        scope={
            "type": "http",
            "app": _StubApp,
            "headers": [],
            "method": "POST",
            "path": "/equity-research/run",
        }
    )

    with pytest.raises(HTTPException) as exc:
        gate_dept_or_409(request, "equity_research")
    assert exc.value.status_code == 409
    assert exc.value.detail == {
        "error": "dept_disabled",
        "reason": "Missing required categories: financial",
    }


def test_gate_dept_or_409_no_op_when_active() -> None:
    from fastapi import Request
    from openlia_server.routes.dept_health import gate_dept_or_409

    class _StubApp:
        class state:
            dept_health: dict = {  # noqa: RUF012
                "equity_research": DepartmentHealth(
                    department_id="equity_research",
                    status="active",
                    reason=None,
                    missing_categories=[],
                )
            }

    request = Request(
        scope={
            "type": "http",
            "app": _StubApp,
            "headers": [],
            "method": "POST",
            "path": "/x",
        }
    )
    # Must not raise
    gate_dept_or_409(request, "equity_research")


def test_gate_dept_or_409_no_op_when_dept_missing_from_cache() -> None:
    from fastapi import Request
    from openlia_server.routes.dept_health import gate_dept_or_409

    class _StubApp:
        class state:
            dept_health: dict = {}  # noqa: RUF012

    request = Request(
        scope={
            "type": "http",
            "app": _StubApp,
            "headers": [],
            "method": "POST",
            "path": "/x",
        }
    )
    # Must not raise — tests bypassing the lifespan shouldn't 409 spuriously
    gate_dept_or_409(request, "macro_research")


# ---------------------------------------------------------------------------
# 409 contract on a real mutating endpoint (MR run-assessment)
# ---------------------------------------------------------------------------


def test_mr_run_assessment_returns_409_when_disabled(db_session_factory) -> None:
    """The MR run-assessment endpoint must short-circuit with 409 when
    macro_research is disabled in the cache."""
    from unittest.mock import MagicMock

    from fastapi import FastAPI
    from fastapi.testclient import TestClient
    from openlia_server.routes.departments.macro_research import (
        build_macro_research_router,
    )

    def _override_auth():
        return MagicMock(id="u-1", email="a@b", is_admin=False)

    app = FastAPI()
    router = build_macro_research_router(
        db_session_factory=db_session_factory,
        mode="personal",
        require_auth_override=_override_auth,
    )
    app.include_router(router)
    app.state.dept_health = {
        "macro_research": DepartmentHealth(
            department_id="macro_research",
            status="disabled",
            reason="Missing required categories: financial",
            missing_categories=[Category.FINANCIAL],
        )
    }

    client = TestClient(app)
    r = client.post(
        "/departments/macro_research/dashboards/world_order/refresh",
        json={},
    )
    assert r.status_code == 409
    body = r.json()
    detail = body["detail"]
    assert detail["error"] == "dept_disabled"
    assert "financial" in detail["reason"]


# ---------------------------------------------------------------------------
# Scheduler skip
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_scheduler_run_job_skips_disabled_dept() -> None:
    from openlia_server.scheduler.registry import JobType
    from openlia_server.scheduler.service import SchedulerService
    from openlia_server.scheduler.settings import SchedulerSettings

    fired: list[tuple] = []

    class _StubExecutor:
        async def execute(self, **kwargs):
            fired.append(("executed", kwargs))

    class _StubFactory:
        def __call__(self):
            class _C:
                def __enter__(self_inner):
                    return self_inner

                def __exit__(self_inner, *_a):
                    return False

                def commit(self_inner):
                    return None

            return _C()

    health_map = {
        "macro_research": DepartmentHealth(
            department_id="macro_research",
            status="disabled",
            reason="Missing required categories: financial",
            missing_categories=[Category.FINANCIAL],
        )
    }

    svc = SchedulerService(
        session_factory=_StubFactory(),
        scheduler=None,
        settings=SchedulerSettings(enabled=True),
        executors={JobType.MR_DASH: _StubExecutor()},
        dept_health_provider=lambda: health_map,
    )

    await svc._run_job(JobType.MR_DASH, "user-1", "panel-foo", "run-1")
    # Disabled dept must be skipped — executor never fires.
    assert fired == []


@pytest.mark.asyncio
async def test_scheduler_run_job_runs_when_active() -> None:
    from openlia_server.scheduler.registry import JobType
    from openlia_server.scheduler.service import SchedulerService
    from openlia_server.scheduler.settings import SchedulerSettings

    fired: list[tuple] = []

    class _StubExecutor:
        async def execute(self, **kwargs):
            fired.append(("executed", kwargs))

    class _StubFactory:
        def __call__(self):
            class _C:
                def __enter__(self_inner):
                    return self_inner

                def __exit__(self_inner, *_a):
                    return False

                def commit(self_inner):
                    return None

            return _C()

    health_map = {
        "macro_research": DepartmentHealth(
            department_id="macro_research",
            status="active",
            reason=None,
            missing_categories=[],
        )
    }

    svc = SchedulerService(
        session_factory=_StubFactory(),
        scheduler=None,
        settings=SchedulerSettings(enabled=True),
        executors={JobType.MR_DASH: _StubExecutor()},
        dept_health_provider=lambda: health_map,
    )

    await svc._run_job(JobType.MR_DASH, "user-1", "panel-foo", "run-1")
    assert len(fired) == 1


@pytest.mark.asyncio
async def test_scheduler_run_job_runs_when_no_provider() -> None:
    """Tests / dev configs that don't install a dept_health_provider must
    still run jobs — no skipping based on a missing health cache."""
    from openlia_server.scheduler.registry import JobType
    from openlia_server.scheduler.service import SchedulerService
    from openlia_server.scheduler.settings import SchedulerSettings

    fired: list[tuple] = []

    class _StubExecutor:
        async def execute(self, **kwargs):
            fired.append(("executed", kwargs))

    class _StubFactory:
        def __call__(self):
            class _C:
                def __enter__(self_inner):
                    return self_inner

                def __exit__(self_inner, *_a):
                    return False

                def commit(self_inner):
                    return None

            return _C()

    svc = SchedulerService(
        session_factory=_StubFactory(),
        scheduler=None,
        settings=SchedulerSettings(enabled=True),
        executors={JobType.MR_DASH: _StubExecutor()},
    )

    await svc._run_job(JobType.MR_DASH, "user-1", "panel-foo", "run-1")
    assert len(fired) == 1
