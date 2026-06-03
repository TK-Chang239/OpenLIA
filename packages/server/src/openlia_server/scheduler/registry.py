"""Canonical enums + job-key helpers used throughout the scheduler.

Job keys serve two purposes:
  1. APScheduler schedule id — uniqueness prevents double-registration.
  2. max_instances=1 per key enforces the "no overlap for a given
     user + job type" rule in the spec.
"""

from __future__ import annotations

from enum import StrEnum


class JobType(StrEnum):
    MB_BRIEFING = "mb_briefing"
    EU_SCAN = "eu_scan"
    MR_ASSESSMENT = "mr_assessment"
    MR_DASH = "mr_dash"
    RS_SNAPSHOT = "rs_snapshot"
    GRAPH_EXTRACTION = "graph_extraction"
    SYSTEM_MAINTENANCE = "system_maintenance"
    PORTFOLIO_PRICE_REFRESH = "portfolio_price_refresh"
    EU_V2_SYNC = "eu_v2_sync"
    EU_V2_DISPATCH = "eu_v2_dispatch"


class JobStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NotificationType(StrEnum):
    REPORT_READY = "report_ready"
    ASSESSMENT_READY = "assessment_ready"
    JOB_FAILED = "job_failed"
    PANIC_LEVEL_CHANGE = "panic_level_change"


MAINTENANCE_JOB_KEY = "system_maintenance"
PORTFOLIO_PRICE_REFRESH_KEY = "portfolio_price_refresh"
EU_V2_SYNC_KEY = "eu_v2_sync"
EU_V2_DISPATCH_KEY = "eu_v2_dispatch"


_DEPARTMENT_BY_JOB: dict[JobType, str] = {
    JobType.MB_BRIEFING: "morning_briefing",
    JobType.EU_SCAN: "earnings_update",
    JobType.MR_ASSESSMENT: "macro_research",
    JobType.MR_DASH: "macro_research",
    JobType.RS_SNAPSHOT: "retail_sentiment",
    JobType.GRAPH_EXTRACTION: "secretary",
    JobType.PORTFOLIO_PRICE_REFRESH: "portfolio",
    JobType.EU_V2_SYNC: "earnings_update_v2",
    JobType.EU_V2_DISPATCH: "earnings_update_v2",
}


def department_for_job_type(job_type: JobType) -> str:
    try:
        return _DEPARTMENT_BY_JOB[job_type]
    except KeyError as exc:
        raise ValueError(f"no department mapping for {job_type!r}") from exc


def job_key(
    job_type: JobType,
    user_id: str | None = None,
    schedule_id: str | None = None,
) -> str:
    if job_type is JobType.SYSTEM_MAINTENANCE:
        return MAINTENANCE_JOB_KEY
    if job_type is JobType.PORTFOLIO_PRICE_REFRESH:
        # Global job — no per-user keying.
        return PORTFOLIO_PRICE_REFRESH_KEY
    if job_type is JobType.EU_V2_SYNC:
        return EU_V2_SYNC_KEY
    if job_type is JobType.EU_V2_DISPATCH:
        return EU_V2_DISPATCH_KEY
    if not user_id:
        raise ValueError(f"user_id required for job_type={job_type.value}")
    base = f"{job_type.value}:{user_id}"
    if schedule_id:
        return f"{base}:sched:{schedule_id}"
    return base


def parse_job_key(key: str) -> tuple[JobType, str | None]:
    """Return (job_type, user_id). The optional `:sched:<id>` suffix is
    stripped — callers that need the schedule_id should keep it themselves."""
    if key == MAINTENANCE_JOB_KEY:
        return (JobType.SYSTEM_MAINTENANCE, None)
    if key == PORTFOLIO_PRICE_REFRESH_KEY:
        return (JobType.PORTFOLIO_PRICE_REFRESH, None)
    if key == EU_V2_SYNC_KEY:
        return (JobType.EU_V2_SYNC, None)
    if key == EU_V2_DISPATCH_KEY:
        return (JobType.EU_V2_DISPATCH, None)
    prefix, _, rest = key.partition(":")
    try:
        job_type = JobType(prefix)
    except ValueError as exc:
        raise ValueError(f"unknown job type in key {key!r}") from exc
    user_id, _sep, _suffix = rest.partition(":")
    if not user_id:
        raise ValueError(f"missing user_id in key {key!r}")
    return (job_type, user_id)
