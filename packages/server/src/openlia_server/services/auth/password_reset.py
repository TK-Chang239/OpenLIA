"""Admin-approved password reset + direct admin reset + self-serve change."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.models.auth import PasswordResetRequest, User
from openlia_server.services.auth import events, passwords, registration, sessions, tokens
from openlia_server.services.auth.errors import AuthError

APPROVED_TTL = timedelta(hours=24)


class TokenInvalidError(AuthError):
    code = "token_invalid"


class TokenExpiredError(AuthError):
    code = "token_expired"


def request_reset(db: DBSession, *, email: str, ip_address: str | None = None) -> None:
    """Create a pending reset request. Silent no-op if the email is unknown."""
    email_norm = registration.normalize_email(email)
    user = db.execute(select(User).where(User.email == email_norm)).scalar_one_or_none()
    if user is None or user.is_disabled:
        return

    db.execute(
        delete(PasswordResetRequest).where(
            PasswordResetRequest.user_id == user.id,
            PasswordResetRequest.status == "pending",
        )
    )
    db.add(
        PasswordResetRequest(
            id=str(uuid.uuid4()),
            user_id=user.id,
            status="pending",
            requested_at=datetime.now(UTC),
            requested_ip=ip_address,
        )
    )
    db.commit()
    events.log_auth_event(
        db,
        event_type="password_reset_requested",
        user_id=user.id,
        ip_address=ip_address,
    )


def approve_request(db: DBSession, *, request_id: str, admin_user_id: str) -> str:
    """Generate a one-time token. Returns the raw token."""
    req = db.get(PasswordResetRequest, request_id)
    if req is None or req.status != "pending":
        raise TokenInvalidError("Request not found or not pending.")

    raw = tokens.generate_opaque_token()
    req.token_hash = tokens.hash_token(raw)
    req.expires_at = datetime.now(UTC) + APPROVED_TTL
    req.status = "approved"
    req.approved_by_user_id = admin_user_id
    req.approved_at = datetime.now(UTC)
    db.commit()

    events.log_auth_event(
        db,
        event_type="password_reset_approved",
        user_id=req.user_id,
        actor_user_id=admin_user_id,
    )
    return raw


def reject_request(db: DBSession, *, request_id: str, admin_user_id: str) -> None:
    req = db.get(PasswordResetRequest, request_id)
    if req is None or req.status != "pending":
        raise TokenInvalidError("Request not found or not pending.")
    req.status = "rejected"
    db.commit()
    events.log_auth_event(
        db,
        event_type="password_reset_rejected",
        user_id=req.user_id,
        actor_user_id=admin_user_id,
    )


def consume_token(db: DBSession, *, token: str, new_password: str) -> None:
    passwords.validate_password_policy(new_password)
    hashed = tokens.hash_token(token)
    req = db.execute(
        select(PasswordResetRequest).where(PasswordResetRequest.token_hash == hashed)
    ).scalar_one_or_none()
    if req is None or req.status != "approved":
        raise TokenInvalidError("Reset token is invalid.")

    now = datetime.now(UTC)
    if req.expires_at is None or req.expires_at <= now:
        req.status = "expired"
        db.commit()
        raise TokenExpiredError("Reset token has expired.")

    user = db.get(User, req.user_id)
    assert user is not None

    user.password_hash = passwords.hash_password(new_password)
    user.must_change_password = False
    user.failed_login_attempts = 0
    user.locked_until = None
    user.updated_at = now

    req.status = "consumed"
    req.consumed_at = now

    db.commit()
    sessions.revoke_all_sessions(db, user_id=user.id)

    events.log_auth_event(
        db,
        event_type="password_reset_consumed",
        user_id=user.id,
        actor_user_id=user.id,
    )


def admin_direct_reset(
    db: DBSession,
    *,
    user_id: str,
    new_password: str,
    admin_user_id: str | None,
    metadata: dict[str, object] | None = None,
) -> None:
    passwords.validate_password_policy(new_password)
    user = db.get(User, user_id)
    if user is None:
        raise TokenInvalidError("User not found.")

    user.password_hash = passwords.hash_password(new_password)
    user.must_change_password = True
    user.updated_at = datetime.now(UTC)
    db.commit()
    sessions.revoke_all_sessions(db, user_id=user.id)

    events.log_auth_event(
        db,
        event_type="password_reset_by_admin",
        user_id=user.id,
        actor_user_id=admin_user_id,
        metadata=metadata,
    )


def change_password(
    db: DBSession, *, user_id: str, current_password: str, new_password: str
) -> None:
    passwords.validate_password_policy(new_password)
    user = db.get(User, user_id)
    if user is None or not passwords.verify_password(user.password_hash, current_password):
        raise AuthError("Current password is incorrect.", code="invalid_credentials")

    user.password_hash = passwords.hash_password(new_password)
    user.must_change_password = False
    user.updated_at = datetime.now(UTC)
    db.commit()
    events.log_auth_event(db, event_type="password_changed", user_id=user.id, actor_user_id=user.id)
