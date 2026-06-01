"""Encryption for connector secrets at rest.

Key resolution order:
1. `OPENLIA_SECRET_KEY` env var (must be a valid Fernet key).
2. Personal mode (`OPENLIA_MODE` != "company"): read or auto-generate a key
   file at `openlia_home()/secret.key` (chmod 600).
3. Company mode with no env key: raise `SecretKeyMissingError`.

Fernet provides authenticated symmetric encryption. The key is a urlsafe
base64-encoded 32-byte value as produced by `Fernet.generate_key()`.
"""
from __future__ import annotations

import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

KEY_FILENAME = "secret.key"

_GENERATE_HINT = (
    'Generate one with: python -c "from cryptography.fernet import Fernet; '
    'print(Fernet.generate_key().decode())"'
)


class SecretKeyMissingError(RuntimeError):
    """No encryption key available (company mode, OPENLIA_SECRET_KEY unset)."""


class SecretKeyInvalidError(RuntimeError):
    """OPENLIA_SECRET_KEY is set but is not a valid Fernet key."""


class SecretDecryptError(RuntimeError):
    """A stored secret could not be decrypted with the current key."""


_fernet: Fernet | None = None


def reset_cache() -> None:
    """Clear the cached Fernet (tests swap keys / data dirs between cases)."""
    global _fernet
    _fernet = None


def _company_mode() -> bool:
    return os.environ.get("OPENLIA_MODE", "personal").lower() == "company"


def _key_file_path() -> Path:
    # Imported lazily so this module stays free of the bootstrap import chain
    # except when a key is actually resolved.
    from openlia_server.db.bootstrap import openlia_home

    return openlia_home() / KEY_FILENAME


def resolve_key() -> bytes:
    env = os.environ.get("OPENLIA_SECRET_KEY")
    if env:
        return env.encode()
    if _company_mode():
        raise SecretKeyMissingError(
            "OPENLIA_SECRET_KEY is required in company mode to encrypt connector "
            f"secrets at rest. {_GENERATE_HINT}"
        )
    path = _key_file_path()
    if path.exists():
        return path.read_bytes().strip()
    key = Fernet.generate_key()
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        fd = os.open(path, os.O_CREAT | os.O_WRONLY | os.O_EXCL, 0o600)
    except FileExistsError:
        # Another process created it between our existence check and here.
        return path.read_bytes().strip()
    try:
        os.write(fd, key)
    finally:
        os.close(fd)
    return key


def get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key = resolve_key()
        try:
            _fernet = Fernet(key)
        except (ValueError, TypeError) as exc:
            if os.environ.get("OPENLIA_SECRET_KEY"):
                msg = f"OPENLIA_SECRET_KEY is not a valid Fernet key. {_GENERATE_HINT}"
            else:
                from openlia_server.db.bootstrap import openlia_home

                key_path = openlia_home() / KEY_FILENAME
                msg = (
                    f"The connector secret key file at {key_path} is not a valid "
                    f"Fernet key; delete it to regenerate, or set OPENLIA_SECRET_KEY. "
                    f"{_GENERATE_HINT}"
                )
            raise SecretKeyInvalidError(msg) from exc
    return _fernet


def ensure_key_available() -> None:
    """Eagerly resolve the key so misconfiguration fails loudly at startup."""
    get_fernet()


def encrypt(plaintext: str) -> str:
    return get_fernet().encrypt(plaintext.encode()).decode()


def decrypt(token: str) -> str:
    try:
        return get_fernet().decrypt(token.encode()).decode()
    except InvalidToken as exc:
        raise SecretDecryptError(
            "Connector secret decryption failed; OPENLIA_SECRET_KEY may have "
            "changed or the stored data is corrupt."
        ) from exc
