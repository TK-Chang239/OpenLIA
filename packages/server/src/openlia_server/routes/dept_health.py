"""GET /api/dept-health endpoint (Phase 10 Task 10.3).

Reads the cached `app.state.dept_health: dict[str, DepartmentHealth]` and
serializes it as a JSON list. The cache is populated at startup and
refreshed on every connector / spec mutation by `dept_health` service
hooks installed in `connectors_service` and `runner_specs_service`.
"""

from __future__ import annotations

from fastapi import APIRouter, Request

from openlia_server.services.dept_health import serialize


def build_dept_health_router() -> APIRouter:
    router = APIRouter(prefix="/dept-health", tags=["dept-health"])

    @router.get("", response_model=list[dict])
    def list_dept_health(request: Request) -> list[dict]:
        cache: dict = getattr(request.app.state, "dept_health", {}) or {}
        return [serialize(h) for h in cache.values()]

    return router
