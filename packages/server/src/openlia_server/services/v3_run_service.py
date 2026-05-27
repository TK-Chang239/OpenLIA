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

import json
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from openlia.llm.runtime.report_v3 import (
    CapabilityError,
    DataTransports,
    LLMSession,
    Runner,
    RunRequest,
    RunResult,
)
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.models.report_v3 import (
    ReportV3,
    ReportV3Chart,
    ReportV3Citation,
    ReportV3Section,
    ReportV3ToolCallLog,
)


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
