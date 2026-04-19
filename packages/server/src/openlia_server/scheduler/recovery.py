"""Startup recovery helpers: mark orphan job_runs rows as cancelled and
determine whether a schedule needs to catch up on a missed run."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from croniter import CroniterBadCronError, croniter
from sqlalchemy import update
from sqlalchemy.orm import Session

from openlia_server.db.models.scheduler import JobRun
from openlia_server.scheduler.registry import JobStatus

ORPHAN_ERROR_MESSAGE = "Server restarted during execution"


def mark_orphans_cancelled(session: Session) -> int:
    """Flip every `status=running` row to `cancelled`. Idempotent: returns
    the number of rows updated (0 if no orphans)."""
    now = datetime.now(UTC)
    stmt = (
        update(JobRun)
        .where(JobRun.status == JobStatus.RUNNING.value)
        .values(
            status=JobStatus.CANCELLED.value,
            completed_at=now,
            error_message=ORPHAN_ERROR_MESSAGE,
        )
        .execution_options(synchronize_session="fetch")
    )
    result = session.execute(stmt)
    return int(result.rowcount or 0)


def should_catch_up(
    *,
    cron_expression: str,
    timezone_name: str,
    last_run_at: datetime | None,
    now: datetime,
    grace_seconds: int,
) -> bool:
    """Return True if the most recent past tick of the cron expression
    (a) is after last_run_at (or last_run_at is None) and
    (b) is within grace_seconds of `now`.
    """
    try:
        tz = ZoneInfo(timezone_name)
    except Exception as exc:
        raise ValueError(f"invalid timezone {timezone_name!r}") from exc

    try:
        local_now = now.astimezone(tz)
        it = croniter(cron_expression, local_now)
        prev_local = it.get_prev(datetime)
    except CroniterBadCronError as exc:
        raise ValueError(f"invalid cron {cron_expression!r}") from exc
    except Exception as exc:
        raise ValueError(f"cron parse failed for {cron_expression!r}") from exc

    prev_utc = prev_local.astimezone(UTC)

    # The previous tick must be within the grace window of `now`.
    if now - prev_utc > timedelta(seconds=grace_seconds):
        return False

    # If we already ran that tick (or later), skip.
    if last_run_at is not None and last_run_at >= prev_utc:
        return False

    return True
