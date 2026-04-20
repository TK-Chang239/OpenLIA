"""Auth dependencies for FastAPI route injection.

In personal mode there is no real auth — `get_current_user` is a
placeholder that routes override in tests and that will be replaced when
company-mode auth is wired up to FastAPI's dependency system."""

from __future__ import annotations

from fastapi import HTTPException

from openlia_server.db.models.auth import User


def get_current_user() -> User:
    """Dependency: return the authenticated user.

    This default implementation always raises 401. Route tests override it
    via ``app.dependency_overrides[get_current_user]``. The company-mode
    auth middleware (or a future JWT/cookie dependency) will replace this
    with a real implementation."""
    raise HTTPException(status_code=401, detail="Not authenticated")
