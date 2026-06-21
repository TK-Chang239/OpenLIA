"""Earnings Update v2 HTTP router — single-model engine.

Mirrors ``equity_research_v3.py``: a factory-built ``APIRouter``. v2 is
now the sole live Earnings Update engine; the ``EARNINGS_ENGINE_VERSION``
gate is retired and the engine is always on.

Endpoints (prefix ``/departments/earnings-update/v2``):

- ``GET/PUT  /settings``                 per-user defaults + connector toggles
- ``GET/POST /watchlist`` ``DELETE /watchlist/{id}``  tracked tickers
- ``POST     /watchlist/sync``           run the calendar sync now
- ``GET/POST /templates`` ``DELETE /templates/{id}``  report templates
- ``GET      /schedule``                 pending forward-calendar rows
- ``POST     /runs/start``               start a run (async) -> {report_id}
- ``GET      /runs`` ``GET /runs/{id}`` ``DELETE /runs/{id}``  run CRUD
- ``POST     /runs/{id}/cancel``         cooperative cancel
- ``GET      /runs/{id}/events``         SSE progress stream
- ``GET      /runs/{id}/html``           rendered HTML download
- ``GET      /runs/{id}/pdf``            rendered PDF download (needs browser launcher)
- ``GET      /runs/{id}/docx``           native .docx download
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

from fastapi import (
    APIRouter,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Request,
    UploadFile,
    status,
)
from fastapi.responses import HTMLResponse, Response, StreamingResponse
from openlia.llm.runtime.report_eu import (
    CancelToken,
    EventBroker,
    is_finish_sentinel,
)
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.db.models.report_eu import (
    EuV2EarningsSchedule,
    ReportEu,
    ReportEuChart,
    ReportEuCitation,
    ReportEuSection,
)
from openlia_server.middleware.auth import build_require_auth
from openlia_server.services import eu_v2_calendar_sync as calendar_sync
from openlia_server.services import eu_v2_data_sources
from openlia_server.services import eu_v2_instructions_service as instructions_svc
from openlia_server.services import eu_v2_render_service as render_svc
from openlia_server.services import eu_v2_run_service as run_svc
from openlia_server.services import eu_v2_settings as settings_svc
from openlia_server.services import eu_v2_template_service as templates_svc
from openlia_server.services import eu_v2_watchlist as watchlist_svc
from openlia_server.services.attachments import (
    FileUpload,
    extract_text,
    validate_uploads,
)
from openlia_server.services.eu_v2_filename import build_download_filename
from openlia_server.services.eu_v2_wiring import (
    build_eu_v2_transports,
    resolve_eodhd_api_key,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Payloads
# ---------------------------------------------------------------------------


class SettingsOut(BaseModel):
    provider_kind: str
    model: str
    template_id: str
    language: str
    length: str
    reasoning_effort: str | None
    enabled_provider_ids: list[str]
    web_search_enabled: bool
    instructions_id: str | None
    batch_enabled: bool


class InstructionsOut(BaseModel):
    id: str
    name: str
    is_builtin: bool
    created_at: datetime
    updated_at: datetime


class DataSourceOut(BaseModel):
    key: str
    display_name: str
    category: str
    routing: str
    available: bool
    enabled: bool
    unavailable_reason: str | None


class DataSourcesOut(BaseModel):
    sources: list[DataSourceOut]


class SettingsUpdateIn(BaseModel):
    provider_kind: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    template_id: str = Field(..., min_length=1)
    language: str = Field(..., min_length=1)
    length: str = Field(..., min_length=1)
    reasoning_effort: str | None = None
    enabled_provider_ids: list[str]
    web_search_enabled: bool
    instructions_id: str | None = None
    batch_enabled: bool = False


class WatchlistEntryOut(BaseModel):
    id: str
    ticker: str
    company_name: str | None
    created_at: datetime


class WatchlistListOut(BaseModel):
    entries: list[WatchlistEntryOut]


class WatchlistAddIn(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=32)


class SyncResultOut(BaseModel):
    synced: int


class TemplateOut(BaseModel):
    id: str
    name: str
    is_builtin: bool
    created_at: datetime
    updated_at: datetime


class TemplateListOut(BaseModel):
    templates: list[TemplateOut]


class TemplateCreateIn(BaseModel):
    name: str = Field(..., min_length=1, max_length=256)
    source_markdown: str = Field(..., min_length=1)


class ScheduleEntryOut(BaseModel):
    id: str
    ticker: str
    fiscal_date: str
    release_timing: str | None
    eps_estimate: str | None
    revenue_estimate: str | None
    scheduled_run_at: datetime
    status: str
    attempts: int
    report_id: str | None


class ScheduleListOut(BaseModel):
    schedule: list[ScheduleEntryOut]


class RunStartIn(BaseModel):
    ticker: str = Field(..., min_length=1, max_length=32)


class RunStartOut(BaseModel):
    report_id: str


class RunSummaryOut(BaseModel):
    report_id: str
    subject: str
    ticker: str
    trigger_kind: str
    fiscal_date: str | None
    template_id: str
    language: str
    length: str
    status: str
    created_at: datetime
    completed_at: datetime | None
    reasoning_effort: str | None = None
    highlights: CardHighlightsOut | None = None


class SectionOut(BaseModel):
    section_id: str
    section_index: int
    title: str
    markdown: str
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
    label: str
    value: str
    change: str | None = None
    tone: str | None = None


class CardHighlightsOut(BaseModel):
    subtitle: str | None = None
    rating: str | None = None
    metrics: list[CoverMetricOut] = Field(default_factory=list)


RunSummaryOut.model_rebuild()


class CoverOut(BaseModel):
    subtitle: str | None = None
    tagline: str | None = None
    tldr: list[str] = Field(default_factory=list)
    key_metrics: list[CoverMetricOut] = Field(default_factory=list)
    rating: str | None = None
    upside_pct: float | None = None


class RunDetailOut(BaseModel):
    report: RunSummaryOut
    error_message: str | None
    sections: list[SectionOut]
    charts: list[ChartOut]
    citations: list[CitationOut]
    cover: CoverOut | None = None


class CancelOut(BaseModel):
    cancelled: bool


# ---------------------------------------------------------------------------
# Mapping helpers
# ---------------------------------------------------------------------------


def _data_source_out(s: eu_v2_data_sources.DataSource) -> DataSourceOut:
    return DataSourceOut(
        key=s.key,
        display_name=s.display_name,
        category=s.category,
        routing=s.routing,
        available=s.available,
        enabled=s.enabled,
        unavailable_reason=s.unavailable_reason,
    )


def _summary(row: ReportEu) -> RunSummaryOut:
    return RunSummaryOut(
        report_id=row.id,
        subject=row.subject,
        ticker=row.ticker,
        trigger_kind=row.trigger_kind,
        fiscal_date=row.fiscal_date,
        template_id=row.template_id,
        language=row.language,
        length=row.length,
        status=row.status,
        created_at=row.created_at,
        completed_at=row.completed_at,
        reasoning_effort=row.reasoning_effort,
        highlights=_card_highlights(row.cover_json),
    )


def _section_out(row: ReportEuSection) -> SectionOut:
    return SectionOut(
        section_id=row.section_id,
        section_index=row.section_index,
        title=row.title,
        markdown=row.markdown,
        version=row.version,
    )


def _chart_out(row: ReportEuChart) -> ChartOut:
    return ChartOut(
        chart_id=row.chart_id,
        chart_type=row.chart_type,
        title=row.title,
        spec=json.loads(row.spec_json),
        rendered_url=row.rendered_url,
        version=row.version,
    )


def _citation_out(row: ReportEuCitation) -> CitationOut:
    return CitationOut(
        source_id=row.source_id,
        tool_name=row.tool_name,
        display_index=row.display_index,
        provenance=json.loads(row.provenance_json),
    )


def _cover_out(raw: str | None) -> CoverOut | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return None
    if not isinstance(data, dict):
        return None
    return CoverOut.model_validate(data)


def _card_highlights(raw: str | None) -> CardHighlightsOut | None:
    cover = _cover_out(raw)
    if cover is None:
        return None
    metrics = cover.key_metrics[:4]
    if not cover.subtitle and not cover.rating and not metrics:
        return None
    return CardHighlightsOut(
        subtitle=cover.subtitle,
        rating=cover.rating,
        metrics=metrics,
    )


# ---------------------------------------------------------------------------
# Streaming-state helpers
# ---------------------------------------------------------------------------


def _streaming_state(request: Request) -> tuple[EventBroker, dict[str, CancelToken]]:
    """Pull the EU v2 broker + cancel registry off ``app.state``.

    Wired once at app startup (Task 17). Read at call time so a
    startup-time race doesn't leave a stale reference behind.
    """
    broker = getattr(request.app.state, "eu_v2_event_broker", None)
    registry = getattr(request.app.state, "eu_v2_cancel_registry", None)
    if broker is None or registry is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "EU v2 streaming infrastructure not initialised. The app "
                "must run with the eu_v2 broker wired on app.state."
            ),
        )
    return broker, registry


def _sse_frame(event_type: str, payload: dict[str, Any]) -> str:
    """SSE wire format: ``event: <name>\\ndata: <json>\\n\\n``."""
    return f"event: {event_type}\ndata: {json.dumps(payload, default=str)}\n\n"


async def _sse_stream(
    broker: EventBroker,
    report_id: str,
    terminal_snapshot: dict[str, Any] | None,
):
    """Async generator yielding SSE-framed events for one run.

    A late subscriber (the run already finished) gets a single
    ``run.snapshot`` frame and the stream closes; otherwise it streams
    live events until the broker finishes the run.
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


def _resolve_eu_transports(db: DBSession):
    """EODHD bundle resolved from env or an installed connector, or None when unconfigured."""
    return build_eu_v2_transports(api_key=resolve_eodhd_api_key(db))


# ---------------------------------------------------------------------------
# Module-level async marker handler.
#
# The actual route handler is the nested ``start_run_async`` below (it
# needs the factory closures). This module-level ``async def start_run``
# exists so the v3 sync-def bug class is guarded structurally: a route
# whose start handler is a sync ``def`` would be dispatched to FastAPI's
# threadpool where ``asyncio.create_task`` has no running loop and raises.
# Keeping a named coroutine here documents + asserts that contract.
# ---------------------------------------------------------------------------


async def start_run() -> None:  # pragma: no cover - structural guard marker
    """Marker: the EU v2 start handler must be ``async def``.

    See ``build_earnings_update_v2_router.start_run_async``.
    """
    raise NotImplementedError("use the router-bound start_run_async handler")


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


def build_earnings_update_v2_router(
    *,
    db_session_factory: Callable[[], DBSession],
    mode: str,
) -> APIRouter:
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
    session_dep = make_session_dependency(db_session_factory)
    router = APIRouter(
        prefix="/departments/earnings-update/v2",
        tags=["earnings-update-v2"],
    )

    # ----- Settings -----

    @router.get("/settings", response_model=SettingsOut)
    def get_settings(
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> SettingsOut:
        dto = settings_svc.get_settings(db, user_id=user.id)
        return SettingsOut(
            provider_kind=dto.provider_kind,
            model=dto.model,
            template_id=dto.template_id,
            language=dto.language,
            length=dto.length,
            reasoning_effort=dto.reasoning_effort,
            enabled_provider_ids=list(dto.enabled_provider_ids),
            web_search_enabled=dto.web_search_enabled,
            instructions_id=dto.instructions_id,
            batch_enabled=dto.batch_enabled,
        )

    @router.get("/data-sources", response_model=DataSourcesOut)
    def get_data_sources(
        provider_kind: str | None = Query(default=None),
        model: str | None = Query(default=None),
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> DataSourcesOut:
        ds = eu_v2_data_sources.compute_data_sources(
            db, user_id=user.id, provider_kind=provider_kind, model=model
        )
        return DataSourcesOut(sources=[_data_source_out(s) for s in ds.sources])

    @router.put("/settings", response_model=SettingsOut)
    def put_settings(
        payload: SettingsUpdateIn,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> SettingsOut:
        if payload.template_id == "freeform" and not payload.instructions_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Pick a template or an instruction profile — at least one is required.",
            )
        try:
            dto = settings_svc.update_settings(
                db,
                user_id=user.id,
                provider_kind=payload.provider_kind,
                model=payload.model,
                template_id=payload.template_id,
                language=payload.language,
                length=payload.length,
                reasoning_effort=payload.reasoning_effort,
                enabled_provider_ids=payload.enabled_provider_ids,
                web_search_enabled=payload.web_search_enabled,
                instructions_id=payload.instructions_id,
                batch_enabled=payload.batch_enabled,
            )
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)
            ) from exc
        return SettingsOut(
            provider_kind=dto.provider_kind,
            model=dto.model,
            template_id=dto.template_id,
            language=dto.language,
            length=dto.length,
            reasoning_effort=dto.reasoning_effort,
            enabled_provider_ids=list(dto.enabled_provider_ids),
            web_search_enabled=dto.web_search_enabled,
            instructions_id=dto.instructions_id,
            batch_enabled=dto.batch_enabled,
        )

    # ----- Watchlist -----

    @router.get("/watchlist", response_model=WatchlistListOut)
    def get_watchlist(
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> WatchlistListOut:
        rows = watchlist_svc.list_entries(db, user_id=user.id)
        return WatchlistListOut(
            entries=[
                WatchlistEntryOut(
                    id=r.id,
                    ticker=r.ticker,
                    company_name=r.company_name,
                    created_at=r.created_at,
                )
                for r in rows
            ]
        )

    @router.post(
        "/watchlist",
        status_code=status.HTTP_201_CREATED,
        response_model=WatchlistEntryOut,
    )
    def add_to_watchlist(
        payload: WatchlistAddIn,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> WatchlistEntryOut:
        try:
            dto = watchlist_svc.add_entry(
                db, user_id=user.id, ticker=payload.ticker, company_name=None
            )
        except watchlist_svc.AlreadyOnWatchlistError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="already on watchlist"
            ) from exc

        # Best-effort: pull the new ticker's forward calendar so the
        # schedule view fills in without waiting for the weekly sync. A
        # sync failure (no EODHD key, network) must never fail the add.
        transports = _resolve_eu_transports(db)
        if transports is not None:
            try:
                calendar_sync.sync_user_watchlist(
                    db,
                    user_id=user.id,
                    earnings_calendar=transports.earnings_calendar,
                    now=datetime.now(UTC),
                )
            except Exception:
                log.warning(
                    "EU v2 post-add calendar sync failed for user=%s ticker=%s",
                    user.id,
                    payload.ticker,
                    exc_info=True,
                )

        return WatchlistEntryOut(
            id=dto.id,
            ticker=dto.ticker,
            company_name=dto.company_name,
            created_at=dto.created_at,
        )

    @router.delete("/watchlist/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
    def remove_from_watchlist(
        entry_id: str,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> None:
        try:
            watchlist_svc.remove_entry(db, user_id=user.id, entry_id=entry_id)
        except watchlist_svc.WatchlistEntryNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="not found") from exc

    @router.post("/watchlist/sync", response_model=SyncResultOut)
    def sync_watchlist(
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> SyncResultOut:
        transports = _resolve_eu_transports(db)
        if transports is None:
            # EODHD not configured — no data source to sync against. A
            # clean {synced: 0} keeps the UI flow simple (mirrors the
            # runner's loud-null transport approach without a 4xx).
            return SyncResultOut(synced=0)
        synced = calendar_sync.sync_user_watchlist(
            db,
            user_id=user.id,
            earnings_calendar=transports.earnings_calendar,
            now=datetime.now(UTC),
        )
        return SyncResultOut(synced=synced)

    # ----- Templates -----

    @router.get("/templates", response_model=TemplateListOut)
    def list_templates(
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> TemplateListOut:
        rows = templates_svc.list_templates(db, user_id=user.id)
        return TemplateListOut(
            templates=[
                TemplateOut(
                    id=r.id,
                    name=r.name,
                    is_builtin=r.is_builtin,
                    created_at=r.created_at,
                    updated_at=r.updated_at,
                )
                for r in rows
            ]
        )

    @router.post(
        "/templates",
        status_code=status.HTTP_201_CREATED,
        response_model=TemplateOut,
    )
    def upload_template(
        payload: TemplateCreateIn,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> TemplateOut:
        try:
            row = templates_svc.create_template_from_markdown(
                db=db,
                user_id=user.id,
                name=payload.name,
                markdown=payload.source_markdown,
            )
        except templates_svc.TemplateValidationError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        db.commit()
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
        try:
            templates_svc.soft_delete_template(db=db, user_id=user.id, template_id=template_id)
        except templates_svc.TemplateNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    # ----- Instructions -----

    @router.get("/instructions", response_model=list[InstructionsOut])
    def list_instructions(
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> list[InstructionsOut]:
        rows = instructions_svc.list_instructions(db=db, user_id=user.id)
        return [
            InstructionsOut(
                id=r.id,
                name=r.name,
                is_builtin=r.is_builtin,
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in rows
        ]

    @router.post(
        "/instructions",
        status_code=status.HTTP_201_CREATED,
        response_model=InstructionsOut,
    )
    async def upload_instructions(
        name: str = Form(..., min_length=1, max_length=256),
        file: UploadFile = File(...),
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> InstructionsOut:
        content = await file.read()
        upload = FileUpload(
            filename=file.filename or "unnamed",
            mime_type=file.content_type or "application/octet-stream",
            content=content,
        )
        errors = validate_uploads([upload])
        if errors:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"errors": [{"filename": e.filename, "reason": e.reason} for e in errors]},
            )
        try:
            row = instructions_svc.create_instructions_from_upload(
                db=db,
                user_id=user.id,
                name=name,
                body_text=extract_text(upload) or "",
                source_doc_blob=content,
                source_doc_mime=upload.mime_type,
            )
        except instructions_svc.InstructionsValidationError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        db.commit()
        return InstructionsOut(
            id=row.id,
            name=row.name,
            is_builtin=row.is_builtin,
            created_at=row.created_at,
            updated_at=row.updated_at,
        )

    @router.delete(
        "/instructions/{instructions_id}",
        status_code=status.HTTP_204_NO_CONTENT,
    )
    def delete_instructions(
        instructions_id: str,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> Response:
        try:
            instructions_svc.soft_delete_instructions(
                db=db, user_id=user.id, instructions_id=instructions_id
            )
        except instructions_svc.InstructionsNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    # ----- Schedule -----

    @router.get("/schedule", response_model=ScheduleListOut)
    def get_schedule(
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> ScheduleListOut:
        rows = (
            db.execute(
                select(EuV2EarningsSchedule)
                .where(
                    EuV2EarningsSchedule.user_id == user.id,
                    EuV2EarningsSchedule.status == "pending",
                )
                .order_by(EuV2EarningsSchedule.scheduled_run_at.asc())
            )
            .scalars()
            .all()
        )
        return ScheduleListOut(
            schedule=[
                ScheduleEntryOut(
                    id=r.id,
                    ticker=r.ticker,
                    fiscal_date=r.fiscal_date,
                    release_timing=r.release_timing,
                    eps_estimate=r.eps_estimate,
                    revenue_estimate=r.revenue_estimate,
                    scheduled_run_at=r.scheduled_run_at,
                    status=r.status,
                    attempts=r.attempts,
                    report_id=r.report_id,
                )
                for r in rows
            ]
        )

    # ----- Runs -----

    @router.post("/runs/start", response_model=RunStartOut)
    async def start_run_async(
        payload: RunStartIn,
        request: Request,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> RunStartOut:
        """Non-blocking POST: returns ``{report_id}`` immediately.

        Defined as ``async def`` so the handler runs on the main asyncio
        loop — ``run_svc.start_run_async`` calls ``asyncio.create_task``
        to schedule the background runner, which requires a running loop.
        A sync ``def`` handler would be dispatched to FastAPI's threadpool
        where no loop is bound and ``create_task`` raises ``RuntimeError:
        no running event loop`` (the exact bug that broke v3).
        """
        broker, cancel_registry = _streaming_state(request)

        try:
            run_request = run_svc.build_run_request(
                db,
                user_id=user.id,
                ticker=payload.ticker,
                trigger_kind="on_demand",
                fiscal_period=None,
                report_date=None,
                release_timing=None,
                eps_estimate=None,
                revenue_estimate=None,
            )
        except run_svc.EmptyBriefError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
        report_id = run_svc.start_run_async(
            db,
            user_id=user.id,
            request=run_request,
            broker=broker,
            cancel_registry=cancel_registry,
            session_factory=db_session_factory,
            trigger_kind="on_demand",
            transports=_resolve_eu_transports(db),
        )
        db.commit()
        return RunStartOut(report_id=report_id)

    @router.get("/runs", response_model=list[RunSummaryOut])
    def list_runs(
        status_filter: str | None = Query(default=None, alias="status"),
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> list[RunSummaryOut]:
        stmt = select(ReportEu).where(ReportEu.user_id == user.id)
        if status_filter is not None:
            stmt = stmt.where(ReportEu.status == status_filter)
        stmt = stmt.order_by(ReportEu.created_at.desc())
        rows = db.execute(stmt).scalars().all()
        return [_summary(r) for r in rows]

    @router.get("/runs/{report_id}", response_model=RunDetailOut)
    def get_run(
        report_id: str,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> RunDetailOut:
        row = _load_owned_run(db, user_id=user.id, report_id=report_id)
        sections = (
            db.execute(
                select(ReportEuSection)
                .where(ReportEuSection.report_id == report_id)
                .order_by(ReportEuSection.section_index.asc())
            )
            .scalars()
            .all()
        )
        charts = (
            db.execute(select(ReportEuChart).where(ReportEuChart.report_id == report_id))
            .scalars()
            .all()
        )
        citations = (
            db.execute(
                select(ReportEuCitation)
                .where(ReportEuCitation.report_id == report_id)
                .order_by(ReportEuCitation.display_index.asc())
            )
            .scalars()
            .all()
        )
        return RunDetailOut(
            report=_summary(row),
            error_message=row.error_message,
            sections=[_section_out(s) for s in sections],
            charts=[_chart_out(c) for c in charts],
            citations=[_citation_out(c) for c in citations],
            cover=_cover_out(row.cover_json),
        )

    @router.delete("/runs/{report_id}", status_code=status.HTTP_204_NO_CONTENT)
    def delete_run(
        report_id: str,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> None:
        row = _load_owned_run(db, user_id=user.id, report_id=report_id)
        db.delete(row)
        db.commit()

    @router.post("/runs/{report_id}/cancel", response_model=CancelOut)
    def cancel_run(
        report_id: str,
        request: Request,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> CancelOut:
        _load_owned_run(db, user_id=user.id, report_id=report_id)
        _, cancel_registry = _streaming_state(request)
        cancelled = run_svc.cancel_run(cancel_registry=cancel_registry, report_id=report_id)
        return CancelOut(cancelled=cancelled)

    @router.get("/runs/{report_id}/events")
    async def stream_events(
        report_id: str,
        request: Request,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> StreamingResponse:
        """Server-Sent Events stream for one run.

        Yields one frame per progress signal until the terminal event.
        A late subscriber (run already finished) gets a single
        ``run.snapshot`` frame and the stream closes immediately.
        """
        row = _load_owned_run(db, user_id=user.id, report_id=report_id)
        terminal_snapshot: dict[str, Any] | None = None
        if row.status in ("completed", "failed", "cancelled"):
            terminal_snapshot = {
                "status": row.status,
                "error_message": row.error_message,
            }
        broker, _ = _streaming_state(request)
        return StreamingResponse(
            _sse_stream(broker, report_id, terminal_snapshot),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    # ----- Exports -----

    @router.get("/runs/{report_id}/html", response_class=HTMLResponse)
    def get_html(
        report_id: str,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> HTMLResponse:
        try:
            row = run_svc.get_report_row(db=db, user_id=user.id, report_id=report_id)
            rendered = render_svc.render_html(db=db, user_id=user.id, report_id=report_id)
        except run_svc.ReportNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        filename = build_download_filename(row=row, ext="html")
        return HTMLResponse(
            content=rendered.html,
            headers={"Content-Disposition": f'inline; filename="{filename}"'},
        )

    @router.get("/runs/{report_id}/pdf")
    async def get_pdf(
        report_id: str,
        request: Request,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> Response:
        launcher = getattr(request.app.state, "browser_launcher", None)
        if launcher is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=(
                    "PDF rendering requires the BrowserLauncher on app.state. "
                    "Use GET /html instead."
                ),
            )
        try:
            row = run_svc.get_report_row(db=db, user_id=user.id, report_id=report_id)
            pdf_bytes = await render_svc.render_pdf(
                db=db, user_id=user.id, report_id=report_id, browser_launcher=launcher
            )
        except run_svc.ReportNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        filename = build_download_filename(row=row, ext="pdf")
        return Response(
            content=pdf_bytes,
            media_type="application/pdf",
            headers={"Content-Disposition": f'inline; filename="{filename}"'},
        )

    @router.get("/runs/{report_id}/docx")
    def get_docx(
        report_id: str,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> Response:
        try:
            row = run_svc.get_report_row(db=db, user_id=user.id, report_id=report_id)
            docx_bytes = render_svc.render_docx(db=db, user_id=user.id, report_id=report_id)
        except run_svc.ReportNotFoundError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except Exception as exc:
            log.exception("eu v2 docx render failed for report_id=%s", report_id)
            raise HTTPException(
                status_code=500,
                detail=f"eu v2 docx render failed: {type(exc).__name__}: {exc}",
            ) from exc
        filename = build_download_filename(row=row, ext="docx")
        return Response(
            content=docx_bytes,
            media_type=("application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return router


def _load_owned_run(db: DBSession, *, user_id: str, report_id: str) -> ReportEu:
    """Load a run scoped to the caller; raise 404 when missing/not owned."""
    row = db.get(ReportEu, report_id)
    if row is None or row.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"eu v2 report {report_id!r} not found",
        )
    return row
