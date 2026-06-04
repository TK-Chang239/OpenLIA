from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from _scheduler_fakes import FakeSleep
from openlia_server.db.models.auth import PasswordResetRequest, User
from openlia_server.db.models.auth import Session as AuthSession
from openlia_server.db.models.scheduler import JobRun, UserNotification
from openlia_server.scheduler.executors.maintenance import (
    MaintenanceExecutor,
    run_maintenance_once,
)
from openlia_server.scheduler.registry import JobStatus, JobType
from sqlalchemy.orm import Session


def _seed(session: Session) -> dict[str, list[str]]:
    now = datetime.now(UTC)

    user = User(
        id="u_1",
        email="u@e.com",
        display_name="u",
        password_hash="h",
        is_admin=False,
        is_disabled=False,
    )
    session.add(user)
    session.flush()

    s_old = AuthSession(
        id="s_old",
        user_id="u_1",
        token_hash="h_old",
        created_at=now - timedelta(days=9),
        last_seen_at=now - timedelta(days=9),
        expires_at=now - timedelta(days=8),
    )
    s_new = AuthSession(
        id="s_new",
        user_id="u_1",
        token_hash="h_new",
        created_at=now,
        last_seen_at=now,
        expires_at=now + timedelta(days=1),
    )
    session.add_all([s_old, s_new])

    r_flip = PasswordResetRequest(
        id="r_flip",
        user_id="u_1",
        status="approved",
        requested_at=now - timedelta(days=2),
        expires_at=now - timedelta(hours=1),
    )
    r_old = PasswordResetRequest(
        id="r_old",
        user_id="u_1",
        status="consumed",
        requested_at=now - timedelta(days=100),
        expires_at=now - timedelta(days=99),
    )
    r_live = PasswordResetRequest(
        id="r_live",
        user_id="u_1",
        status="pending",
        requested_at=now,
        expires_at=now + timedelta(days=1),
    )
    session.add_all([r_flip, r_old, r_live])

    n_old = UserNotification(
        id="n_old",
        user_id="u_1",
        type="report_ready",
        department="morning_briefing",
        message="m",
        job_run_id=None,
        created_at=now - timedelta(days=40),
        read_at=None,
    )
    n_new = UserNotification(
        id="n_new",
        user_id="u_1",
        type="report_ready",
        department="morning_briefing",
        message="m",
        job_run_id=None,
        created_at=now - timedelta(days=1),
        read_at=None,
    )
    session.add_all([n_old, n_new])

    j_old_ok = JobRun(
        id="j_old_ok",
        user_id="u_1",
        job_type="mb_briefing",
        schedule_id="s",
        status=JobStatus.COMPLETED.value,
        started_at=now - timedelta(days=120),
        completed_at=now - timedelta(days=120),
        attempt=1,
    )
    j_old_cancel = JobRun(
        id="j_old_cancel",
        user_id="u_1",
        job_type="mb_briefing",
        schedule_id="s",
        status=JobStatus.CANCELLED.value,
        started_at=now - timedelta(days=95),
        completed_at=now - timedelta(days=95),
        attempt=1,
    )
    j_old_failed = JobRun(
        id="j_old_failed",
        user_id="u_1",
        job_type="mb_briefing",
        schedule_id="s",
        status=JobStatus.FAILED.value,
        started_at=now - timedelta(days=200),
        completed_at=now - timedelta(days=200),
        error_message="x",
        attempt=1,
    )
    j_new_ok = JobRun(
        id="j_new_ok",
        user_id="u_1",
        job_type="mb_briefing",
        schedule_id="s",
        status=JobStatus.COMPLETED.value,
        started_at=now - timedelta(days=2),
        completed_at=now - timedelta(days=2),
        attempt=1,
    )
    session.add_all([j_old_ok, j_old_cancel, j_old_failed, j_new_ok])

    session.commit()

    return {
        "sessions": ["s_new"],
        "password_reset_requests": ["r_flip", "r_live"],
        "user_notifications": ["n_new"],
        "job_runs": ["j_old_failed", "j_new_ok"],
    }


def test_run_maintenance_once_prunes_every_target(db_session: Session) -> None:
    expected = _seed(db_session)

    summary = run_maintenance_once(db_session)
    db_session.commit()

    assert summary["sessions_deleted"] == 1
    assert summary["password_resets_expired"] == 1
    assert summary["password_resets_deleted"] == 1
    assert summary["notifications_deleted"] == 1
    assert summary["job_runs_deleted"] == 2

    surviving_sessions = {s.id for s in db_session.query(AuthSession).all()}
    assert surviving_sessions == set(expected["sessions"])

    prrs = {r.id: r.status for r in db_session.query(PasswordResetRequest).all()}
    assert prrs == {"r_flip": "expired", "r_live": "pending"}

    notifs = {n.id for n in db_session.query(UserNotification).all()}
    assert notifs == set(expected["user_notifications"])

    runs = {j.id for j in db_session.query(JobRun).all()}
    assert runs == set(expected["job_runs"])


def _mk_report(
    db: Session,
    *,
    rid: str,
    user_id: str | None,
    created_at: datetime,
    title: str = "Stock Initiation",
) -> None:
    from openlia_server.db.models.content import Report

    row = Report(
        id=rid,
        user_id=user_id,
        department="equity_research",
        report_type="stock_initiation",
        title=title,
        subject="AAPL",
        content_markdown="# Body",
        content_structured={"cover": {"title": title}},
        model_ref="test-model",
        created_at=created_at,
        updated_at=created_at,
    )
    db.add(row)
    db.flush()


def _mk_repo_item(db: Session, *, report_id: str, user_id: str) -> None:
    from openlia_server.db.models.content import RepoItem

    db.add(RepoItem(id=f"ri-{report_id}", user_id=user_id, report_id=report_id))
    db.flush()


def _ensure_user(db: Session, *, uid: str = "u_1") -> None:
    if db.get(User, uid) is None:
        db.add(
            User(
                id=uid,
                email=f"{uid}@e.com",
                display_name=uid,
                password_hash="h",
                is_admin=False,
                is_disabled=False,
            )
        )
        db.flush()


def test_sweep_tombstones_old_unsaved_owned_report(db_session: Session) -> None:
    from openlia_server.db.models.content import Report

    _ensure_user(db_session)
    now = datetime.now(UTC)
    _mk_report(db_session, rid="r_old", user_id="u_1", created_at=now - timedelta(days=8))
    _mk_report(db_session, rid="r_new", user_id="u_1", created_at=now - timedelta(days=1))
    db_session.commit()

    summary = run_maintenance_once(db_session)
    db_session.commit()

    assert summary["reports_tombstoned"] == 1
    assert summary["reports_hard_deleted"] == 0

    db_session.expire_all()
    r_old = db_session.get(Report, "r_old")
    assert r_old is not None
    assert r_old.expired_at is not None
    assert r_old.content_markdown == ""
    assert r_old.content_structured == {}

    r_new = db_session.get(Report, "r_new")
    assert r_new is not None
    assert r_new.expired_at is None
    assert r_new.content_markdown == "# Body"


def test_sweep_skips_old_saved_report(db_session: Session) -> None:
    from openlia_server.db.models.content import Report

    _ensure_user(db_session)
    now = datetime.now(UTC)
    _mk_report(db_session, rid="r_saved", user_id="u_1", created_at=now - timedelta(days=30))
    _mk_repo_item(db_session, report_id="r_saved", user_id="u_1")
    db_session.commit()

    summary = run_maintenance_once(db_session)
    db_session.commit()

    assert summary["reports_tombstoned"] == 0
    db_session.expire_all()
    row = db_session.get(Report, "r_saved")
    assert row.expired_at is None
    assert row.content_markdown == "# Body"


def test_sweep_hard_deletes_orphan_reports(db_session: Session) -> None:
    from openlia_server.db.models.content import Report

    now = datetime.now(UTC)
    _mk_report(db_session, rid="r_orphan_old", user_id=None, created_at=now - timedelta(days=8))
    _mk_report(db_session, rid="r_orphan_new", user_id=None, created_at=now - timedelta(days=2))
    db_session.commit()

    summary = run_maintenance_once(db_session)
    db_session.commit()

    assert summary["reports_hard_deleted"] == 1
    assert summary["reports_tombstoned"] == 0

    db_session.expire_all()
    assert db_session.get(Report, "r_orphan_old") is None
    assert db_session.get(Report, "r_orphan_new") is not None


def test_sweep_is_idempotent(db_session: Session) -> None:
    _ensure_user(db_session)
    now = datetime.now(UTC)
    _mk_report(db_session, rid="r_old", user_id="u_1", created_at=now - timedelta(days=8))
    db_session.commit()

    summary_1 = run_maintenance_once(db_session)
    db_session.commit()
    summary_2 = run_maintenance_once(db_session)
    db_session.commit()

    assert summary_1["reports_tombstoned"] == 1
    assert summary_2["reports_tombstoned"] == 0


def test_sweep_respects_env_retention_override(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    from openlia_server.db.models.content import Report

    monkeypatch.setenv("OPENLIA_UNSAVED_REPORT_RETENTION_DAYS", "30")
    _ensure_user(db_session)
    now = datetime.now(UTC)
    _mk_report(db_session, rid="r_10d", user_id="u_1", created_at=now - timedelta(days=10))
    db_session.commit()

    summary = run_maintenance_once(db_session)
    db_session.commit()

    assert summary["reports_tombstoned"] == 0
    db_session.expire_all()
    assert db_session.get(Report, "r_10d").expired_at is None


def test_sweep_summary_contains_both_new_keys(db_session: Session) -> None:
    summary = run_maintenance_once(db_session)
    assert "reports_tombstoned" in summary
    assert "reports_hard_deleted" in summary


@pytest.mark.asyncio
async def test_maintenance_executor_writes_completed_job_run(session_factory) -> None:
    with session_factory() as s:
        _seed(s)

    ex = MaintenanceExecutor(session_factory=session_factory, sleep=FakeSleep())
    run_id = await ex.execute(user_id=None, schedule_id=None)

    with session_factory() as s:
        row = s.get(JobRun, run_id)
        assert row is not None
        assert row.status == JobStatus.COMPLETED.value
        assert row.job_type == JobType.SYSTEM_MAINTENANCE.value
        import json

        summary = json.loads(row.result_summary)
        assert summary["sessions_deleted"] == 1
        assert s.query(UserNotification).filter_by(job_run_id=run_id).count() == 0
