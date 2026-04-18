"""AES-256-GCM column encryption for provider API keys.

Key sources, in priority order:
1. OPENLIA_SECRET_KEY env var (base64-encoded 32 bytes).
2. ~/.openlia/secret.key (0600 permissions, auto-generated on first run).
"""
from __future__ import annotations

import base64
import os
import secrets
import stat
from pathlib import Path
from typing import Final

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from openlia_server.db.bootstrap import openlia_home

KEY_LENGTH_BYTES: Final[int] = 32
NONCE_LENGTH_BYTES: Final[int] = 12
KEY_FILE_NAME: Final[str] = "secret.key"
KEY_FILE_MODE: Final[int] = 0o600


class SecretKeyError(RuntimeError):
    """Raised when the AES-256 key cannot be loaded or is invalid."""


_cached_key: bytes | None = None


def _reset_cached_key() -> None:
    """Test hook to invalidate the module-level cache."""
    global _cached_key
    _cached_key = None


def load_secret_key() -> bytes:
    """Return the 32-byte AES-256 key, loading and caching on first call."""
    global _cached_key
    if _cached_key is not None:
        return _cached_key

    env_value = os.environ.get("OPENLIA_SECRET_KEY")
    if env_value:
        key = _decode_env_key(env_value)
    else:
        key = _load_or_create_file_key()

    _cached_key = key
    return key


def _decode_env_key(b64: str) -> bytes:
    try:
        raw = base64.b64decode(b64, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise SecretKeyError(
            "OPENLIA_SECRET_KEY is not valid base64"
        ) from exc
    if len(raw) != KEY_LENGTH_BYTES:
        raise SecretKeyError(
            f"OPENLIA_SECRET_KEY must decode to exactly {KEY_LENGTH_BYTES} bytes"
        )
    return raw


def _load_or_create_file_key() -> bytes:
    key_path = openlia_home() / KEY_FILE_NAME
    if key_path.exists():
        mode = stat.S_IMODE(key_path.stat().st_mode)
        if mode != KEY_FILE_MODE:
            raise SecretKeyError(
                f"{key_path} must have 0600 permissions, found {oct(mode)}"
            )
        raw = base64.b64decode(key_path.read_bytes(), validate=True)
        if len(raw) != KEY_LENGTH_BYTES:
            raise SecretKeyError(f"{key_path} does not contain a 32-byte key")
        return raw

    raw = secrets.token_bytes(KEY_LENGTH_BYTES)
    key_path.write_bytes(base64.b64encode(raw))
    key_path.chmod(KEY_FILE_MODE)
    return raw


class DecryptError(RuntimeError):
    """Raised when AES-GCM authentication fails (wrong key, wrong AAD, or tamper)."""


def encrypt_for_row(row_id: str, plaintext: str) -> str:
    """Encrypt `plaintext` bound to `row_id` via AAD.

    Layout: base64( nonce(12) || ciphertext || tag(16) ).
    """
    cipher = AESGCM(load_secret_key())
    nonce = secrets.token_bytes(NONCE_LENGTH_BYTES)
    aad = row_id.encode("utf-8")
    ct_with_tag = cipher.encrypt(nonce, plaintext.encode("utf-8"), aad)
    return base64.b64encode(nonce + ct_with_tag).decode("ascii")


def decrypt_for_row(row_id: str, token: str) -> str:
    """Inverse of `encrypt_for_row`. Raises DecryptError on any auth failure."""
    try:
        raw = base64.b64decode(token, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise DecryptError("ciphertext is not valid base64") from exc
    if len(raw) < NONCE_LENGTH_BYTES + 16:
        raise DecryptError("ciphertext too short")
    nonce, ct_with_tag = raw[:NONCE_LENGTH_BYTES], raw[NONCE_LENGTH_BYTES:]
    try:
        plaintext = AESGCM(load_secret_key()).decrypt(
            nonce, ct_with_tag, row_id.encode("utf-8")
        )
    except Exception as exc:
        raise DecryptError("authenticated decryption failed") from exc
    return plaintext.decode("utf-8")
