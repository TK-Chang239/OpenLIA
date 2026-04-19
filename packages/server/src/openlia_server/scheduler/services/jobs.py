"""CRUD helpers for the `job_runs` table.

All functions take an active SQLAlchemy Session; none commit. Callers
own transaction boundaries so a single executor run can insert a
job_runs row + a user_notifications row in one commit."""

from __future__ import annotations

import uuid
from collections.abc import Sequence
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia_server.db.models.scheduler import JobRun
from openlia_server.scheduler.registry import JobStatus, JobType


def _now() -> datetime:
    return datetime.now(UTC)


def start_run(
    session: Session,
    *,
    user_id: str | None,
    job_type: JobType,
    schedule_id: str | None,
    retry_of: str | None = None,
) -> str:
    run_id = uuid.uuid4().hex
    run = JobRun(
        id=run_id,
        user_id=user_id,
        job_type=job_type.value,
        schedule_id=schedule_id,
        status=JobStatus.RUNNING.value,
        started_at=_now(),
        completed_at=None,
        error_message=None,
        result_summary=None,
        retry_of=retry_of,
        attempt=1,
    )
    session.add(run)
    return run_id


def mark_completed(session: Session, run_id: str, *, result_summary: str | None = None) -> None:
    row = _require(session, run_id)
    row.status = JobStatus.COMPLETED.value
    row.completed_at = _now()
    row.result_summary = result_summary


def mark_failed(session: Session, run_id: str, *, error_message: str) -> None:
    row = _require(session, run_id)
    row.status = JobStatus.FAILED.value
    row.completed_at = _now()
    row.error_message = error_message


def mark_cancelled(session: Session, run_id: str, *, error_message: str | None = None) -> None:
    row = _require(session, run_id)
    row.status = JobStatus.CANCELLED.value
    row.completed_at = _now()
    if error_message is not None:
        row.error_message = error_message


def bump_attempt(session: Session, run_id: str, *, error_message: str) -> None:
    """Increment attempt counter after a transient failure; stays RUNNING."""
    row = _require(session, run_id)
    row.attempt += 1
    row.error_message = error_message


def list_orphans(session: Session) -> list[str]:
    stmt = select(JobRun.id).where(JobRun.status == JobStatus.RUNNING.value)
    return [row[0] for row in session.execute(stmt)]


def most_recent_for_schedule(session: Session, schedule_id: str) -> JobRun | None:
    stmt = (
        select(JobRun)
        .where(JobRun.schedule_id == schedule_id)
        .order_by(JobRun.started_at.desc())
        .limit(1)
    )
    return session.execute(stmt).scalar_one_or_none()


def list_for_user(
    session: Session,
    *,
    user_id: str,
    job_type: JobType | None = None,
    status: JobStatus | None = None,
    since: datetime | None = None,
    limit: int = 50,
    offset: int = 0,
) -> Sequence[JobRun]:
    stmt = select(JobRun).where(JobRun.user_id == user_id)
    if job_type is not None:
        stmt = stmt.where(JobRun.job_type == job_type.value)
    if status is not None:
        stmt = stmt.where(JobRun.status == status.value)
    if since is not None:
        stmt = stmt.where(JobRun.started_at >= since)
    stmt = stmt.order_by(JobRun.started_at.desc()).offset(offset).limit(limit)
    return list(session.execute(stmt).scalars())


def _require(session: Session, run_id: str) -> JobRun:
    row = session.get(JobRun, run_id)
    if row is None:
        raise LookupError(f"job_run {run_id!r} not found")
    return row
