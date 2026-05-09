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
from openlia_server.middleware.auth import build_require_auth
from openlia_server.services import mb_config as config_svc
from openlia_server.services import mb_runner
from openlia_server.services import mb_schedules as schedules_svc


def _optional_scheduler(request: Request):
    return getattr(request.app.state, "scheduler", None)


def _report_runner_dep(request: Request):
    runner = getattr(request.app.state, "report_runner", None)
    if runner is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "report runner not initialized")
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
    days_of_week: list[Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]] = Field(
        min_length=1
    )
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
    # Per-run overrides — when present, replace the corresponding saved-config
    # field for this single manual run only. None means "use saved config."
    report_length: Literal["concise", "normal", "elaborative"] | None = None
    enabled_section_ids: list[str] | None = None
    section_topics: dict[str, list[_TopicIn]] | None = None
    custom_sections: list[_CustomSectionIn] | None = None
    reference_portfolio: bool | None = None


def build_morning_briefing_router(
    *,
    db_session_factory: Callable[[], DBSession],
    mode: Literal["personal", "company"],
) -> APIRouter:
    router = APIRouter(prefix="/departments/morning-briefing", tags=["morning-briefing"])
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
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
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
        return _ConfigOut(
            report_length=cfg.report_length,
            enabled_section_ids=list(cfg.enabled_section_ids),
            section_topics=dict(cfg.section_topics),
            custom_sections=list(cfg.custom_sections),
            reference_portfolio=bool(cfg.reference_portfolio),
        )

    # ----- Schedules (multiple per user) -----

    def _dto_to_out(dto: schedules_svc.MbScheduleDTO) -> _ScheduleOut:
        return _ScheduleOut(
            id=dto.id,
            time=dto.time,
            timezone=dto.timezone,
            days_of_week=list(dto.days_of_week),
            label=dto.label,
            is_enabled=dto.is_enabled,
        )

    @router.get("/schedules", response_model=list[_ScheduleOut])
    def list_schedules(
        user: User = require_auth,
        db: DBSession = Depends(session_dep),
    ) -> list[_ScheduleOut]:
        return [_dto_to_out(d) for d in schedules_svc.list_schedules(db, user_id=user.id)]

    @router.post(
        "/schedules",
        response_model=_ScheduleOut,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_schedule(
        payload: _ScheduleIn,
        user: User = require_auth,
        db: DBSession = Depends(session_dep),
        scheduler=Depends(_optional_scheduler),
    ) -> _ScheduleOut:
        if scheduler is None:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "scheduler not initialized")
        try:
            dto = await schedules_svc.create_schedule(
                db,
                user_id=user.id,
                time=payload.time,
                timezone=payload.timezone,
                days_of_week=list(payload.days_of_week),
                label=payload.label,
                scheduler=scheduler,
            )
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
        return _dto_to_out(dto)

    @router.patch("/schedules/{schedule_id}", response_model=_ScheduleOut)
    async def update_schedule(
        schedule_id: str,
        payload: _ScheduleIn,
        user: User = require_auth,
        db: DBSession = Depends(session_dep),
        scheduler=Depends(_optional_scheduler),
    ) -> _ScheduleOut:
        if scheduler is None:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "scheduler not initialized")
        try:
            dto = await schedules_svc.update_schedule(
                db,
                user_id=user.id,
                schedule_id=schedule_id,
                time=payload.time,
                timezone=payload.timezone,
                days_of_week=list(payload.days_of_week),
                label=payload.label,
                scheduler=scheduler,
            )
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
        if dto is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "schedule not found")
        return _dto_to_out(dto)

    @router.delete("/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_schedule(
        schedule_id: str,
        user: User = require_auth,
        db: DBSession = Depends(session_dep),
        scheduler=Depends(_optional_scheduler),
    ) -> None:
        if scheduler is None:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "scheduler not initialized")
        deleted = await schedules_svc.delete_schedule(
            db, user_id=user.id, schedule_id=schedule_id, scheduler=scheduler
        )
        if not deleted:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "schedule not found")

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

        from openlia.llm.runtime.cancellation import CancellationToken

        cancel_token = CancellationToken()

        overrides: config_svc.MbConfigOverrides | None = None
        any_override = (
            payload.report_length is not None
            or payload.enabled_section_ids is not None
            or payload.section_topics is not None
            or payload.custom_sections is not None
            or payload.reference_portfolio is not None
        )
        if any_override:
            try:
                overrides = config_svc.MbConfigOverrides(
                    report_length=payload.report_length,
                    enabled_section_ids=list(payload.enabled_section_ids)
                    if payload.enabled_section_ids is not None
                    else None,
                    section_topics={
                        sid: [t.model_dump() for t in topics]
                        for sid, topics in payload.section_topics.items()
                    }
                    if payload.section_topics is not None
                    else None,
                    custom_sections=[cs.model_dump() for cs in payload.custom_sections]
                    if payload.custom_sections is not None
                    else None,
                    reference_portfolio=payload.reference_portfolio,
                )
            except ValueError as exc:
                raise HTTPException(
                    status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)
                ) from exc

        async def gen() -> AsyncIterator[bytes]:
            try:
                async for event in mb_runner.run_on_demand(
                    session=db,
                    user_id=user_id,
                    report_runner=runner,
                    cancel_token=cancel_token,
                    overrides=overrides,
                ):
                    if await request.is_disconnected():
                        cancel_token.cancel()
                        break
                    if isinstance(event, mb_runner.ReportSavedEvent):
                        wire = {
                            "type": "report.saved",
                            "report_id": event.report_id,
                        }
                    else:
                        wire = to_wire(event)
                    yield (f"event: {wire['type']}\ndata: {json.dumps(wire)}\n\n").encode()
            except ValueError as exc:
                error_payload = {"type": "report.error", "message": str(exc)}
                yield (f"event: report.error\ndata: {json.dumps(error_payload)}\n\n").encode()

        return StreamingResponse(
            gen(),
            media_type="text/event-stream",
            headers={"cache-control": "no-cache", "x-accel-buffering": "no"},
        )

    return router
