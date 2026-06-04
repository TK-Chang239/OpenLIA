"""Retail Sentiment department routes (MR-shaped dashboard engine).

Endpoints mirror Macro Research's dashboard route pattern:
  GET  /dashboard/{ticker}          — latest RsDashboardCache row
  GET  /dashboard/{ticker}/history  — recent cache rows (within N days)
  GET  /config                      — per-user config
  PUT  /config                      — update per-user config
  POST /dashboard/{ticker}/refresh  — enqueue RS_SNAPSHOT job (202)
  GET  /schedule                    — RS cron schedule
  PUT  /schedule                    — upsert RS cron schedule
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.db.models.dashboard import RsDashboardCache
from openlia_server.db.models.scheduler import JobRun
from openlia_server.middleware.auth import build_require_auth
from openlia_server.routes.dept_health import gate_dept_or_409
from openlia_server.scheduler.registry import JobStatus, JobType
from openlia_server.scheduler.services import jobs as jobs_svc
from openlia_server.services import rs_schedules as rs_schedules_svc
from openlia_server.services.rs_config import RsConfigService

_DEFAULT_TTL_SECONDS = 24 * 3600

# Reject a concurrent re-trigger while a run for the same ticker is in flight.
# Rows older than this are treated as dead orphans (crashed mid-run) and ignored.
_RUN_GUARD_STALE_SECONDS = 30 * 60


def _is_stale(generated_at: datetime) -> bool:
    return (datetime.now(UTC) - generated_at).total_seconds() > _DEFAULT_TTL_SECONDS


class _ConfigDTO(BaseModel):
    active_tab: str | None = None
    metric_settings: dict[str, Any] | None = None
    filter_presets: list[Any] | None = None
    refresh_interval_minutes: int | None = None


class _ScheduleIn(BaseModel):
    time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    timezone: str = Field(min_length=3, max_length=64)
    days_of_week: list[Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]] = Field(
        min_length=1
    )
    label: str = Field(default="", max_length=64)
    is_enabled: bool = True


class _ScheduleOut(BaseModel):
    id: str
    time: str
    timezone: str
    days_of_week: list[str]
    label: str
    is_enabled: bool


def _config_out(cfg: Any) -> dict[str, Any]:
    return {
        "id": cfg.id,
        "user_id": cfg.user_id,
        "active_tab": cfg.active_tab,
        "metric_settings": cfg.metric_settings,
        "filter_presets": cfg.filter_presets,
        "refresh_interval_minutes": cfg.refresh_interval_minutes,
    }


def _optional_scheduler(request: Request) -> Any:
    return getattr(request.app.state, "scheduler", None)


def build_retail_sentiment_router(
    *,
    db_session_factory: Callable[[], Any],
    mode: str,
    require_auth_override: Callable[..., Any] | None = None,
) -> APIRouter:
    router = APIRouter(prefix="/departments/retail_sentiment", tags=["retail_sentiment"])

    if require_auth_override is not None:
        require_auth = Depends(require_auth_override)
    else:
        require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)

    session_dep = make_session_dependency(db_session_factory)

    def _config_svc() -> RsConfigService:
        return RsConfigService(session_factory=db_session_factory)

    # ------------------------------------------------------------------
    # GET /dashboard/{ticker}
    # ------------------------------------------------------------------

    @router.get("/dashboard/{ticker}")
    def get_dashboard(ticker: str, user: User = require_auth) -> dict[str, Any]:
        with db_session_factory() as session:
            row = (
                session.query(RsDashboardCache)
                .filter(
                    RsDashboardCache.user_id == user.id,
                    RsDashboardCache.ticker == ticker,
                )
                .order_by(RsDashboardCache.generated_at.desc())
                .first()
            )
        if row is None:
            return {"payload": None, "generated_at": None, "is_stale": True, "provenance": None}
        generated_at = row.generated_at
        if generated_at.tzinfo is None:
            generated_at = generated_at.replace(tzinfo=UTC)
        return {
            "payload": json.loads(row.payload_json),
            "generated_at": generated_at.isoformat(),
            "is_stale": _is_stale(generated_at),
            "provenance": row.provenance,
        }

    # ------------------------------------------------------------------
    # GET /dashboard/{ticker}/history
    # ------------------------------------------------------------------

    @router.get("/dashboard/{ticker}/history")
    def get_history(
        ticker: str,
        days: int = 7,
        user: User = require_auth,
    ) -> list[dict[str, Any]]:
        cutoff = datetime.now(UTC) - timedelta(days=days)
        with db_session_factory() as session:
            rows = (
                session.query(RsDashboardCache)
                .filter(
                    RsDashboardCache.user_id == user.id,
                    RsDashboardCache.ticker == ticker,
                    RsDashboardCache.generated_at >= cutoff,
                )
                .order_by(RsDashboardCache.generated_at.desc())
                .all()
            )
        result: list[dict[str, Any]] = []
        for row in rows:
            generated_at = row.generated_at
            if generated_at.tzinfo is None:
                generated_at = generated_at.replace(tzinfo=UTC)
            result.append(
                {
                    "payload": json.loads(row.payload_json),
                    "generated_at": generated_at.isoformat(),
                }
            )
        return result

    # ------------------------------------------------------------------
    # GET /config
    # ------------------------------------------------------------------

    @router.get("/config")
    def get_config(user: User = require_auth) -> dict[str, Any]:
        return _config_out(_config_svc().get_or_create(user.id))

    # ------------------------------------------------------------------
    # PUT /config
    # ------------------------------------------------------------------

    @router.put("/config")
    def put_config(payload: _ConfigDTO, user: User = require_auth) -> dict[str, Any]:
        try:
            cfg = _config_svc().update(
                user.id,
                active_tab=payload.active_tab,
                metric_settings=payload.metric_settings,
                filter_presets=payload.filter_presets,
                refresh_interval_minutes=payload.refresh_interval_minutes,
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        return _config_out(cfg)

    # ------------------------------------------------------------------
    # POST /dashboard/{ticker}/refresh
    # ------------------------------------------------------------------

    @router.post("/dashboard/{ticker}/refresh", status_code=202)
    async def refresh_dashboard(
        ticker: str,
        request: Request,
        user: User = require_auth,
    ) -> dict[str, Any]:
        gate_dept_or_409(request, "retail_sentiment")

        if not ticker or not ticker.strip():
            raise HTTPException(status_code=404, detail="ticker is required")

        not_before = datetime.now(UTC) - timedelta(seconds=_RUN_GUARD_STALE_SECONDS)
        with db_session_factory() as session:
            active = jobs_svc.active_run_for_schedule(
                session,
                user_id=user.id,
                job_type=JobType.RS_SNAPSHOT,
                schedule_id=ticker,
                not_before=not_before,
            )
        if active is not None:
            raise HTTPException(
                status_code=409,
                detail=f"a {ticker!r} dashboard run is already in progress",
            )

        run_id = uuid.uuid4().hex
        with db_session_factory() as session:
            session.add(
                JobRun(
                    id=run_id,
                    user_id=user.id,
                    job_type=JobType.RS_SNAPSHOT.value,
                    schedule_id=ticker,
                    status=JobStatus.RUNNING.value,
                    started_at=datetime.now(UTC),
                )
            )
            session.commit()

        scheduler = getattr(request.app.state, "scheduler", None)
        if scheduler is None:
            with db_session_factory() as session:
                fresh = session.get(JobRun, run_id)
                if fresh is not None:
                    fresh.status = JobStatus.CANCELLED.value
                    fresh.completed_at = datetime.now(UTC)
                    fresh.error_message = "scheduler disabled"
                    session.commit()
            return {"job_run_id": run_id, "status": "cancelled"}

        await scheduler.run_now(
            job_type=JobType.RS_SNAPSHOT,
            user_id=user.id,
            schedule_id=ticker,
            run_id=run_id,
        )
        return {"job_run_id": run_id, "status": "queued"}

    # ------------------------------------------------------------------
    # GET /schedule
    # ------------------------------------------------------------------

    @router.get("/schedule")
    def get_schedule(
        user: User = require_auth,
        db: DBSession = Depends(session_dep),
    ) -> dict[str, Any]:
        dto = rs_schedules_svc.get_schedule(db, user_id=user.id)
        if dto is None:
            return {"schedule": None}
        return {
            "schedule": _ScheduleOut(
                id=dto.id,
                time=dto.time,
                timezone=dto.timezone,
                days_of_week=list(dto.days_of_week),
                label=dto.label,
                is_enabled=dto.is_enabled,
            ).model_dump()
        }

    # ------------------------------------------------------------------
    # PUT /schedule
    # ------------------------------------------------------------------

    @router.put("/schedule", response_model=_ScheduleOut)
    async def put_schedule(
        payload: _ScheduleIn,
        user: User = require_auth,
        db: DBSession = Depends(session_dep),
        scheduler: Any = Depends(_optional_scheduler),
    ) -> _ScheduleOut:
        if scheduler is None:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "scheduler not initialized")
        try:
            dto = await rs_schedules_svc.upsert_schedule(
                db,
                user_id=user.id,
                time=payload.time,
                timezone=payload.timezone,
                days_of_week=list(payload.days_of_week),
                label=payload.label,
                is_enabled=payload.is_enabled,
                scheduler=scheduler,
            )
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
        return _ScheduleOut(
            id=dto.id,
            time=dto.time,
            timezone=dto.timezone,
            days_of_week=list(dto.days_of_week),
            label=dto.label,
            is_enabled=dto.is_enabled,
        )

    return router
