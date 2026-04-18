"""Argon2id password hashing and policy enforcement."""
from __future__ import annotations

import os

from argon2 import PasswordHasher
from argon2.exceptions import VerificationError, VerifyMismatchError

from openlia_server.services.auth.errors import AuthError


class WeakPasswordError(AuthError):
    code = "weak_password"


_HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=64 * 1024,
    parallelism=4,
)

_DUMMY_HASH = _HASHER.hash("dummy-password-used-only-for-timing-pad")


def hash_password(plaintext: str) -> str:
    return _HASHER.hash(plaintext)


def verify_password(stored_hash: str | None, plaintext: str) -> bool:
    """Constant-time verify. Returns False for None / missing hash."""
    if not stored_hash:
        return False
    try:
        return _HASHER.verify(stored_hash, plaintext)
    except (VerifyMismatchError, VerificationError):
        return False


def dummy_verify() -> None:
    """Run a verify against a throwaway hash to pad timing when the user is unknown."""
    try:
        _HASHER.verify(_DUMMY_HASH, "any-value")
    except (VerifyMismatchError, VerificationError):
        pass


def validate_password_policy(plaintext: str) -> None:
    """Raise WeakPasswordError if the password fails policy."""
    min_len = int(os.environ.get("OPENLIA_PASSWORD_MIN_LENGTH", "8"))
    if len(plaintext) < min_len:
        raise WeakPasswordError(
            f"Password must be at least {min_len} characters long."
        )
