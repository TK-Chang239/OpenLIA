"""CRUD for the `user_notifications` table. Polling-based mechanism:
insert on job completion/failure, read via unread_counts, clear via
mark_department_read."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from openlia_server.db.models.config import UserPrefs
from openlia_server.db.models.scheduler import UserNotification
from openlia_server.scheduler.registry import NotificationType


def _now() -> datetime:
    return datetime.now(UTC)


def _inapp_enabled(session: Session, user_id: str) -> bool:
    enabled = session.execute(
        select(UserPrefs.notify_inapp).where(UserPrefs.user_id == user_id)
    ).scalar_one_or_none()
    # No prefs row yet = the column's default (on).
    return enabled is None or bool(enabled)


def insert(
    session: Session,
    *,
    user_id: str,
    type: NotificationType,
    department: str,
    message: str,
    job_run_id: str | None,
) -> str | None:
    """Insert a notification row, or return None when the user has in-app
    notifications turned off (Settings > General)."""
    if not _inapp_enabled(session, user_id):
        return None
    notif_id = uuid.uuid4().hex
    row = UserNotification(
        id=notif_id,
        user_id=user_id,
        type=type.value,
        department=department,
        message=message,
        job_run_id=job_run_id,
        created_at=_now(),
        read_at=None,
    )
    session.add(row)
    return notif_id


def unread_total(session: Session, *, user_id: str) -> int:
    stmt = (
        select(func.count())
        .select_from(UserNotification)
        .where(
            UserNotification.user_id == user_id,
            UserNotification.read_at.is_(None),
        )
    )
    return int(session.execute(stmt).scalar_one())


def unread_counts_by_department(session: Session, *, user_id: str) -> dict[str, int]:
    stmt = (
        select(UserNotification.department, func.count())
        .where(
            UserNotification.user_id == user_id,
            UserNotification.read_at.is_(None),
        )
        .group_by(UserNotification.department)
    )
    return {dept: int(count) for dept, count in session.execute(stmt).all()}


def mark_department_read(session: Session, *, user_id: str, department: str) -> int:
    stmt = (
        update(UserNotification)
        .where(
            UserNotification.user_id == user_id,
            UserNotification.department == department,
            UserNotification.read_at.is_(None),
        )
        .values(read_at=_now())
        .execution_options(synchronize_session="fetch")
    )
    result = session.execute(stmt)
    return int(result.rowcount or 0)


def prune_older_than(session: Session, *, cutoff: datetime) -> int:
    stmt = delete(UserNotification).where(UserNotification.created_at < cutoff)
    return int(session.execute(stmt).rowcount or 0)
