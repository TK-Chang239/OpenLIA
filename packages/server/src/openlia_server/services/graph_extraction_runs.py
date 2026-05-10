"""Slice 4 — audit log for nightly graph-extraction runs.

Each invocation of the extraction pipeline (whether scheduled or
admin-forced) writes one row. The high-watermark for "what's new since
last extraction" is the latest ``started_at`` of a *successful* run per
user — failed runs (``error != None``) do not advance it, so an LLM
outage doesn't silently drop yesterday's sessions on the next attempt.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia_server.db.models.graph import GraphExtractionRun


def record_run_start(
    db: Session,
    *,
    user_id: str,
    model_id: str,
) -> GraphExtractionRun:
    row = GraphExtractionRun(
        id=str(uuid.uuid4()),
        user_id=user_id,
        started_at=datetime.now(UTC),
        model_id=model_id,
    )
    db.add(row)
    db.flush()
    return row


def record_run_finish(
    db: Session,
    *,
    run_id: str,
    proposals_inserted: int = 0,
    sessions_processed: int = 0,
    error: str | None = None,
) -> GraphExtractionRun:
    row = db.get(GraphExtractionRun, run_id)
    if row is None:
        raise LookupError(f"run not found: {run_id}")
    row.finished_at = datetime.now(UTC)
    row.proposals_inserted = proposals_inserted
    row.sessions_processed = sessions_processed
    row.error = error
    db.flush()
    return row


def get_run(db: Session, *, run_id: str) -> GraphExtractionRun:
    row = db.get(GraphExtractionRun, run_id)
    if row is None:
        raise LookupError(f"run not found: {run_id}")
    return row


def high_watermark(db: Session, *, user_id: str) -> datetime | None:
    """Latest ``started_at`` of a successful run for the user, or
    ``None`` if no successful run has ever completed."""
    stmt = (
        select(GraphExtractionRun.started_at)
        .where(
            GraphExtractionRun.user_id == user_id,
            GraphExtractionRun.error.is_(None),
            GraphExtractionRun.finished_at.is_not(None),
        )
        .order_by(GraphExtractionRun.started_at.desc())
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none()
