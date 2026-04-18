"""Login + lockout state machine."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.models.auth import User
from openlia_server.db.models.infrastructure import ConfigStore
from openlia_server.services.auth import events, passwords, registration
from openlia_server.services.auth.errors import AuthError

LOCKOUT_THRESHOLD = 5
LOCKOUT_DURATION = timedelta(minutes=15)
LOCKOUT_CONFIG_KEY = "auth.lockout.enabled"


class InvalidCredentialsError(AuthError):
    code = "invalid_credentials"


class AccountDisabledError(AuthError):
    code = "account_disabled"


class AccountLockedError(AuthError):
    code = "account_locked"

    def __init__(self, retry_after_seconds: int):
        super().__init__("Account is temporarily locked.")
        self.retry_after_seconds = retry_after_seconds


@dataclass
class AuthenticatedUser:
    user: User
    must_change_password: bool


def authenticate(
    db: DBSession,
    *,
    email: str,
    password: str,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuthenticatedUser:
    email_norm = registration.normalize_email(email)
    user = db.execute(select(User).where(User.email == email_norm)).scalar_one_or_none()

    if user is None or user.password_hash is None:
        passwords.dummy_verify()
        events.log_auth_event(
            db,
            event_type="login_failure",
            ip_address=ip_address,
            user_agent=user_agent,
            metadata={"reason": "unknown_email"},
        )
        raise InvalidCredentialsError("Email or password is incorrect.")

    if user.is_disabled:
        events.log_auth_event(
            db,
            event_type="login_failure",
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata={"reason": "disabled"},
        )
        raise AccountDisabledError("Account is disabled. Contact your administrator.")

    lockout_enabled = _lockout_enabled(db)
    now = datetime.now(UTC)
    if lockout_enabled and user.locked_until is not None and user.locked_until > now:
        retry = int((user.locked_until - datetime.now(UTC)).total_seconds())
        events.log_auth_event(
            db,
            event_type="login_failure",
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata={"reason": "locked", "retry_after_seconds": retry},
        )
        raise AccountLockedError(retry_after_seconds=retry)

    if not passwords.verify_password(user.password_hash, password):
        if lockout_enabled:
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
            if user.failed_login_attempts >= LOCKOUT_THRESHOLD:
                user.locked_until = datetime.now(UTC) + LOCKOUT_DURATION
                events.log_auth_event(
                    db,
                    event_type="account_locked",
                    user_id=user.id,
                    ip_address=ip_address,
                    user_agent=user_agent,
                )
        db.commit()
        events.log_auth_event(
            db,
            event_type="login_failure",
            user_id=user.id,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata={"reason": "wrong_password"},
        )
        raise InvalidCredentialsError("Email or password is incorrect.")

    user.failed_login_attempts = 0
    user.locked_until = None
    user.last_login_at = datetime.now(UTC)
    db.commit()

    events.log_auth_event(
        db,
        event_type="login_success",
        user_id=user.id,
        actor_user_id=user.id,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    return AuthenticatedUser(user=user, must_change_password=bool(user.must_change_password))


def _lockout_enabled(db: DBSession) -> bool:
    row = db.execute(
        select(ConfigStore).where(ConfigStore.key == LOCKOUT_CONFIG_KEY)
    ).scalar_one_or_none()
    if row is None:
        return True
    value = row.value or {}
    return bool(value.get("enabled", True))
