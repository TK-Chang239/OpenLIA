"""SchedulerService — APScheduler wrapper that owns the lifecycle
(startup rehydration, hot-reload add/modify/remove, graceful shutdown)
for the four job types defined in registry.JobType."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any

from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.date import DateTrigger
from openlia.llm.runtime.cancellation import CancellationToken

from openlia_server.db.models.auth import User
from openlia_server.db.models.dashboard import MrDashboardState
from openlia_server.db.models.scheduler import (
    EuSchedule,
    MbSchedule,
    RsSchedule,
)
from openlia_server.scheduler.executors.base import BaseExecutor, SessionFactory
from openlia_server.scheduler.recovery import (
    mark_orphans_cancelled,
    should_catch_up,
)
from openlia_server.scheduler.registry import (
    MAINTENANCE_JOB_KEY,
    PORTFOLIO_PRICE_REFRESH_KEY,
    JobType,
    department_for_job_type,
    job_key,
)
from openlia_server.scheduler.settings import SchedulerSettings

log = logging.getLogger(__name__)

_VALID_DAY_NAMES: frozenset[str] = frozenset({"mon", "tue", "wed", "thu", "fri", "sat", "sun"})
_DAY_INDEX_TO_NAME: dict[int, str] = {
    0: "mon",
    1: "tue",
    2: "wed",
    3: "thu",
    4: "fri",
    5: "sat",
    6: "sun",
}


@dataclass
class SchedulerService:
    session_factory: SessionFactory
    scheduler: Any  # APScheduler AsyncScheduler (or FakeAPScheduler in tests)
    settings: SchedulerSettings
    executors: dict[JobType, BaseExecutor] = field(default_factory=dict)
    clock: Callable[[], datetime] = field(default_factory=lambda: lambda: datetime.now(UTC))
    # Phase 10: when the dept_health cache reports a dept disabled, _run_job
    # logs and skips. The provider returns the cache map (or None to disable
    # the check entirely so tests without a health cache keep running jobs).
    dept_health_provider: Callable[[], dict | None] | None = None

    is_running: bool = field(init=False, default=False)
    _active_tokens: dict[str, CancellationToken] = field(init=False, default_factory=dict)

    # ------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------

    async def start(self) -> None:
        if not self.settings.enabled:
            log.info("scheduler disabled via settings; skipping start")
            return

        # Crash recovery: mark any status=running rows as cancelled.
        with self.session_factory() as session:
            mark_orphans_cancelled(session)
            session.commit()

        self.scheduler.start_in_background()
        self.is_running = True

        await self._register_maintenance_job()
        await self._register_portfolio_price_refresh_job()

        with self.session_factory() as session:
            enabled_user_ids = {
                u.id for u in session.query(User).filter(User.is_disabled.is_(False))
            }
            mb_rows = session.query(MbSchedule).filter(MbSchedule.is_enabled.is_(True)).all()
            eu_rows = session.query(EuSchedule).filter(EuSchedule.is_enabled.is_(True)).all()
            rs_rows = session.query(RsSchedule).filter(RsSchedule.is_enabled.is_(True)).all()

        for row in mb_rows:
            if row.user_id not in enabled_user_ids:
                continue
            await self._register_schedule(job_type=JobType.MB_BRIEFING, schedule=row)
            await self._maybe_backfill(job_type=JobType.MB_BRIEFING, schedule=row)

        for row in eu_rows:
            if row.user_id not in enabled_user_ids:
                continue
            await self._register_schedule(job_type=JobType.EU_SCAN, schedule=row)
            await self._maybe_backfill(job_type=JobType.EU_SCAN, schedule=row)

        for row in rs_rows:
            if row.user_id not in enabled_user_ids:
                continue
            if JobType.RS_SNAPSHOT not in self.executors:
                continue
            await self._register_schedule(job_type=JobType.RS_SNAPSHOT, schedule=row)
            await self._maybe_backfill(job_type=JobType.RS_SNAPSHOT, schedule=row)

    async def shutdown(self) -> None:
        """Cancel all in-flight jobs, wait up to `shutdown_grace_seconds`
        for them to unwind, then stop the APScheduler instance."""
        if not self.is_running:
            return

        for token in list(self._active_tokens.values()):
            token.cancel()

        deadline = self.clock() + timedelta(seconds=self.settings.shutdown_grace_seconds)
        while self._active_tokens and self.clock() < deadline:
            await asyncio.sleep(0.05)

        await self.scheduler.stop()
        self.is_running = False

    # ------------------------------------------------------------
    # Hot-reload API (called by route handlers)
    # ------------------------------------------------------------

    async def add_schedule(
        self, schedule: MbSchedule | EuSchedule | RsSchedule | MrDashboardState
    ) -> None:
        job_type = self._job_type_for(schedule)
        if job_type not in self.executors:
            raise RuntimeError(f"no executor registered for job_type={job_type.value!r}")
        if isinstance(schedule, MrDashboardState) and not schedule.assessment_schedule:
            raise ValueError("assessment_schedule must be set before registering an MR schedule")
        await self._register_schedule(job_type=job_type, schedule=schedule)

    async def modify_schedule(
        self, schedule: MbSchedule | EuSchedule | RsSchedule | MrDashboardState
    ) -> None:
        job_type = self._job_type_for(schedule)
        if isinstance(schedule, MrDashboardState) and not schedule.assessment_schedule:
            raise ValueError("assessment_schedule must be set before modifying an MR schedule")
        sid = schedule.id if isinstance(schedule, MbSchedule) else None
        await self.remove_schedule(job_type=job_type, user_id=schedule.user_id, schedule_id=sid)
        await self._register_schedule(job_type=job_type, schedule=schedule)

    async def remove_schedule(
        self,
        *,
        job_type: JobType,
        user_id: str,
        schedule_id: str | None = None,
    ) -> None:
        await self.scheduler.remove_schedule(job_key(job_type, user_id, schedule_id))

    async def run_retry(self, *, run_id: str) -> None:
        """Fire a one-shot re-run of a prior job_runs row. Looks up the
        original (job_type, user_id, schedule_id) and schedules a
        DateTrigger for `now + 1s`."""
        from openlia_server.db.models.scheduler import JobRun

        with self.session_factory() as session:
            original = session.get(JobRun, run_id)
            if original is None:
                raise LookupError(f"job_run {run_id!r} not found")
            job_type = JobType(original.job_type)
            user_id = original.user_id
            schedule_id = original.schedule_id

        run_time = self.clock() + timedelta(seconds=1)
        await self.scheduler.add_schedule(
            self._run_job,
            DateTrigger(run_time=run_time),
            id=f"{job_key(job_type, user_id or '')}:retry:{run_id}",
            args=(job_type, user_id, schedule_id),
            misfire_grace_time=self.settings.misfire_grace_seconds,
        )

    async def run_now(
        self,
        *,
        job_type: JobType,
        user_id: str,
        schedule_id: str,
        run_id: str,
    ) -> None:
        """Fire a one-shot dispatch of a job (used by ad-hoc "Run now" routes).

        Mirrors `run_retry` but takes the (job_type, user_id, schedule_id)
        triple directly so the caller can persist the JobRun row with its
        own id and pass it through. The pre-allocated `run_id` is forwarded
        to the executor so it reuses the row instead of opening a new one,
        which lets the route return a real id synchronously."""
        run_time = self.clock() + timedelta(seconds=1)
        await self.scheduler.add_schedule(
            self._run_job,
            DateTrigger(run_time=run_time),
            id=f"{job_key(job_type, user_id)}:run_now:{run_id}",
            args=(job_type, user_id, schedule_id, run_id),
            misfire_grace_time=self.settings.misfire_grace_seconds,
        )

    def wire_mr(self, *, builder: Any, cache_store: Any) -> None:
        """Replace the stub builder/cache on the MR executor with real implementations.

        Called once after build_scheduler_service() so the MR executor
        stops raising DepartmentPayloadBuilderNotWired at fire time.
        """
        from openlia_server.scheduler.registry import JobType

        executor = self.executors.get(JobType.MR_ASSESSMENT)
        if executor is None:
            return
        if hasattr(executor, "_mr_builder"):
            executor._mr_builder = builder
        if hasattr(executor, "_mr_cache_store"):
            executor._mr_cache_store = cache_store

    async def remove_all_for_user(self, user_id: str) -> None:
        # MB allows multiple schedules per user — find every row and remove
        # each by its own (user_id, schedule_id) key.
        with self.session_factory() as session:
            mb_ids = [
                row.id for row in session.query(MbSchedule).filter(MbSchedule.user_id == user_id)
            ]
        for sid in mb_ids:
            try:
                await self.scheduler.remove_schedule(job_key(JobType.MB_BRIEFING, user_id, sid))
            except Exception:
                log.debug(
                    "remove_schedule failed for mb_briefing/%s/%s (may not be registered)",
                    user_id,
                    sid,
                )

        for jt in (
            JobType.EU_SCAN,
            JobType.MR_ASSESSMENT,
            JobType.RS_SNAPSHOT,
        ):
            try:
                await self.scheduler.remove_schedule(job_key(jt, user_id))
            except Exception:
                log.debug("remove_schedule failed for %s/%s (may not be registered)", jt, user_id)

    # ------------------------------------------------------------
    # Job callback (invoked by APScheduler at trigger time)
    # ------------------------------------------------------------

    async def _run_job(
        self,
        job_type: JobType,
        user_id: str | None,
        schedule_id: str | None,
        run_id: str | None = None,
    ) -> None:
        if job_type is JobType.SYSTEM_MAINTENANCE:
            key = MAINTENANCE_JOB_KEY
        elif job_type is JobType.MB_BRIEFING:
            # MB now supports multiple schedules per user, each with its own
            # cancellation slot so two distinct schedules don't block each
            # other.
            key = job_key(job_type, user_id or "", schedule_id)
        else:
            key = job_key(job_type, user_id or "")
        if key in self._active_tokens:
            log.info("skipping %s: previous run still active", key)
            return

        # Phase 10: dept-health pre-flight. Skip jobs whose dept is disabled.
        if job_type is not JobType.SYSTEM_MAINTENANCE and self.dept_health_provider is not None:
            try:
                cache = self.dept_health_provider() or {}
            except Exception:
                cache = {}
            try:
                dept_id = department_for_job_type(job_type)
            except KeyError:
                dept_id = None
            if dept_id is not None:
                health = cache.get(dept_id)
                if health is not None and getattr(health, "status", None) == "disabled":
                    log.info(
                        "skipping %s: dept %r disabled (%s)",
                        key,
                        dept_id,
                        getattr(health, "reason", None),
                    )
                    return

        executor = self.executors.get(job_type)
        if executor is None:
            log.error("no executor registered for %s", job_type)
            return

        token = CancellationToken()
        self._active_tokens[key] = token
        try:
            await executor.execute(
                user_id=user_id,
                schedule_id=schedule_id,
                cancel_token=token,
                run_id=run_id,
            )
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("unhandled error in scheduled job %s", key)
        finally:
            self._active_tokens.pop(key, None)

    # ------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------

    async def _register_schedule(
        self,
        *,
        job_type: JobType,
        schedule: MbSchedule | EuSchedule | RsSchedule | MrDashboardState,
    ) -> None:
        trigger = self._cron_trigger_for(schedule)
        # MR executor uses the dashboard slug in the schedule_id slot so it
        # knows which dashboard to run; MB/EU use the row id.
        schedule_id = schedule.dashboard if isinstance(schedule, MrDashboardState) else schedule.id
        # MB allows multiple schedules per user — key by schedule_id so they
        # don't collide. Other job types remain keyed by (type, user) only.
        key_schedule_id = schedule.id if isinstance(schedule, MbSchedule) else None
        await self.scheduler.add_schedule(
            self._run_job,
            trigger,
            id=job_key(job_type, schedule.user_id, key_schedule_id),
            args=(job_type, schedule.user_id, schedule_id),
            misfire_grace_time=self.settings.misfire_grace_seconds,
            max_instances=1,
            coalesce=True,
        )

    async def _register_maintenance_job(self) -> None:
        # Always register the maintenance schedule; if no executor is
        # configured _run_job will log and return without doing work.
        trigger = CronTrigger(hour=3, minute=0, timezone=UTC)
        await self.scheduler.add_schedule(
            self._run_job,
            trigger,
            id=MAINTENANCE_JOB_KEY,
            args=(JobType.SYSTEM_MAINTENANCE, None, None),
            misfire_grace_time=self.settings.misfire_grace_seconds,
            max_instances=1,
            coalesce=True,
        )

    async def _register_portfolio_price_refresh_job(self) -> None:
        # Top-of-hour fire (UTC). The per-tick logic in refresh_due_quotes
        # decides which tickers are actually due and skips fresh / closed
        # markets. When no executor is configured (e.g. tests without a
        # financial adapter) _run_job logs and returns without doing work.
        if JobType.PORTFOLIO_PRICE_REFRESH not in self.executors:
            log.info("portfolio price refresh executor not configured; skipping schedule")
            return
        trigger = CronTrigger(minute=0, timezone=UTC)
        await self.scheduler.add_schedule(
            self._run_job,
            trigger,
            id=PORTFOLIO_PRICE_REFRESH_KEY,
            args=(JobType.PORTFOLIO_PRICE_REFRESH, None, None),
            misfire_grace_time=self.settings.misfire_grace_seconds,
            max_instances=1,
            coalesce=True,
        )
        # Sub-hour intraday cron: fires every 15 minutes so the 1D chart
        # and per-ticker sparklines accumulate >= 4 points per market hour
        # (~26 across a US session, ~18 across a TWSE session). The
        # per-ticker market_hours gate inside refresh_due_quotes still
        # suppresses fetches for tickers whose home market is closed, so
        # this only adds writes during open sessions.
        await self.scheduler.add_schedule(
            self._run_job,
            CronTrigger(minute="*/15", timezone=UTC),
            id=f"{PORTFOLIO_PRICE_REFRESH_KEY}:intraday",
            args=(JobType.PORTFOLIO_PRICE_REFRESH, None, None),
            misfire_grace_time=self.settings.misfire_grace_seconds,
            max_instances=1,
            coalesce=True,
        )
        # Wake-up sweep: one-shot fire shortly after start so we catch up on
        # any tickers that aged past their cadence while the server was down.
        run_time = self.clock() + timedelta(seconds=5)
        await self.scheduler.add_schedule(
            self._run_job,
            DateTrigger(run_time=run_time),
            id=f"{PORTFOLIO_PRICE_REFRESH_KEY}:wakeup",
            args=(JobType.PORTFOLIO_PRICE_REFRESH, None, None),
            misfire_grace_time=self.settings.misfire_grace_seconds,
        )
        # Phase 3 post-close fires: capture the canonical close price into
        # portfolio_quote_daily once each market has settled. US closes at
        # 16:00 ET (~20:30 UTC during DST, with a 30-min buffer); TWSE
        # closes at 13:30 Taipei (~05:30 UTC, +30-min buffer).
        for fire_id, hour, minute in (
            (f"{PORTFOLIO_PRICE_REFRESH_KEY}:us_close", 20, 30),
            (f"{PORTFOLIO_PRICE_REFRESH_KEY}:twse_close", 6, 0),
        ):
            await self.scheduler.add_schedule(
                self._run_job,
                CronTrigger(
                    hour=hour,
                    minute=minute,
                    day_of_week="mon,tue,wed,thu,fri",
                    timezone=UTC,
                ),
                id=fire_id,
                args=(JobType.PORTFOLIO_PRICE_REFRESH, None, None),
                misfire_grace_time=self.settings.misfire_grace_seconds,
                max_instances=1,
                coalesce=True,
            )

    async def _maybe_backfill(
        self,
        *,
        job_type: JobType,
        schedule: MbSchedule | EuSchedule | RsSchedule,
    ) -> None:
        cron = self._cron_expression_for(schedule)
        if not should_catch_up(
            cron_expression=cron,
            timezone_name=schedule.timezone,
            last_run_at=schedule.last_run_at,
            now=self.clock(),
            grace_seconds=self.settings.misfire_grace_seconds,
        ):
            return

        run_time = self.clock() + timedelta(seconds=1)
        key_schedule_id = schedule.id if isinstance(schedule, MbSchedule) else None
        await self.scheduler.add_schedule(
            self._run_job,
            DateTrigger(run_time=run_time),
            id=f"{job_key(job_type, schedule.user_id, key_schedule_id)}:backfill",
            args=(job_type, schedule.user_id, schedule.id),
            misfire_grace_time=self.settings.misfire_grace_seconds,
        )

    # --- cron helpers ---

    @staticmethod
    def _job_type_for(
        schedule: MbSchedule | EuSchedule | RsSchedule | MrDashboardState,
    ) -> JobType:
        if isinstance(schedule, MbSchedule):
            return JobType.MB_BRIEFING
        if isinstance(schedule, EuSchedule):
            return JobType.EU_SCAN
        if isinstance(schedule, RsSchedule):
            return JobType.RS_SNAPSHOT
        if isinstance(schedule, MrDashboardState):
            return JobType.MR_ASSESSMENT
        raise TypeError(f"unknown schedule type: {type(schedule).__name__}")

    @staticmethod
    def _days_to_names(days_raw: list[int | str]) -> list[str]:
        """Normalize day values to APScheduler name strings (mon-sun).

        Accepts either integer indices (0=mon … 6=sun) or day-name strings.
        Raises ValueError for any unrecognised value.
        """
        names: list[str] = []
        for d in days_raw:
            if isinstance(d, int):
                if d not in _DAY_INDEX_TO_NAME:
                    raise ValueError(f"invalid day index: {d!r}")
                names.append(_DAY_INDEX_TO_NAME[d])
            elif isinstance(d, str):
                if d not in _VALID_DAY_NAMES:
                    raise ValueError(f"invalid day name: {d!r}")
                names.append(d)
            else:
                raise ValueError(f"invalid day value: {d!r}")
        return names

    @staticmethod
    def _cron_trigger_for(
        schedule: MbSchedule | EuSchedule | RsSchedule | MrDashboardState,
    ) -> CronTrigger:
        if isinstance(schedule, MrDashboardState):
            if not schedule.assessment_schedule:
                raise ValueError(
                    "MR assessment_schedule must be set before registering "
                    "an MR schedule (no silent default)"
                )
            return CronTrigger.from_crontab(schedule.assessment_schedule, timezone="UTC")
        hour, minute = [int(p) for p in schedule.time.split(":")]
        days_raw = json.loads(schedule.days_of_week)
        days = ",".join(SchedulerService._days_to_names(days_raw))
        return CronTrigger(
            hour=hour,
            minute=minute,
            day_of_week=days,
            timezone=schedule.timezone,
        )

    @staticmethod
    def _cron_expression_for(
        schedule: MbSchedule | EuSchedule | RsSchedule | MrDashboardState,
    ) -> str:
        """croniter-compatible 5-field string. Used only by should_catch_up."""
        if isinstance(schedule, MrDashboardState):
            return schedule.assessment_schedule or ""
        hour, minute = [int(p) for p in schedule.time.split(":")]
        days_raw = json.loads(schedule.days_of_week)
        days = ",".join(SchedulerService._days_to_names(days_raw))
        return f"{minute} {hour} * * {days}"
