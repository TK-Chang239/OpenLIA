from __future__ import annotations

from datetime import UTC, datetime, timedelta

from openlia_server.db.models.auth import User
from openlia_server.db.models.scheduler import UserNotification
from openlia_server.scheduler.registry import NotificationType
from openlia_server.scheduler.services import notifications as notif_svc
from sqlalchemy.orm import Session


def _make_user(session: Session, uid: str = "u_1") -> None:
    u = User(
        id=uid,
        email=f"{uid}@e.com",
        display_name=f"user-{uid}",
        password_hash="h",
        is_admin=False,
        is_disabled=False,
    )
    session.add(u)
    session.commit()


def test_insert_notification(db_session: Session) -> None:
    _make_user(db_session)
    notif_id = notif_svc.insert(
        db_session,
        user_id="u_1",
        type=NotificationType.REPORT_READY,
        department="morning_briefing",
        message="Your 7:00 AM briefing is ready.",
        job_run_id=None,
    )
    db_session.commit()
    row = db_session.get(UserNotification, notif_id)
    assert row is not None
    assert row.type == "report_ready"
    assert row.department == "morning_briefing"
    assert row.read_at is None


def test_unread_counts_by_department(db_session: Session) -> None:
    _make_user(db_session)
    notif_svc.insert(
        db_session,
        user_id="u_1",
        type=NotificationType.REPORT_READY,
        department="morning_briefing",
        message="a",
        job_run_id=None,
    )
    notif_svc.insert(
        db_session,
        user_id="u_1",
        type=NotificationType.REPORT_READY,
        department="morning_briefing",
        message="b",
        job_run_id=None,
    )
    notif_svc.insert(
        db_session,
        user_id="u_1",
        type=NotificationType.REPORT_READY,
        department="earnings_update",
        message="c",
        job_run_id=None,
    )
    db_session.commit()
    counts = notif_svc.unread_counts_by_department(db_session, user_id="u_1")
    assert counts == {"morning_briefing": 2, "earnings_update": 1}
    assert notif_svc.unread_total(db_session, user_id="u_1") == 3


def test_mark_read_only_affects_unread_rows_for_department(
    db_session: Session,
) -> None:
    _make_user(db_session)
    n1 = notif_svc.insert(
        db_session,
        user_id="u_1",
        type=NotificationType.REPORT_READY,
        department="morning_briefing",
        message="a",
        job_run_id=None,
    )
    n2 = notif_svc.insert(
        db_session,
        user_id="u_1",
        type=NotificationType.REPORT_READY,
        department="earnings_update",
        message="b",
        job_run_id=None,
    )
    db_session.commit()
    affected = notif_svc.mark_department_read(
        db_session, user_id="u_1", department="morning_briefing"
    )
    db_session.commit()
    assert affected == 1
    assert db_session.get(UserNotification, n1).read_at is not None
    assert db_session.get(UserNotification, n2).read_at is None


def test_mark_department_read_skips_already_read(db_session: Session) -> None:
    _make_user(db_session)
    notif_svc.insert(
        db_session,
        user_id="u_1",
        type=NotificationType.REPORT_READY,
        department="morning_briefing",
        message="a",
        job_run_id=None,
    )
    db_session.commit()
    first = notif_svc.mark_department_read(db_session, user_id="u_1", department="morning_briefing")
    db_session.commit()
    second = notif_svc.mark_department_read(
        db_session, user_id="u_1", department="morning_briefing"
    )
    db_session.commit()
    assert first == 1
    assert second == 0


def test_prune_older_than(db_session: Session) -> None:
    _make_user(db_session)
    old_id = notif_svc.insert(
        db_session,
        user_id="u_1",
        type=NotificationType.REPORT_READY,
        department="morning_briefing",
        message="old",
        job_run_id=None,
    )
    db_session.commit()
    old_row = db_session.get(UserNotification, old_id)
    old_row.created_at = datetime.now(UTC) - timedelta(days=45)
    db_session.commit()
    notif_svc.insert(
        db_session,
        user_id="u_1",
        type=NotificationType.REPORT_READY,
        department="morning_briefing",
        message="fresh",
        job_run_id=None,
    )
    db_session.commit()
    removed = notif_svc.prune_older_than(db_session, cutoff=datetime.now(UTC) - timedelta(days=30))
    db_session.commit()
    assert removed == 1
    assert db_session.get(UserNotification, old_id) is None
