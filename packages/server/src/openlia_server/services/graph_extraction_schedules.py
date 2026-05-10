"""Per-user graph-extraction schedule registration (slice 6 of runtime spec).

There is no ``GraphExtractionSchedule`` table — the schedule is derived
from ``user_prefs.timezone`` + ``user_prefs.graph_extraction_time``.
This module is the surface other code calls when those preferences
change (or on boot, via the rehydrate service).

The APScheduler-level identity for the job is
``job_key(JobType.GRAPH_EXTRACTION, user_id)``. Idempotent: if a job
with that id is already registered, ``ensure_schedule_registered``
re-registers it (remove then add) so a TZ/time change takes effect
without a server restart.
"""

from __future__ import annotations

import re
import zoneinfo
from typing import Protocol

from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from openlia_server.db.models.config import UserPrefs
from openlia_server.scheduler.registry import JobType, job_key

_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class SchedulerControl(Protocol):
    """Subset of APScheduler-shape calls this service needs.

    Production passes the live ``scheduler.scheduler`` (the APScheduler
    AsyncScheduler). Tests pass a recording fake.
    """

    async def add_schedule(self, func, trigger, *, id: str, args: tuple, **kwargs) -> str: ...

    async def remove_schedule(self, id: str) -> None: ...


def _validate(time: str, timezone: str) -> None:
    if not _TIME_RE.match(time):
        raise ValueError(f"invalid HH:MM time: {time!r}")
    try:
        zoneinfo.ZoneInfo(timezone)
    except Exception as exc:
        raise ValueError(f"invalid timezone: {timezone!r}") from exc


def _trigger_from_prefs(prefs: UserPrefs) -> CronTrigger:
    _validate(prefs.graph_extraction_time, prefs.timezone)
    hour, minute = (int(p) for p in prefs.graph_extraction_time.split(":"))
    return CronTrigger(
        hour=hour,
        minute=minute,
        timezone=prefs.timezone,
    )


async def ensure_schedule_registered(
    *,
    db: Session,
    user_id: str,
    scheduler_control: SchedulerControl,
    callback,
    misfire_grace_time: int = 600,
) -> str:
    """Register (or re-register) the nightly extraction job for ``user_id``.

    Reads the user's ``UserPrefs`` for the trigger time + tz. Returns
    the APScheduler job id. Idempotent — safe to call from a route
    handler on every PUT of timezone / graph_extraction_time.

    Raises ``ValueError`` if the user has no UserPrefs row or the
    persisted values are invalid (the latter would indicate corrupt
    data; the route validators block invalid writes).
    """
    prefs = db.query(UserPrefs).filter_by(user_id=user_id).one_or_none()
    if prefs is None:
        raise ValueError(f"no user_prefs for user_id={user_id!r}")

    trigger = _trigger_from_prefs(prefs)
    jid = job_key(JobType.GRAPH_EXTRACTION, user_id)

    # Remove-then-add — APScheduler add raises on duplicate id, so we
    # can't blindly call add on every boot.
    try:
        await scheduler_control.remove_schedule(jid)
    except Exception:
        # Not previously registered or backend doesn't track absence —
        # both are fine; we're about to add.
        pass

    await scheduler_control.add_schedule(
        callback,
        trigger,
        id=jid,
        args=(JobType.GRAPH_EXTRACTION, user_id, None),
        misfire_grace_time=misfire_grace_time,
        max_instances=1,
        coalesce=True,
    )
    return jid


async def remove_schedule(
    *,
    user_id: str,
    scheduler_control: SchedulerControl,
) -> None:
    """Tear down the graph-extraction job for ``user_id``.

    Used on user deletion / disable. No-op if the job wasn't registered.
    """
    jid = job_key(JobType.GRAPH_EXTRACTION, user_id)
    try:
        await scheduler_control.remove_schedule(jid)
    except Exception:
        pass


__all__ = [
    "SchedulerControl",
    "ensure_schedule_registered",
    "remove_schedule",
]
