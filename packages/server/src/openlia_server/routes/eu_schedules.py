"""EU schedule CRUD routes with APScheduler hot-reload."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.models.auth import User
from openlia_server.db.models.scheduler import EuSchedule
from openlia_server.middleware.auth import build_require_active_user
from openlia_server.scheduler.registry import JobType


class EuScheduleIn(BaseModel):
    time: str = Field(pattern=r"^\d{2}:\d{2}$")
    timezone: str
    days_of_week: list[int]
    label: str | None = None
    is_enabled: bool = True


class EuScheduleOut(BaseModel):
    id: str
    user_id: str
    time: str
    timezone: str
    days_of_week: list[int]
    label: str | None
    is_enabled: bool
    created_at: datetime
    last_run_at: datetime | None


def _require_scheduler(request: Request) -> Any:
    svc = getattr(request.app.state, "scheduler", None)
    if svc is None:
        raise HTTPException(
            status_code=503,
            detail="scheduler is disabled; scheduler-backed actions are unavailable",
        )
    return svc


def _row_to_out(row: EuSchedule) -> EuScheduleOut:
    return EuScheduleOut(
        id=row.id,
        user_id=row.user_id,
        time=row.time,
        timezone=row.timezone,
        days_of_week=json.loads(row.days_of_week),
        label=row.label,
        is_enabled=row.is_enabled,
        created_at=row.created_at,
        last_run_at=row.last_run_at,
    )


def build_eu_schedules_router(
    *,
    db_session_factory: Callable[[], DBSession],
    mode: Literal["personal", "company"],
) -> APIRouter:
    require_auth = build_require_active_user(db_session_factory=db_session_factory, mode=mode)
    router = APIRouter(prefix="/departments/earnings-update/schedules", tags=["eu-schedules"])

    @router.post("", response_model=EuScheduleOut, status_code=201)
    async def create_schedule(
        body: EuScheduleIn,
        request: Request,
        user: User = require_auth,
    ) -> EuScheduleOut:
        svc = _require_scheduler(request)
        with db_session_factory() as session:
            row = EuSchedule(
                id=str(uuid4()),
                user_id=user.id,
                time=body.time,
                timezone=body.timezone,
                days_of_week=json.dumps(body.days_of_week),
                label=body.label,
                is_enabled=body.is_enabled,
                created_at=datetime.now(UTC),
            )
            session.add(row)
            session.commit()
            session.expunge(row)
        if row.is_enabled:
            await svc.add_schedule(row)
        return _row_to_out(row)

    @router.patch("/{schedule_id}", response_model=EuScheduleOut)
    async def update_schedule(
        schedule_id: str,
        body: EuScheduleIn,
        request: Request,
        user: User = require_auth,
    ) -> EuScheduleOut:
        svc = _require_scheduler(request)
        with db_session_factory() as session:
            row = session.get(EuSchedule, schedule_id)
            if row is None or row.user_id != user.id:
                raise HTTPException(status_code=404, detail="schedule not found")
            row.time = body.time
            row.timezone = body.timezone
            row.days_of_week = json.dumps(body.days_of_week)
            row.label = body.label
            row.is_enabled = body.is_enabled
            session.commit()
            session.expunge(row)
        if row.is_enabled:
            await svc.modify_schedule(row)
        else:
            await svc.remove_schedule(job_type=JobType.EU_SCAN, user_id=row.user_id)
        return _row_to_out(row)

    @router.delete("/{schedule_id}")
    async def delete_schedule(
        schedule_id: str,
        request: Request,
        user: User = require_auth,
    ) -> dict[str, str]:
        svc = _require_scheduler(request)
        with db_session_factory() as session:
            row = session.get(EuSchedule, schedule_id)
            if row is None or row.user_id != user.id:
                raise HTTPException(status_code=404, detail="schedule not found")
            user_id = row.user_id
            session.delete(row)
            session.commit()
        await svc.remove_schedule(job_type=JobType.EU_SCAN, user_id=user_id)
        return {"deleted": schedule_id}

    @router.get("", response_model=list[EuScheduleOut])
    def list_schedules(
        user: User = require_auth,
    ) -> list[EuScheduleOut]:
        with db_session_factory() as session:
            rows = session.query(EuSchedule).filter(EuSchedule.user_id == user.id).all()
            return [_row_to_out(row) for row in rows]

    return router
