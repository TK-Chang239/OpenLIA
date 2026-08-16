"""Earnings Update HTTP routes.

Factory-style router exposing watchlist, config, schedules, on-demand report,
and recent reports endpoints under `/departments/earnings-update`.
"""

from __future__ import annotations

import json
import re
import zoneinfo
from collections.abc import AsyncIterator, Callable
from datetime import UTC, date, datetime
from typing import Any, Literal
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from openlia.llm.runtime.cancellation import CancellationToken
from openlia.llm.runtime.events import to_wire
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.db.models.content import Report
from openlia_server.db.models.scheduler import EuSchedule
from openlia_server.middleware.auth import build_require_active_user
from openlia_server.scheduler.registry import JobType
from openlia_server.services import eu_config as config_svc
from openlia_server.services import eu_runner
from openlia_server.services import eu_watchlist as watchlist_svc

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")
_VALID_DAY_INTS: frozenset[int] = frozenset({0, 1, 2, 3, 4, 5, 6})


def _earnings_adapter_dep(request: Request):
    adapter = getattr(request.app.state, "earnings_adapter", None)
    if adapter is None:
        raise HTTPException(
            status.HTTP_500_INTERNAL_SERVER_ERROR, "earnings adapter not configured"
        )
    return adapter


def _report_runner_dep(request: Request):
    runner = getattr(request.app.state, "report_runner", None)
    if runner is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "report runner not initialized")
    return runner


def _require_scheduler(request: Request) -> Any:
    svc = getattr(request.app.state, "scheduler", None)
    if svc is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="scheduler is disabled; scheduler-backed actions are unavailable",
        )
    return svc


class _WatchlistEntryOut(BaseModel):
    id: str
    ticker: str
    company_name: str
    next_earnings_date: date | None
    release_timing: str | None


class _WatchlistListOut(BaseModel):
    entries: list[_WatchlistEntryOut]


class _AddEntryIn(BaseModel):
    ticker: str = Field(min_length=1, max_length=16)


class _CustomSectionIn(BaseModel):
    id: str = Field(min_length=1, max_length=128)
    title: str = Field(min_length=1, max_length=256)
    description: str = Field(default="", max_length=2000)


class _ConfigIn(BaseModel):
    report_length: Literal["concise", "normal", "elaborative"]
    enabled_section_ids: list[str]
    custom_sections: list[_CustomSectionIn]


class _ConfigOut(BaseModel):
    report_length: str
    enabled_section_ids: list[str]
    custom_sections: list[dict]


class _ReportIn(BaseModel):
    ticker: str = Field(min_length=1, max_length=16)


class _RecentReportOut(BaseModel):
    id: str
    title: str
    subject: str | None
    report_type: str
    created_at: str


class _ReportsListOut(BaseModel):
    reports: list[_RecentReportOut]


class _EuScheduleIn(BaseModel):
    time: str = Field(pattern=r"^\d{2}:\d{2}$")
    timezone: str
    days_of_week: list[int]
    label: str | None = None
    is_enabled: bool = True


class _EuScheduleOut(BaseModel):
    id: str
    user_id: str
    time: str
    timezone: str
    days_of_week: list[int]
    label: str | None
    is_enabled: bool
    created_at: datetime
    last_run_at: datetime | None


def _validate_schedule_input(body: _EuScheduleIn) -> None:
    if not _TIME_RE.match(body.time):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"invalid time: {body.time!r}",
        )
    try:
        zoneinfo.ZoneInfo(body.timezone)
    except Exception as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"invalid timezone: {body.timezone!r}",
        ) from exc
    if not body.days_of_week:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "days_of_week must be non-empty",
        )
    bad = [d for d in body.days_of_week if d not in _VALID_DAY_INTS]
    if bad:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            f"invalid days_of_week: {bad!r}",
        )


def _row_to_schedule_out(row: EuSchedule) -> _EuScheduleOut:
    return _EuScheduleOut(
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


def build_earnings_update_router(
    *,
    db_session_factory: Callable[[], DBSession],
    mode: Literal["personal", "company"],
) -> APIRouter:
    router = APIRouter(prefix="/departments/earnings-update", tags=["earnings-update"])
    require_auth = build_require_active_user(db_session_factory=db_session_factory, mode=mode)
    session_dep = make_session_dependency(db_session_factory)

    # ----- Watchlist -----

    @router.get("/watchlist", response_model=_WatchlistListOut)
    def get_watchlist(
        user: User = require_auth,
        db: DBSession = Depends(session_dep),
    ) -> _WatchlistListOut:
        entries = watchlist_svc.list_entries(db, user_id=user.id)
        return _WatchlistListOut(
            entries=[
                _WatchlistEntryOut(
                    id=e.id,
                    ticker=e.ticker,
                    company_name=e.company_name,
                    next_earnings_date=e.next_earnings_date,
                    release_timing=e.release_timing,
                )
                for e in entries
            ]
        )

    @router.post(
        "/watchlist",
        status_code=status.HTTP_201_CREATED,
        response_model=_WatchlistEntryOut,
    )
    def add_to_watchlist(
        payload: _AddEntryIn,
        user: User = require_auth,
        db: DBSession = Depends(session_dep),
        adapter=Depends(_earnings_adapter_dep),
    ) -> _WatchlistEntryOut:
        try:
            entry = watchlist_svc.add_entry(
                db, user_id=user.id, ticker=payload.ticker, adapter=adapter
            )
        except watchlist_svc.AlreadyOnWatchlistError as exc:
            raise HTTPException(status.HTTP_409_CONFLICT, "already on watchlist") from exc
        except watchlist_svc.TickerNotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "ticker not found") from exc
        return _WatchlistEntryOut(
            id=entry.id,
            ticker=entry.ticker,
            company_name=entry.company_name,
            next_earnings_date=entry.next_earnings_date,
            release_timing=entry.release_timing,
        )

    @router.delete("/watchlist/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
    def remove_from_watchlist(
        entry_id: str,
        user: User = require_auth,
        db: DBSession = Depends(session_dep),
    ) -> None:
        try:
            watchlist_svc.remove_entry(db, user_id=user.id, entry_id=entry_id)
        except watchlist_svc.WatchlistEntryNotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "not found") from exc

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
            custom_sections=list(cfg.custom_sections),
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
                custom_sections=[section.model_dump() for section in payload.custom_sections],
            )
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
        return _ConfigOut(
            report_length=cfg.report_length,
            enabled_section_ids=list(cfg.enabled_section_ids),
            custom_sections=list(cfg.custom_sections),
        )

    # ----- Schedules -----

    @router.get("/schedules", response_model=list[_EuScheduleOut])
    def list_schedules(
        user: User = require_auth,
    ) -> list[_EuScheduleOut]:
        with db_session_factory() as session:
            rows = (
                session.query(EuSchedule)
                .filter(EuSchedule.user_id == user.id)
                .order_by(EuSchedule.time)
                .all()
            )
            return [_row_to_schedule_out(row) for row in rows]

    @router.post("/schedules", response_model=_EuScheduleOut, status_code=201)
    async def create_schedule(
        body: _EuScheduleIn,
        request: Request,
        user: User = require_auth,
    ) -> _EuScheduleOut:
        _validate_schedule_input(body)
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
        return _row_to_schedule_out(row)

    @router.patch("/schedules/{schedule_id}", response_model=_EuScheduleOut)
    async def update_schedule(
        schedule_id: str,
        body: _EuScheduleIn,
        request: Request,
        user: User = require_auth,
    ) -> _EuScheduleOut:
        _validate_schedule_input(body)
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
        return _row_to_schedule_out(row)

    @router.delete("/schedules/{schedule_id}")
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

    # ----- On-demand report + recent reports -----

    # NOTE: This endpoint intentionally does NOT use Depends(_earnings_adapter_dep).
    # The on-demand runner relies on the report runner's own tool-call loop to
    # pull earnings data via the data-provider tools registered in app.state, so
    # we don't need a typed earnings adapter at this layer. The adapter is only
    # required by the synchronous /watchlist POST flow above (which writes the
    # next_earnings_date snapshot directly).
    @router.post("/report")
    async def generate_report(
        payload: _ReportIn,
        request: Request,
        user: User = require_auth,
        db: DBSession = Depends(session_dep),
        runner=Depends(_report_runner_dep),
    ) -> StreamingResponse:
        user_id = user.id

        cancel_token = CancellationToken()

        async def gen() -> AsyncIterator[bytes]:
            try:
                async for event in eu_runner.run_on_demand(
                    session=db,
                    user_id=user_id,
                    ticker=payload.ticker,
                    report_runner=runner,
                    cancel_token=cancel_token,
                ):
                    if await request.is_disconnected():
                        cancel_token.cancel()
                        break
                    wire = to_wire(event)
                    yield f"event: {wire['type']}\ndata: {json.dumps(wire)}\n\n".encode()
            except ValueError as exc:
                error_payload = {"type": "report.error", "message": str(exc)}
                yield (f"event: report.error\ndata: {json.dumps(error_payload)}\n\n").encode()

        return StreamingResponse(
            gen(),
            media_type="text/event-stream",
            headers={"cache-control": "no-cache", "x-accel-buffering": "no"},
        )

    @router.get("/reports", response_model=_ReportsListOut)
    def list_recent_reports(
        limit: int = 5,
        q: str | None = Query(default=None, max_length=200),
        ticker: str | None = Query(default=None, max_length=32),
        date_from: date | None = Query(default=None, alias="from"),
        date_to: date | None = Query(default=None, alias="to"),
        user: User = require_auth,
        db: DBSession = Depends(session_dep),
    ) -> _ReportsListOut:
        bounded = max(1, min(limit, 200))
        query = db.query(Report).filter_by(user_id=user.id, department="earnings_update")
        if ticker:
            query = query.filter(Report.subject == ticker.strip().upper())
        if q:
            needle = f"%{q.strip()}%"
            query = query.filter(Report.title.ilike(needle))
        if date_from is not None:
            query = query.filter(
                Report.created_at >= datetime.combine(date_from, datetime.min.time())
            )
        if date_to is not None:
            query = query.filter(Report.created_at < datetime.combine(date_to, datetime.min.time()))
        rows = query.order_by(Report.created_at.desc()).limit(bounded).all()
        return _ReportsListOut(
            reports=[
                _RecentReportOut(
                    id=row.id,
                    title=row.title,
                    subject=row.subject,
                    report_type=row.report_type,
                    created_at=row.created_at.isoformat(),
                )
                for row in rows
            ]
        )

    @router.delete("/reports/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_report(
        report_id: str,
        user: User = require_auth,
        db: DBSession = Depends(session_dep),
    ) -> None:
        row = db.execute(
            select(Report).where(
                Report.id == report_id,
                Report.user_id == user.id,
                Report.department == "earnings_update",
            )
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "report not found")
        db.delete(row)
        db.commit()

    return router
