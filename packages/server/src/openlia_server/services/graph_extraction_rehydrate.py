"""Boot-time rehydrate of graph-extraction schedules (slice 6).

Walks every enabled user at lifespan startup and registers their
nightly extraction job. The job derives from ``user_prefs.timezone`` +
``user_prefs.graph_extraction_time``, both of which have non-null
defaults — so any user with a ``user_prefs`` row gets a registration.

Idempotent: ``ensure_schedule_registered`` removes any prior
APScheduler entry under the same id before re-adding, so a server
restart never duplicates jobs.
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia_server.db.models.auth import User
from openlia_server.db.models.config import UserPrefs
from openlia_server.services.graph_extraction_schedules import (
    SchedulerControl,
    ensure_schedule_registered,
)

log = logging.getLogger(__name__)


async def rehydrate_all(
    *,
    session_factory: Callable[[], Session],
    scheduler_control: SchedulerControl,
    callback,
) -> int:
    """Re-register every enabled user's graph-extraction schedule.

    Returns the count of successfully registered jobs. Failures on
    individual users are logged and skipped; one bad user must not
    block startup.
    """
    with session_factory() as s:
        stmt = (
            select(UserPrefs.user_id)
            .join(User, User.id == UserPrefs.user_id)
            .where(User.is_disabled.is_(False))
        )
        user_ids = [uid for (uid,) in s.execute(stmt).all()]

    count = 0
    for uid in user_ids:
        try:
            with session_factory() as s:
                await ensure_schedule_registered(
                    db=s,
                    user_id=uid,
                    scheduler_control=scheduler_control,
                    callback=callback,
                )
            count += 1
        except (ValueError, RuntimeError) as exc:
            log.warning("graph-extraction rehydrate failed for %s: %s", uid, exc)
    return count


__all__ = [
    "rehydrate_all",
]
