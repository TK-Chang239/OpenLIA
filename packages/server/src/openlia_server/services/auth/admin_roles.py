"""Admin-role (is_admin) promotion/demotion with a last-admin safeguard.

Registration always creates non-admin users and the setup wizard only ever
mints the very first admin, so without this helper an instance has no in-app
way to grant or revoke admin. Demotion is guarded so the last active admin can
never strip their own (or anyone's) admin flag and lock everyone out.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.models.auth import User
from openlia_server.services.auth.errors import AuthError


class UserNotFoundError(AuthError):
    code = "user_not_found"


class LastAdminError(AuthError):
    code = "last_admin"


def count_active_admins(db: DBSession) -> int:
    """Number of enabled admins currently able to sign in and administer."""
    return int(
        db.execute(
            select(func.count())
            .select_from(User)
            .where(User.is_admin.is_(True), User.is_disabled.is_(False))
        ).scalar_one()
    )


def set_admin_flag(db: DBSession, *, user_id: str, is_admin: bool) -> User:
    """Grant or revoke a user's admin flag.

    Refuses to demote the last active admin, which would leave the instance
    with no administrator and only CLI recovery.
    """
    user = db.get(User, user_id)
    if user is None:
        raise UserNotFoundError("User not found.")

    if user.is_admin and not is_admin and not user.is_disabled and count_active_admins(db) <= 1:
        raise LastAdminError("Cannot demote the last remaining admin.")

    user.is_admin = is_admin
    user.updated_at = datetime.now(UTC)
    db.flush()
    return user
