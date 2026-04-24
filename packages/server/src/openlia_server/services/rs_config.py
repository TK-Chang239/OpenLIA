"""Retail Sentiment per-user configuration CRUD."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia_server.db.models.dashboard import RsUserConfig


class RsConfigService:
    def __init__(self, *, session_factory: Callable[[], Session]) -> None:
        self._factory = session_factory

    def get_or_create(self, user_id: str) -> RsUserConfig:
        with self._factory() as s:
            row = s.scalars(select(RsUserConfig).where(RsUserConfig.user_id == user_id)).first()
            if row is None:
                row = RsUserConfig(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    active_tab="overview",
                    metric_settings={},
                    filter_presets=[],
                    refresh_interval_minutes=60,
                )
                s.add(row)
                s.commit()
                s.refresh(row)
            s.expunge(row)
            return row

    def update(
        self,
        user_id: str,
        *,
        active_tab: str | None = None,
        metric_settings: dict[str, Any] | None = None,
        filter_presets: list[Any] | None = None,
        refresh_interval_minutes: int | None = None,
    ) -> RsUserConfig:
        with self._factory() as s:
            row = s.scalars(select(RsUserConfig).where(RsUserConfig.user_id == user_id)).first()
            if row is None:
                row = RsUserConfig(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    active_tab="overview",
                    metric_settings={},
                    filter_presets=[],
                    refresh_interval_minutes=60,
                )
                s.add(row)
            if active_tab is not None:
                row.active_tab = active_tab
            if metric_settings is not None:
                row.metric_settings = metric_settings
            if filter_presets is not None:
                row.filter_presets = filter_presets
            if refresh_interval_minutes is not None:
                if refresh_interval_minutes < 5:
                    raise ValueError("refresh_interval_minutes must be >= 5")
                row.refresh_interval_minutes = refresh_interval_minutes
            s.commit()
            s.refresh(row)
            s.expunge(row)
            return row
