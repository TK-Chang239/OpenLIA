from __future__ import annotations

from datetime import UTC, datetime

import pytest
from openlia_server.db.models.auth import User
from openlia_server.db.models.scheduler import JobRun
from openlia_server.scheduler.recovery import (
    mark_orphans_cancelled,
    should_catch_up,
)
from openlia_server.scheduler.registry import JobStatus, JobType
from openlia_server.scheduler.services import jobs as jobs_svc
from sqlalchemy.orm import Session


def _make_user(session: Session, uid: str = "u_1") -> None:
    session.add(
        User(
            id=uid,
            email=f"{uid}@e.com",
            display_name=f"u-{uid}",
            password_hash="h",
            is_admin=False,
            is_disabled=False,
        )
    )
    session.commit()


def test_mark_orphans_cancelled_flips_all_running_rows(db_session: Session) -> None:
    _make_user(db_session)
    r1 = jobs_svc.start_run(
        db_session, user_id="u_1", job_type=JobType.MB_BRIEFING, schedule_id="s1"
    )
    r2 = jobs_svc.start_run(db_session, user_id="u_1", job_type=JobType.EU_SCAN, schedule_id="s2")
    r3 = jobs_svc.start_run(db_session, user_id="u_1", job_type=JobType.MR_DASH, schedule_id="s3")
    jobs_svc.mark_completed(db_session, r3)
    db_session.commit()
    n = mark_orphans_cancelled(db_session)
    db_session.commit()
    assert n == 2
    for rid in (r1, r2):
        row = db_session.get(JobRun, rid)
        assert row.status == JobStatus.CANCELLED.value
        assert row.error_message == "Server restarted during execution"
        assert row.completed_at is not None
    unchanged = db_session.get(JobRun, r3)
    assert unchanged.status == JobStatus.COMPLETED.value


def test_mark_orphans_cancelled_is_idempotent(db_session: Session) -> None:
    assert mark_orphans_cancelled(db_session) == 0
    db_session.commit()


def test_should_catch_up_fires_when_last_run_predates_recent_cron_tick() -> None:
    now = datetime(2026, 4, 17, 9, 0, tzinfo=UTC)
    last_run = datetime(2026, 4, 17, 6, 30, tzinfo=UTC)
    assert (
        should_catch_up(
            cron_expression="0 7 * * *",
            timezone_name="UTC",
            last_run_at=last_run,
            now=now,
            grace_seconds=21_600,
        )
        is True
    )


def test_should_catch_up_skipped_when_tick_is_older_than_grace() -> None:
    now = datetime(2026, 4, 17, 23, 0, tzinfo=UTC)
    last_run = datetime(2026, 4, 16, 20, 0, tzinfo=UTC)
    assert (
        should_catch_up(
            cron_expression="0 7 * * *",
            timezone_name="UTC",
            last_run_at=last_run,
            now=now,
            grace_seconds=21_600,
        )
        is False
    )


def test_should_catch_up_no_prior_run_fires_if_recent_tick_in_grace() -> None:
    now = datetime(2026, 4, 17, 9, 0, tzinfo=UTC)
    assert (
        should_catch_up(
            cron_expression="0 7 * * *",
            timezone_name="UTC",
            last_run_at=None,
            now=now,
            grace_seconds=21_600,
        )
        is True
    )


def test_should_catch_up_skips_when_last_run_is_after_tick() -> None:
    now = datetime(2026, 4, 17, 9, 0, tzinfo=UTC)
    last_run = datetime(2026, 4, 17, 7, 30, tzinfo=UTC)
    assert (
        should_catch_up(
            cron_expression="0 7 * * *",
            timezone_name="UTC",
            last_run_at=last_run,
            now=now,
            grace_seconds=21_600,
        )
        is False
    )


def test_should_catch_up_respects_non_utc_timezone() -> None:
    now = datetime(2026, 4, 17, 12, 0, tzinfo=UTC)
    last_run = datetime(2026, 4, 17, 10, 0, tzinfo=UTC)
    assert (
        should_catch_up(
            cron_expression="0 7 * * *",
            timezone_name="America/New_York",
            last_run_at=last_run,
            now=now,
            grace_seconds=21_600,
        )
        is True
    )


def test_should_catch_up_rejects_bad_cron() -> None:
    with pytest.raises(ValueError, match="cron"):
        should_catch_up(
            cron_expression="not a cron",
            timezone_name="UTC",
            last_run_at=None,
            now=datetime(2026, 4, 17, 9, 0, tzinfo=UTC),
            grace_seconds=21_600,
        )
