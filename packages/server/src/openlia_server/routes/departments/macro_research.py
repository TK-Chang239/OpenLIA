"""Macro Research router factory."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from openlia.macro_research.dashboards import DASHBOARDS
from pydantic import BaseModel

from openlia_server.db.models.auth import User
from openlia_server.db.models.scheduler import JobRun
from openlia_server.middleware.auth import build_require_auth
from openlia_server.scheduler.registry import JobStatus, JobType


class DashboardConfigUpdate(BaseModel):
    view_config: dict[str, Any] | None = None
    threshold_overrides: dict[str, Any] | None = None


class ThresholdOverridesUpdate(BaseModel):
    threshold_overrides: dict[str, Any]


class RunAssessmentRequest(BaseModel):
    force: bool = False


def build_macro_research_router(
    *,
    db_session_factory: Callable[[], Any],
    mode: str,
    mr_runner: Any,
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
    def get_dashboard(
        slug: str,
        smart_mode: bool = Query(False),
        user: User = require_auth,
    ) -> dict[str, Any]:
        if slug not in DASHBOARDS:
            raise HTTPException(status_code=404, detail=f"dashboard {slug!r} not found")
        result = mr_runner.run(
            user_id=user.id, dashboard_slug=slug, portfolio=None, smart_mode=smart_mode
        )
        return result.model_dump(mode="json")

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

    @router.post("/dashboards/{slug}/assessment/run", status_code=202)
    async def run_assessment(
        slug: str,
        body: RunAssessmentRequest,
        request: Request,
        user: User = require_auth,
    ) -> dict[str, Any]:
        if slug not in DASHBOARDS:
            raise HTTPException(status_code=404, detail=f"dashboard {slug!r} not found")

        # Pre-allocate a JobRun row so the route can return a real id
        # synchronously and the executor reuses the same row when fired.
        run_id = uuid.uuid4().hex
        with db_session_factory() as session:
            session.add(
                JobRun(
                    id=run_id,
                    user_id=user.id,
                    job_type=JobType.MR_ASSESSMENT.value,
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
            job_type=JobType.MR_ASSESSMENT,
            user_id=user.id,
            schedule_id=slug,
            run_id=run_id,
        )
        return {"job_run_id": run_id, "status": "queued"}

    return router
