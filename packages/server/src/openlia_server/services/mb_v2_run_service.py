"""MB v2 run lifecycle service.

Wraps ``openlia.llm.runtime.report_mb.Runner`` with database
persistence. Forked from ``eu_v2_run_service.py``: build a ``report_mb``
``RunRequest`` from a firing schedule's bound config (or an ad-hoc
on-demand config) + the resolved template + the briefing context,
construct an ``LLMSession`` + ``Runner``, run the engine, persist the
``RunResult`` into the ``report_mb`` artifact tables, and stream progress
events through the broker.

Both the on-demand route and the scheduled dispatcher call
``start_run_async``. The runner is spawned on a background asyncio task
so the route returns the ``report_id`` immediately; the client then
connects to the SSE endpoint keyed by ``report_id``.

MB v2 deltas vs. EU v2:
  - There is no per-user settings row. A schedule (or an ad-hoc
    on-demand call) binds its own template / instructions / connectors /
    model, so ``build_run_request`` takes those as explicit arguments
    rather than reading a settings service.
  - The earnings/ticker anchor is replaced by a briefing anchor: the
    request carries a ``BriefingContext`` (run date + schedule label +
    time / timezone) instead of a ``TriggerContext``. The ``report_mb``
    row has no ``ticker`` / ``fiscal_date`` columns; it carries
    ``trigger_kind`` (scheduled | on_demand), a nullable ``schedule_id``,
    and a nullable ``instructions_id``.
  - ``insert_report_row`` also creates the ``repo_items`` pointer
    (``mb_v2_report_id``) so a briefing lands in the repository at
    dispatch time.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from collections.abc import Callable, Mapping
from datetime import UTC, date, datetime

from openlia.connectors.dispatch import Dispatcher
from openlia.connectors.types import ConnectorStatus
from openlia.llm.capabilities import capabilities_for
from openlia.llm.runtime.report_mb import (
    BriefingContext,
    BrokerEmitter,
    CancelToken,
    EnabledConnectors,
    EventBroker,
    Language,
    LLMSession,
    MbDataTransports,
    ReportLength,
    Runner,
    RunRequest,
    RunResult,
    TemplateSpec,
)
from openlia.llm.types import ReasoningEffort
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.models.content import RepoItem
from openlia_server.db.models.report_mb import (
    ReportMb,
    ReportMbChart,
    ReportMbCitation,
    ReportMbSection,
    ReportMbToolCallLog,
)
from openlia_server.services import (
    connectors_service,
    dispatcher_factory,
    mb_v2_instructions_service,
    mb_v2_template_service,
)
from openlia_server.services.mb_v2_wiring import (
    build_mb_transports,
    resolve_eodhd_api_key,
)

log = logging.getLogger(__name__)

# Strong references to in-flight background tasks. asyncio.create_task
# only keeps a weak reference internally, so a task can be GC'd mid-run
# if no one holds it. We add on create and discard on completion.
_BACKGROUND_TASKS: set[asyncio.Task] = set()

# Sentinel ``template_id`` for a "No template (instructions only)" run.
# Resolves to a freeform TemplateSpec (empty sections) instead of a DB
# lookup; the run is shaped entirely by the selected instruction profile.
MB_FREEFORM_TEMPLATE_ID = "freeform"


class EmptyBriefError(ValueError):
    """A freeform run was requested with no instruction profile.

    With no template and no instructions there is nothing to shape the
    report, so the run is rejected before it starts. Callers map this to
    a 400 with the message text.
    """


class ReportNotFoundError(LookupError):
    """The requested report_mb row doesn't exist or isn't owned by the user."""


def get_report_row(*, db: DBSession, user_id: str, report_id: str) -> ReportMb:
    row = db.get(ReportMb, report_id)
    if row is None or row.user_id != user_id:
        raise ReportNotFoundError(f"MB report {report_id} not found")
    return row


def get_run(
    *, db: DBSession, user_id: str, report_id: str
) -> tuple[ReportMb, list[ReportMbSection], list[ReportMbChart], list[ReportMbCitation]]:
    """Load a report_mb row + its ordered sections/charts/citations."""
    from sqlalchemy import select as _select

    row = get_report_row(db=db, user_id=user_id, report_id=report_id)
    sections = list(
        db.execute(
            _select(ReportMbSection)
            .where(ReportMbSection.report_id == report_id)
            .order_by(ReportMbSection.section_index.asc())
        ).scalars()
    )
    charts = list(
        db.execute(_select(ReportMbChart).where(ReportMbChart.report_id == report_id)).scalars()
    )
    citations = list(
        db.execute(
            _select(ReportMbCitation)
            .where(ReportMbCitation.report_id == report_id)
            .order_by(ReportMbCitation.display_index.asc())
        ).scalars()
    )
    return row, sections, charts, citations


def _freeform_template_spec() -> TemplateSpec:
    """A sections-less template for instructions-only runs.

    ``TemplateSpec.sections`` is declared ``min_length=1`` (the shared
    v2.3 schema predates freeform), so we ``model_construct`` to bypass
    that one constraint rather than weaken the cross-engine contract.
    Safe here: the spec is never round-tripped through validation —
    only ``template_id`` is persisted, and the runner reads ``name`` /
    ``shape_description`` / the empty ``sections`` directly.
    """
    return TemplateSpec.model_construct(
        template_id=MB_FREEFORM_TEMPLATE_ID,
        name="Freeform",
        shape_description=(
            "No fixed template — the briefing's structure is guided by the "
            "analyst instructions and the subject."
        ),
        ticker_anchored=False,
        default_length=None,
        sections=[],
    )


def _today_str() -> str:
    return date.today().isoformat()


def build_run_request(
    db: DBSession,
    *,
    user_id: str,
    trigger_kind: str,
    template_id: str,
    instructions_id: str | None,
    enabled_connectors: Mapping[str, object] | None,
    provider_kind: str,
    model: str,
    language: str,
    length: str,
    reasoning_effort: str | None,
    run_date: str | None = None,
    schedule_label: str | None = None,
    time_label: str | None = None,
    timezone: str | None = None,
) -> RunRequest:
    """Build a ``report_mb.RunRequest`` from a schedule / ad-hoc config.

    Accepts the same per-run config a firing ``mb_schedules`` row binds
    (``template_id`` / ``instructions_id`` / ``enabled_connectors`` JSON
    / ``provider_kind`` / ``model`` / ``language`` / ``length`` /
    ``reasoning_effort``) or an ad-hoc on-demand config carrying the same
    fields. The briefing anchor is built from ``run_date`` (defaults to
    today for on-demand) + the schedule's ``schedule_label`` / ``time`` /
    ``timezone``.

    ``trigger_kind`` is accepted so callers pass the same value they later
    persist on the ``report_mb`` row; it does not ride on the
    ``RunRequest`` (the engine doesn't need it) but the route/dispatcher
    keep one source of truth.
    """
    del trigger_kind  # persisted on the row, not part of the engine request

    instructions_text: str | None = None
    if instructions_id:
        try:
            instructions_text = mb_v2_instructions_service.resolve_instructions(
                db=db, user_id=user_id, instructions_id=instructions_id
            )
        except mb_v2_instructions_service.InstructionsNotFoundError:
            instructions_text = None

    if template_id == MB_FREEFORM_TEMPLATE_ID:
        if not instructions_text:
            raise EmptyBriefError(
                "A freeform run (no template) requires an instruction profile. "
                "Pick a template or an instruction profile."
            )
        template = _freeform_template_spec()
    else:
        template = mb_v2_template_service.resolve_template(
            db, user_id=user_id, template_id=template_id
        )

    connectors = _build_enabled_connectors(
        db,
        enabled_connectors=enabled_connectors,
        provider_kind=provider_kind,
        model=model,
    )

    resolved_run_date = run_date or _today_str()
    briefing_context = BriefingContext(
        run_date=resolved_run_date,
        schedule_label=schedule_label,
        time_label=time_label,
        timezone=timezone,
    )
    subject = _build_subject(resolved_run_date, schedule_label)

    return RunRequest(
        subject=subject,
        template=template,
        language=Language(language),
        length=ReportLength(length),
        provider_kind=provider_kind,
        model=model,
        reasoning_effort=(
            ReasoningEffort(reasoning_effort) if reasoning_effort is not None else None
        ),
        enabled_connectors=connectors,
        briefing_context=briefing_context,
        instructions=instructions_text,
    )


def _build_subject(run_date: str, schedule_label: str | None) -> str:
    """Compose the briefing label used as the report subject."""
    if schedule_label:
        return f"{schedule_label} - {run_date}"
    return f"Morning Briefing - {run_date}"


def _build_enabled_connectors(
    db: DBSession,
    *,
    enabled_connectors: Mapping[str, object] | None,
    provider_kind: str,
    model: str,
) -> EnabledConnectors:
    """Resolve the schedule's ``enabled_connectors`` JSON into a gated set.

    Mirrors the EU gating: the schedule-enabled provider set is AND-gated
    by the validated connector registry (a provider is only honored if a
    validated connector backs it), EODHD is curated and bypasses that gate
    but still requires a resolvable key, and ``web_search`` is gated by the
    selected model's native web-search capability.
    """
    raw = enabled_connectors or {}
    provider_ids_raw = raw.get("provider_ids") or []
    if isinstance(provider_ids_raw, (list, tuple, set, frozenset)):
        providers = {str(p) for p in provider_ids_raw}
    else:
        providers = set()
    web_search_flag = bool(raw.get("web_search", False))

    eodhd_available = resolve_eodhd_api_key(db) is not None
    caps = capabilities_for(provider_kind=provider_kind, model=model)
    validated_provider_ids = {
        row.provider_id
        for row in connectors_service.list_connectors(db)
        if row.status == ConnectorStatus.VALIDATED.value
    }
    providers = {p for p in providers if p == "eodhd" or p in validated_provider_ids}
    if "eodhd" in providers and not eodhd_available:
        providers.discard("eodhd")
    return EnabledConnectors(
        provider_ids=frozenset(providers),
        web_search=web_search_flag and caps.web_search_native,
    )


def insert_report_row(
    db: DBSession,
    *,
    user_id: str,
    request: RunRequest,
    trigger_kind: str,
    schedule_id: str | None = None,
    instructions_id: str | None = None,
) -> str:
    """Insert the ``report_mb`` row + its ``repo_items`` pointer; return id.

    Creates the run in ``running`` status (the engine flips it to
    completed / failed) and a ``repo_items`` row with ``mb_v2_report_id``
    set so the briefing appears in the repository immediately.
    """
    context = request.briefing_context
    report_id = str(uuid.uuid4())
    row = ReportMb(
        id=report_id,
        user_id=user_id,
        subject=request.subject,
        trigger_kind=trigger_kind,
        schedule_id=schedule_id,
        template_id=request.template.template_id,
        instructions_id=instructions_id,
        language=request.language.value,
        length=request.length.value,
        provider_kind=request.provider_kind,
        model=request.model,
        status="running",
        error_message=None,
        created_at=datetime.now(UTC),
        completed_at=None,
        cover_json=None,
        reasoning_effort=(
            request.reasoning_effort.value if request.reasoning_effort is not None else None
        ),
    )
    db.add(row)
    db.flush()

    db.add(
        RepoItem(
            id=str(uuid.uuid4()),
            user_id=user_id,
            mb_v2_report_id=report_id,
        )
    )
    db.flush()
    del context  # briefing metadata rides on the request, not the row
    return report_id


def build_mb_dispatcher(
    db: DBSession,
    *,
    enabled_provider_ids: frozenset[str] | set[str],
) -> Dispatcher | None:
    """Build a connector ``Dispatcher`` scoped to the enabled providers.

    Blocklist semantics: every connector whose ``provider_id`` is not in
    ``enabled_provider_ids`` is passed to ``build_dispatcher`` as a disabled
    (blocked) row so the runtime router never offers its tools. EODHD is
    always blocked from the dispatcher too — it is served by the curated
    data path, so leaving it routable would make the dispatcher enumerate
    its full SDK surface only for ``build_dispatcher_tools`` to skip it.

    Returns ``None`` when there is nothing for the dispatcher to route —
    i.e. no validated connector whose provider is enabled and != "eodhd".
    The runner then stays on the curated-only path rather than carrying an
    empty dispatcher.
    """
    rows = connectors_service.list_connectors(db)
    disabled = frozenset(
        r.id for r in rows if r.provider_id not in enabled_provider_ids or r.provider_id == "eodhd"
    )
    routable = any(
        r.status == ConnectorStatus.VALIDATED.value
        and r.provider_id in enabled_provider_ids
        and r.provider_id != "eodhd"
        for r in rows
    )
    if not routable:
        return None
    return dispatcher_factory.build_dispatcher(db, disabled_connector_ids=disabled)


def start_run_async(
    db: DBSession,
    *,
    user_id: str,
    request: RunRequest,
    broker: EventBroker,
    cancel_registry: dict[str, CancelToken],
    session_factory: Callable[[], DBSession],
    trigger_kind: str = "on_demand",
    schedule_id: str | None = None,
    instructions_id: str | None = None,
    transports: MbDataTransports | None = None,
    session: LLMSession | None = None,
) -> str:
    """Insert the ``report_mb`` row, schedule the runner as a bg task.

    Returns the new ``report_id`` immediately. The background task
    publishes events through ``broker`` keyed by report_id and persists
    the outcome through a fresh session built by ``session_factory``
    (the request session that owns ``db`` closes when the route returns).

    ``session`` is an optional pre-built ``LLMSession`` (tests inject a
    fake adapter); when omitted the runner builds one from env on first
    generate. ``transports`` overrides the env-resolved EODHD bundle.
    """
    report_id = insert_report_row(
        db,
        user_id=user_id,
        request=request,
        trigger_kind=trigger_kind,
        schedule_id=schedule_id,
        instructions_id=instructions_id,
    )

    if transports is None:
        transports = build_mb_transports(api_key=resolve_eodhd_api_key(db))
    # Build the connector dispatcher from db rows now (request-time), like
    # transports — it is an in-memory object safe to hand to the bg task.
    dispatcher = build_mb_dispatcher(
        db, enabled_provider_ids=request.enabled_connectors.provider_ids
    )
    cancel_token = CancelToken()
    cancel_registry[report_id] = cancel_token
    emitter = BrokerEmitter(broker=broker, report_id=report_id)

    task = asyncio.create_task(
        _run_in_background(
            report_id=report_id,
            request=request,
            session=session,
            transports=transports,
            dispatcher=dispatcher,
            emitter=emitter,
            cancel_token=cancel_token,
            session_factory=session_factory,
            broker=broker,
            cancel_registry=cancel_registry,
        )
    )
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)

    return report_id


async def _run_in_background(
    *,
    report_id: str,
    request: RunRequest,
    session: LLMSession | None,
    transports: MbDataTransports | None,
    dispatcher: Dispatcher | None,
    emitter: BrokerEmitter,
    cancel_token: CancelToken,
    session_factory: Callable[[], DBSession],
    broker: EventBroker,
    cancel_registry: dict[str, CancelToken],
) -> None:
    """Run the engine in a background task.

    Always finishes the broker subscription (success or failure) so
    connected SSE consumers see a terminal event, and always drops the
    cancel token from the registry so cancel-after-finish is a no-op.
    """
    try:
        runner = Runner(
            request=request,
            transports=_resolve_transports(transports),
            dispatcher=dispatcher,
        )
        try:
            if session is None:
                session = LLMSession.create(
                    provider_kind=request.provider_kind,
                    model=request.model,
                )
            result = await runner.run(
                session=session,
                emitter=emitter,
                cancel_token=cancel_token,
            )
        except Exception as exc:
            log.exception("MB v2 run %s crashed unexpectedly", report_id)
            _emit_and_mark_failed(emitter, session_factory, report_id, f"unexpected: {exc}")
            return

        _persist_background_outcome(
            session_factory=session_factory,
            report_id=report_id,
            result=result,
        )
    except Exception as exc:
        # Setup-phase failures (Runner construction, session build) land
        # here — outside the inner loop's handler. Emit a terminal event +
        # mark failed so the SSE client never sees a silently-closed stream.
        log.exception("MB v2 run %s failed before the engine loop", report_id)
        _emit_and_mark_failed(emitter, session_factory, report_id, f"setup: {exc}")
    finally:
        cancel_registry.pop(report_id, None)
        broker.finish(report_id)


def _persist_background_outcome(
    *,
    session_factory: Callable[[], DBSession],
    report_id: str,
    result: RunResult,
) -> None:
    """Persist the outcome from the background task using a fresh session."""
    with session_factory() as bg_db:
        row = bg_db.get(ReportMb, report_id)
        if row is None:
            log.warning("MB v2 background outcome for missing report %s", report_id)
            return
        persist_result(bg_db, report_id=report_id, result=result)
        row.status = result.status
        row.error_message = result.message or None
        row.completed_at = datetime.now(UTC)
        bg_db.commit()


def _emit_and_mark_failed(
    emitter: BrokerEmitter,
    session_factory: Callable[[], DBSession],
    report_id: str,
    message: str,
) -> None:
    """Publish a terminal ``run.failed`` event AND flip the row to failed.

    The engine's own ``_finish`` emits run.failed for cancel/deadline, but
    an exception thrown out of ``runner.run`` (e.g. an httpx ``ReadError``
    on the LLM call) bypasses it. Without a terminal frame the SSE stream
    would close via ``broker.finish`` with no signal, leaving the client's
    generating UI spinning forever.
    """
    emitter.emit(
        "run.failed",
        {"error": message, "message": message, "partial_sections_written": 0},
    )
    _mark_failed(session_factory, report_id, message)


def _mark_failed(
    session_factory: Callable[[], DBSession],
    report_id: str,
    error_message: str,
) -> None:
    """Flip the report row to failed when the engine never returned a result."""
    with session_factory() as bg_db:
        row = bg_db.get(ReportMb, report_id)
        if row is None:
            log.warning("MB v2 background failure for missing report %s", report_id)
            return
        row.status = "failed"
        row.error_message = error_message
        row.completed_at = datetime.now(UTC)
        bg_db.commit()


def cancel_run(*, cancel_registry: dict[str, CancelToken], report_id: str) -> bool:
    """Flip the cancel flag for a running MB v2 run; return True if found."""
    token = cancel_registry.get(report_id)
    if token is None:
        return False
    token.cancel()
    return True


def persist_result(db: DBSession, *, report_id: str, result: RunResult) -> None:
    """Write sections + charts + citations + tool-call log + cover.

    Citations get ``display_index`` assigned in template order: every
    section in ``result.sections`` is scanned for ``[^source_id]``
    markers and the first appearance of each source_id wins index 1, 2,
    3, ... — the bibliography view consumes this ordering verbatim.
    """
    for index, section_payload in enumerate(result.sections):
        db.add(
            ReportMbSection(
                report_id=report_id,
                section_id=section_payload["section_id"],
                section_index=index,
                title=section_payload["title"],
                markdown=section_payload["markdown"],
            )
        )

    for chart in result.charts:
        db.add(
            ReportMbChart(
                report_id=report_id,
                chart_id=chart.chart_id,
                chart_type=chart.chart_type,
                title=chart.title,
                spec_json=chart.model_dump_json(),
                rendered_url=None,
            )
        )

    display_index_by_source_id = _assign_display_indexes(result)
    for entry in result.citations:
        db.add(
            ReportMbCitation(
                report_id=report_id,
                source_id=entry.source_id,
                tool_name=entry.tool_name,
                display_index=display_index_by_source_id.get(entry.source_id),
                provenance_json=json.dumps(entry.provenance, default=str),
            )
        )
        db.add(
            ReportMbToolCallLog(
                report_id=report_id,
                turn_index=0,
                tool_name=entry.tool_name,
                arguments_json=json.dumps(entry.arguments, default=str),
                result_summary=entry.result_summary,
                provenance_json=json.dumps(entry.provenance, default=str),
                source_id=entry.source_id,
                input_tokens=entry.input_tokens,
                output_tokens=entry.output_tokens,
                wall_time_ms=entry.wall_time_ms,
                timestamp=entry.timestamp,
            )
        )

    if result.cover is not None:
        row = db.get(ReportMb, report_id)
        if row is not None:
            row.cover_json = result.cover.model_dump_json()
    db.flush()


def _assign_display_indexes(result: RunResult) -> dict[str, int]:
    """Walk body sections in order; first-appearance source_id wins next index."""
    pattern = re.compile(r"\[\^([a-z0-9_]+)\]")
    order: list[str] = []
    seen: set[str] = set()
    for section in result.sections:
        for match in pattern.finditer(section.get("markdown", "")):
            sid = match.group(1)
            if sid in seen:
                continue
            seen.add(sid)
            order.append(sid)
    return {sid: i + 1 for i, sid in enumerate(order)}


def cleanup_orphaned_running_rows(
    *,
    db: DBSession,
    reason: str = "server restart - run did not complete",
) -> int:
    """Flip any report_mb rows stuck in 'running' (from a crash) to 'failed'.

    Call at startup. MB v2 has no batch mode, so every stuck running row is
    simply failed.
    """
    from sqlalchemy import update

    now = datetime.now(UTC)
    stmt = (
        update(ReportMb)
        .where(ReportMb.status == "running")
        .values(status="failed", error_message=reason, completed_at=now)
    )
    result = db.execute(stmt)
    db.commit()
    return result.rowcount or 0


def _null_transports() -> MbDataTransports:
    """A loud transport bundle for when EODHD is not configured.

    Every data callable raises a clear error the runner surfaces back
    to the model as a tool error (the loop never crashes on it). Used
    when ``build_mb_transports`` returns None (no ``EODHD_API_KEY``)
    and no override was supplied.
    """

    def _unconfigured(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError(
            "EODHD is not configured. Set EODHD_API_KEY to enable the market-data tools."
        )

    return MbDataTransports(
        quotes=_unconfigured,
        prices=_unconfigured,
        news=_unconfigured,
        economic_calendar=_unconfigured,
        macro_indicators=_unconfigured,
    )


def _resolve_transports(transports: MbDataTransports | None) -> MbDataTransports:
    """Resolve the data bundle: explicit override, env-wired, or null."""
    if transports is not None:
        return transports
    return build_mb_transports() or _null_transports()


__all__ = [
    "MB_FREEFORM_TEMPLATE_ID",
    "EmptyBriefError",
    "ReportNotFoundError",
    "build_mb_dispatcher",
    "build_run_request",
    "cancel_run",
    "cleanup_orphaned_running_rows",
    "get_report_row",
    "get_run",
    "insert_report_row",
    "persist_result",
    "start_run_async",
]
