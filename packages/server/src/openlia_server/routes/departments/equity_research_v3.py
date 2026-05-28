"""v3 equity-research route — single-model engine.

Endpoints:

- ``POST   /api/departments/equity-research/v3/runs``
    Start + execute a v3 run. Persists the outcome and returns the
    populated ``RunResult`` plus the assigned ``report_id``.
- ``GET    /api/departments/equity-research/v3/runs``
    List the caller's runs (newest first). Optional ``status`` filter.
- ``GET    /api/departments/equity-research/v3/runs/{report_id}``
    Read one persisted run: row + sections (template order) + charts
    + bibliography citations (display_index order).
- ``DELETE /api/departments/equity-research/v3/runs/{report_id}``
    Drop a run (cascades to child rows).

The route is gated by the ``REPORT_ENGINE_VERSION`` environment
variable. When the value is anything other than ``v3`` (default
``v2.3``) every endpoint returns 503 with a clear pointer to the
v2.3 path.

Capability gate failures (``CapabilityError``) come back as 400.
``ReportNotFoundError`` from get/delete comes back as 404. Other
errors bubble as 500.
"""

from __future__ import annotations

import json
import os
from collections.abc import Callable
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from openlia.llm.runtime.report_v2_3.schemas import ReportType
from openlia.llm.runtime.report_v2_3.templates.builtins import get_builtin
from openlia.llm.runtime.report_v3 import (
    CancelToken,
    CapabilityError,
    EventBroker,
    Language,
    ReportLength,
    RunRequest,
    RunResult,
    TemplateSpec,
    is_finish_sentinel,
)
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.db.models.report_v3 import (
    ReportV3,
    ReportV3Chart,
    ReportV3Citation,
    ReportV3Section,
)
from openlia_server.middleware.auth import build_require_auth
from openlia_server.services import v3_render_service as render_svc
from openlia_server.services import v3_run_service as svc

_ENV_FLAG = "REPORT_ENGINE_VERSION"
_ENABLED_VALUE = "v3"


# ---------------------------------------------------------------------------
# Payloads
# ---------------------------------------------------------------------------


class StartV3Payload(BaseModel):
    subject: str = Field(..., min_length=1)
    language: Language = Language.EN
    length: ReportLength = ReportLength.NORMAL
    # Phase 0 resolves the template from the ``report_type`` built-in
    # registry. Phase 1.5 will accept user-uploaded templates via a
    # separate ``template_id`` field; Phase 0 keeps the surface minimal.
    report_type: ReportType = ReportType.INITIATION
    provider_kind: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)


class StartV3Response(BaseModel):
    """Returned by ``POST /runs``: the persisted id + full result."""

    report_id: str
    result: RunResult


class ReportSummaryOut(BaseModel):
    report_id: str
    subject: str
    template_id: str
    language: str
    length: str
    status: str
    created_at: datetime
    completed_at: datetime | None


class SectionOut(BaseModel):
    section_id: str
    section_index: int
    title: str
    markdown: str


class ChartOut(BaseModel):
    chart_id: str
    chart_type: str
    title: str
    spec: dict[str, Any]
    rendered_url: str | None


class CitationOut(BaseModel):
    source_id: str
    tool_name: str
    display_index: int | None
    provenance: dict[str, Any]


class ReportDetailOut(BaseModel):
    report: ReportSummaryOut
    error_message: str | None
    sections: list[SectionOut]
    charts: list[ChartOut]
    citations: list[CitationOut]


# ---------------------------------------------------------------------------
# Mapping helpers
# ---------------------------------------------------------------------------


def _summary(row: ReportV3) -> ReportSummaryOut:
    return ReportSummaryOut(
        report_id=row.id,
        subject=row.subject,
        template_id=row.template_id,
        language=row.language,
        length=row.length,
        status=row.status,
        created_at=row.created_at,
        completed_at=row.completed_at,
    )


def _section_out(row: ReportV3Section) -> SectionOut:
    return SectionOut(
        section_id=row.section_id,
        section_index=row.section_index,
        title=row.title,
        markdown=row.markdown,
    )


def _chart_out(row: ReportV3Chart) -> ChartOut:
    return ChartOut(
        chart_id=row.chart_id,
        chart_type=row.chart_type,
        title=row.title,
        spec=json.loads(row.spec_json),
        rendered_url=row.rendered_url,
    )


def _citation_out(row: ReportV3Citation) -> CitationOut:
    return CitationOut(
        source_id=row.source_id,
        tool_name=row.tool_name,
        display_index=row.display_index,
        provenance=json.loads(row.provenance_json),
    )


# ---------------------------------------------------------------------------
# Route gate
# ---------------------------------------------------------------------------


def _engine_disabled() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail=(
            f"v3 engine disabled. Set {_ENV_FLAG}={_ENABLED_VALUE} to enable. "
            f"Default engine is v2.3 at /departments/equity-research/v2.3/runs."
        ),
    )


def _engine_enabled() -> bool:
    return os.environ.get(_ENV_FLAG, "").strip().lower() == _ENABLED_VALUE


def _streaming_state(request: Request) -> tuple[EventBroker, dict[str, CancelToken]]:
    """Pull the v3 broker + cancel registry off ``app.state``.

    These are initialized once during app startup (see
    ``openlia_server.app``). Routes that need streaming pull them at
    call time so a startup-time race doesn't leave them stale.
    """
    broker = getattr(request.app.state, "v3_event_broker", None)
    registry = getattr(request.app.state, "v3_cancel_registry", None)
    if broker is None or registry is None:
        raise HTTPException(
            status_code=503,
            detail=(
                "v3 streaming infrastructure not initialised. The app "
                "must run with the v3 broker wired on app.state."
            ),
        )
    return broker, registry


async def _sse_stream(
    broker: EventBroker,
    report_id: str,
    terminal_snapshot: dict[str, Any] | None,
):
    """Async generator yielding SSE-framed events for one run.

    - When the run already finished before the subscriber connected,
      yields a single ``run.snapshot`` event with the persisted
      status and closes.
    - Otherwise, yields the live event stream until the broker
      finishes the run.
    """
    if terminal_snapshot is not None:
        yield _sse_frame("run.snapshot", terminal_snapshot)
        return

    async with broker.subscribe(report_id) as queue:
        while True:
            item = await queue.get()
            if is_finish_sentinel(item):
                break
            yield _sse_frame(item.type, item.payload)


def _sse_frame(event_type: str, payload: dict[str, Any]) -> str:
    """SSE wire format: ``event: <name>\\ndata: <json>\\n\\n``."""
    return f"event: {event_type}\ndata: {json.dumps(payload, default=str)}\n\n"


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


def build_equity_research_v3_router(
    *,
    db_session_factory: Callable[[], DBSession],
    mode: str,
) -> APIRouter:
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
    session_dep = make_session_dependency(db_session_factory)
    router = APIRouter(
        prefix="/departments/equity-research/v3",
        tags=["equity-research-v3"],
    )

    @router.post("/runs", response_model=StartV3Response)
    async def start_run(
        payload: StartV3Payload,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> StartV3Response:
        if not _engine_enabled():
            raise _engine_disabled()

        template: TemplateSpec = get_builtin(payload.report_type)
        run_request = RunRequest(
            subject=payload.subject,
            template=template,
            language=payload.language,
            length=payload.length,
            provider_kind=payload.provider_kind,
            model=payload.model,
        )
        try:
            outcome = await svc.start_run(
                db=db,
                user_id=user.id,
                request=run_request,
            )
        except CapabilityError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return StartV3Response(report_id=outcome.report_id, result=outcome.result)

    @router.get("/runs", response_model=list[ReportSummaryOut])
    def list_runs(
        status: str | None = Query(default=None),
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> list[ReportSummaryOut]:
        if not _engine_enabled():
            raise _engine_disabled()
        rows = svc.list_runs(db=db, user_id=user.id, status=status)
        return [_summary(r) for r in rows]

    @router.get("/runs/{report_id}", response_model=ReportDetailOut)
    def get_run(
        report_id: str,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> ReportDetailOut:
        if not _engine_enabled():
            raise _engine_disabled()
        try:
            row, sections, charts, citations = svc.get_run(
                db=db, user_id=user.id, report_id=report_id
            )
        except svc.ReportNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return ReportDetailOut(
            report=_summary(row),
            error_message=row.error_message,
            sections=[_section_out(s) for s in sections],
            charts=[_chart_out(c) for c in charts],
            citations=[_citation_out(c) for c in citations],
        )

    @router.delete("/runs/{report_id}", status_code=204)
    def delete_run(
        report_id: str,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> None:
        if not _engine_enabled():
            raise _engine_disabled()
        try:
            svc.delete_run(db=db, user_id=user.id, report_id=report_id)
        except svc.ReportNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @router.post("/runs/start")
    async def start_run_async(
        payload: StartV3Payload,
        request: Request,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> dict[str, str]:
        """Non-blocking POST: returns {report_id} immediately.

        The engine runs in a background task; the client connects to
        ``GET /v3/runs/{report_id}/events`` (SSE) to receive
        progress + the final state. Use the blocking ``POST /runs``
        instead when you don't want streaming.

        Defined as ``async def`` so the handler runs on the main
        asyncio loop — ``svc.start_run_async`` calls
        ``asyncio.create_task`` to schedule the background runner,
        which requires a running event loop. A sync ``def`` handler
        would be dispatched to FastAPI's threadpool where no loop
        is bound, and the create_task call would raise
        ``RuntimeError: no running event loop``.
        """
        if not _engine_enabled():
            raise _engine_disabled()
        broker, cancel_registry = _streaming_state(request)

        template: TemplateSpec = get_builtin(payload.report_type)
        run_request = RunRequest(
            subject=payload.subject,
            template=template,
            language=payload.language,
            length=payload.length,
            provider_kind=payload.provider_kind,
            model=payload.model,
        )
        try:
            handle = svc.start_run_async(
                db=db,
                user_id=user.id,
                request=run_request,
                session_factory=db_session_factory,
                broker=broker,
                cancel_registry=cancel_registry,
            )
        except CapabilityError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return {"report_id": handle.report_id}

    @router.get("/runs/{report_id}/events")
    async def stream_events(
        report_id: str,
        request: Request,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> StreamingResponse:
        """Server-Sent Events stream for one run.

        Yields one event per progress signal (tool.called,
        tool.completed, section.written, chart.emitted, etc.). The
        stream closes after the terminal event (run.completed,
        run.failed, or run.cancelled).

        Reconnects don't replay missed events — connect early via
        the report_id returned by ``POST /runs/start``. If the run
        already finished before the subscribe lands, the endpoint
        emits a single ``run.snapshot`` event with the current
        terminal status and closes immediately.
        """
        if not _engine_enabled():
            raise _engine_disabled()
        # Authorise + 404 here using the request session before
        # opening the long-lived stream.
        try:
            row, _, _, _ = svc.get_run(db=db, user_id=user.id, report_id=report_id)
        except svc.ReportNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        terminal_snapshot = None
        if row.status in ("completed", "failed"):
            terminal_snapshot = {
                "status": row.status,
                "error_message": row.error_message,
            }

        broker, _ = _streaming_state(request)
        return StreamingResponse(
            _sse_stream(broker, report_id, terminal_snapshot),
            media_type="text/event-stream",
            headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
        )

    @router.post("/runs/{report_id}/cancel")
    def cancel_run(
        report_id: str,
        request: Request,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> dict[str, bool]:
        """Flip the cancel flag for a running v3 run.

        Cooperative — the runner exits at the next safe point (turn
        boundary). 404 if the run isn't owned by the caller; returns
        ``{cancelled: False}`` if the run already finished and no
        token is registered (which is fine — caller's intent is
        satisfied).
        """
        if not _engine_enabled():
            raise _engine_disabled()
        try:
            svc.get_run(db=db, user_id=user.id, report_id=report_id)
        except svc.ReportNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        _, cancel_registry = _streaming_state(request)
        cancelled = svc.cancel_run(
            cancel_registry=cancel_registry, report_id=report_id
        )
        return {"cancelled": cancelled}

    @router.get("/runs/{report_id}/html", response_class=HTMLResponse)
    def get_html(
        report_id: str,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> HTMLResponse:
        if not _engine_enabled():
            raise _engine_disabled()
        try:
            rendered = render_svc.render_html(
                db=db, user_id=user.id, report_id=report_id
            )
        except svc.ReportNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return HTMLResponse(content=rendered.html)

    @router.get("/runs/{report_id}/pdf")
    async def get_pdf(
        report_id: str,
        request: Request,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> Response:
        if not _engine_enabled():
            raise _engine_disabled()
        launcher = getattr(request.app.state, "browser_launcher", None)
        if launcher is None:
            raise HTTPException(
                status_code=503,
                detail=(
                    "PDF rendering requires the BrowserLauncher to be "
                    "wired on app.state (Playwright headless chromium). "
                    "Use GET /html instead, or run the full server "
                    "process where the launcher is initialised at "
                    "startup."
                ),
            )
        try:
            pdf_bytes = await render_svc.render_pdf(
                db=db,
                user_id=user.id,
                report_id=report_id,
                browser_launcher=launcher,
            )
        except svc.ReportNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": (
                    f'inline; filename="v3-report-{report_id}.pdf"'
                ),
            },
        )

    return router
