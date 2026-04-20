from __future__ import annotations

from datetime import UTC, datetime, timedelta

from openlia_server.db.models.auth import User
from openlia_server.db.models.scheduler import JobRun
from openlia_server.scheduler.registry import JobStatus, JobType
from openlia_server.scheduler.services import jobs as jobs_svc
from sqlalchemy.orm import Session


def _make_user(session: Session, user_id: str = "u_1") -> User:
    user = User(
        id=user_id,
        email=f"{user_id}@example.com",
        display_name=f"user-{user_id}",
        password_hash="h",
        is_admin=False,
        is_disabled=False,
    )
    session.add(user)
    session.commit()
    return user


def test_start_run_inserts_row_and_returns_id(db_session: Session) -> None:
    _make_user(db_session)
    run_id = jobs_svc.start_run(
        db_session,
        user_id="u_1",
        job_type=JobType.MB_BRIEFING,
        schedule_id="sched_1",
    )
    db_session.commit()
    row = db_session.get(JobRun, run_id)
    assert row is not None
    assert row.status == JobStatus.RUNNING.value
    assert row.attempt == 1
    assert row.job_type == "mb_briefing"
    assert row.schedule_id == "sched_1"
    assert row.error_message is None
    assert row.completed_at is None


def test_start_run_for_maintenance_accepts_null_user(db_session: Session) -> None:
    run_id = jobs_svc.start_run(
        db_session,
        user_id=None,
        job_type=JobType.SYSTEM_MAINTENANCE,
        schedule_id=None,
    )
    db_session.commit()
    row = db_session.get(JobRun, run_id)
    assert row is not None
    assert row.user_id is None
    assert row.schedule_id is None


def test_start_run_retry_of_copies_attempt_plus_one(db_session: Session) -> None:
    _make_user(db_session)
    original = jobs_svc.start_run(
        db_session, user_id="u_1", job_type=JobType.MB_BRIEFING, schedule_id="s1"
    )
    jobs_svc.mark_failed(db_session, original, error_message="boom")
    db_session.commit()

    retry = jobs_svc.start_run(
        db_session,
        user_id="u_1",
        job_type=JobType.MB_BRIEFING,
        schedule_id="s1",
        retry_of=original,
    )
    db_session.commit()

    retry_row = db_session.get(JobRun, retry)
    assert retry_row is not None
    assert retry_row.retry_of == original
    assert retry_row.attempt == 1  # user-triggered retry starts a new attempt chain


def test_mark_completed(db_session: Session) -> None:
    _make_user(db_session)
    run_id = jobs_svc.start_run(
        db_session, user_id="u_1", job_type=JobType.MB_BRIEFING, schedule_id="s1"
    )
    jobs_svc.mark_completed(db_session, run_id, result_summary='{"report_id": "r_1"}')
    db_session.commit()
    row = db_session.get(JobRun, run_id)
    assert row.status == JobStatus.COMPLETED.value
    assert row.completed_at is not None
    assert row.result_summary == '{"report_id": "r_1"}'


def test_mark_failed(db_session: Session) -> None:
    _make_user(db_session)
    run_id = jobs_svc.start_run(
        db_session, user_id="u_1", job_type=JobType.EU_SCAN, schedule_id="s1"
    )
    jobs_svc.mark_failed(db_session, run_id, error_message="ContextLengthError: 8192")
    db_session.commit()
    row = db_session.get(JobRun, run_id)
    assert row.status == JobStatus.FAILED.value
    assert row.error_message == "ContextLengthError: 8192"
    assert row.completed_at is not None


def test_mark_cancelled(db_session: Session) -> None:
    _make_user(db_session)
    run_id = jobs_svc.start_run(
        db_session, user_id="u_1", job_type=JobType.MR_ASSESSMENT, schedule_id="s1"
    )
    jobs_svc.mark_cancelled(db_session, run_id, error_message="Server restarted during execution")
    db_session.commit()
    row = db_session.get(JobRun, run_id)
    assert row.status == JobStatus.CANCELLED.value
    assert row.error_message == "Server restarted during execution"


def test_bump_attempt_stays_running_and_records_error(db_session: Session) -> None:
    _make_user(db_session)
    run_id = jobs_svc.start_run(
        db_session, user_id="u_1", job_type=JobType.MB_BRIEFING, schedule_id="s1"
    )
    jobs_svc.bump_attempt(db_session, run_id, error_message="transient timeout")
    db_session.commit()
    row = db_session.get(JobRun, run_id)
    assert row.status == JobStatus.RUNNING.value
    assert row.attempt == 2
    assert row.error_message == "transient timeout"


def test_list_orphans_returns_running_ids_only(db_session: Session) -> None:
    _make_user(db_session)
    r1 = jobs_svc.start_run(
        db_session, user_id="u_1", job_type=JobType.MB_BRIEFING, schedule_id="s1"
    )
    r2 = jobs_svc.start_run(db_session, user_id="u_1", job_type=JobType.EU_SCAN, schedule_id="s2")
    jobs_svc.mark_completed(db_session, r1)
    db_session.commit()
    assert jobs_svc.list_orphans(db_session) == [r2]


def test_most_recent_for_schedule(db_session: Session) -> None:
    _make_user(db_session)
    older = jobs_svc.start_run(
        db_session, user_id="u_1", job_type=JobType.MB_BRIEFING, schedule_id="s1"
    )
    jobs_svc.mark_completed(db_session, older)
    db_session.commit()

    newer = jobs_svc.start_run(
        db_session, user_id="u_1", job_type=JobType.MB_BRIEFING, schedule_id="s1"
    )
    jobs_svc.mark_completed(db_session, newer)
    db_session.commit()

    row = jobs_svc.most_recent_for_schedule(db_session, "s1")
    assert row is not None
    assert row.id == newer


def test_list_for_user_filters_by_type_and_pagination(db_session: Session) -> None:
    _make_user(db_session)
    ids: list[str] = []
    for _ in range(5):
        ids.append(
            jobs_svc.start_run(
                db_session,
                user_id="u_1",
                job_type=JobType.MB_BRIEFING,
                schedule_id="s1",
            )
        )
    jobs_svc.start_run(db_session, user_id="u_1", job_type=JobType.EU_SCAN, schedule_id="s2")
    db_session.commit()

    mb = jobs_svc.list_for_user(
        db_session, user_id="u_1", job_type=JobType.MB_BRIEFING, limit=3, offset=0
    )
    assert len(mb) == 3
    mb_page2 = jobs_svc.list_for_user(
        db_session, user_id="u_1", job_type=JobType.MB_BRIEFING, limit=3, offset=3
    )
    assert len(mb_page2) == 2
    mb_ids = {r.id for r in mb} | {r.id for r in mb_page2}
    assert mb_ids == set(ids)


def test_list_for_user_filters_by_status(db_session: Session) -> None:
    _make_user(db_session)
    r1 = jobs_svc.start_run(
        db_session, user_id="u_1", job_type=JobType.MB_BRIEFING, schedule_id="s1"
    )
    jobs_svc.mark_completed(db_session, r1)
    r2 = jobs_svc.start_run(
        db_session, user_id="u_1", job_type=JobType.MB_BRIEFING, schedule_id="s1"
    )
    jobs_svc.mark_failed(db_session, r2, error_message="nope")
    db_session.commit()

    failed = jobs_svc.list_for_user(db_session, user_id="u_1", status=JobStatus.FAILED)
    assert [r.id for r in failed] == [r2]


def test_list_for_user_since_filter(db_session: Session) -> None:
    _make_user(db_session)
    r1 = jobs_svc.start_run(
        db_session, user_id="u_1", job_type=JobType.MB_BRIEFING, schedule_id="s1"
    )
    db_session.commit()
    # Shift r1 into the past.
    row = db_session.get(JobRun, r1)
    row.started_at = datetime.now(UTC) - timedelta(days=5)
    db_session.commit()

    r2 = jobs_svc.start_run(
        db_session, user_id="u_1", job_type=JobType.MB_BRIEFING, schedule_id="s1"
    )
    db_session.commit()

    recent = jobs_svc.list_for_user(
        db_session,
        user_id="u_1",
        since=datetime.now(UTC) - timedelta(days=1),
    )
    assert [r.id for r in recent] == [r2]
