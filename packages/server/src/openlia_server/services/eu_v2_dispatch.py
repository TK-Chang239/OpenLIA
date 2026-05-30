"""Dispatch helpers for the EU v2 scheduled-run pipeline.

Pure DB helpers over ``eu_v2_earnings_schedule``: select the rows whose
``scheduled_run_at`` has arrived and that are still ``pending``, then mark
each row ``reported`` (run fired) or, after exhausting retries,
``skipped``.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from openlia_server.db.models.report_eu import EuV2EarningsSchedule


def select_due_rows(db: Session, *, now: datetime) -> list[EuV2EarningsSchedule]:
    """Return pending rows whose scheduled_run_at has passed, oldest first."""
    return (
        db.query(EuV2EarningsSchedule)
        .filter(
            EuV2EarningsSchedule.status == "pending",
            EuV2EarningsSchedule.scheduled_run_at <= now,
        )
        .order_by(EuV2EarningsSchedule.scheduled_run_at)
        .all()
    )


def mark_reported(db: Session, *, row_id: str, report_id: str) -> None:
    """Flip a schedule row to ``reported`` and anchor its report_id."""
    row = db.get(EuV2EarningsSchedule, row_id)
    if row is None:
        raise LookupError(f"eu_v2_earnings_schedule row {row_id!r} not found")
    row.status = "reported"
    row.report_id = report_id
    db.commit()


def mark_failed(db: Session, *, row_id: str, max_attempts: int) -> None:
    """Record a failed dispatch attempt.

    Increments ``attempts``; once it reaches ``max_attempts`` the row is
    ``skipped`` (gave up), otherwise it stays ``pending`` for a later retry.
    """
    row = db.get(EuV2EarningsSchedule, row_id)
    if row is None:
        raise LookupError(f"eu_v2_earnings_schedule row {row_id!r} not found")
    row.attempts += 1
    if row.attempts >= max_attempts:
        row.status = "skipped"
    db.commit()
