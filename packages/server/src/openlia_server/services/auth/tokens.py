"""Opaque random tokens for sessions, invites, and password-reset links."""
from __future__ import annotations

import hashlib
import secrets

TOKEN_BYTE_LENGTH = 32


def generate_opaque_token() -> str:
    """32 random bytes, URL-safe base64 (no padding)."""
    return secrets.token_urlsafe(TOKEN_BYTE_LENGTH)


def hash_token(token: str) -> str:
    """Hex SHA-256 of a token."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
