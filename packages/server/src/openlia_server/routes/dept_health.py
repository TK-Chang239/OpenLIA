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

from fastapi import APIRouter, HTTPException, Request

from openlia_server.services.dept_health import is_disabled, serialize


def build_dept_health_router() -> APIRouter:
    router = APIRouter(prefix="/dept-health", tags=["dept-health"])

    @router.get("", response_model=list[dict])
    def list_dept_health(request: Request) -> list[dict]:
        cache: dict = getattr(request.app.state, "dept_health", {}) or {}
        return [serialize(h) for h in cache.values()]

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
