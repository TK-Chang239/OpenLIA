"""v3 run lifecycle service.

Wraps ``openlia.llm.runtime.report_v3.Runner`` with database
persistence. Each ``start_run`` call:

  1. Creates a ``ReportV3`` row with status="running".
  2. Executes ``Runner.run`` (which builds + runs the tool-use loop).
  3. Persists the full ``RunWorkspace`` + ``CitationLedger`` into the
     five v3 tables in one transaction.
  4. Updates the report row with the final status + completed_at +
     error_message.
  5. Returns the populated ``RunResult`` and the persisted row id.

Persistence happens once at completion (or once on failure with
partial work preserved) — there are no per-tool-call hooks in Phase
2a. Phase 3 adds streaming events that can mirror state mid-run.

The render pipeline (chart_renderer, citation_rewriter,
report_assembler) lands in Phase 2b; this module only owns the
write-path through to the DB.
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from openlia.llm.runtime.report_v3 import (
    BrokerEmitter,
    CancelToken,
    CapabilityError,
    DataTransports,
    EventBroker,
    LLMSession,
    Runner,
    RunRequest,
    RunResult,
)
from sqlalchemy import select, update
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.models.report_v3 import (
    ReportV3,
    ReportV3Chart,
    ReportV3Citation,
    ReportV3Section,
    ReportV3ToolCallLog,
)

log = logging.getLogger(__name__)

# Strong references to in-flight background tasks. asyncio.create_task
# only keeps a weak reference internally, so a task can be GC'd mid-run
# if no one holds it. We add on create and discard on completion.
_BACKGROUND_TASKS: set[asyncio.Task] = set()


class ReportNotFoundError(LookupError):
    """The requested v3 report row does not exist for this user."""


@dataclass(frozen=True)
class StartRunResult:
    """Outcome of a start_run call.

    ``report_id`` is the persisted row's id (also the v3 run id);
    ``result`` is the ``RunResult`` the runner returned (status,
    sections, charts, citations).
    """

    report_id: str
    result: RunResult


async def start_run(
    *,
    db: DBSession,
    user_id: str,
    request: RunRequest,
    runner: Runner | None = None,
    session: LLMSession | None = None,
    transports: DataTransports | None = None,
) -> StartRunResult:
    """Create a Report row, run the engine, persist the outcome."""
    report_id = str(uuid.uuid4())
    created_at = datetime.now(UTC)

    row = ReportV3(
        id=report_id,
        user_id=user_id,
        subject=request.subject,
        template_id=request.template.template_id,
        language=request.language.value,
        length=request.length.value,
        provider_kind=request.provider_kind,
        model=request.model,
        status="running",
        error_message=None,
        created_at=created_at,
        completed_at=None,
    )
    db.add(row)
    db.flush()

    runner = runner or _default_runner(transports)

    try:
        result = await runner.run(request, session=session)
    except CapabilityError as exc:
        row.status = "failed"
        row.error_message = str(exc)
        row.completed_at = datetime.now(UTC)
        db.flush()
        raise
    except Exception as exc:
        row.status = "failed"
        row.error_message = f"unexpected: {exc}"
        row.completed_at = datetime.now(UTC)
        db.flush()
        raise

    _persist_outcome(db=db, report_row=row, result=result, runner=runner)

    return StartRunResult(report_id=report_id, result=result)


def get_run(
    *,
    db: DBSession,
    user_id: str,
    report_id: str,
) -> tuple[ReportV3, list[ReportV3Section], list[ReportV3Chart], list[ReportV3Citation]]:
    """Return the report row + its sections (ordered) + charts + citations.

    Raises ``ReportNotFoundError`` if the row is missing or owned by a
    different user.
    """
    row = _load_report(db=db, user_id=user_id, report_id=report_id)
    sections = list(
        db.scalars(
            select(ReportV3Section)
            .where(ReportV3Section.report_id == report_id)
            .order_by(ReportV3Section.section_index)
        )
    )
    charts = list(
        db.scalars(
            select(ReportV3Chart)
            .where(ReportV3Chart.report_id == report_id)
            .order_by(ReportV3Chart.id)
        )
    )
    citations = list(
        db.scalars(
            select(ReportV3Citation)
            .where(ReportV3Citation.report_id == report_id)
            .order_by(ReportV3Citation.display_index.is_(None), ReportV3Citation.display_index)
        )
    )
    return row, sections, charts, citations


def list_runs(
    *,
    db: DBSession,
    user_id: str,
    status: str | None = None,
    limit: int = 50,
) -> list[ReportV3]:
    """Return the caller's reports (newest first). Optional status filter."""
    stmt = select(ReportV3).where(ReportV3.user_id == user_id)
    if status:
        stmt = stmt.where(ReportV3.status == status)
    stmt = stmt.order_by(ReportV3.created_at.desc()).limit(limit)
    return list(db.scalars(stmt))


def delete_run(*, db: DBSession, user_id: str, report_id: str) -> None:
    """Drop the report and all child rows (FK cascade)."""
    row = _load_report(db=db, user_id=user_id, report_id=report_id)
    db.delete(row)
    db.flush()


# ---------------------------------------------------------------------------
# Async / streaming variant
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StartRunHandle:
    """Lightweight handle returned by ``start_run_async``.

    The route immediately returns ``report_id`` to the client; the
    background task continues running independently. The client then
    connects to the SSE endpoint keyed by ``report_id`` to receive
    progress events.
    """

    report_id: str


def start_run_async(
    *,
    db: DBSession,
    user_id: str,
    request: RunRequest,
    session_factory: Callable[[], DBSession],
    broker: EventBroker,
    cancel_registry: dict[str, CancelToken],
    runner: Runner | None = None,
    llm_session: LLMSession | None = None,
    transports: DataTransports | None = None,
) -> StartRunHandle:
    """Create the Report row, schedule the runner as a background task.

    Returns immediately with the new report_id. The background task
    publishes events through ``broker`` keyed by report_id. Cancel
    tokens land in ``cancel_registry`` so the cancel endpoint can
    flip them without sharing object references through HTTP.

    ``session_factory`` must return a fresh DB session — the request
    session that owns ``db`` closes when the route returns, so the
    background task does its own write inside its own session.
    """
    report_id = str(uuid.uuid4())
    created_at = datetime.now(UTC)

    row = ReportV3(
        id=report_id,
        user_id=user_id,
        subject=request.subject,
        template_id=request.template.template_id,
        language=request.language.value,
        length=request.length.value,
        provider_kind=request.provider_kind,
        model=request.model,
        status="running",
        error_message=None,
        created_at=created_at,
        completed_at=None,
    )
    db.add(row)
    db.flush()

    cancel_token = CancelToken()
    cancel_registry[report_id] = cancel_token

    bg_runner = runner or _default_runner(transports)
    emitter = BrokerEmitter(broker=broker, report_id=report_id)

    task = asyncio.create_task(
        _run_in_background(
            report_id=report_id,
            user_id=user_id,
            request=request,
            runner=bg_runner,
            session=llm_session,
            emitter=emitter,
            cancel_token=cancel_token,
            session_factory=session_factory,
            broker=broker,
            cancel_registry=cancel_registry,
        )
    )
    _BACKGROUND_TASKS.add(task)
    task.add_done_callback(_BACKGROUND_TASKS.discard)

    return StartRunHandle(report_id=report_id)


async def _run_in_background(
    *,
    report_id: str,
    user_id: str,
    request: RunRequest,
    runner: Runner,
    session: LLMSession | None,
    emitter: BrokerEmitter,
    cancel_token: CancelToken,
    session_factory: Callable[[], DBSession],
    broker: EventBroker,
    cancel_registry: dict[str, CancelToken],
) -> None:
    """Run the engine in a background task.

    Always finishes the broker subscription (success, failure, or
    cancel) so connected SSE consumers see a terminal event. Always
    drops the cancel token from the registry so cancel-after-finish
    is a no-op rather than a memory leak.
    """
    del user_id  # not currently used post-row-creation; reserved for audit logs
    try:
        try:
            result = await runner.run(
                request,
                session=session,
                emitter=emitter,
                cancel_token=cancel_token,
            )
        except CapabilityError as exc:
            _mark_failed(session_factory, report_id, str(exc))
            return
        except Exception as exc:
            log.exception("v3 run %s crashed unexpectedly", report_id)
            _mark_failed(session_factory, report_id, f"unexpected: {exc}")
            return

        _persist_background_outcome(
            session_factory=session_factory,
            report_id=report_id,
            result=result,
            runner=runner,
        )
    finally:
        cancel_registry.pop(report_id, None)
        broker.finish(report_id)


def _mark_failed(
    session_factory: Callable[[], DBSession],
    report_id: str,
    error_message: str,
) -> None:
    """Update the Report row to failed when the engine never returned a result."""
    with session_factory() as bg_db:
        row = bg_db.get(ReportV3, report_id)
        if row is None:
            log.warning("v3 background failure for missing report %s", report_id)
            return
        row.status = "failed"
        row.error_message = error_message
        row.completed_at = datetime.now(UTC)
        bg_db.commit()


def _persist_background_outcome(
    *,
    session_factory: Callable[[], DBSession],
    report_id: str,
    result: RunResult,
    runner: Runner,
) -> None:
    """Persist the full outcome from a background task using a fresh session."""
    with session_factory() as bg_db:
        row = bg_db.get(ReportV3, report_id)
        if row is None:
            log.warning("v3 background outcome for missing report %s", report_id)
            return
        _persist_outcome(db=bg_db, report_row=row, result=result, runner=runner)
        bg_db.commit()


def cancel_run(*, cancel_registry: dict[str, CancelToken], report_id: str) -> bool:
    """Flip the cancel flag for a running v3 run; return True if found."""
    token = cancel_registry.get(report_id)
    if token is None:
        return False
    token.cancel()
    return True


def cleanup_orphaned_running_rows(
    *,
    db: DBSession,
    reason: str = "server restart — run did not complete",
) -> int:
    """Mark every ``status='running'`` row as 'failed' on server boot.

    Background tasks die with the process; rows they left behind
    would otherwise sit in the "running" state forever and confuse
    the list view. Run once during app startup. Returns the count
    of rows updated.
    """
    now = datetime.now(UTC)
    stmt = (
        update(ReportV3)
        .where(ReportV3.status == "running")
        .values(status="failed", error_message=reason, completed_at=now)
    )
    result = db.execute(stmt)
    db.commit()
    return result.rowcount or 0


# ---------------------------------------------------------------------------
# Internals
# ---------------------------------------------------------------------------


def _load_report(*, db: DBSession, user_id: str, report_id: str) -> ReportV3:
    row = db.get(ReportV3, report_id)
    if row is None or row.user_id != user_id:
        raise ReportNotFoundError(f"v3 report {report_id!r} not found")
    return row


def _default_runner(transports: DataTransports | None) -> Runner:
    if transports is None:
        return Runner()
    return Runner(transports_factory=lambda: transports)


def _persist_outcome(
    *,
    db: DBSession,
    report_row: ReportV3,
    result: RunResult,
    runner: Runner,
) -> None:
    """Write sections + charts + citations + audit log + status update.

    Citations get ``display_index`` assigned here in template order:
    every section in ``result.sections`` is scanned for ``[^source_id]``
    markers and the first appearance of each source_id wins index 1, 2,
    3, ... The bibliography view consumes this ordering verbatim.
    """
    del runner  # no per-runner state to persist yet

    for index, section_payload in enumerate(result.sections):
        section_id = section_payload["section_id"]
        title = section_payload["title"]
        markdown = section_payload["markdown"]
        db.add(
            ReportV3Section(
                report_id=report_row.id,
                section_id=section_id,
                section_index=index,
                title=title,
                markdown=markdown,
            )
        )

    for chart in result.charts:
        db.add(
            ReportV3Chart(
                report_id=report_row.id,
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
            ReportV3Citation(
                report_id=report_row.id,
                source_id=entry.source_id,
                tool_name=entry.tool_name,
                display_index=display_index_by_source_id.get(entry.source_id),
                provenance_json=json.dumps(entry.provenance, default=str),
            )
        )
        db.add(
            ReportV3ToolCallLog(
                report_id=report_row.id,
                turn_index=0,  # per-turn attribution lands in Phase 3
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

    report_row.status = result.status
    report_row.error_message = result.message or None
    report_row.completed_at = datetime.now(UTC)
    db.flush()


def _assign_display_indexes(result: RunResult) -> dict[str, int]:
    """Walk body sections in order; first-appearance source_id wins next index."""
    import re

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
