from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import ClassVar

import pytest
from _scheduler_fakes import FakeAPScheduler, FakeSleep
from openlia.llm.runtime.cancellation import CancellationToken
from openlia_server.db.models.auth import User
from openlia_server.db.models.scheduler import EuSchedule, JobRun, MbSchedule
from openlia_server.scheduler.executors.base import (
    BaseExecutor,
    JobOutcome,
    SessionFactory,
)
from openlia_server.scheduler.registry import (
    MAINTENANCE_JOB_KEY,
    PORTFOLIO_PRICE_REFRESH_KEY,
    JobStatus,
    JobType,
    job_key,
)
from openlia_server.scheduler.service import SchedulerService
from openlia_server.scheduler.settings import SchedulerSettings
from sqlalchemy.orm import Session

# --- Minimal recording executor for dispatch tests -----------------


class _RecordingExecutor(BaseExecutor):
    def __init__(
        self,
        *,
        session_factory: SessionFactory,
        job_type: JobType,
        outcome: JobOutcome | None = None,
        raise_exc: Exception | None = None,
    ) -> None:
        super().__init__(session_factory=session_factory, sleep=FakeSleep())
        # BaseExecutor has job_type as ClassVar — override on the instance.
        self.job_type = job_type  # type: ignore[misc]
        self.calls: list[dict] = []
        self._outcome = outcome or JobOutcome(result_summary={"ok": True}, notifications=[])
        self._raise_exc = raise_exc

    async def _do_work(
        self,
        *,
        user_id: str | None,
        schedule_id: str | None,
        run_id: str,
        cancel_token: CancellationToken | None,
    ):
        self.calls.append(
            {
                "user_id": user_id,
                "schedule_id": schedule_id,
                "run_id": run_id,
                "cancel_token": cancel_token,
            }
        )
        if self._raise_exc is not None:
            raise self._raise_exc
        return self._outcome


def _seed_user(session: Session) -> None:
    session.add(
        User(
            id="u_1",
            email="u@e.com",
            display_name="u",
            password_hash="h",
            is_admin=False,
            is_disabled=False,
        )
    )
    session.commit()


def _mb_schedule(
    *,
    id: str = "sch_mb",
    user_id: str = "u_1",
    time: str = "07:00",
    tz: str = "UTC",
    enabled: bool = True,
    last_run_at: datetime | None = None,
) -> MbSchedule:
    return MbSchedule(
        id=id,
        user_id=user_id,
        time=time,
        timezone=tz,
        days_of_week='["mon","tue","wed","thu","fri"]',
        label="Pre-Market",
        is_enabled=enabled,
        created_at=datetime.now(UTC),
        last_run_at=last_run_at,
    )


def _eu_schedule(
    *,
    id: str = "sch_eu",
    user_id: str = "u_1",
    enabled: bool = True,
) -> EuSchedule:
    return EuSchedule(
        id=id,
        user_id=user_id,
        time="16:30",
        timezone="America/New_York",
        days_of_week='["mon","tue","wed","thu","fri"]',
        label="Post-Market",
        is_enabled=enabled,
        created_at=datetime.now(UTC),
        last_run_at=None,
    )


# --- Tests ---------------------------------------------------------


@pytest.mark.asyncio
async def test_start_registers_maintenance_job(session_factory) -> None:
    with session_factory() as s:
        _seed_user(s)

    scheduler = FakeAPScheduler()
    svc = SchedulerService(
        session_factory=session_factory,
        scheduler=scheduler,
        settings=SchedulerSettings(enabled=True),
    )
    await svc.start()

    assert scheduler.started is True
    assert MAINTENANCE_JOB_KEY in scheduler.jobs
    assert svc.is_running is True


@pytest.mark.asyncio
async def test_start_rehydrates_enabled_mb_and_eu_schedules(
    session_factory,
) -> None:
    with session_factory() as s:
        _seed_user(s)
        s.add(_mb_schedule(id="sch_mb", enabled=True))
        s.add(_mb_schedule(id="sch_mb_off", enabled=False))
        s.add(_eu_schedule(id="sch_eu", enabled=True))
        s.commit()

    scheduler = FakeAPScheduler()
    svc = SchedulerService(
        session_factory=session_factory,
        scheduler=scheduler,
        settings=SchedulerSettings(enabled=True),
    )
    await svc.start()

    assert job_key(JobType.MB_BRIEFING, "u_1", "sch_mb") in scheduler.jobs
    assert job_key(JobType.EU_SCAN, "u_1") in scheduler.jobs
    assert job_key(JobType.MB_BRIEFING, "u_1", "sch_mb_off") not in scheduler.jobs


@pytest.mark.asyncio
async def test_start_skips_schedules_for_disabled_users(
    session_factory,
) -> None:
    with session_factory() as s:
        s.add(
            User(
                id="u_bad",
                email="x@e.com",
                display_name="x",
                password_hash="h",
                is_admin=False,
                is_disabled=True,
            )
        )
        s.add(_mb_schedule(id="sch_bad", user_id="u_bad"))
        s.commit()

    scheduler = FakeAPScheduler()
    svc = SchedulerService(
        session_factory=session_factory,
        scheduler=scheduler,
        settings=SchedulerSettings(enabled=True),
    )
    await svc.start()

    assert job_key(JobType.MB_BRIEFING, "u_bad") not in scheduler.jobs


@pytest.mark.asyncio
async def test_disabled_flag_does_not_start_scheduler(session_factory) -> None:
    scheduler = FakeAPScheduler()
    svc = SchedulerService(
        session_factory=session_factory,
        scheduler=scheduler,
        settings=SchedulerSettings(enabled=False),
    )
    await svc.start()

    assert scheduler.started is False
    assert svc.is_running is False
    assert scheduler.jobs == {}


@pytest.mark.asyncio
async def test_add_schedule_registers_job_with_correct_key_and_trigger(
    session_factory,
) -> None:
    from apscheduler.triggers.cron import CronTrigger

    with session_factory() as s:
        _seed_user(s)

    mb_exec = _RecordingExecutor(
        session_factory=session_factory,
        job_type=JobType.MB_BRIEFING,
    )
    scheduler = FakeAPScheduler()
    svc = SchedulerService(
        session_factory=session_factory,
        scheduler=scheduler,
        settings=SchedulerSettings(enabled=True),
        executors={JobType.MB_BRIEFING: mb_exec},
    )
    await svc.start()

    await svc.add_schedule(_mb_schedule(time="09:30", tz="America/New_York"))

    key = job_key(JobType.MB_BRIEFING, "u_1", "sch_mb")
    assert key in scheduler.jobs
    job = scheduler.jobs[key]
    assert isinstance(job.trigger, CronTrigger)
    assert job.args == (JobType.MB_BRIEFING, "u_1", "sch_mb")


@pytest.mark.asyncio
async def test_modify_schedule_replaces_existing_job(session_factory) -> None:
    with session_factory() as s:
        _seed_user(s)

    mb_exec = _RecordingExecutor(
        session_factory=session_factory,
        job_type=JobType.MB_BRIEFING,
    )
    scheduler = FakeAPScheduler()
    svc = SchedulerService(
        session_factory=session_factory,
        scheduler=scheduler,
        settings=SchedulerSettings(enabled=True),
        executors={JobType.MB_BRIEFING: mb_exec},
    )
    await svc.start()

    await svc.add_schedule(_mb_schedule(time="07:00"))
    await svc.modify_schedule(_mb_schedule(time="08:30"))

    key = job_key(JobType.MB_BRIEFING, "u_1", "sch_mb")
    assert key in scheduler.jobs
    # Trigger swap: there's still exactly one MB job for u_1/sch_mb.
    mb_ids = [k for k in scheduler.jobs if k.startswith("mb_briefing:")]
    assert mb_ids == [key]


@pytest.mark.asyncio
async def test_remove_schedule_unregisters_job(session_factory) -> None:
    with session_factory() as s:
        _seed_user(s)

    mb_exec = _RecordingExecutor(
        session_factory=session_factory,
        job_type=JobType.MB_BRIEFING,
    )
    scheduler = FakeAPScheduler()
    svc = SchedulerService(
        session_factory=session_factory,
        scheduler=scheduler,
        settings=SchedulerSettings(enabled=True),
        executors={JobType.MB_BRIEFING: mb_exec},
    )
    await svc.start()
    await svc.add_schedule(_mb_schedule())

    await svc.remove_schedule(job_type=JobType.MB_BRIEFING, user_id="u_1", schedule_id="sch_mb")
    assert job_key(JobType.MB_BRIEFING, "u_1", "sch_mb") not in scheduler.jobs


@pytest.mark.asyncio
async def test_add_schedule_raises_when_executor_not_registered(
    session_factory,
) -> None:
    with session_factory() as s:
        _seed_user(s)

    scheduler = FakeAPScheduler()
    # Intentionally pass executors={} so MB is unregistered.
    svc = SchedulerService(
        session_factory=session_factory,
        scheduler=scheduler,
        settings=SchedulerSettings(enabled=True),
        executors={},
    )
    await svc.start()

    with pytest.raises(RuntimeError, match="no executor registered"):
        await svc.add_schedule(_mb_schedule())


@pytest.mark.asyncio
async def test_dispatch_routes_call_to_registered_executor(
    session_factory,
) -> None:
    with session_factory() as s:
        _seed_user(s)

    mb_exec = _RecordingExecutor(
        session_factory=session_factory,
        job_type=JobType.MB_BRIEFING,
    )
    scheduler = FakeAPScheduler()
    svc = SchedulerService(
        session_factory=session_factory,
        scheduler=scheduler,
        settings=SchedulerSettings(enabled=True),
        executors={JobType.MB_BRIEFING: mb_exec},
    )
    await svc.start()
    await svc.add_schedule(_mb_schedule())

    # Fire the APScheduler callback manually.
    key = job_key(JobType.MB_BRIEFING, "u_1", "sch_mb")
    await scheduler.fire(key)

    assert len(mb_exec.calls) == 1
    assert mb_exec.calls[0]["user_id"] == "u_1"
    assert mb_exec.calls[0]["schedule_id"] == "sch_mb"
    assert mb_exec.calls[0]["cancel_token"] is not None


@pytest.mark.asyncio
async def test_startup_backfills_missed_tick_within_grace(
    session_factory,
) -> None:
    """Schedule ran at 07:00 UTC daily. last_run_at is 2 days ago, grace
    is 6 hours. The schedule's most recent tick is today 07:00 — within
    6h if startup is <=13:00 — so a catch-up run must be queued."""
    from apscheduler.triggers.date import DateTrigger

    now = datetime(2026, 4, 17, 10, 0, tzinfo=UTC)
    with session_factory() as s:
        _seed_user(s)
        s.add(
            _mb_schedule(
                time="07:00",
                tz="UTC",
                last_run_at=datetime(2026, 4, 16, 7, 0, tzinfo=UTC),
            )
        )
        s.commit()

    mb_exec = _RecordingExecutor(
        session_factory=session_factory,
        job_type=JobType.MB_BRIEFING,
    )
    scheduler = FakeAPScheduler()
    svc = SchedulerService(
        session_factory=session_factory,
        scheduler=scheduler,
        settings=SchedulerSettings(enabled=True, misfire_grace_seconds=6 * 3600),
        executors={JobType.MB_BRIEFING: mb_exec},
        clock=lambda: now,
    )
    await svc.start()

    # The normal cron registration.
    assert job_key(JobType.MB_BRIEFING, "u_1", "sch_mb") in scheduler.jobs
    # Plus a one-shot backfill with a DateTrigger.
    backfill_key = f"{job_key(JobType.MB_BRIEFING, 'u_1', 'sch_mb')}:backfill"
    assert backfill_key in scheduler.jobs
    assert isinstance(scheduler.jobs[backfill_key].trigger, DateTrigger)


@pytest.mark.asyncio
async def test_startup_does_not_backfill_when_tick_outside_grace(
    session_factory,
) -> None:
    """Daily 07:00 UTC, last ran 5 days ago, grace is 6 hours, startup is
    18:00 UTC. The most recent tick was 07:00 today — 11h ago — outside
    6h. No backfill."""
    now = datetime(2026, 4, 17, 18, 0, tzinfo=UTC)
    with session_factory() as s:
        _seed_user(s)
        s.add(
            _mb_schedule(
                time="07:00",
                tz="UTC",
                last_run_at=datetime(2026, 4, 12, 7, 0, tzinfo=UTC),
            )
        )
        s.commit()

    scheduler = FakeAPScheduler()
    svc = SchedulerService(
        session_factory=session_factory,
        scheduler=scheduler,
        settings=SchedulerSettings(enabled=True, misfire_grace_seconds=6 * 3600),
        clock=lambda: now,
    )
    await svc.start()

    assert f"{job_key(JobType.MB_BRIEFING, 'u_1', 'sch_mb')}:backfill" not in scheduler.jobs


@pytest.mark.asyncio
async def test_startup_marks_running_jobs_as_cancelled(
    session_factory,
) -> None:
    """If a previous process died with status=running rows, recovery flips
    them to status=cancelled before rehydration."""
    with session_factory() as s:
        _seed_user(s)
        s.add(
            JobRun(
                id="run_orphan",
                job_type=JobType.MB_BRIEFING.value,
                user_id="u_1",
                schedule_id="sch_mb",
                attempt=1,
                status=JobStatus.RUNNING.value,
                started_at=datetime.now(UTC) - timedelta(hours=1),
            )
        )
        s.commit()

    scheduler = FakeAPScheduler()
    svc = SchedulerService(
        session_factory=session_factory,
        scheduler=scheduler,
        settings=SchedulerSettings(enabled=True),
    )
    await svc.start()

    with session_factory() as s:
        row = s.get(JobRun, "run_orphan")
        assert row.status == JobStatus.CANCELLED.value
        assert "restart" in (row.error_message or "").lower()


@pytest.mark.asyncio
async def test_shutdown_cancels_active_tokens_and_stops_scheduler(
    session_factory,
) -> None:
    import asyncio

    with session_factory() as s:
        _seed_user(s)

    # Executor that parks forever so we can observe cancellation.
    class _Sleeper(BaseExecutor):
        def __init__(self, *, session_factory: SessionFactory) -> None:
            super().__init__(session_factory=session_factory, sleep=FakeSleep())
            self.cancel_seen = asyncio.Event()

        job_type: ClassVar[JobType] = JobType.MB_BRIEFING

        async def _do_work(
            self,
            *,
            user_id: str | None,
            schedule_id: str | None,
            run_id: str,
            cancel_token: CancellationToken | None,
        ):
            # Wait for cancellation.
            while not cancel_token.is_cancelled:
                await asyncio.sleep(0.01)
            self.cancel_seen.set()
            raise asyncio.CancelledError

    sleeper = _Sleeper(session_factory=session_factory)
    scheduler = FakeAPScheduler()
    svc = SchedulerService(
        session_factory=session_factory,
        scheduler=scheduler,
        settings=SchedulerSettings(enabled=True, shutdown_grace_seconds=1),
        executors={JobType.MB_BRIEFING: sleeper},
    )
    await svc.start()
    await svc.add_schedule(_mb_schedule())

    # Kick off a job in the background and let it reach its sleep.
    key = job_key(JobType.MB_BRIEFING, "u_1", "sch_mb")
    task = asyncio.create_task(scheduler.fire(key))
    await asyncio.sleep(0.05)

    await svc.shutdown()

    assert sleeper.cancel_seen.is_set()
    assert scheduler.stopped is True
    # Let the job task unwind.
    with pytest.raises(asyncio.CancelledError):
        await task


@pytest.mark.asyncio
async def test_add_schedule_sets_max_instances(session_factory) -> None:
    """NEW-6-05: per-{job_type, user_id} max_instances=1 must be passed
    to the underlying scheduler at registration time."""
    with session_factory() as s:
        _seed_user(s)

    mb_exec = _RecordingExecutor(
        session_factory=session_factory,
        job_type=JobType.MB_BRIEFING,
    )
    scheduler = FakeAPScheduler()
    svc = SchedulerService(
        session_factory=session_factory,
        scheduler=scheduler,
        settings=SchedulerSettings(enabled=True),
        executors={JobType.MB_BRIEFING: mb_exec},
    )
    await svc.start()

    await svc.add_schedule(_mb_schedule())
    key = job_key(JobType.MB_BRIEFING, "u_1", "sch_mb")
    job = scheduler.jobs[key]
    assert job.max_instances == 1
    assert job.coalesce is True
    # Maintenance job carries the same caps.
    maint = scheduler.jobs[MAINTENANCE_JOB_KEY]
    assert maint.max_instances == 1
    assert maint.coalesce is True


@pytest.mark.asyncio
async def test_run_retry_fires_original_schedule_as_one_shot(
    session_factory,
) -> None:
    from apscheduler.triggers.date import DateTrigger
    from openlia_server.db.models.scheduler import JobRun

    with session_factory() as s:
        _seed_user(s)
        s.add(_mb_schedule())
        s.add(
            JobRun(
                id="run_failed",
                job_type=JobType.MB_BRIEFING.value,
                user_id="u_1",
                schedule_id="sch_mb",
                attempt=3,
                status=JobStatus.FAILED.value,
                started_at=datetime.now(UTC) - timedelta(hours=2),
                completed_at=datetime.now(UTC) - timedelta(hours=1),
                error_message="429",
            )
        )
        s.commit()

    scheduler = FakeAPScheduler()
    svc = SchedulerService(
        session_factory=session_factory,
        scheduler=scheduler,
        settings=SchedulerSettings(enabled=True),
    )
    await svc.start()

    await svc.run_retry(run_id="run_failed")

    retry_key = f"{job_key(JobType.MB_BRIEFING, 'u_1')}:retry:run_failed"
    assert retry_key in scheduler.jobs
    assert isinstance(scheduler.jobs[retry_key].trigger, DateTrigger)


@pytest.mark.asyncio
async def test_run_now_dispatches_one_shot_with_pre_allocated_run_id(
    session_factory,
) -> None:
    """NEW Phase 19 P1-05: scheduler.run_now schedules a one-shot DateTrigger
    keyed to the pre-allocated job_runs id and forwards it via the args
    tuple so the executor reuses the row."""
    from apscheduler.triggers.date import DateTrigger

    with session_factory() as s:
        _seed_user(s)

    scheduler = FakeAPScheduler()
    svc = SchedulerService(
        session_factory=session_factory,
        scheduler=scheduler,
        settings=SchedulerSettings(enabled=True),
    )
    await svc.start()

    await svc.run_now(
        job_type=JobType.MR_DASH,
        user_id="u_1",
        schedule_id="debt_cycle",
        run_id="run-123",
    )

    expected_key = f"{job_key(JobType.MR_DASH, 'u_1')}:run_now:run-123"
    assert expected_key in scheduler.jobs
    job = scheduler.jobs[expected_key]
    assert isinstance(job.trigger, DateTrigger)
    # Args carry job_type, user_id, schedule_id, run_id (4-tuple).
    assert job.args[1] == "u_1"
    assert job.args[2] == "debt_cycle"
    assert job.args[3] == "run-123"


@pytest.mark.asyncio
async def test_start_registers_intraday_subhour_cron_for_portfolio_refresh(
    session_factory,
) -> None:
    """1D charts need sub-hour intraday samples. When a portfolio refresh
    executor is configured, the scheduler must register a cron that fires
    at least 4x per hour (i.e. every 15 minutes or faster) in addition to
    the top-of-hour and post-close fires.
    """
    from apscheduler.triggers.cron import CronTrigger

    portfolio_exec = _RecordingExecutor(
        session_factory=session_factory,
        job_type=JobType.PORTFOLIO_PRICE_REFRESH,
    )
    scheduler = FakeAPScheduler()
    svc = SchedulerService(
        session_factory=session_factory,
        scheduler=scheduler,
        settings=SchedulerSettings(enabled=True),
        executors={JobType.PORTFOLIO_PRICE_REFRESH: portfolio_exec},
    )
    await svc.start()

    intraday_key = f"{PORTFOLIO_PRICE_REFRESH_KEY}:intraday"
    assert intraday_key in scheduler.jobs, (
        "expected an intraday sub-hour cron to be registered for portfolio price refresh"
    )
    job = scheduler.jobs[intraday_key]
    assert isinstance(job.trigger, CronTrigger)

    # Sub-hour cadence: the minute field must be an interval pattern */N
    # with N <= 15 so we accumulate >= 4 points per market hour.
    minute_field = str(job.trigger.minute)
    assert minute_field.startswith("*/"), (
        f"intraday cron minute must be an interval pattern, got {minute_field!r}"
    )
    interval = int(minute_field.removeprefix("*/"))
    assert 1 <= interval <= 15, f"intraday cron interval must be in [1, 15] minutes, got {interval}"


@pytest.mark.asyncio
async def test_us_post_close_fire_lands_30min_after_close_year_round(
    session_factory,
) -> None:
    """The US post-close capture must fire 30 min after the 16:00 ET close in
    BOTH EST and EDT. A fixed 20:30 UTC fire is only correct under EDT; under
    EST (16:00 ET == 21:00 UTC) it would run at 15:30 ET — mid-session, before
    the close — and _upsert_today_daily would persist that print as the
    canonical daily close. Pinning the cron to 16:30 America/New_York keeps it
    30 min after the close year-round regardless of DST.
    """
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from apscheduler.triggers.cron import CronTrigger

    portfolio_exec = _RecordingExecutor(
        session_factory=session_factory,
        job_type=JobType.PORTFOLIO_PRICE_REFRESH,
    )
    scheduler = FakeAPScheduler()
    svc = SchedulerService(
        session_factory=session_factory,
        scheduler=scheduler,
        settings=SchedulerSettings(enabled=True),
        executors={JobType.PORTFOLIO_PRICE_REFRESH: portfolio_exec},
    )
    await svc.start()

    us_key = f"{PORTFOLIO_PRICE_REFRESH_KEY}:us_close"
    assert us_key in scheduler.jobs, "expected a US post-close fire to be registered"
    trigger = scheduler.jobs[us_key].trigger
    assert isinstance(trigger, CronTrigger)

    # The fire must be declared in US Eastern local time, not a fixed UTC hour.
    ny = ZoneInfo("America/New_York")
    assert trigger.timezone == ny, (
        f"US post-close fire must be timezone-aware (America/New_York), got {trigger.timezone!r}"
    )
    assert (trigger.hour, trigger.minute) == (16, 30)

    # Prove year-round correctness by resolving the next fire from the
    # registered trigger's own fields on both sides of the DST boundary.
    for label, start in (
        ("EST winter", datetime(2026, 1, 15, tzinfo=ZoneInfo("UTC"))),
        ("EDT summer", datetime(2026, 7, 15, tzinfo=ZoneInfo("UTC"))),
    ):
        seasonal = CronTrigger(
            hour=trigger.hour,
            minute=trigger.minute,
            day_of_week="mon,tue,wed,thu,fri",
            timezone=trigger.timezone,
            start_time=start,
        )
        fire = seasonal.next()
        assert fire is not None
        fire_et = fire.astimezone(ny)
        assert (fire_et.hour, fire_et.minute) == (16, 30), (
            f"{label}: US post-close fire must land at 16:30 ET, got {fire_et:%H:%M %Z}"
        )
        # 30 min strictly after the 16:00 ET close on the same trading day.
        close_et = fire_et.replace(hour=16, minute=0)
        assert fire_et > close_et, (
            f"{label}: fire {fire_et:%H:%M %Z} must be after the 16:00 ET close"
        )


@pytest.mark.asyncio
async def test_twse_post_close_fire_stays_fixed_utc(session_factory) -> None:
    """TWSE has no DST (Taipei is UTC+8 year-round): 13:30 Taipei close ==
    05:30 UTC, so the +30-min buffer fire stays pinned at 06:00 UTC. Guard
    against the DST fix accidentally moving it.
    """
    from zoneinfo import ZoneInfo

    from apscheduler.triggers.cron import CronTrigger

    portfolio_exec = _RecordingExecutor(
        session_factory=session_factory,
        job_type=JobType.PORTFOLIO_PRICE_REFRESH,
    )
    scheduler = FakeAPScheduler()
    svc = SchedulerService(
        session_factory=session_factory,
        scheduler=scheduler,
        settings=SchedulerSettings(enabled=True),
        executors={JobType.PORTFOLIO_PRICE_REFRESH: portfolio_exec},
    )
    await svc.start()

    twse_key = f"{PORTFOLIO_PRICE_REFRESH_KEY}:twse_close"
    assert twse_key in scheduler.jobs
    trigger = scheduler.jobs[twse_key].trigger
    assert isinstance(trigger, CronTrigger)
    # CronTrigger normalizes datetime.UTC to ZoneInfo("UTC").
    assert trigger.timezone == ZoneInfo("UTC")
    assert (trigger.hour, trigger.minute) == (6, 0)
