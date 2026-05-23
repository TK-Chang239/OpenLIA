"""Service layer for the ``pipeline_runs`` table (Step 2).

Thin CRUD operations against :class:`PipelineRun`. The SSE endpoint
calls these helpers when a run starts, when the Clarifier pauses it,
when the user submits answers via the resume endpoint, and on
completion/failure.

The service stays narrow on purpose: it does not own the orchestrator
or know anything about :class:`RunnerV2` events. The route layer
mediates between the two.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from openlia_server.db.models.pipeline_runs import PipelineRun


def _now() -> datetime:
    return datetime.now(UTC)


def create_run(
    session: Session,
    *,
    user_id: str,
    session_id: str | None,
    department: str,
    template_id: str,
    template_raw: str,
    template_format: str,
    composer_inputs: dict[str, Any],
) -> PipelineRun:
    """Create a STARTED run row before kicking off the orchestrator."""
    now = _now()
    row = PipelineRun(
        id=str(uuid.uuid4()),
        user_id=user_id,
        session_id=session_id,
        department=department,
        template_id=template_id,
        template_raw=template_raw,
        template_format=template_format,
        composer_inputs=dict(composer_inputs),
        state="STARTED",
        clarification_history=[],
        created_at=now,
        updated_at=now,
    )
    session.add(row)
    session.flush()
    return row


def mark_paused(
    session: Session,
    run_id: str,
    *,
    stage: str,
    clarifier_output: dict[str, Any],
    clarifier_round: int,
    clarification_history: list[dict[str, Any]],
) -> PipelineRun:
    """Move a run into CLARIFY_AWAITING_USER and snapshot the clarifier output."""
    row = _require(session, run_id)
    now = _now()
    row.state = "CLARIFY_AWAITING_USER"
    row.paused_at_stage = stage
    row.last_clarifier_output = clarifier_output
    row.last_clarifier_round = clarifier_round
    row.clarification_history = list(clarification_history)
    row.paused_at = now
    row.updated_at = now
    session.flush()
    return row


def mark_running(session: Session, run_id: str) -> PipelineRun:
    """Move a paused run back into RUNNING when a resume starts."""
    row = _require(session, run_id)
    now = _now()
    row.state = "RUNNING"
    row.paused_at_stage = None
    row.updated_at = now
    session.flush()
    return row


def mark_completed(
    session: Session,
    run_id: str,
    *,
    degraded: bool = False,
    final_report: dict[str, Any] | None = None,
) -> PipelineRun:
    """Mark a run COMPLETED (or DEGRADED) and persist its ReportV2 JSON.

    `final_report` is the ReportV2.model_dump() payload — typed cover,
    sections (with typed-block dicts), citations, run_summary,
    verification_history.
    """
    row = _require(session, run_id)
    now = _now()
    row.state = "DEGRADED" if degraded else "COMPLETED"
    row.completed_at = now
    row.updated_at = now
    if final_report is not None:
        row.final_report_json = final_report
        row.final_report_at = now
    session.flush()
    return row


def mark_failed(session: Session, run_id: str, *, reason: str) -> PipelineRun:
    row = _require(session, run_id)
    now = _now()
    row.state = "FAILED"
    row.failure_reason = reason
    row.completed_at = now
    row.updated_at = now
    session.flush()
    return row


def get_run(session: Session, run_id: str) -> PipelineRun | None:
    return session.get(PipelineRun, run_id)


def soft_delete_run(session: Session, run_id: str) -> PipelineRun:
    """Tombstone a run (sets deleted_at). The row stays for audit/retention;
    GET endpoints filter it out, and repo_items pointing at it cascade away
    naturally via the FK.
    """
    row = _require(session, run_id)
    if row.deleted_at is None:
        row.deleted_at = _now()
        row.updated_at = row.deleted_at
        session.flush()
    return row


def _require(session: Session, run_id: str) -> PipelineRun:
    row = session.get(PipelineRun, run_id)
    if row is None:
        raise KeyError(f"pipeline_run {run_id!r} not found")
    return row
