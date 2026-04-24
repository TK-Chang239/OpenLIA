"""Macro Research router factory."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from openlia.macro_research.dashboards import DASHBOARDS
from pydantic import BaseModel

from openlia_server.db.models.auth import User
from openlia_server.middleware.auth import build_require_auth


class DashboardConfigUpdate(BaseModel):
    view_config: dict[str, Any] | None = None
    threshold_overrides: dict[str, Any] | None = None


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
    def get_dashboard(slug: str, user: User = require_auth) -> dict[str, Any]:
        if slug not in DASHBOARDS:
            raise HTTPException(status_code=404, detail=f"dashboard {slug!r} not found")
        result = mr_runner.run(
            user_id=user.id, dashboard_slug=slug, portfolio=None, smart_mode=False
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

    @router.post("/dashboards/{slug}/assessment/run", status_code=202)
    def run_assessment(
        slug: str,
        body: RunAssessmentRequest,
        user: User = require_auth,
    ) -> dict[str, Any]:
        if slug not in DASHBOARDS:
            raise HTTPException(status_code=404, detail=f"dashboard {slug!r} not found")
        job_run_id = str(uuid.uuid4())
        return {"job_run_id": job_run_id, "status": "queued"}

    return router
