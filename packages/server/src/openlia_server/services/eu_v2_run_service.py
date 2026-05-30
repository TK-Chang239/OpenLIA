"""EU v2 run lifecycle service.

Wraps ``openlia.llm.runtime.report_eu.Runner`` with database
persistence. Mirrors ``v3_run_service.py``: build a ``report_eu``
``RunRequest`` from per-user settings + the resolved template + the
trigger context, construct an ``LLMSession`` + ``Runner``, run the
engine, persist the ``RunResult`` into the ``report_eu`` artifact
tables, and stream progress events through the broker.

Both the on-demand route and the scheduled dispatcher call
``start_run_async``. The runner is spawned on a background asyncio
task so the route returns the ``report_id`` immediately; the client
then connects to the SSE endpoint keyed by ``report_id``.

EU v2 deltas vs. v3:
  - ``Runner`` carries ``request`` + ``transports`` on the dataclass
    (v3 passes ``request`` into ``run``); ``run`` here is keyword-only
    (``session`` / ``emitter`` / ``cancel_token``).
  - No capability gate at session construction (web search is opt-in).
  - The ``report_eu`` row carries ``ticker`` / ``trigger_kind`` /
    ``fiscal_date`` anchor columns.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from openlia.llm.runtime.report_eu import (
    BrokerEmitter,
    CancelToken,
    EnabledConnectors,
    EuDataTransports,
    EventBroker,
    Language,
    LLMSession,
    ReportLength,
    Runner,
    RunRequest,
    RunResult,
    TriggerContext,
)
from openlia.llm.types import ReasoningEffort
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.models.report_eu import (
    ReportEu,
    ReportEuChart,
    ReportEuCitation,
    ReportEuSection,
    ReportEuToolCallLog,
)
from openlia_server.services import eu_v2_settings, eu_v2_template_service
from openlia_server.services.eu_v2_wiring import build_eu_v2_transports

log = logging.getLogger(__name__)

# Strong references to in-flight background tasks. asyncio.create_task
# only keeps a weak reference internally, so a task can be GC'd mid-run
# if no one holds it. We add on create and discard on completion.
_BACKGROUND_TASKS: set[asyncio.Task] = set()


def build_run_request(
    db: DBSession,
    *,
    user_id: str,
    ticker: str,
    trigger_kind: str,
    fiscal_period: str | None,
    report_date: str | None,
    release_timing: str | None,
    eps_estimate: str | None,
    revenue_estimate: str | None,
) -> RunRequest:
    """Build a ``report_eu.RunRequest`` from settings + template + trigger.

    ``trigger_kind`` is accepted so callers pass the same value they
    later persist on the ``report_eu`` row; it does not ride on the
    ``RunRequest`` (the engine doesn't need it) but the route/dispatcher
    keep one source of truth.
    """
    del trigger_kind  # persisted on the row, not part of the engine request
    settings = eu_v2_settings.get_settings(db, user_id=user_id)
    template = eu_v2_template_service.resolve_template(
        db, user_id=user_id, template_id=settings.template_id
    )

    connectors = EnabledConnectors(
        financial=settings.financial_enabled,
        earnings_calendar=settings.calendar_enabled,
        web_search=settings.web_search_enabled,
    )
    trigger_context = TriggerContext(
        ticker=ticker,
        company_name=None,
        fiscal_period=fiscal_period,
        report_date=report_date,
        release_timing=release_timing,
        eps_estimate=eps_estimate,
        revenue_estimate=revenue_estimate,
    )
    subject = f"{ticker} {fiscal_period} earnings" if fiscal_period else f"{ticker} earnings"

    return RunRequest(
        subject=subject,
        template=template,
        language=Language(settings.language),
        length=ReportLength(settings.length),
        provider_kind=settings.provider_kind,
        model=settings.model,
        reasoning_effort=(
            ReasoningEffort(settings.reasoning_effort)
            if settings.reasoning_effort is not None
            else None
        ),
        enabled_connectors=connectors,
        trigger_context=trigger_context,
    )


def start_run_async(
    db: DBSession,
    *,
    user_id: str,
    request: RunRequest,
    broker: EventBroker,
    cancel_registry: dict[str, CancelToken],
    session_factory: Callable[[], DBSession],
    trigger_kind: str = "on_demand",
    transports: EuDataTransports | None = None,
    session: LLMSession | None = None,
) -> str:
    """Insert the ``report_eu`` row, schedule the runner as a bg task.

    Returns the new ``report_id`` immediately. The background task
    publishes events through ``broker`` keyed by report_id and persists
    the outcome through a fresh session built by ``session_factory``
    (the request session that owns ``db`` closes when the route returns).

    ``session`` is an optional pre-built ``LLMSession`` (tests inject a
    fake adapter); when omitted the runner builds one from env on first
    generate. ``transports`` overrides the env-resolved EODHD bundle.
    """
    trigger = request.trigger_context
    report_id = str(uuid.uuid4())
    created_at = datetime.now(UTC)

    row = ReportEu(
        id=report_id,
        user_id=user_id,
        subject=request.subject,
        ticker=trigger.ticker if trigger is not None else request.subject,
        trigger_kind=trigger_kind,
        fiscal_date=trigger.report_date if trigger is not None else None,
        template_id=request.template.template_id,
        language=request.language.value,
        length=request.length.value,
        provider_kind=request.provider_kind,
        model=request.model,
        status="running",
        error_message=None,
        created_at=created_at,
        completed_at=None,
        cover_json=None,
        reasoning_effort=(
            request.reasoning_effort.value if request.reasoning_effort is not None else None
        ),
    )
    db.add(row)
    db.flush()

    cancel_token = CancelToken()
    cancel_registry[report_id] = cancel_token
    emitter = BrokerEmitter(broker=broker, report_id=report_id)

    task = asyncio.create_task(
        _run_in_background(
            report_id=report_id,
            request=request,
            session=session,
            transports=transports,
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
    transports: EuDataTransports | None,
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
        runner = Runner(request=request, transports=_resolve_transports(transports))
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
            log.exception("EU v2 run %s crashed unexpectedly", report_id)
            _mark_failed(session_factory, report_id, f"unexpected: {exc}")
            return

        _persist_background_outcome(
            session_factory=session_factory,
            report_id=report_id,
            result=result,
        )
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
        row = bg_db.get(ReportEu, report_id)
        if row is None:
            log.warning("EU v2 background outcome for missing report %s", report_id)
            return
        persist_result(bg_db, report_id=report_id, result=result)
        row.status = result.status
        row.error_message = result.message or None
        row.completed_at = datetime.now(UTC)
        bg_db.commit()


def _mark_failed(
    session_factory: Callable[[], DBSession],
    report_id: str,
    error_message: str,
) -> None:
    """Flip the report row to failed when the engine never returned a result."""
    with session_factory() as bg_db:
        row = bg_db.get(ReportEu, report_id)
        if row is None:
            log.warning("EU v2 background failure for missing report %s", report_id)
            return
        row.status = "failed"
        row.error_message = error_message
        row.completed_at = datetime.now(UTC)
        bg_db.commit()


def cancel_run(*, cancel_registry: dict[str, CancelToken], report_id: str) -> bool:
    """Flip the cancel flag for a running EU v2 run; return True if found."""
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
            ReportEuSection(
                report_id=report_id,
                section_id=section_payload["section_id"],
                section_index=index,
                title=section_payload["title"],
                markdown=section_payload["markdown"],
            )
        )

    for chart in result.charts:
        db.add(
            ReportEuChart(
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
            ReportEuCitation(
                report_id=report_id,
                source_id=entry.source_id,
                tool_name=entry.tool_name,
                display_index=display_index_by_source_id.get(entry.source_id),
                provenance_json=json.dumps(entry.provenance, default=str),
            )
        )
        db.add(
            ReportEuToolCallLog(
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
        row = db.get(ReportEu, report_id)
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
    """Flip any report_eu rows stuck in 'running' (from a crash) to 'failed'. Call at startup."""
    from sqlalchemy import update

    now = datetime.now(UTC)
    stmt = (
        update(ReportEu)
        .where(ReportEu.status == "running")
        .values(status="failed", error_message=reason, completed_at=now)
    )
    result = db.execute(stmt)
    db.commit()
    return result.rowcount or 0


def _null_transports() -> EuDataTransports:
    """A loud transport bundle for when EODHD is not configured.

    Every data callable raises a clear error the runner surfaces back
    to the model as a tool error (the loop never crashes on it). Used
    when ``build_eu_v2_transports`` returns None (no ``EODHD_API_KEY``)
    and no override was supplied.
    """

    def _unconfigured(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError(
            "EODHD is not configured. Set EODHD_API_KEY to enable the "
            "financial / earnings-calendar data tools."
        )

    return EuDataTransports(
        fundamentals=_unconfigured,
        prices=_unconfigured,
        news=_unconfigured,
        earnings_calendar=_unconfigured,
    )


def _resolve_transports(transports: EuDataTransports | None) -> EuDataTransports:
    """Resolve the data bundle: explicit override, env-wired, or null."""
    if transports is not None:
        return transports
    return build_eu_v2_transports() or _null_transports()


__all__ = [
    "build_run_request",
    "cancel_run",
    "cleanup_orphaned_running_rows",
    "persist_result",
    "start_run_async",
]
