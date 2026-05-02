"""CRUD operations for ChatSession and ChatMessage, scoped to a single user."""

from __future__ import annotations

import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from openlia_server.db.models.content import ChatMessage, ChatSession


def create_session(db: Session, *, user_id: str, department: str, title: str) -> ChatSession:
    row = ChatSession(
        id=str(uuid.uuid4()),
        user_id=user_id,
        department=department,
        title=title,
        is_pinned=False,
        is_archived=False,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def list_sessions(
    db: Session,
    *,
    user_id: str,
    include_archived: bool = False,
    department: str | None = None,
    q: str | None = None,
) -> list[ChatSession]:
    last_activity = (
        select(ChatMessage.session_id, func.max(ChatMessage.created_at).label("last_at"))
        .group_by(ChatMessage.session_id)
        .subquery()
    )
    stmt = (
        select(ChatSession)
        .outerjoin(last_activity, ChatSession.id == last_activity.c.session_id)
        .where(ChatSession.user_id == user_id)
        .order_by(
            ChatSession.is_pinned.desc(),
            func.coalesce(last_activity.c.last_at, ChatSession.created_at).desc(),
        )
    )
    if not include_archived:
        stmt = stmt.where(ChatSession.is_archived.is_(False))
    if department is not None:
        stmt = stmt.where(ChatSession.department == department)
    if q is not None and q.strip():
        like = f"%{q.strip().lower()}%"
        stmt = stmt.where(func.lower(ChatSession.title).like(like))
    return list(db.execute(stmt).scalars())


def ensure_titled(
    db: Session, *, session_id: str, first_user_text: str, default_title: str = "New chat"
) -> None:
    """If the session still has the default title, replace it with the
    first 48 characters of the first user message.

    Idempotent — safe to call after every user message; it only mutates
    when ``title == default_title``.
    """
    row = db.get(ChatSession, session_id)
    if row is None:
        return
    if row.title != default_title:
        return
    text = (first_user_text or "").strip()
    if not text:
        return
    row.title = text[:48]
    db.commit()


def get_session(db: Session, *, session_id: str, user_id: str) -> ChatSession:
    row = db.get(ChatSession, session_id)
    if row is None:
        raise LookupError(f"session {session_id} not found")
    if row.user_id != user_id:
        raise PermissionError("session does not belong to this user")
    return row


def rename_session(db: Session, *, session_id: str, user_id: str, new_title: str) -> None:
    row = get_session(db, session_id=session_id, user_id=user_id)
    if not new_title.strip():
        raise ValueError("title cannot be empty")
    row.title = new_title.strip()[:200]
    db.commit()


def set_pinned(db: Session, *, session_id: str, user_id: str, pinned: bool) -> None:
    row = get_session(db, session_id=session_id, user_id=user_id)
    row.is_pinned = pinned
    db.commit()


def archive_session(db: Session, *, session_id: str, user_id: str) -> None:
    row = get_session(db, session_id=session_id, user_id=user_id)
    row.is_archived = True
    db.commit()


def unarchive_session(db: Session, *, session_id: str, user_id: str) -> None:
    row = get_session(db, session_id=session_id, user_id=user_id)
    row.is_archived = False
    db.commit()


def delete_session(db: Session, *, session_id: str, user_id: str) -> None:
    row = get_session(db, session_id=session_id, user_id=user_id)
    db.delete(row)
    db.commit()


def get_or_create_default_session(db: Session, *, user_id: str, department: str) -> ChatSession:
    """Return the per-user default session for a department, creating one if
    none exists.

    Picks the oldest non-archived session as the stable identity so repeated
    calls return the same row, then `ensure_titled` can rename it on the
    first user message just like any other freshly created session.
    """
    stmt = (
        select(ChatSession)
        .where(
            ChatSession.user_id == user_id,
            ChatSession.department == department,
            ChatSession.is_archived.is_(False),
        )
        .order_by(ChatSession.created_at.asc(), ChatSession.id.asc())
        .limit(1)
    )
    existing = db.execute(stmt).scalar_one_or_none()
    if existing is not None:
        return existing
    return create_session(db, user_id=user_id, department=department, title="New chat")


def list_messages(db: Session, *, session_id: str, user_id: str) -> list[ChatMessage]:
    get_session(db, session_id=session_id, user_id=user_id)  # authz
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
    )
    return list(db.execute(stmt).scalars())
