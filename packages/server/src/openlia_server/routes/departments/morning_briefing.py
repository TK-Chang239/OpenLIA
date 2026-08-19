"""Morning Briefing HTTP router — single-model engine (report_mb).

Rewritten in the Earnings Update v2 shape (``earnings_update_v2.py``): a
factory-built ``APIRouter`` exposing per-schedule config + on-demand run
lifecycle for the ``report_mb`` engine. Unlike EU, Morning Briefing has
no feature gate (this is the only Morning Briefing surface) and no
per-user settings row — each schedule (or an ad-hoc on-demand call) binds
its own template / instructions / connectors / model / language / length.

Endpoints (prefix ``/departments/morning-briefing``):

- ``GET/POST   /schedules`` ``PATCH/DELETE /schedules/{id}``  cron schedules
                                                              with full binding
- ``GET/POST   /templates`` ``DELETE /templates/{id}``        report templates
- ``GET/POST   /instructions`` ``DELETE /instructions/{id}``  methodology profiles
- ``GET        /data-sources``         effective data-source list
- ``POST       /runs/start``           start a run (async) -> {report_id}
- ``GET        /runs`` ``GET /runs/{id}`` ``DELETE /runs/{id}``  run CRUD
- ``POST       /runs/{id}/cancel``     cooperative cancel
- ``GET        /runs/{id}/events``     SSE progress stream
- ``GET        /runs/{id}/html``       rendered HTML download
- ``GET        /runs/{id}/pdf``        rendered PDF download (needs browser launcher)
- ``GET        /runs/{id}/docx``       native .docx download

The Morning Briefing feed lists ``report_mb`` rows directly (via
``GET /runs``); the run service does not auto-create ``repo_items``
pointers. A pointer is created only on explicit save (see
``services/repo.save_mb_report_to_repo``).
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any, Literal

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
from openlia.llm.runtime.report_mb import (
    CancelToken,
    EventBroker,
    is_finish_sentinel,
)
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.deps import make_session_dependency
from openlia_server.db.models.auth import User
from openlia_server.db.models.report_mb import (
    ReportMb,
    ReportMbChart,
    ReportMbCitation,
    ReportMbSection,
)
from openlia_server.middleware.auth import build_require_active_user
from openlia_server.services import mb_v2_data_sources
from openlia_server.services import mb_v2_instructions_service as instructions_svc
from openlia_server.services import mb_v2_render_service as render_svc
from openlia_server.services import mb_v2_run_service as run_svc
from openlia_server.services import mb_v2_schedules as schedules_svc
from openlia_server.services import mb_v2_template_service as templates_svc
from openlia_server.services.attachments import (
    FileUpload,
    extract_text,
    validate_uploads,
)
from openlia_server.services.mb_v2_filename import build_download_filename
from openlia_server.services.user_prefs import resolve_report_language

log = logging.getLogger(__name__)

# Defaults for the data-sources + ad-hoc run endpoints when the caller supplies
# neither a referenced schedule nor explicit fields. Mirror the EU v2 settings
# defaults so web-search availability is computed against a real model.
_DEFAULT_PROVIDER_KIND = "anthropic"
_DEFAULT_MODEL = "claude-sonnet-4-6"

# The freeform sentinel id, re-exported through the run service.
MB_FREEFORM_TEMPLATE_ID = run_svc.MB_FREEFORM_TEMPLATE_ID


# ---------------------------------------------------------------------------
# Payloads
# ---------------------------------------------------------------------------


class EnabledConnectorsIn(BaseModel):
    provider_ids: list[str] = Field(default_factory=list)
    web_search: bool = False


class ScheduleIn(BaseModel):
    time: str = Field(pattern=r"^([01]\d|2[0-3]):[0-5]\d$")
    timezone: str = Field(min_length=3, max_length=64)
    days_of_week: list[Literal["mon", "tue", "wed", "thu", "fri", "sat", "sun"]] = Field(
        min_length=1
    )
    label: str = Field(default="", max_length=64)
    template_id: str | None = None
    instructions_id: str | None = None
    enabled_connectors: EnabledConnectorsIn = Field(default_factory=EnabledConnectorsIn)
    provider_kind: str | None = None
    model: str | None = None
    # None = no explicit choice; the route resolves it against the user's
    # global report-language pref.
    language: str | None = None
    length: str = "normal"
    reasoning_effort: str | None = None
    is_enabled: bool = True


class ScheduleOut(BaseModel):
    id: str
    time: str
    timezone: str
    days_of_week: list[str]
    label: str
    is_enabled: bool
    template_id: str | None
    instructions_id: str | None
    enabled_connectors: dict[str, Any]
    provider_kind: str | None
    model: str | None
    language: str
    length: str
    reasoning_effort: str | None
    web_search: bool


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


class RunStartIn(BaseModel):
    """Start a run either by referencing a schedule's bound config, or by
    supplying an ad-hoc config inline.

    When ``schedule_id`` is set, every other field is ignored and the run
    reuses that schedule's binding. Otherwise the ad-hoc fields shape the run
    (``template_id`` defaults to the freeform sentinel only with instructions).
    """

    schedule_id: str | None = None
    template_id: str = "mb_default"
    instructions_id: str | None = None
    enabled_connectors: EnabledConnectorsIn = Field(default_factory=EnabledConnectorsIn)
    provider_kind: str = _DEFAULT_PROVIDER_KIND
    model: str = _DEFAULT_MODEL
    language: str | None = None
    length: str = "normal"
    reasoning_effort: str | None = None


class RunStartOut(BaseModel):
    report_id: str


class RunSummaryOut(BaseModel):
    report_id: str
    subject: str
    trigger_kind: str
    schedule_id: str | None
    template_id: str
    instructions_id: str | None
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


def _schedule_out(dto: schedules_svc.MbScheduleDTO) -> ScheduleOut:
    return ScheduleOut(
        id=dto.id,
        time=dto.time,
        timezone=dto.timezone,
        days_of_week=list(dto.days_of_week),
        label=dto.label,
        is_enabled=dto.is_enabled,
        template_id=dto.template_id,
        instructions_id=dto.instructions_id,
        enabled_connectors=dict(dto.enabled_connectors),
        provider_kind=dto.provider_kind,
        model=dto.model,
        language=dto.language,
        length=dto.length,
        reasoning_effort=dto.reasoning_effort,
        web_search=dto.web_search,
    )


def _data_source_out(s: mb_v2_data_sources.DataSource) -> DataSourceOut:
    return DataSourceOut(
        key=s.key,
        display_name=s.display_name,
        category=s.category,
        routing=s.routing,
        available=s.available,
        enabled=s.enabled,
        unavailable_reason=s.unavailable_reason,
    )


def _summary(row: ReportMb) -> RunSummaryOut:
    return RunSummaryOut(
        report_id=row.id,
        subject=row.subject,
        trigger_kind=row.trigger_kind,
        schedule_id=row.schedule_id,
        template_id=row.template_id,
        instructions_id=row.instructions_id,
        language=row.language,
        length=row.length,
        status=row.status,
        created_at=row.created_at,
        completed_at=row.completed_at,
        reasoning_effort=row.reasoning_effort,
        highlights=_card_highlights(row.cover_json),
    )


def _section_out(row: ReportMbSection) -> SectionOut:
    return SectionOut(
        section_id=row.section_id,
        section_index=row.section_index,
        title=row.title,
        markdown=row.markdown,
        version=row.version,
    )


def _chart_out(row: ReportMbChart) -> ChartOut:
    return ChartOut(
        chart_id=row.chart_id,
        chart_type=row.chart_type,
        title=row.title,
        spec=json.loads(row.spec_json),
        rendered_url=row.rendered_url,
        version=row.version,
    )


def _citation_out(row: ReportMbCitation) -> CitationOut:
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
# Streaming-state + SSE helpers
# ---------------------------------------------------------------------------


def _streaming_state(request: Request) -> tuple[EventBroker, dict[str, CancelToken]]:
    """Pull the MB v2 broker + cancel registry off ``app.state``.

    Wired at app startup. Read at call time so a startup-time race doesn't
    leave a stale reference behind.
    """
    broker = getattr(request.app.state, "mb_v2_event_broker", None)
    registry = getattr(request.app.state, "mb_v2_cancel_registry", None)
    if broker is None or registry is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "MB v2 streaming infrastructure not initialised. The app "
                "must run with the mb_v2 broker wired on app.state."
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


# ---------------------------------------------------------------------------
# Module-level async marker handler (see EU v2 for the rationale).
# ---------------------------------------------------------------------------


async def start_run() -> None:  # pragma: no cover - structural guard marker
    """Marker: the MB v2 start handler must be ``async def``.

    See ``build_morning_briefing_router.start_run_async``.
    """
    raise NotImplementedError("use the router-bound start_run_async handler")


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------


def build_morning_briefing_router(
    *,
    db_session_factory: Callable[[], DBSession],
    mode: Literal["personal", "company"],
) -> APIRouter:
    require_auth = build_require_active_user(db_session_factory=db_session_factory, mode=mode)
    session_dep = make_session_dependency(db_session_factory)
    router = APIRouter(prefix="/departments/morning-briefing", tags=["morning-briefing"])

    def _optional_scheduler(request: Request):
        scheduler = getattr(request.app.state, "scheduler", None)
        if scheduler is None:
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "scheduler not initialized")
        return scheduler

    # ----- Schedules -----

    @router.get("/schedules", response_model=list[ScheduleOut])
    def list_schedules(
        user: User = require_auth,
        db: DBSession = Depends(session_dep),
    ) -> list[ScheduleOut]:
        return [_schedule_out(d) for d in schedules_svc.list_schedules(db, user_id=user.id)]

    @router.post(
        "/schedules",
        response_model=ScheduleOut,
        status_code=status.HTTP_201_CREATED,
    )
    async def create_schedule(
        payload: ScheduleIn,
        user: User = require_auth,
        db: DBSession = Depends(session_dep),
        scheduler=Depends(_optional_scheduler),
    ) -> ScheduleOut:
        try:
            dto = await schedules_svc.create_schedule(
                db,
                user_id=user.id,
                time=payload.time,
                timezone=payload.timezone,
                days_of_week=list(payload.days_of_week),
                label=payload.label,
                scheduler=scheduler,
                template_id=payload.template_id,
                instructions_id=payload.instructions_id,
                enabled_connectors=payload.enabled_connectors.model_dump(),
                provider_kind=payload.provider_kind,
                model=payload.model,
                language=resolve_report_language(db, user_id=user.id, explicit=payload.language),
                length=payload.length,
                reasoning_effort=payload.reasoning_effort,
                web_search=payload.enabled_connectors.web_search,
                is_enabled=payload.is_enabled,
            )
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
        return _schedule_out(dto)

    @router.patch("/schedules/{schedule_id}", response_model=ScheduleOut)
    async def update_schedule(
        schedule_id: str,
        payload: ScheduleIn,
        user: User = require_auth,
        db: DBSession = Depends(session_dep),
        scheduler=Depends(_optional_scheduler),
    ) -> ScheduleOut:
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
                template_id=payload.template_id,
                instructions_id=payload.instructions_id,
                enabled_connectors=payload.enabled_connectors.model_dump(),
                provider_kind=payload.provider_kind,
                model=payload.model,
                language=resolve_report_language(db, user_id=user.id, explicit=payload.language),
                length=payload.length,
                reasoning_effort=payload.reasoning_effort,
                web_search=payload.enabled_connectors.web_search,
                is_enabled=payload.is_enabled,
            )
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
        if dto is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "schedule not found")
        return _schedule_out(dto)

    @router.delete("/schedules/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
    async def delete_schedule(
        schedule_id: str,
        user: User = require_auth,
        db: DBSession = Depends(session_dep),
        scheduler=Depends(_optional_scheduler),
    ) -> None:
        deleted = await schedules_svc.delete_schedule(
            db, user_id=user.id, schedule_id=schedule_id, scheduler=scheduler
        )
        if not deleted:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "schedule not found")

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
    async def upload_template(
        request: Request,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> TemplateOut:
        """Create a template from either a JSON markdown body or a document
        upload (mirrors EU's two-channel template intake)."""
        content_type = request.headers.get("content-type", "")
        if content_type.startswith("multipart/form-data"):
            form = await request.form()
            name = str(form.get("name") or "").strip()
            upload_file = form.get("file")
            if not name or upload_file is None:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    "multipart upload requires both 'name' and 'file' fields",
                )
            raw = await upload_file.read()
            upload = FileUpload(
                filename=getattr(upload_file, "filename", None) or "unnamed",
                mime_type=getattr(upload_file, "content_type", None) or "application/octet-stream",
                content=raw,
            )
            errors = validate_uploads([upload])
            if errors:
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    {"errors": [{"filename": e.filename, "reason": e.reason} for e in errors]},
                )
            markdown = extract_text(upload) or ""
            source_blob: bytes | None = raw
            source_mime: str | None = upload.mime_type
        else:
            body = await request.json()
            try:
                parsed = TemplateCreateIn.model_validate(body)
            except ValueError as exc:
                raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, str(exc)) from exc
            name = parsed.name
            markdown = parsed.source_markdown
            source_blob = None
            source_mime = None

        try:
            row = templates_svc.create_template_from_markdown(
                db=db,
                user_id=user.id,
                name=name,
                markdown=markdown,
                source_doc_blob=source_blob,
                source_doc_mime=source_mime,
            )
        except templates_svc.TemplateValidationError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
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
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
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
                status.HTTP_400_BAD_REQUEST,
                {"errors": [{"filename": e.filename, "reason": e.reason} for e in errors]},
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
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc
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
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
        db.commit()
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    # ----- Data sources -----

    @router.get("/data-sources", response_model=DataSourcesOut)
    def get_data_sources(
        schedule_id: str | None = Query(default=None),
        provider_kind: str | None = Query(default=None),
        model: str | None = Query(default=None),
        enabled_provider_ids: list[str] | None = Query(default=None),
        web_search: bool | None = Query(default=None),
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> DataSourcesOut:
        """Compute the effective data-source list.

        MB has no settings table, so the binding is sourced from a referenced
        schedule (``schedule_id``) when given, then overridden by any explicit
        query params; with neither it falls back to sensible defaults (empty
        enabled set, no web search, default model for capability checks).
        """
        eff_provider = provider_kind or _DEFAULT_PROVIDER_KIND
        eff_model = model or _DEFAULT_MODEL
        eff_enabled: set[str] = set(enabled_provider_ids or [])
        eff_web_search = bool(web_search) if web_search is not None else False

        if schedule_id is not None:
            dto = schedules_svc.get_schedule_by_id(db, user_id=user.id, schedule_id=schedule_id)
            if dto is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "schedule not found")
            if provider_kind is None and dto.provider_kind:
                eff_provider = dto.provider_kind
            if model is None and dto.model:
                eff_model = dto.model
            if enabled_provider_ids is None:
                raw_ids = dto.enabled_connectors.get("provider_ids") or []
                eff_enabled = {str(p) for p in raw_ids}
            if web_search is None:
                eff_web_search = dto.web_search

        ds = mb_v2_data_sources.compute_data_sources(
            db,
            provider_kind=eff_provider,
            model=eff_model,
            enabled_provider_ids=eff_enabled,
            web_search_enabled=eff_web_search,
        )
        return DataSourcesOut(sources=[_data_source_out(s) for s in ds.sources])

    # ----- Runs -----

    @router.post("/runs/start", response_model=RunStartOut)
    async def start_run_async(
        payload: RunStartIn,
        request: Request,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> RunStartOut:
        """Non-blocking POST: returns ``{report_id}`` immediately.

        Defined as ``async def`` so ``run_svc.start_run_async`` (which calls
        ``asyncio.create_task``) runs on the main asyncio loop.
        """
        broker, cancel_registry = _streaming_state(request)

        schedule_id = payload.schedule_id
        schedule_label: str | None = None
        time_label: str | None = None
        timezone: str | None = None

        if schedule_id is not None:
            dto = schedules_svc.get_schedule_by_id(db, user_id=user.id, schedule_id=schedule_id)
            if dto is None:
                raise HTTPException(status.HTTP_404_NOT_FOUND, "schedule not found")
            template_id = dto.template_id or MB_FREEFORM_TEMPLATE_ID
            instructions_id = dto.instructions_id
            enabled_connectors = dict(dto.enabled_connectors)
            provider_kind = dto.provider_kind or _DEFAULT_PROVIDER_KIND
            model = dto.model or _DEFAULT_MODEL
            language = dto.language
            length = dto.length
            reasoning_effort = dto.reasoning_effort
            schedule_label = dto.label or None
            time_label = dto.time
            timezone = dto.timezone
        else:
            template_id = payload.template_id
            instructions_id = payload.instructions_id
            enabled_connectors = payload.enabled_connectors.model_dump()
            provider_kind = payload.provider_kind
            model = payload.model
            language = resolve_report_language(db, user_id=user.id, explicit=payload.language)
            length = payload.length
            reasoning_effort = payload.reasoning_effort

        try:
            run_request = run_svc.build_run_request(
                db,
                user_id=user.id,
                trigger_kind="on_demand",
                template_id=template_id,
                instructions_id=instructions_id,
                enabled_connectors=enabled_connectors,
                provider_kind=provider_kind,
                model=model,
                language=language,
                length=length,
                reasoning_effort=reasoning_effort,
                run_date=None,
                schedule_label=schedule_label,
                time_label=time_label,
                timezone=timezone,
            )
        except run_svc.EmptyBriefError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc)) from exc

        report_id = run_svc.start_run_async(
            db,
            user_id=user.id,
            request=run_request,
            broker=broker,
            cancel_registry=cancel_registry,
            session_factory=db_session_factory,
            trigger_kind="on_demand",
            schedule_id=schedule_id,
            instructions_id=instructions_id,
        )
        db.commit()
        return RunStartOut(report_id=report_id)

    @router.get("/runs", response_model=list[RunSummaryOut])
    def list_runs(
        status_filter: str | None = Query(default=None, alias="status"),
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> list[RunSummaryOut]:
        stmt = select(ReportMb).where(ReportMb.user_id == user.id)
        if status_filter is not None:
            stmt = stmt.where(ReportMb.status == status_filter)
        stmt = stmt.order_by(ReportMb.created_at.desc())
        rows = db.execute(stmt).scalars().all()
        return [_summary(r) for r in rows]

    @router.get("/runs/{report_id}", response_model=RunDetailOut)
    def get_run(
        report_id: str,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> RunDetailOut:
        try:
            row, sections, charts, citations = run_svc.get_run(
                db=db, user_id=user.id, report_id=report_id
            )
        except run_svc.ReportNotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
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
        try:
            row = run_svc.get_report_row(db=db, user_id=user.id, report_id=report_id)
        except run_svc.ReportNotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
        db.delete(row)
        db.commit()

    @router.post("/runs/{report_id}/cancel", response_model=CancelOut)
    def cancel_run(
        report_id: str,
        request: Request,
        db: DBSession = Depends(session_dep),
        user: User = require_auth,
    ) -> CancelOut:
        try:
            run_svc.get_report_row(db=db, user_id=user.id, report_id=report_id)
        except run_svc.ReportNotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
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

        Yields one frame per progress signal until the terminal event. A
        late subscriber (run already finished) gets a single ``run.snapshot``
        frame and the stream closes immediately.
        """
        try:
            row = run_svc.get_report_row(db=db, user_id=user.id, report_id=report_id)
        except run_svc.ReportNotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
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
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
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
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
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
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
        except Exception as exc:
            log.exception("mb v2 docx render failed for report_id=%s", report_id)
            raise HTTPException(
                status_code=500,
                detail=f"mb v2 docx render failed: {type(exc).__name__}: {exc}",
            ) from exc
        filename = build_download_filename(row=row, ext="docx")
        return Response(
            content=docx_bytes,
            media_type=("application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    return router
