"""Session lifecycle helpers."""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.models.auth import Session as SessionRow, User
from openlia_server.services.auth import tokens

PERSISTENT_TTL = timedelta(days=30)
NON_PERSISTENT_TTL = timedelta(hours=12)
LAST_SEEN_DEBOUNCE = timedelta(seconds=60)
INACTIVITY_CAP = timedelta(days=30)


@dataclass
class CreatedSession:
    raw_token: str
    session: SessionRow


@dataclass
class ValidatedSession:
    session: SessionRow
    user: User


def create_session(
    db: DBSession,
    *,
    user_id: str,
    persistent: bool,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> CreatedSession:
    now = datetime.now(timezone.utc)
    raw = tokens.generate_opaque_token()
    ttl = PERSISTENT_TTL if persistent else NON_PERSISTENT_TTL
    row = SessionRow(
        id=str(uuid.uuid4()),
        user_id=user_id,
        token_hash=tokens.hash_token(raw),
        created_at=now,
        last_seen_at=now,
        expires_at=now + ttl,
        user_agent=(user_agent or "")[:512] or None,
        ip_address=ip_address,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return CreatedSession(raw_token=raw, session=row)


def validate_session(db: DBSession, raw_token: str) -> ValidatedSession | None:
    if not raw_token:
        return None
    hashed = tokens.hash_token(raw_token)
    stmt = select(SessionRow, User).join(User, User.id == SessionRow.user_id).where(
        SessionRow.token_hash == hashed
    )
    row = db.execute(stmt).first()
    if row is None:
        return None

    session, user = row
    now = datetime.now(timezone.utc)
    if session.revoked_at is not None:
        return None
    if session.expires_at <= now:
        return None
    if session.last_seen_at < now - INACTIVITY_CAP:
        return None
    if user.is_disabled:
        return None

    if session.last_seen_at < now - LAST_SEEN_DEBOUNCE:
        session.last_seen_at = now
        db.commit()

    return ValidatedSession(session=session, user=user)


def revoke_session(db: DBSession, session_id: str) -> None:
    db.execute(
        update(SessionRow)
        .where(SessionRow.id == session_id, SessionRow.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )
    db.commit()


def revoke_all_sessions(db: DBSession, *, user_id: str) -> None:
    db.execute(
        update(SessionRow)
        .where(SessionRow.user_id == user_id, SessionRow.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )
    db.commit()


def prune_expired(db: DBSession, *, older_than_days: int = 7) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
    result = db.execute(delete(SessionRow).where(SessionRow.expires_at < cutoff))
    db.commit()
    return int(result.rowcount or 0)
