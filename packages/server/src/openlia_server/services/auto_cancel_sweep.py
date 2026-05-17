"""Background asyncio task that cancels in-flight reports for users
who have been disconnected from the notifications SSE for >grace_seconds."""

from __future__ import annotations

import asyncio
import logging
from datetime import UTC, datetime

from openlia_server.services.background_report_registry import BackgroundReportRegistry
from openlia_server.services.user_presence_registry import UserPresenceRegistry

log = logging.getLogger(__name__)


async def auto_cancel_tick(
    *,
    presence: UserPresenceRegistry,
    registry: BackgroundReportRegistry,
    db_session_factory,
    grace_seconds: int = 90,
) -> list[str]:
    """One sweep cycle. Returns list of cancelled report_ids."""
    cancelled_all: list[str] = []
    now = datetime.now(UTC)
    for user_id, last_seen in presence.users_with_no_connections().items():
        if (now - last_seen).total_seconds() >= grace_seconds:
            cancelled = registry.cancel_user(user_id)
            cancelled_all.extend(cancelled)
            if cancelled:
                from openlia_server.db.models.content import Report

                with db_session_factory() as session:
                    for rid in cancelled:
                        row = session.get(Report, rid)
                        if row and row.status == "generating":
                            row.status = "cancelled"
                            row.failure_reason = "session_disconnected"
                    session.commit()
                log.info("auto-cancelled %d reports for user %s", len(cancelled), user_id)
    return cancelled_all


async def auto_cancel_loop(
    *,
    presence: UserPresenceRegistry,
    registry: BackgroundReportRegistry,
    db_session_factory,
    grace_seconds: int = 90,
    poll_seconds: int = 15,
) -> None:
    while True:
        await asyncio.sleep(poll_seconds)
        try:
            await auto_cancel_tick(
                presence=presence,
                registry=registry,
                db_session_factory=db_session_factory,
                grace_seconds=grace_seconds,
            )
        except Exception:
            log.exception("auto_cancel_tick failed")
