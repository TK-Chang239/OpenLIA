"""Invite-gated, email/password registration."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.models.auth import SignupInvite, User
from openlia_server.services.auth import passwords, signup_policy
from openlia_server.services.auth.errors import AuthError


class InviteRequiredError(AuthError):
    code = "invite_required"


class InviteInvalidError(AuthError):
    code = "invite_invalid"


class RegistrationFailedError(AuthError):
    code = "registration_failed"


def normalize_email(raw: str) -> str:
    return raw.strip().lower()


def register(
    db: DBSession,
    *,
    email: str,
    password: str,
    display_name: str,
    invite_token: str | None,
) -> User:
    signup_policy.assert_registration_open(db)

    if not invite_token:
        raise InviteRequiredError("An invite token is required to register.")

    invite = db.execute(
        select(SignupInvite).where(SignupInvite.token == invite_token)
    ).scalar_one_or_none()
    _validate_invite(invite)

    email_norm = normalize_email(email)
    signup_policy.check_email_allowed(db, email_norm)
    passwords.validate_password_policy(password)

    existing = db.execute(select(User).where(User.email == email_norm)).scalar_one_or_none()
    if existing is not None:
        raise RegistrationFailedError("Registration failed.")

    now = datetime.now(UTC)
    user = User(
        id=str(uuid.uuid4()),
        email=email_norm,
        display_name=display_name or email_norm.split("@", 1)[0],
        password_hash=passwords.hash_password(password),
        is_admin=False,
        is_disabled=False,
        must_change_password=False,
        failed_login_attempts=0,
        created_at=now,
        updated_at=now,
    )
    assert invite is not None
    invite.use_count = (invite.use_count or 0) + 1
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _validate_invite(invite: SignupInvite | None) -> None:
    if invite is None:
        raise InviteInvalidError("Invite is invalid.")
    now = datetime.now(UTC)
    if invite.revoked_at is not None:
        raise InviteInvalidError("Invite is invalid.")
    if invite.expires_at is not None and invite.expires_at <= now:
        raise InviteInvalidError("Invite is invalid.")
    if invite.max_uses is not None and (invite.use_count or 0) >= invite.max_uses:
        raise InviteInvalidError("Invite is invalid.")
