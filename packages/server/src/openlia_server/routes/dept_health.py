"""GET /api/dept-health endpoint + 409-gate helper (Phase 10 Task 10.3).

Reads the cached `app.state.dept_health: dict[str, DepartmentHealth]` and
serializes it as a JSON list. The cache is populated at startup and
refreshed on every connector / spec mutation by `dept_health` service
hooks installed in `connectors_service` and `runner_specs_service`.

`gate_dept_or_409` is the per-handler short-circuit: route code calls it
before processing a mutating dept request. When the dept is disabled it
raises an `HTTPException(409, ...)` whose body matches the contract
`{"error": "dept_disabled", "reason": ...}`.
"""

from __future__ import annotations

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.deps import make_session_dependency
from openlia_server.services.dept_health import compute_all, is_disabled, serialize


def build_dept_health_router(
    *,
    db_session_factory: Callable[[], DBSession] | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/dept-health", tags=["dept-health"])

    @router.get("", response_model=list[dict])
    def list_dept_health(request: Request) -> list[dict]:
        cache: dict = getattr(request.app.state, "dept_health", {}) or {}
        return [serialize(h) for h in cache.values()]

    if db_session_factory is not None:
        session_dep = make_session_dependency(db_session_factory)

        @router.post("/refresh", response_model=list[dict])
        def refresh_dept_health(
            request: Request, db: DBSession = Depends(session_dep)
        ) -> list[dict]:
            request.app.state.dept_health = compute_all(db)
            return [serialize(h) for h in request.app.state.dept_health.values()]

    return router


def gate_dept_or_409(request: Request, dept_id: str) -> None:
    """Raise HTTP 409 when `dept_id` is currently disabled.

    No-op when the cache is missing or the dept entry is absent so tests
    that bypass the lifespan keep working.
    """
    cache: dict = getattr(request.app.state, "dept_health", {}) or {}
    disabled, reason = is_disabled(cache, dept_id)
    if disabled:
        raise HTTPException(
            status_code=409,
            detail={"error": "dept_disabled", "reason": reason or ""},
        )
