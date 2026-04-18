"""Auth-service error hierarchy."""

from __future__ import annotations


class AuthError(Exception):
    """Base class for all services.auth errors."""

    code: str = "auth_error"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code
