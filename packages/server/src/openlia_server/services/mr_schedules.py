"""MR schedule service — singleton schedule per user tracked on
the canonical `world_order` mr_dashboard_state row."""

from __future__ import annotations

import uuid
from collections.abc import Callable

from apscheduler.triggers.cron import CronTrigger
from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia_server.db.models.dashboard import MrDashboardState
from openlia_server.scheduler.registry import JobType
from openlia_server.scheduler.service import SchedulerService


def _validate_cron(cron_expression: str) -> None:
    """Raise ValueError if the cron expression is not a valid 5-field crontab.

    Mirrors what `SchedulerService._cron_trigger_for` will do at fire time;
    surfaces the error at write time so users see a 400 instead of a silent
    fallback in the scheduler.
    """
    try:
        CronTrigger.from_crontab(cron_expression)
    except (ValueError, TypeError) as exc:
        raise ValueError(f"invalid cron expression: {cron_expression!r} ({exc})") from exc


class MRScheduleService:
    """One schedule per user — persisted on the world_order dashboard row."""

    CANONICAL_DASHBOARD = "world_order"

    def __init__(
        self,
        *,
        session_factory: Callable[[], Session],
        scheduler: SchedulerService | None = None,
    ) -> None:
        self._session_factory = session_factory
        self._scheduler = scheduler

    def get(self, *, user_id: str) -> MrDashboardState | None:
        with self._session_factory() as s:
            stmt = select(MrDashboardState).where(
                MrDashboardState.user_id == user_id,
                MrDashboardState.dashboard == self.CANONICAL_DASHBOARD,
            )
            return s.scalars(stmt).first()

    async def upsert(self, *, user_id: str, cron_expression: str) -> MrDashboardState:
        _validate_cron(cron_expression)
        with self._session_factory() as s:
            existing = s.scalars(
                select(MrDashboardState).where(
                    MrDashboardState.user_id == user_id,
                    MrDashboardState.dashboard == self.CANONICAL_DASHBOARD,
                )
            ).first()
            if existing is None:
                existing = MrDashboardState(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    dashboard=self.CANONICAL_DASHBOARD,
                    view_config={},
                    threshold_overrides={},
                )
                s.add(existing)
            existing.assessment_schedule = cron_expression
            s.commit()
            s.refresh(existing)
            # Detach from session so callers can access attributes after
            # the with-block closes without triggering SQL.
            s.expunge(existing)
        if self._scheduler is not None and existing.assessment_schedule:
            await self._scheduler.modify_schedule(existing)
        return existing

    async def delete(self, *, user_id: str) -> None:
        row = self.get(user_id=user_id)
        if row is None or row.assessment_schedule is None:
            return
        if self._scheduler is not None:
            await self._scheduler.remove_schedule(job_type=JobType.MR_DASH, user_id=user_id)
        with self._session_factory() as s:
            fresh = s.scalars(
                select(MrDashboardState).where(
                    MrDashboardState.user_id == user_id,
                    MrDashboardState.dashboard == self.CANONICAL_DASHBOARD,
                )
            ).first()
            if fresh is not None:
                fresh.assessment_schedule = None
                s.commit()

    async def rehydrate_all(self) -> int:
        """Called at lifespan startup. Returns number of rehydrated rows."""
        with self._session_factory() as s:
            rows = list(
                s.scalars(
                    select(MrDashboardState).where(
                        MrDashboardState.dashboard == self.CANONICAL_DASHBOARD,
                        MrDashboardState.assessment_schedule.is_not(None),
                    )
                ).all()
            )
            for row in rows:
                s.expunge(row)
        count = 0
        if self._scheduler is None:
            return count
        for row in rows:
            await self._scheduler.add_schedule(row)
            count += 1
        return count
