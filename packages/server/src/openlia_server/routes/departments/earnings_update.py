"""Earnings Update HTTP routes.

Factory-style router exposing watchlist, config, schedules, on-demand report,
and recent reports endpoints under `/departments/earnings-update`.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from openlia.llm.runtime.cancellation import CancellationToken
from openlia.llm.runtime.events import to_wire
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.db.models.content import Report
from openlia_server.middleware.auth import build_require_auth
from openlia_server.services import eu_config as config_svc
from openlia_server.services import eu_runner
from openlia_server.services import eu_watchlist as watchlist_svc


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


def build_earnings_update_router(
    *,
    db_session_factory: Callable[[], DBSession],
    mode: Literal["personal", "company"],
) -> APIRouter:
    router = APIRouter(prefix="/departments/earnings-update", tags=["earnings-update"])
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
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

    # ----- On-demand report + recent reports -----

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
        user: User = require_auth,
        db: DBSession = Depends(session_dep),
    ) -> _ReportsListOut:
        bounded = max(1, min(limit, 200))
        rows = (
            db.query(Report)
            .filter_by(user_id=user.id, department="earnings_update")
            .order_by(Report.created_at.desc())
            .limit(bounded)
            .all()
        )
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

    return router
