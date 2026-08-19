"""The in-app notifications toggle (user_prefs.notify_inapp) gates
notification creation at the shared insert helper."""

from __future__ import annotations

from openlia_server.db.models.config import UserPrefs
from openlia_server.db.models.scheduler import UserNotification
from openlia_server.scheduler.registry import NotificationType
from openlia_server.scheduler.services import notifications as notif_svc
from sqlalchemy import select


def _insert(session, user_id: str) -> str | None:
    return notif_svc.insert(
        session,
        user_id=user_id,
        type=NotificationType.JOB_FAILED,
        department="morning_briefing",
        message="boom",
        job_run_id=None,
    )


def _rows(session, user_id: str) -> list[UserNotification]:
    return list(
        session.execute(
            select(UserNotification).where(UserNotification.user_id == user_id)
        ).scalars()
    )


def test_insert_skipped_when_notify_inapp_disabled(db_session, make_user):
    user = make_user(email="off@example.com")
    db_session.add(UserPrefs(user_id=user.id, notify_inapp=False))
    db_session.commit()

    assert _insert(db_session, user.id) is None
    db_session.commit()
    assert _rows(db_session, user.id) == []


def test_insert_written_when_notify_inapp_enabled(db_session, make_user):
    user = make_user(email="on@example.com")
    db_session.add(UserPrefs(user_id=user.id, notify_inapp=True))
    db_session.commit()

    assert _insert(db_session, user.id) is not None
    db_session.commit()
    assert len(_rows(db_session, user.id)) == 1


def test_insert_written_without_prefs_row(db_session, make_user):
    """No prefs row yet = the column default (notifications on)."""
    user = make_user(email="fresh@example.com")

    assert _insert(db_session, user.id) is not None
    db_session.commit()
    assert len(_rows(db_session, user.id)) == 1
