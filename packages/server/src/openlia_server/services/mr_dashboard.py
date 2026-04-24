"""Per-user MR dashboard state CRUD."""

from __future__ import annotations

import uuid
from typing import Any, Callable

from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia_server.db.models.dashboard import MrDashboardState


class MRDashboardService:
    def __init__(self, *, session_factory: Callable[[], Session]) -> None:
        self._factory = session_factory

    def get_or_create(self, *, user_id: str, dashboard: str) -> MrDashboardState:
        with self._factory() as s:
            stmt = select(MrDashboardState).where(
                MrDashboardState.user_id == user_id,
                MrDashboardState.dashboard == dashboard,
            )
            row = s.scalars(stmt).first()
            if row is None:
                row = MrDashboardState(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    dashboard=dashboard,
                    view_config={},
                    threshold_overrides={},
                )
                s.add(row)
                s.commit()
                s.refresh(row)
            s.expunge(row)
            return row

    def update_config(
        self,
        *,
        user_id: str,
        dashboard: str,
        view_config: dict[str, Any] | None = None,
        threshold_overrides: dict[str, Any] | None = None,
    ) -> MrDashboardState:
        with self._factory() as s:
            stmt = select(MrDashboardState).where(
                MrDashboardState.user_id == user_id,
                MrDashboardState.dashboard == dashboard,
            )
            row = s.scalars(stmt).first()
            if row is None:
                row = MrDashboardState(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    dashboard=dashboard,
                    view_config={},
                    threshold_overrides={},
                )
                s.add(row)
            if view_config is not None:
                row.view_config = view_config
            if threshold_overrides is not None:
                row.threshold_overrides = threshold_overrides
            s.commit()
            s.refresh(row)
            s.expunge(row)
            return row

    def list_for_user(self, *, user_id: str) -> list[MrDashboardState]:
        with self._factory() as s:
            stmt = select(MrDashboardState).where(MrDashboardState.user_id == user_id)
            rows = list(s.scalars(stmt).all())
            for r in rows:
                s.expunge(r)
            return rows
