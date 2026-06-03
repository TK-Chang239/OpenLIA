"""Snapshot reader backing MacroResearchDepartment.get_current_snapshot from
the MrDashboardCache table. Thin storage adapter: loads the latest cached
payload for a (user, dashboard) and derives its snapshot value via the core
snapshot helpers."""

from __future__ import annotations

import json
from collections.abc import Callable
from datetime import UTC
from typing import Any

from openlia.macro_research.schemas import SnapshotEntry
from openlia.macro_research.snapshot import snapshot_value_for

from openlia_server.db.models.dashboard import MrDashboardCache


class MrDashboardSnapshotReader:
    def __init__(self, session_factory: Callable[[], Any]) -> None:
        self._session_factory = session_factory

    def latest_snapshot(self, *, user_id: str, dashboard: str) -> SnapshotEntry | None:
        with self._session_factory() as session:
            row = (
                session.query(MrDashboardCache)
                .filter_by(user_id=user_id, dashboard=dashboard)
                .one_or_none()
            )
            if row is None:
                return None
            value = snapshot_value_for(dashboard, json.loads(row.payload_json))
            if value is None:
                return None
            generated_at = row.generated_at
            if generated_at.tzinfo is None:
                generated_at = generated_at.replace(tzinfo=UTC)
            return SnapshotEntry(value=value, generated_at=generated_at)
