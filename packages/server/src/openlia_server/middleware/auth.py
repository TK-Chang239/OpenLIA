"""Session-cookie dependency.

`build_require_auth(...)` is a factory returning the FastAPI dependency to
attach to protected routes. In personal mode the dependency short-circuits to
the synthetic `local` user without touching the `sessions` table.
"""
from __future__ import annotations

from typing import Callable, Literal

from fastapi import Cookie, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.models.auth import User
from openlia_server.services.auth import sessions as session_service

COOKIE_NAME = "openlia_session"
LOCAL_USER_ID = "local"


def build_require_auth(
    *,
    db_session_factory: Callable[[], DBSession],
    mode: Literal["personal", "company"],
):
    """Return a FastAPI dependency enforcing auth for the given deployment mode."""

    def require_auth(
        openlia_session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ) -> User:
        db = db_session_factory()
        if mode == "personal":
            user = db.execute(select(User).where(User.id == LOCAL_USER_ID)).scalar_one_or_none()
            if user is None:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="local user not seeded; bootstrap did not run",
                )
            return user

        if not openlia_session:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated")
        validated = session_service.validate_session(db, openlia_session)
        if validated is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="not authenticated")
        return validated.user

    return Depends(require_auth)


def build_require_admin(
    *,
    db_session_factory: Callable[[], DBSession],
    mode: Literal["personal", "company"],
):
    """Dependency requiring `is_admin = true` on the resolved user."""

    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)

    def require_admin(user: User = require_auth) -> User:  # type: ignore[assignment]
        if not user.is_admin:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="admin only")
        return user

    return Depends(require_admin)
