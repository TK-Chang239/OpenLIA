"""Morning Briefing HTTP routes.

Factory-style router exposing config, schedule, on-demand report, and chat
session endpoints under `/departments/morning-briefing`.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from openlia.llm.runtime.events import to_wire
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.db.models.content import ChatSession
from openlia_server.middleware.auth import build_require_auth
from openlia_server.services import mb_config as config_svc
from openlia_server.services import mb_runner
from openlia_server.services import mb_schedules as schedules_svc


def _scheduler_dep(request: Request):
    scheduler = getattr(request.app.state, "scheduler", None)
    if scheduler is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "scheduler not initialized"
        )
    return scheduler


def _report_runner_dep(request: Request):
    runner = getattr(request.app.state, "report_runner", None)
    if runner is None:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, "report runner not initialized"
        )
    return runner


class _TopicIn(BaseModel):
    topic: str = Field(min_length=1, max_length=128)
    notes: str = Field(default="", max_length=2000)


class _CustomSectionIn(BaseModel):
    id: str = Field(min_length=1, max_length=64)
    title: str = Field(min_length=1, max_length=256)
    description: str = Field(default="", max_length=2000)


class _ConfigIn(BaseModel):
    report_length: Literal["concise", "normal", "elaborative"]
    enabled_section_ids: list[str]
    section_topics: dict[str, list[_TopicIn]]
    custom_sections: list[_CustomSectionIn]
    reference_portfolio: bool = False


class _ConfigOut(BaseModel):
    report_length: str
    enabled_section_ids: list[str]
    section_topics: dict[str, list[dict]]
    custom_sections: list[dict]
    reference_portfolio: bool


class _ScheduleIn(BaseModel):
    time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    timezone: str = Field(min_length=3, max_length=64)
    days_of_week: list[
        Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
    ] = Field(min_length=1)
    label: str = Field(default="", max_length=64)


class _ScheduleOut(BaseModel):
    id: str
    time: str
    timezone: str
    days_of_week: list[str]
    label: str
    is_enabled: bool


class _ReportIn(BaseModel):
    user_input: str = Field(default="", max_length=4000)
    session_id: str | None = None


class _ChatSessionOut(BaseModel):
    session_id: str


def build_morning_briefing_router(
    *,
    db_session_factory: Callable[[], DBSession],
    mode: Literal["personal", "company"],
) -> APIRouter:
    router = APIRouter(
        prefix="/departments/morning-briefing", tags=["morning-briefing"]
    )
    require_auth = build_require_auth(
        db_session_factory=db_session_factory, mode=mode
    )
    session_dep = make_session_dependency(db_session_factory)

    # ----- Config -----

    @router.get("/config", response_model=_ConfigOut)
    def get_config(
        user: User = require_auth,
        db: DBSession = Depends(session_dep),
    ) -> _ConfigOut:
        cfg = config_svc.get_config(db, user_id=user.id)
        return _ConfigOut(
            report_length=cfg.report_length,
            enabled_section_ids=list(cfg.enabled_section_ids),
            section_topics=dict(cfg.section_topics),
            custom_sections=list(cfg.custom_sections),
            reference_portfolio=bool(cfg.reference_portfolio),
        )

    @router.put("/config", response_model=_ConfigOut)
    def put_config(
        payload: _ConfigIn,
        user: User = require_auth,
        db: DBSession = Depends(session_dep),
    ) -> _ConfigOut:
        try:
            cfg = config_svc.update_config(
                db,
                user_id=user.id,
                report_length=payload.report_length,
                enabled_section_ids=list(payload.enabled_section_ids),
                section_topics={
                    sid: [t.model_dump() for t in topics]
                    for sid, topics in payload.section_topics.items()
                },
                custom_sections=[cs.model_dump() for cs in payload.custom_sections],
                reference_portfolio=bool(payload.reference_portfolio),
            )
        except ValueError as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)
            ) from exc
        return _ConfigOut(
            report_length=cfg.report_length,
            enabled_section_ids=list(cfg.enabled_section_ids),
            section_topics=dict(cfg.section_topics),
            custom_sections=list(cfg.custom_sections),
            reference_portfolio=bool(cfg.reference_portfolio),
        )

    # ----- Schedule -----

    @router.get("/schedule")
    def get_schedule(
        user: User = require_auth,
        db: DBSession = Depends(session_dep),
    ) -> _ScheduleOut | None:
        dto = schedules_svc.get_schedule(db, user_id=user.id)
        if dto is None:
            return None
        return _ScheduleOut(
            id=dto.id,
            time=dto.time,
            timezone=dto.timezone,
            days_of_week=list(dto.days_of_week),
            label=dto.label,
            is_enabled=dto.is_enabled,
        )

    @router.put("/schedule", response_model=_ScheduleOut)
    async def put_schedule(
        payload: _ScheduleIn,
        user: User = require_auth,
        db: DBSession = Depends(session_dep),
        scheduler=Depends(_scheduler_dep),
    ) -> _ScheduleOut:
        try:
            dto = await schedules_svc.upsert_schedule(
                db,
                user_id=user.id,
                time=payload.time,
                timezone=payload.timezone,
                days_of_week=list(payload.days_of_week),
                label=payload.label,
                scheduler=scheduler,
            )
        except ValueError as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)
            ) from exc
        return _ScheduleOut(
            id=dto.id,
            time=dto.time,
            timezone=dto.timezone,
            days_of_week=list(dto.days_of_week),
            label=dto.label,
            is_enabled=dto.is_enabled,
        )

    @router.delete("/schedule", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_schedule(
        user: User = require_auth,
        db: DBSession = Depends(session_dep),
        scheduler=Depends(_scheduler_dep),
    ) -> None:
        await schedules_svc.delete_schedule(
            db, user_id=user.id, scheduler=scheduler
        )

    # ----- On-demand report (SSE, named events) -----

    @router.post("/report")
    async def generate_report(
        payload: _ReportIn,
        request: Request,
        user: User = require_auth,
        db: DBSession = Depends(session_dep),
        runner=Depends(_report_runner_dep),
    ) -> StreamingResponse:
        user_id = user.id

        async def gen() -> AsyncIterator[bytes]:
            try:
                async for event in mb_runner.run_on_demand(
                    session=db,
                    user_id=user_id,
                    report_runner=runner,
                ):
                    if await request.is_disconnected():
                        break
                    if isinstance(event, mb_runner.ReportSavedEvent):
                        wire = {
                            "type": "report.saved",
                            "report_id": event.report_id,
                        }
                    else:
                        wire = to_wire(event)
                    yield (
                        f"event: {wire['type']}\ndata: {json.dumps(wire)}\n\n"
                    ).encode()
            except ValueError as exc:
                error_payload = {"type": "report.error", "message": str(exc)}
                yield (
                    f"event: report.error\ndata: {json.dumps(error_payload)}\n\n"
                ).encode()

        return StreamingResponse(
            gen(),
            media_type="text/event-stream",
            headers={"cache-control": "no-cache", "x-accel-buffering": "no"},
        )

    # ----- Chat session resolve-or-create -----

    @router.post("/chat/session", response_model=_ChatSessionOut)
    def resolve_or_create_chat_session(
        user: User = require_auth,
        db: DBSession = Depends(session_dep),
    ) -> _ChatSessionOut:
        import uuid

        existing = (
            db.query(ChatSession)
            .filter_by(user_id=user.id, department="morning_briefing")
            .order_by(ChatSession.updated_at.desc())
            .first()
        )
        if existing is not None:
            return _ChatSessionOut(session_id=existing.id)
        sid = str(uuid.uuid4())
        db.add(
            ChatSession(
                id=sid,
                user_id=user.id,
                department="morning_briefing",
                title="Morning Briefing",
            )
        )
        db.commit()
        return _ChatSessionOut(session_id=sid)

    return router
