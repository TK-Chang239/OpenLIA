"""Persistent cache for computed Panic Thermometer dashboards.

One row per user in ``pt_dashboard_cache``. The route serves a fresh row
instantly instead of paying the ~12-upstream-call compute on every GET,
and the scheduled ``pt_dash`` job keeps rows warm so even the first load
after a restart is instant. Config mutations invalidate the row so the
next GET recomputes against the new ruleset.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from openlia_server.db.models.dashboard import PtDashboardCache
from openlia_server.services.pt_runner import DashboardPayload

# Slightly under the UI's 5-minute auto-refresh: every poll past the TTL
# recomputes (keeping data current), while loads inside the window are
# served straight from the row.
FRESH_TTL_SECONDS = 240.0


def payload_to_dict(payload: DashboardPayload) -> dict[str, Any]:
    """The wire/cache shape — identical to what the route always returned."""
    return {
        "panels": payload.panels,
        "composite": payload.composite,
        "generated_at": payload.generated_at,
        "warnings": payload.warnings,
    }


def read_cache(session: Session, user_id: str) -> tuple[dict[str, Any] | None, datetime | None]:
    import json

    row = session.query(PtDashboardCache).filter_by(user_id=user_id).one_or_none()
    if row is None:
        return None, None
    generated_at = row.generated_at
    if generated_at is not None and generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=UTC)
    return json.loads(row.payload_json), generated_at


def is_fresh(generated_at: datetime | None, *, ttl_seconds: float = FRESH_TTL_SECONDS) -> bool:
    if generated_at is None:
        return False
    return (datetime.now(UTC) - generated_at).total_seconds() < ttl_seconds


def upsert_cache(session: Session, user_id: str, payload: dict[str, Any]) -> None:
    import json

    row = session.query(PtDashboardCache).filter_by(user_id=user_id).one_or_none()
    now = datetime.now(UTC)
    if row is None:
        session.add(
            PtDashboardCache(
                user_id=user_id,
                payload_json=json.dumps(payload, default=str),
                generated_at=now,
            )
        )
    else:
        row.payload_json = json.dumps(payload, default=str)
        row.generated_at = now
    session.flush()


def invalidate(session: Session, user_id: str) -> None:
    session.query(PtDashboardCache).filter_by(user_id=user_id).delete(synchronize_session=False)
    session.flush()
