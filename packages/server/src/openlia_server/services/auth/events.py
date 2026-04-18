"""Append-only audit log writes."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session as DBSession

from openlia_server.db.models.auth import AuthEvent


def log_auth_event(
    db: DBSession,
    *,
    event_type: str,
    user_id: str | None = None,
    actor_user_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    row = AuthEvent(
        id=str(uuid.uuid4()),
        event_type=event_type,
        user_id=user_id,
        actor_user_id=actor_user_id,
        ip_address=ip_address,
        user_agent=(user_agent or "")[:512] or None,
        event_metadata=metadata,
        created_at=datetime.now(UTC),
    )
    db.add(row)
    db.commit()
