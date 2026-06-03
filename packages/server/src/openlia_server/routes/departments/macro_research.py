"""Macro Research router factory."""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from openlia.llm.runtime.report_dash_mr import implemented_dashboard_slugs
from openlia.macro_research.dashboards import DASHBOARDS
from pydantic import BaseModel

from openlia_server.db.models.auth import User
from openlia_server.db.models.dashboard import MrDashboardCache
from openlia_server.db.models.scheduler import JobRun
from openlia_server.middleware.auth import build_require_auth
from openlia_server.routes.dept_health import gate_dept_or_409
from openlia_server.scheduler.registry import JobStatus, JobType
from openlia_server.scheduler.services import jobs as jobs_svc


class DashboardConfigUpdate(BaseModel):
    view_config: dict[str, Any] | None = None
    threshold_overrides: dict[str, Any] | None = None


class ThresholdOverridesUpdate(BaseModel):
    threshold_overrides: dict[str, Any]


_STALE_TTL_SECONDS: dict[str, int] = {"debt_cycle": 24 * 3600}
_DEFAULT_TTL_SECONDS = 24 * 3600

# A re-trigger is rejected while a run for the same dashboard is in flight.
# The window must exceed the worst-case single run (engine time plus the
# executor's transient-retry backoff, ~30 min); a RUNNING row older than this
# is a dead orphan and is ignored so a crash never permanently blocks the
# button.
_RUN_GUARD_STALE_SECONDS = 30 * 60


def _is_stale(slug: str, generated_at: datetime) -> bool:
    ttl = _STALE_TTL_SECONDS.get(slug, _DEFAULT_TTL_SECONDS)
    return (datetime.now(UTC) - generated_at).total_seconds() > ttl


def build_macro_research_router(
    *,
    db_session_factory: Callable[[], Any],
    mode: str,
    dashboard_service: Any,
    require_auth_override: Callable[..., Any] | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/departments/macro_research", tags=["macro_research"])
    if require_auth_override is not None:
        require_auth = Depends(require_auth_override)
    else:
        require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)

    @router.get("/dashboards")
    def list_dashboards(user: User = require_auth) -> dict[str, Any]:
        return {
            "dashboards": [
                {"slug": slug, "display_name": d.display_name} for slug, d in DASHBOARDS.items()
            ]
        }

    @router.get("/dashboards/{slug}")
    def get_dashboard(slug: str, user: User = require_auth) -> dict[str, Any]:
        if slug not in DASHBOARDS:
            raise HTTPException(status_code=404, detail=f"dashboard {slug!r} not found")
        with db_session_factory() as session:
            row = (
                session.query(MrDashboardCache)
                .filter_by(user_id=user.id, dashboard=slug)
                .one_or_none()
            )
        if row is None:
            return {"payload": None, "generated_at": None, "is_stale": True, "provenance": None}
        generated_at = row.generated_at
        if generated_at.tzinfo is None:
            generated_at = generated_at.replace(tzinfo=UTC)
        return {
            "payload": json.loads(row.payload_json),
            "generated_at": generated_at.isoformat(),
            "is_stale": _is_stale(slug, generated_at),
            "provenance": row.provenance,
        }

    @router.get("/dashboards/{slug}/config")
    def get_config(slug: str, user: User = require_auth) -> dict[str, Any]:
        if slug not in DASHBOARDS:
            raise HTTPException(status_code=404, detail=f"dashboard {slug!r} not found")
        row = dashboard_service.get_or_create(user_id=user.id, dashboard=slug)
        return {
            "view_config": row.view_config,
            "threshold_overrides": row.threshold_overrides,
        }

    @router.put("/dashboards/{slug}/config")
    def put_config(
        slug: str,
        body: DashboardConfigUpdate,
        user: User = require_auth,
    ) -> dict[str, Any]:
        if slug not in DASHBOARDS:
            raise HTTPException(status_code=404, detail=f"dashboard {slug!r} not found")
        row = dashboard_service.update_config(
            user_id=user.id,
            dashboard=slug,
            view_config=body.view_config,
            threshold_overrides=body.threshold_overrides,
        )
        return {
            "view_config": row.view_config,
            "threshold_overrides": row.threshold_overrides,
        }

    @router.put("/dashboards/{slug}/threshold-overrides")
    def put_threshold_overrides(
        slug: str,
        body: ThresholdOverridesUpdate,
        user: User = require_auth,
    ) -> dict[str, Any]:
        if slug not in DASHBOARDS:
            raise HTTPException(status_code=404, detail=f"dashboard {slug!r} not found")
        row = dashboard_service.update_config(
            user_id=user.id,
            dashboard=slug,
            view_config=None,
            threshold_overrides=body.threshold_overrides,
        )
        return {
            "view_config": row.view_config,
            "threshold_overrides": row.threshold_overrides,
        }

    @router.post("/dashboards/{slug}/refresh", status_code=202)
    async def refresh_dashboard(
        slug: str,
        request: Request,
        user: User = require_auth,
    ) -> dict[str, Any]:
        gate_dept_or_409(request, "macro_research")
        if slug not in DASHBOARDS:
            raise HTTPException(status_code=404, detail=f"dashboard {slug!r} not found")
        if slug not in implemented_dashboard_slugs():
            raise HTTPException(
                status_code=409,
                detail=f"dashboard {slug!r} is not yet available for generation",
            )

        # Reject a concurrent re-trigger: if a run for this dashboard is
        # already in flight, do not pre-allocate a second row or fire a second
        # (expensive) engine run. The UI disables the button during a run, so
        # this guards rapid double-clicks, multiple tabs, and direct API use.
        not_before = datetime.now(UTC) - timedelta(seconds=_RUN_GUARD_STALE_SECONDS)
        with db_session_factory() as session:
            active = jobs_svc.active_run_for_schedule(
                session,
                user_id=user.id,
                job_type=JobType.MR_DASH,
                schedule_id=slug,
                not_before=not_before,
            )
        if active is not None:
            raise HTTPException(
                status_code=409,
                detail=f"a {slug!r} dashboard run is already in progress",
            )

        # Pre-allocate a JobRun row so the route can return a real id
        # synchronously and the executor reuses the same row when fired.
        run_id = uuid.uuid4().hex
        with db_session_factory() as session:
            session.add(
                JobRun(
                    id=run_id,
                    user_id=user.id,
                    job_type=JobType.MR_DASH.value,
                    schedule_id=slug,
                    status=JobStatus.RUNNING.value,
                    started_at=datetime.now(UTC),
                )
            )
            session.commit()

        scheduler = getattr(request.app.state, "scheduler", None)
        if scheduler is None:
            # Scheduler disabled (e.g. test env without lifespan). Persist
            # the row as cancelled so the caller still gets a meaningful
            # status when polling and we don't leave it RUNNING forever.
            with db_session_factory() as session:
                fresh = session.get(JobRun, run_id)
                if fresh is not None:
                    fresh.status = JobStatus.CANCELLED.value
                    fresh.completed_at = datetime.now(UTC)
                    fresh.error_message = "scheduler disabled"
                    session.commit()
            return {"job_run_id": run_id, "status": "cancelled"}

        await scheduler.run_now(
            job_type=JobType.MR_DASH,
            user_id=user.id,
            schedule_id=slug,
            run_id=run_id,
        )
        return {"job_run_id": run_id, "status": "queued"}

    return router
