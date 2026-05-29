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

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
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
from openlia.llm.types import ReasoningEffort
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
from openlia_server.services import v3_revision_service as revision_svc
from openlia_server.services import v3_run_service as svc
from openlia_server.services import v3_template_service as templates_svc
from openlia_server.services.v3_filename import build_download_filename
from openlia_server.services.v3_wiring import build_v3_transports

_ENV_FLAG = "REPORT_ENGINE_VERSION"
_ENABLED_VALUE = "v3"


# ---------------------------------------------------------------------------
# Payloads
# ---------------------------------------------------------------------------


class StartV3Payload(BaseModel):
    subject: str = Field(..., min_length=1)
    language: Language = Language.EN
    length: ReportLength = ReportLength.NORMAL
    # ``template_id`` resolves against ``report_v3_templates`` (built-in
    # or user-uploaded). When omitted, falls back to the ``report_type``
    # default built-in. The frontend always sends one of the two; the
    # report_type fallback exists so legacy clients and tests stay
    # green.
    template_id: str | None = None
    report_type: ReportType = ReportType.INITIATION
    provider_kind: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    # Extended-thinking knob. ``None`` (or omitted) = off; "medium" /
    # "high" enable provider-specific reasoning params. Adapters whose
    # model doesn't support thinking ignore the field silently.
    reasoning_effort: ReasoningEffort | None = None


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
    # User-selected extended-thinking knob at dispatch time, or null
    # when reasoning was off. PR12 follow-up: lets the chat-thread
    # chips show what was used even after a page reload.
    reasoning_effort: str | None = None


class SectionOut(BaseModel):
    section_id: str
    section_index: int
    title: str
    markdown: str
    # 1 = written by the original run; >1 = touched by a revision.
    # The frontend reads this to render a "Revised in vN" badge.
    version: int = 1


class ChartOut(BaseModel):
    chart_id: str
    chart_type: str
    title: str
    spec: dict[str, Any]
    rendered_url: str | None
    version: int = 1


class CitationOut(BaseModel):
    source_id: str
    tool_name: str
    display_index: int | None
    provenance: dict[str, Any]


class CoverMetricOut(BaseModel):
    """One headline metric card on the report cover."""

    label: str
    value: str
    change: str | None = None
    tone: str | None = None


class CoverOut(BaseModel):
    """Cover hero content populated by the model's ``set_cover`` call.

    All fields are optional — an unpopulated cover renders with the
    bare subject + template-derived eyebrow.
    """

    subtitle: str | None = None
    tagline: str | None = None
    tldr: list[str] = Field(default_factory=list)
    key_metrics: list[CoverMetricOut] = Field(default_factory=list)
    rating: str | None = None
    upside_pct: float | None = None


class ReportDetailOut(BaseModel):
    report: ReportSummaryOut
    error_message: str | None
    sections: list[SectionOut]
    charts: list[ChartOut]
    citations: list[CitationOut]
    # Cover hero content, or None when the model never called
    # ``set_cover`` for this report (older rows + early v3 runs).
    cover: CoverOut | None = None


class TemplateOut(BaseModel):
    """Listing/return shape for a v3 template.

    Holds metadata only; the spec body is not returned to the client
    (it's only needed at run dispatch time, where the route loads it
    via ``resolve_template`` directly).
    """

    id: str
    name: str
    is_builtin: bool
    created_at: datetime
    updated_at: datetime


class TemplateCreatePayload(BaseModel):
    """Upload payload — markdown + display name.

    ``source_doc_blob`` / ``source_doc_mime`` are optional and let the
    UI round-trip the original upload (.md vs ingested .docx) so a
    future re-parse / edit flow can show the source.
    """

    name: str = Field(..., min_length=1, max_length=256)
    markdown: str = Field(..., min_length=1)
    source_doc_blob: bytes | None = None
    source_doc_mime: str | None = Field(default=None, max_length=128)


class RevisionStartPayload(BaseModel):
    """POST /v3/runs/{report_id}/revise body.

    ``request`` is the free-form revision instruction the user typed
    in chat ("rewrite the bull case to lead with EBITDA margins").
    """

    request: str = Field(..., min_length=1)


class RevisionOut(BaseModel):
    id: str
    report_id: str
    revision_index: int
    request: str
    status: str
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None


class RevisionStartResponse(BaseModel):
    """Returned by ``POST /v3/runs/{report_id}/revise``."""

    revision_id: str


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
        reasoning_effort=row.reasoning_effort,
    )


def _section_out(row: ReportV3Section) -> SectionOut:
    return SectionOut(
        section_id=row.section_id,
        section_index=row.section_index,
        title=row.title,
        markdown=row.markdown,
        version=row.version,
    )


def _chart_out(row: ReportV3Chart) -> ChartOut:
    return ChartOut(
        chart_id=row.chart_id,
        chart_type=row.chart_type,
        title=row.title,
        spec=json.loads(row.spec_json),
        rendered_url=row.rendered_url,
        version=row.version,
    )


def _citation_out(row: ReportV3Citation) -> CitationOut:
    return CitationOut(
        source_id=row.source_id,
        tool_name=row.tool_name,
        display_index=row.display_index,
        provenance=json.loads(row.provenance_json),
    )


def _cover_out(raw: str | None) -> CoverOut | None:
    """Deserialise ``ReportV3.cover_json`` to ``CoverOut``. Returns
    None for runs where the model never called ``set_cover`` (older
    rows + early v3 runs); returns None on parse failure too so a
    corrupt cover row never breaks the detail endpoint."""
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    return CoverOut.model_validate(data)


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

    def _resolve_template_for_run(
        *, db: DBSession, user_id: str, payload: StartV3Payload
    ) -> TemplateSpec:
        """Pick the template the engine should follow.

        Priority: explicit ``template_id`` (user-uploaded or built-in
        looked up via the DB) > fallback to the ``report_type``
        built-in resolved through the in-code registry. The in-code
        fallback keeps legacy clients and pre-migration tests green;
        new clients always send ``template_id``.
        """
        if payload.template_id:
            try:
                return templates_svc.resolve_template(
                    db=db, user_id=user_id, template_id=payload.template_id
                )
            except templates_svc.TemplateNotFoundError as exc:
                raise HTTPException(status_code=404, detail=str(exc)) from exc
        return get_builtin(payload.report_type)

    @router.post("/runs", response_model=StartV3Response)
    async def start_run(
        payload: StartV3Payload,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> StartV3Response:
        if not _engine_enabled():
            raise _engine_disabled()

        template: TemplateSpec = _resolve_template_for_run(db=db, user_id=user.id, payload=payload)
        run_request = RunRequest(
            subject=payload.subject,
            template=template,
            language=payload.language,
            length=payload.length,
            provider_kind=payload.provider_kind,
            model=payload.model,
            reasoning_effort=payload.reasoning_effort,
        )
        try:
            outcome = await svc.start_run(
                db=db,
                user_id=user.id,
                request=run_request,
                transports=build_v3_transports(),
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
            cover=_cover_out(row.cover_json),
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

        template: TemplateSpec = _resolve_template_for_run(db=db, user_id=user.id, payload=payload)
        run_request = RunRequest(
            subject=payload.subject,
            template=template,
            language=payload.language,
            length=payload.length,
            provider_kind=payload.provider_kind,
            model=payload.model,
            reasoning_effort=payload.reasoning_effort,
        )
        try:
            handle = svc.start_run_async(
                db=db,
                user_id=user.id,
                request=run_request,
                session_factory=db_session_factory,
                broker=broker,
                cancel_registry=cancel_registry,
                transports=build_v3_transports(),
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
        cancelled = svc.cancel_run(cancel_registry=cancel_registry, report_id=report_id)
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
            row = svc.get_report_row(db=db, user_id=user.id, report_id=report_id)
            rendered = render_svc.render_html(db=db, user_id=user.id, report_id=report_id)
        except svc.ReportNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        filename = build_download_filename(row=row, ext="html")
        return HTMLResponse(
            content=rendered.html,
            headers={
                "Content-Disposition": f'inline; filename="{filename}"',
            },
        )

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
            row = svc.get_report_row(db=db, user_id=user.id, report_id=report_id)
            pdf_bytes = await render_svc.render_pdf(
                db=db,
                user_id=user.id,
                report_id=report_id,
                browser_launcher=launcher,
            )
        except svc.ReportNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        filename = build_download_filename(row=row, ext="pdf")
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={
                "Content-Disposition": f'inline; filename="{filename}"',
            },
        )

    @router.get("/runs/{report_id}/docx")
    def get_docx(
        report_id: str,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> Response:
        """Native .docx download — no Playwright dependency.

        Builds the Word document from the persisted section /
        chart / citation rows via python-docx. Charts render via
        matplotlib (the same path the HTML / PDF surface uses);
        when matplotlib is unavailable or a chart's data is
        mis-shaped, the renderer emits a labelled placeholder so
        the export never silently drops content.
        """
        if not _engine_enabled():
            raise _engine_disabled()
        try:
            row = svc.get_report_row(db=db, user_id=user.id, report_id=report_id)
            docx_bytes = render_svc.render_docx(db=db, user_id=user.id, report_id=report_id)
        except svc.ReportNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            # Surface the failure usefully — without this catch the
            # frontend gets an opaque 500 and the user sees only
            # "Download failed" with no clue why. The full traceback
            # already lands in the server log via logger.exception.
            import logging

            logging.getLogger(__name__).exception(
                "v3 docx render failed for report_id=%s", report_id
            )
            raise HTTPException(
                status_code=500,
                detail=f"v3 docx render failed: {type(exc).__name__}: {exc}",
            ) from exc
        filename = build_download_filename(row=row, ext="docx")
        return Response(
            content=docx_bytes,
            media_type=("application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            headers={
                "Content-Disposition": f'attachment; filename="{filename}"',
            },
        )

    # ------------------------------------------------------------------
    # Templates CRUD — PR3
    #
    # Built-ins are seeded by the ``2026-05-27_2300_report_v3_templates``
    # migration and visible to every user. User uploads are owner-scoped
    # and soft-deleted (the resolver filters on ``deleted_at IS NULL``).
    # ------------------------------------------------------------------

    @router.get("/templates", response_model=list[TemplateOut])
    def list_templates(
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> list[TemplateOut]:
        if not _engine_enabled():
            raise _engine_disabled()
        rows = templates_svc.list_templates(db=db, user_id=user.id)
        return [
            TemplateOut(
                id=r.id,
                name=r.name,
                is_builtin=r.is_builtin,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in rows
        ]

    @router.post(
        "/templates",
        response_model=TemplateOut,
        status_code=status.HTTP_201_CREATED,
    )
    def upload_template(
        payload: TemplateCreatePayload,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> TemplateOut:
        if not _engine_enabled():
            raise _engine_disabled()
        try:
            row = templates_svc.create_template_from_markdown(
                db=db,
                user_id=user.id,
                name=payload.name,
                markdown=payload.markdown,
                source_doc_blob=payload.source_doc_blob,
                source_doc_mime=payload.source_doc_mime,
            )
        except templates_svc.TemplateValidationError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return TemplateOut(
            id=row.id,
            name=row.name,
            is_builtin=row.is_builtin,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_template(
        template_id: str,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> Response:
        if not _engine_enabled():
            raise _engine_disabled()
        try:
            templates_svc.soft_delete_template(db=db, user_id=user.id, template_id=template_id)
        except templates_svc.TemplateNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    # ------------------------------------------------------------------
    # Revisions — PR4
    #
    # Each revision is one round of "user asked for a change". The
    # engine runs in a background task; the SSE stream lives at
    # ``/revisions/{revision_id}/events``. Concurrency: 409 when
    # another revision is in flight on the same report.
    # ------------------------------------------------------------------

    @router.post(
        "/runs/{report_id}/revise",
        response_model=RevisionStartResponse,
    )
    async def start_revision(
        report_id: str,
        payload: RevisionStartPayload,
        request: Request,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> RevisionStartResponse:
        """Non-blocking POST: returns {revision_id} immediately.

        The revision engine loads the prior report state, runs the
        same Runner with a ReviseContext, and persists new section /
        chart versions. Client connects to
        ``GET /v3/revisions/{revision_id}/events`` (SSE) for progress.

        Defined as ``async def`` for the same reason as
        ``start_run_async`` — ``asyncio.create_task`` inside the
        service requires a running event loop.
        """
        if not _engine_enabled():
            raise _engine_disabled()
        broker, cancel_registry = _streaming_state(request)

        # Owner-scope + load the parent so we can build the
        # ReviseContext and a RunRequest sized to the prior run.
        parent = db.get(ReportV3, report_id)
        if parent is None or parent.user_id != user.id:
            raise HTTPException(status_code=404, detail=f"v3 report {report_id!r} not found")
        if parent.status not in ("completed", "failed"):
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Cannot revise a report in status {parent.status!r}. "
                    f"Wait for the current run / revision to finish."
                ),
            )

        # Re-resolve the parent's template so the revision engine has
        # the same structural authority as the original run.
        try:
            template: TemplateSpec = templates_svc.resolve_template(
                db=db, user_id=user.id, template_id=parent.template_id
            )
        except templates_svc.TemplateNotFoundError:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Parent report's template {parent.template_id!r} is "
                    f"no longer available. Re-upload it or revise after "
                    f"restoring."
                ),
            ) from None

        run_request = RunRequest(
            subject=parent.subject,
            template=template,
            language=Language(parent.language),
            length=ReportLength(parent.length),
            provider_kind=parent.provider_kind,
            model=parent.model,
            # Reasoning effort is not persisted on ReportV3 yet —
            # revisions default to "off". A follow-up can let the
            # client send an override per-revision.
            reasoning_effort=None,
        )
        revise_ctx = revision_svc.build_revise_context_from_db(
            db=db, report_id=report_id, revision_request=payload.request
        )

        try:
            handle = revision_svc.start_revision_async(
                db=db,
                user_id=user.id,
                report_id=report_id,
                revision_request=payload.request,
                request=run_request,
                revise=revise_ctx,
                session_factory=db_session_factory,
                broker=broker,
                cancel_registry=cancel_registry,
                transports=build_v3_transports(),
            )
        except revision_svc.RevisionInFlightError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except CapabilityError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        return RevisionStartResponse(revision_id=handle.revision_id)

    @router.get(
        "/runs/{report_id}/revisions",
        response_model=list[RevisionOut],
    )
    def list_run_revisions(
        report_id: str,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> list[RevisionOut]:
        if not _engine_enabled():
            raise _engine_disabled()
        try:
            rows = revision_svc.list_revisions(db=db, user_id=user.id, report_id=report_id)
        except svc.ReportNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        return [
            RevisionOut(
                id=r.id,
                report_id=r.report_id,
                revision_index=r.revision_index,
                request=r.request,
                status=r.status,
                error_message=r.error_message,
                created_at=r.created_at,
                completed_at=r.completed_at,
            )
            for r in rows
        ]

    @router.post("/revisions/{revision_id}/cancel")
    async def cancel_revision(
        revision_id: str,
        request: Request,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> dict[str, bool]:
        if not _engine_enabled():
            raise _engine_disabled()
        try:
            revision_svc.get_revision(db=db, user_id=user.id, revision_id=revision_id)
        except revision_svc.RevisionNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        _, cancel_registry = _streaming_state(request)
        cancelled = revision_svc.cancel_revision(
            cancel_registry=cancel_registry, revision_id=revision_id
        )
        return {"cancelled": cancelled}

    @router.get("/revisions/{revision_id}/events")
    async def stream_revision_events(
        revision_id: str,
        request: Request,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> StreamingResponse:
        if not _engine_enabled():
            raise _engine_disabled()
        try:
            row = revision_svc.get_revision(db=db, user_id=user.id, revision_id=revision_id)
        except revision_svc.RevisionNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        broker, _ = _streaming_state(request)

        # Late-connect: if the revision already finished, replay a
        # single run.snapshot frame with the terminal status so the
        # client renders the final state without waiting forever.
        terminal_snapshot: dict[str, Any] | None = None
        if row.status in ("completed", "failed", "cancelled"):
            terminal_snapshot = {
                "status": row.status,
                "error_message": row.error_message,
            }

        return StreamingResponse(
            _sse_stream(broker, revision_id, terminal_snapshot),
            media_type="text/event-stream",
            headers={
                "Cache-Control": "no-cache",
                "X-Accel-Buffering": "no",
            },
        )

    return router
