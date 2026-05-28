"""v3 revision service — start, persist, list, cancel revisions.

A revision is one "the user asked for a change" round on a completed
v3 report. Mirrors the v3_run_service shape: a sync ``start_revision_async``
that schedules a background ``_run_in_background``, plus listing /
cancel helpers. The engine path is shared — ``Runner.run`` accepts
a ``ReviseContext`` that flips the workspace into revision mode and
threads the prior report into the model's context.

Concurrency: only one revision (status not in {completed, failed,
cancelled}) may be active per report at a time. The route enforces
this via ``has_active_revision`` and returns 409.

Persistence diff (what makes a revision different from a fresh run):
  - Only sections whose ``markdown`` differs from their prior version
    are persisted as a new ``ReportV3Section`` row at the next version
    number. Untouched sections stay at their prior version.
  - Same diff rule for charts (compare ``ChartSpec.model_dump_json``).
  - Citations: new entries (source_ids absent from the prior set)
    persist as new ``ReportV3Citation`` rows. Display indices for the
    whole report are recomputed from scratch over the LATEST section
    versions so the bibliography reflects the current state.
  - The parent ``ReportV3.status`` flips to ``revising`` for the
    in-flight window and back to ``completed`` on success
    (``failed`` / ``cancelled`` on the unhappy paths).
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from openlia.llm.runtime.report_v3 import (
    BrokerEmitter,
    CancelToken,
    CapabilityError,
    EventBroker,
    LLMSession,
    PriorCitation,
    PriorSection,
    ReviseContext,
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
    ReportV3Revision,
    ReportV3Section,
    ReportV3ToolCallLog,
)
from openlia_server.services.v3_run_service import (
    ReportNotFoundError,
    _default_runner,
)

log = logging.getLogger(__name__)

# Module-level strong refs so asyncio doesn't garbage-collect the
# background revision tasks. Mirrors the v3_run_service pattern.
_BACKGROUND_TASKS: set[asyncio.Task[Any]] = set()


class RevisionInFlightError(RuntimeError):
    """Another revision on this report is already running."""


class RevisionNotFoundError(LookupError):
    """No revision with the given id (or owned by this user)."""


# Statuses that mean "still in flight" — used by the concurrency gate.
_NON_TERMINAL_REVISION_STATUSES: frozenset[str] = frozenset({"running"})


@dataclass(frozen=True)
class StartRevisionHandle:
    revision_id: str


def has_active_revision(*, db: DBSession, report_id: str) -> bool:
    """True if any non-terminal revision exists for this report."""
    stmt = (
        select(ReportV3Revision.id)
        .where(ReportV3Revision.report_id == report_id)
        .where(ReportV3Revision.status.in_(_NON_TERMINAL_REVISION_STATUSES))
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none() is not None


def list_revisions(
    *, db: DBSession, user_id: str, report_id: str
) -> list[ReportV3Revision]:
    """All revisions for this report, oldest first. Owner-scoped."""
    parent = db.get(ReportV3, report_id)
    if parent is None or parent.user_id != user_id:
        raise ReportNotFoundError(f"v3 report {report_id!r} not found")
    stmt = (
        select(ReportV3Revision)
        .where(ReportV3Revision.report_id == report_id)
        .order_by(ReportV3Revision.revision_index.asc())
    )
    return list(db.execute(stmt).scalars().all())


def get_revision(
    *, db: DBSession, user_id: str, revision_id: str
) -> ReportV3Revision:
    row = db.get(ReportV3Revision, revision_id)
    if row is None or row.user_id != user_id:
        raise RevisionNotFoundError(f"v3 revision {revision_id!r} not found")
    return row


def cancel_revision(
    *, cancel_registry: dict[str, CancelToken], revision_id: str
) -> bool:
    """Flip the cancel flag for an in-flight revision. Returns True
    if a token was found (cancellation is cooperative — the runner
    exits at the next safe point)."""
    token = cancel_registry.get(_cancel_key(revision_id))
    if token is None:
        return False
    token.cancel()
    return True


def start_revision_async(
    *,
    db: DBSession,
    user_id: str,
    report_id: str,
    revision_request: str,
    request: RunRequest,
    revise: ReviseContext,
    session_factory: Callable[[], DBSession],
    broker: EventBroker,
    cancel_registry: dict[str, CancelToken],
    runner: Runner | None = None,
    llm_session: LLMSession | None = None,
) -> StartRevisionHandle:
    """Create the revision row, schedule the background runner."""
    if has_active_revision(db=db, report_id=report_id):
        raise RevisionInFlightError(
            f"Another revision is already in flight for report {report_id!r}. "
            f"Wait for it to finish or cancel it first."
        )

    # Monotonic per-report index. Counts ALL prior revisions (including
    # failed/cancelled) so the chronological story stays consistent.
    revision_index = (
        db.query(ReportV3Revision)
        .filter(ReportV3Revision.report_id == report_id)
        .count()
        + 1
    )
    revision_id = str(uuid.uuid4())
    now = datetime.now(UTC)

    revision_row = ReportV3Revision(
        id=revision_id,
        report_id=report_id,
        user_id=user_id,
        revision_index=revision_index,
        request=revision_request,
        status="running",
        error_message=None,
        created_at=now,
        completed_at=None,
    )
    db.add(revision_row)

    # Flip parent run into the explicit revising state so the list
    # view can show a badge without joining ``report_v3_revisions``.
    parent = db.get(ReportV3, report_id)
    if parent is not None:
        parent.status = "revising"

    db.flush()

    cancel_token = CancelToken()
    cancel_registry[_cancel_key(revision_id)] = cancel_token
    bg_runner = runner or _default_runner(transports=None)
    emitter = BrokerEmitter(broker=broker, report_id=revision_id)

    task = asyncio.create_task(
        _run_revision_in_background(
            revision_id=revision_id,
            report_id=report_id,
            request=request,
            revise=revise,
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
    return StartRevisionHandle(revision_id=revision_id)


async def _run_revision_in_background(
    *,
    revision_id: str,
    report_id: str,
    request: RunRequest,
    revise: ReviseContext,
    runner: Runner,
    session: LLMSession | None,
    emitter: BrokerEmitter,
    cancel_token: CancelToken,
    session_factory: Callable[[], DBSession],
    broker: EventBroker,
    cancel_registry: dict[str, CancelToken],
) -> None:
    try:
        try:
            result = await runner.run(
                request,
                session=session,
                emitter=emitter,
                cancel_token=cancel_token,
                revise=revise,
            )
        except CapabilityError as exc:
            _mark_revision_failed(session_factory, revision_id, report_id, str(exc))
            return
        except Exception as exc:
            log.exception("v3 revision %s crashed unexpectedly", revision_id)
            _mark_revision_failed(
                session_factory, revision_id, report_id, f"unexpected: {exc}"
            )
            return

        _persist_revision_outcome(
            session_factory=session_factory,
            revision_id=revision_id,
            report_id=report_id,
            result=result,
            revise=revise,
        )
    finally:
        cancel_registry.pop(_cancel_key(revision_id), None)
        broker.finish(revision_id)


def _persist_revision_outcome(
    *,
    session_factory: Callable[[], DBSession],
    revision_id: str,
    report_id: str,
    result: RunResult,
    revise: ReviseContext,
) -> None:
    """Diff result vs. prior; persist only the new versions + new
    citations; recompute display_index over the latest sections;
    flip statuses to ``completed``."""
    prior_section_by_id = {p.section_id: p for p in revise.prior_sections}
    prior_chart_by_id = {c.chart_id: c for c in revise.prior_charts}
    prior_citation_ids = {c.source_id for c in revise.prior_citations}

    with session_factory() as bg_db:
        revision_row = bg_db.get(ReportV3Revision, revision_id)
        parent_row = bg_db.get(ReportV3, report_id)
        if revision_row is None or parent_row is None:
            log.warning(
                "v3 revision outcome for missing revision/report %s/%s",
                revision_id,
                report_id,
            )
            return

        # ----- Sections: persist a new version per touched id ------
        for section_index, payload in enumerate(result.sections):
            section_id = payload["section_id"]
            markdown = payload["markdown"]
            title = payload["title"]
            prior = prior_section_by_id.get(section_id)
            if prior is not None and prior.markdown == markdown:
                # Untouched — prior version still represents the
                # current state; skip persisting a duplicate row.
                continue
            next_version = _next_version_for(bg_db, report_id, section_id, "section")
            bg_db.add(
                ReportV3Section(
                    report_id=report_id,
                    section_id=section_id,
                    section_index=section_index,
                    title=title,
                    markdown=markdown,
                    revision_id=revision_id,
                    version=next_version,
                )
            )

        # ----- Charts: persist a new version per touched id --------
        for chart in result.charts:
            spec_json = chart.model_dump_json()
            prior = prior_chart_by_id.get(chart.chart_id)
            if prior is not None and prior.model_dump_json() == spec_json:
                continue
            next_version = _next_version_for(
                bg_db, report_id, chart.chart_id, "chart"
            )
            bg_db.add(
                ReportV3Chart(
                    report_id=report_id,
                    chart_id=chart.chart_id,
                    chart_type=chart.chart_type,
                    title=chart.title,
                    spec_json=spec_json,
                    rendered_url=None,
                    revision_id=revision_id,
                    version=next_version,
                )
            )

        # ----- Citations: insert new entries; recompute indices -----
        for entry in result.citations:
            if entry.source_id in prior_citation_ids:
                continue
            bg_db.add(
                ReportV3Citation(
                    report_id=report_id,
                    source_id=entry.source_id,
                    tool_name=entry.tool_name,
                    display_index=None,  # recomputed below
                    provenance_json=json.dumps(entry.provenance, default=str),
                )
            )
            bg_db.add(
                ReportV3ToolCallLog(
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
                    timestamp=datetime.now(UTC),
                )
            )

        bg_db.flush()
        _recompute_display_indices(bg_db, report_id)

        # ----- Terminal status updates ----------------------------
        now = datetime.now(UTC)
        revision_row.status = "completed"
        revision_row.completed_at = now
        parent_row.status = "completed"
        parent_row.completed_at = now
        bg_db.commit()


def _next_version_for(
    db: DBSession, report_id: str, item_id: str, kind: str
) -> int:
    """Return the next version number for a (report_id, section_id)
    or (report_id, chart_id). Falls back to 1 when no prior rows."""
    if kind == "section":
        stmt = (
            select(ReportV3Section.version)
            .where(ReportV3Section.report_id == report_id)
            .where(ReportV3Section.section_id == item_id)
            .order_by(ReportV3Section.version.desc())
            .limit(1)
        )
    else:
        stmt = (
            select(ReportV3Chart.version)
            .where(ReportV3Chart.report_id == report_id)
            .where(ReportV3Chart.chart_id == item_id)
            .order_by(ReportV3Chart.version.desc())
            .limit(1)
        )
    current = db.execute(stmt).scalar_one_or_none()
    return (current or 0) + 1


def _recompute_display_indices(db: DBSession, report_id: str) -> None:
    """Walk the LATEST section versions in section_index order;
    assign citation display_index by first-appearance.

    Run after every revision so the bibliography reflects the current
    rendered state — a source that only appeared in a since-revised
    section drops out of the live numbering."""
    latest_sections = _latest_section_rows(db, report_id)
    citations = (
        db.query(ReportV3Citation)
        .filter(ReportV3Citation.report_id == report_id)
        .all()
    )
    citation_by_source = {c.source_id: c for c in citations}

    import re

    marker_re = re.compile(r"\[\^([a-z0-9_]+)\]")
    seen: dict[str, int] = {}
    next_index = 1
    for section in latest_sections:
        for sid in marker_re.findall(section.markdown):
            if sid in seen:
                continue
            if sid not in citation_by_source:
                continue
            seen[sid] = next_index
            next_index += 1

    for citation in citations:
        citation.display_index = seen.get(citation.source_id)


def _latest_section_rows(
    db: DBSession, report_id: str
) -> list[ReportV3Section]:
    """One row per section_id at its highest version, ordered by
    the latest version's section_index."""
    rows = (
        db.query(ReportV3Section)
        .filter(ReportV3Section.report_id == report_id)
        .all()
    )
    latest_by_section_id: dict[str, ReportV3Section] = {}
    for row in rows:
        current = latest_by_section_id.get(row.section_id)
        if current is None or row.version > current.version:
            latest_by_section_id[row.section_id] = row
    return sorted(latest_by_section_id.values(), key=lambda r: r.section_index)


def _mark_revision_failed(
    session_factory: Callable[[], DBSession],
    revision_id: str,
    report_id: str,
    error_message: str,
) -> None:
    with session_factory() as bg_db:
        revision_row = bg_db.get(ReportV3Revision, revision_id)
        parent_row = bg_db.get(ReportV3, report_id)
        now = datetime.now(UTC)
        if revision_row is not None:
            revision_row.status = "failed"
            revision_row.error_message = error_message
            revision_row.completed_at = now
        if parent_row is not None:
            # Failed revision: restore parent to ``completed`` so the
            # report is still usable. The error lives on the revision
            # row for chat-history rendering.
            parent_row.status = "completed"
            parent_row.completed_at = now
        bg_db.commit()


def build_revise_context_from_db(
    *, db: DBSession, report_id: str, revision_request: str
) -> ReviseContext:
    """Read the latest persisted state of a report and assemble a
    ``ReviseContext`` for the engine. Used by the route + tests."""
    latest_sections = _latest_section_rows(db, report_id)
    prior_sections = [
        PriorSection(
            section_id=row.section_id,
            title=row.title,
            markdown=row.markdown,
        )
        for row in latest_sections
    ]

    latest_charts = _latest_chart_rows(db, report_id)
    from openlia.llm.runtime.report_v3 import ChartSpec

    prior_charts = [
        ChartSpec.model_validate_json(row.spec_json) for row in latest_charts
    ]

    citation_rows = (
        db.query(ReportV3Citation)
        .filter(ReportV3Citation.report_id == report_id)
        .all()
    )
    prior_citations = [
        PriorCitation(
            source_id=row.source_id,
            tool_name=row.tool_name,
            provenance=json.loads(row.provenance_json),
        )
        for row in citation_rows
    ]

    return ReviseContext(
        revision_request=revision_request,
        prior_sections=prior_sections,
        prior_charts=prior_charts,
        prior_citations=prior_citations,
    )


def _latest_chart_rows(
    db: DBSession, report_id: str
) -> list[ReportV3Chart]:
    rows = (
        db.query(ReportV3Chart)
        .filter(ReportV3Chart.report_id == report_id)
        .all()
    )
    latest_by_chart_id: dict[str, ReportV3Chart] = {}
    for row in rows:
        current = latest_by_chart_id.get(row.chart_id)
        if current is None or row.version > current.version:
            latest_by_chart_id[row.chart_id] = row
    return list(latest_by_chart_id.values())


def _cancel_key(revision_id: str) -> str:
    """Namespace revision cancel tokens so they don't collide with
    run cancel tokens in the shared registry."""
    return f"revision:{revision_id}"
