"""Verifies the 4 scheduler + notification tables:
  mb_schedules, eu_schedules, job_runs, user_notifications.

Declared in database-design.md § 7 and background-task-scheduling-design.md.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session


@pytest.fixture
def create_tables(engine):
    import openlia_server.db.models.auth
    import openlia_server.db.models.scheduler  # noqa: F401 — register models
    from openlia_server.db.base import Base

    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


def _make_user(db_session: Session, user_id: str = "u1") -> None:
    from openlia_server.db.models.auth import User

    db_session.add(User(id=user_id, email=f"{user_id}@example.com", display_name=user_id))
    db_session.commit()


# ---------- mb_schedules ----------


def test_mb_schedules_columns(create_tables) -> None:
    from openlia_server.db.models.scheduler import MbSchedule

    cols = {c.name: c for c in MbSchedule.__table__.columns}
    expected = {
        "id",
        "user_id",
        "time",
        "timezone",
        "days_of_week",
        "label",
        "is_enabled",
        "created_at",
        "last_run_at",
    }
    assert set(cols.keys()) == expected
    assert cols["is_enabled"].default.arg is True


def test_mb_schedules_cascade_on_user_delete(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.auth import User
    from openlia_server.db.models.scheduler import MbSchedule

    _make_user(db_session)
    db_session.add(
        MbSchedule(
            id="s1",
            user_id="u1",
            time="07:30",
            timezone="America/New_York",
            days_of_week='["Mon","Tue"]',
        )
    )
    db_session.commit()

    db_session.delete(db_session.get(User, "u1"))
    db_session.commit()

    assert db_session.execute(select(MbSchedule)).scalar_one_or_none() is None


# ---------- eu_schedules ----------


def test_eu_schedules_columns(create_tables) -> None:
    from openlia_server.db.models.scheduler import EuSchedule

    cols = {c.name: c for c in EuSchedule.__table__.columns}
    expected = {
        "id",
        "user_id",
        "time",
        "timezone",
        "days_of_week",
        "label",
        "is_enabled",
        "created_at",
        "last_run_at",
    }
    assert set(cols.keys()) == expected


def test_eu_schedules_cascade_on_user_delete(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.auth import User
    from openlia_server.db.models.scheduler import EuSchedule

    _make_user(db_session)
    db_session.add(
        EuSchedule(
            id="s1",
            user_id="u1",
            time="09:00",
            timezone="America/New_York",
            days_of_week='["Mon"]',
        )
    )
    db_session.commit()

    db_session.delete(db_session.get(User, "u1"))
    db_session.commit()

    assert db_session.execute(select(EuSchedule)).scalar_one_or_none() is None


# ---------- job_runs ----------


def test_job_runs_columns(create_tables) -> None:
    from openlia_server.db.models.scheduler import JobRun

    cols = {c.name: c for c in JobRun.__table__.columns}
    expected = {
        "id",
        "user_id",
        "job_type",
        "schedule_id",
        "status",
        "started_at",
        "completed_at",
        "error_message",
        "result_summary",
        "retry_of",
        "attempt",
    }
    assert set(cols.keys()) == expected
    assert cols["user_id"].nullable is True  # NULL for system_maintenance
    assert cols["attempt"].default.arg == 1


def test_job_runs_user_id_cascade_on_user_delete(create_tables, db_session: Session) -> None:
    """Per the spec, user-scoped job_runs cascade on user deletion. System
    maintenance rows (user_id NULL) are unaffected."""
    from openlia_server.db.models.auth import User
    from openlia_server.db.models.scheduler import JobRun

    _make_user(db_session)
    now = datetime.now(UTC)
    db_session.add(
        JobRun(
            id="j1",
            user_id="u1",
            job_type="mb_briefing",
            status="completed",
            started_at=now,
        )
    )
    db_session.add(
        JobRun(
            id="j2",
            user_id=None,
            job_type="system_maintenance",
            status="completed",
            started_at=now,
        )
    )
    db_session.commit()

    db_session.delete(db_session.get(User, "u1"))
    db_session.commit()

    rows = db_session.execute(select(JobRun)).scalars().all()
    assert {r.id for r in rows} == {"j2"}


def test_job_runs_retry_of_self_reference(create_tables, db_session: Session) -> None:
    """retry_of is a self-FK into job_runs.id with ondelete=SET NULL."""
    from openlia_server.db.models.scheduler import JobRun

    now = datetime.now(UTC)
    original = JobRun(
        id="orig",
        user_id=None,
        job_type="system_maintenance",
        status="failed",
        started_at=now,
    )
    retry = JobRun(
        id="retry",
        user_id=None,
        job_type="system_maintenance",
        status="completed",
        started_at=now,
        retry_of="orig",
        attempt=2,
    )
    db_session.add_all([original, retry])
    db_session.commit()

    db_session.delete(original)
    db_session.commit()

    db_session.expire_all()
    fresh = db_session.get(JobRun, "retry")
    assert fresh is not None
    assert fresh.retry_of is None


# ---------- user_notifications ----------


def test_user_notifications_columns(create_tables) -> None:
    from openlia_server.db.models.scheduler import UserNotification

    cols = {c.name: c for c in UserNotification.__table__.columns}
    expected = {
        "id",
        "user_id",
        "type",
        "department",
        "message",
        "job_run_id",
        "created_at",
        "read_at",
    }
    assert set(cols.keys()) == expected


def test_user_notifications_cascade_on_user_delete(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.auth import User
    from openlia_server.db.models.scheduler import UserNotification

    _make_user(db_session)
    db_session.add(
        UserNotification(
            id="n1",
            user_id="u1",
            type="report_ready",
            department="morning_briefing",
            message="Your briefing is ready",
        )
    )
    db_session.commit()

    db_session.delete(db_session.get(User, "u1"))
    db_session.commit()

    assert db_session.execute(select(UserNotification)).scalar_one_or_none() is None


def test_user_notifications_job_run_set_null_on_job_delete(
    create_tables, db_session: Session
) -> None:
    from openlia_server.db.models.scheduler import JobRun, UserNotification

    _make_user(db_session)
    now = datetime.now(UTC)
    job = JobRun(
        id="j1",
        user_id="u1",
        job_type="mb_briefing",
        status="completed",
        started_at=now,
    )
    notif = UserNotification(
        id="n1",
        user_id="u1",
        type="report_ready",
        department="morning_briefing",
        message="ok",
        job_run_id="j1",
    )
    db_session.add_all([job, notif])
    db_session.commit()

    db_session.delete(job)
    db_session.commit()

    db_session.expire_all()
    fresh = db_session.get(UserNotification, "n1")
    assert fresh.job_run_id is None
