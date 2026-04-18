# Phase 2 — Secrets Encryption & Auth Primitives — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the server-side auth and secrets stack so providers can store encrypted API keys and company-mode users can register, log in, change passwords, and reset credentials via an admin-approved flow.

**Architecture:** AES-256-GCM column encryption bound to row IDs (AAD) with a key loaded from `OPENLIA_SECRET_KEY` or an auto-created `~/.openlia/secret.key` (0600). Argon2id for password hashing via `argon2-cffi`. Opaque 32-byte session tokens issued as cookies, SHA-256 hashed at rest. Session middleware is mode-aware: personal mode resolves `require_auth()` to the synthetic `local` user and never consults `sessions`; company mode mounts `/auth/*` + `/admin/*` routes and validates session cookies. Rate limiting is an in-process sliding window. Auth events go into `auth_events` for forensic audit.

**Tech Stack:** Python 3.12, `argon2-cffi>=23.1`, `cryptography>=42.0`, FastAPI dependencies, SQLAlchemy 2.x (reuses the session factory from Plan 1A), `itsdangerous`-free opaque tokens via `secrets.token_urlsafe`.

**Source specs:**
- `planning/specs/systems/database-design.md` §3 (auth tables), §5 (secrets + encryption)
- `planning/specs/components/AccountManagementSpec.md` (full)
- `planning/specs/pages/LoginPageSpec.md` (server-facing flows only)

**Depends on:** Plan 1A (database baseline — 22 tables including `users`, `sessions`, `signup_invites`, `signup_policy`, `password_reset_requests`, `auth_events`, `config_store`).

**Unblocks:** Plan 3 (data providers encrypt API keys), Plan 4 (LLM providers encrypt API keys), Plan 7 (admin CLI reuses service helpers), Plan 9 (Login + Account Management UI wires to `/auth/*`).

**Out of scope (deferred):**
- Admin CLI subcommands — Plan 7 will import from `services/auth/` but add the Typer wiring there. This plan only writes the service-layer helpers the CLI will eventually call.
- Any React UI — frontend plans (8–12) wire the routes from this plan.
- `openlia secrets rotate-key` CLI — helper function ships here but CLI wrapper is Plan 7.
- SMTP / email delivery — explicitly non-goal per AccountManagementSpec §16.
- Key rotation automation on schedule — manual-only per spec §5.
- Admin panel user CRUD beyond enable/disable + direct reset — invites and reset-requests are the minimum. More admin surface ships in Plan 11.

**Deviations from `projectStructure.md`:**
- `services/auth.py` is listed as a single file but this plan creates a `services/auth/` *package* (`passwords.py`, `tokens.py`, `sessions.py`, `registration.py`, `login.py`, `password_reset.py`, `events.py`, `signup_policy.py`, `__init__.py`). Rationale: the single-file version would exceed 1000 lines and cross several responsibilities. The public API re-exported from `services/auth/__init__.py` matches what the structure doc implies. Update `projectStructure.md` when executing Task 1 of Plan 7 (CLI) — or sooner if the implementer sees fit during this plan.

---

## Architecture summary

```
packages/server/src/openlia_server/
├── db/
│   └── crypto.py                 # AES-256-GCM key loading + encrypt_for_row/decrypt_for_row (NEW)
├── middleware/
│   ├── __init__.py               # NEW (empty package marker)
│   ├── auth.py                   # require_auth() dependency + CurrentUser (NEW)
│   └── rate_limit.py             # In-process sliding-window limiter (NEW)
├── services/
│   ├── __init__.py               # NEW (empty package marker)
│   └── auth/
│       ├── __init__.py           # Re-exports public API (NEW)
│       ├── errors.py             # AuthError hierarchy (NEW)
│       ├── events.py             # log_auth_event() helper (NEW)
│       ├── passwords.py          # Argon2id hash/verify + dummy_verify for timing (NEW)
│       ├── tokens.py             # Opaque token gen + SHA-256 hashing (NEW)
│       ├── sessions.py           # Session CRUD + TTL logic (NEW)
│       ├── signup_policy.py      # Policy seeding + domain allowlist check (NEW)
│       ├── registration.py       # Invite-gated register (NEW)
│       ├── login.py              # Login + lockout state machine (NEW)
│       └── password_reset.py     # request/approve/reject/consume + change_password (NEW)
├── routes/
│   ├── __init__.py               # NEW (empty package marker)
│   ├── auth.py                   # /auth/* routes (NEW)
│   └── admin.py                  # /admin/* routes (NEW)
├── app.py                        # MODIFIED — mount routes + middleware by mode
└── cli.py                        # MODIFIED — seed signup_policy during bootstrap

packages/server/tests/
├── test_db/
│   └── test_crypto.py            # AES helpers + key loader (NEW)
├── test_middleware/
│   ├── __init__.py               # NEW
│   ├── test_auth.py              # require_auth happy + failure paths (NEW)
│   └── test_rate_limit.py        # Sliding window math (NEW)
├── test_services/
│   ├── __init__.py               # NEW
│   └── test_auth/
│       ├── __init__.py           # NEW
│       ├── conftest.py           # Shared fixtures (app_client, make_user, make_invite) (NEW)
│       ├── test_passwords.py     # NEW
│       ├── test_tokens.py        # NEW
│       ├── test_sessions.py      # NEW
│       ├── test_signup_policy.py # NEW
│       ├── test_registration.py  # NEW
│       ├── test_login.py         # NEW
│       └── test_password_reset.py# NEW
└── test_routes/
    ├── __init__.py               # NEW
    ├── test_auth_routes.py       # NEW
    └── test_admin_routes.py      # NEW
```

All tests use the in-memory SQLite fixtures from `tests/test_db/conftest.py` (from Plan 1A). This plan adds `tests/test_services/test_auth/conftest.py` with HTTP client + user/invite helpers.

---

## Task 1: Add runtime dependencies

**Files:**
- Modify: `packages/server/pyproject.toml`

- [ ] **Step 1: Read current server pyproject**

Run: `cat packages/server/pyproject.toml`

Confirm `argon2-cffi` and `cryptography` are either missing or not yet pinned. Plan 1A already added `sqlalchemy` and `alembic`; this plan extends the same list.

- [ ] **Step 2: Add dependencies**

Edit the `dependencies` list in `packages/server/pyproject.toml` to include:

```toml
dependencies = [
    "openlia-core",
    "fastapi>=0.115",
    "uvicorn>=0.34",
    "sqlalchemy>=2.0",
    "alembic>=1.13",
    "argon2-cffi>=23.1",
    "cryptography>=42.0",
    "typer>=0.12",
]
```

Keep the existing entries; only add `argon2-cffi` and `cryptography`. Other Plan-6-era packages (`apscheduler`) stay out of this plan.

- [ ] **Step 3: Sync the workspace**

Run: `uv sync --all-packages`
Expected: success, resolves both new libs; no import errors.

- [ ] **Step 4: Commit**

```bash
git add packages/server/pyproject.toml uv.lock
git commit -m "phase-2(auth): add argon2-cffi and cryptography deps"
```

---

## Task 2: AES-256-GCM key loading (`db/crypto.py`, part 1)

**Files:**
- Create: `packages/server/src/openlia_server/db/crypto.py`
- Create: `packages/server/tests/test_db/test_crypto.py`

- [ ] **Step 1: Write the failing test for the key loader**

Create `packages/server/tests/test_db/test_crypto.py`:

```python
"""Tests for db.crypto — AES-256-GCM key loading and column encryption."""
from __future__ import annotations

import base64
import os
import stat
from pathlib import Path

import pytest

from openlia_server.db import crypto


@pytest.fixture(autouse=True)
def _reset_key_cache():
    """Ensure every test starts with a fresh module-level key cache."""
    crypto._reset_cached_key()
    yield
    crypto._reset_cached_key()


class TestLoadSecretKey:
    def test_env_var_preferred_over_file(self, tmp_path, monkeypatch):
        raw = b"\x01" * 32
        monkeypatch.setenv("OPENLIA_SECRET_KEY", base64.b64encode(raw).decode())
        monkeypatch.setenv("OPENLIA_HOME", str(tmp_path))
        # Deliberately write a different key to disk. Env var should win.
        key_file = tmp_path / "secret.key"
        key_file.write_bytes(base64.b64encode(b"\x02" * 32))
        key_file.chmod(0o600)

        assert crypto.load_secret_key() == raw

    def test_env_var_rejects_wrong_length(self, monkeypatch, tmp_path):
        monkeypatch.setenv("OPENLIA_SECRET_KEY", base64.b64encode(b"short").decode())
        monkeypatch.setenv("OPENLIA_HOME", str(tmp_path))
        with pytest.raises(crypto.SecretKeyError, match="32 bytes"):
            crypto.load_secret_key()

    def test_file_fallback_generates_if_missing(self, tmp_path, monkeypatch):
        monkeypatch.delenv("OPENLIA_SECRET_KEY", raising=False)
        monkeypatch.setenv("OPENLIA_HOME", str(tmp_path))
        tmp_path.chmod(0o700)

        key = crypto.load_secret_key()
        assert len(key) == 32

        key_file = tmp_path / "secret.key"
        assert key_file.exists()
        mode = stat.S_IMODE(key_file.stat().st_mode)
        assert mode == 0o600

    def test_file_fallback_rejects_loose_permissions(self, tmp_path, monkeypatch):
        monkeypatch.delenv("OPENLIA_SECRET_KEY", raising=False)
        monkeypatch.setenv("OPENLIA_HOME", str(tmp_path))
        tmp_path.chmod(0o700)
        key_file = tmp_path / "secret.key"
        key_file.write_bytes(base64.b64encode(b"\x03" * 32))
        key_file.chmod(0o644)

        with pytest.raises(crypto.SecretKeyError, match="0600"):
            crypto.load_secret_key()

    def test_cached_after_first_call(self, tmp_path, monkeypatch):
        raw = b"\x04" * 32
        monkeypatch.setenv("OPENLIA_SECRET_KEY", base64.b64encode(raw).decode())
        monkeypatch.setenv("OPENLIA_HOME", str(tmp_path))

        first = crypto.load_secret_key()
        monkeypatch.delenv("OPENLIA_SECRET_KEY")
        second = crypto.load_secret_key()
        assert first is second  # same bytes object returned from cache
```

- [ ] **Step 2: Run the failing test**

Run: `uv run pytest packages/server/tests/test_db/test_crypto.py::TestLoadSecretKey -v`
Expected: ImportError on `openlia_server.db.crypto`, or `AttributeError: module has no attribute 'load_secret_key'`.

- [ ] **Step 3: Implement the key loader**

Create `packages/server/src/openlia_server/db/crypto.py`:

```python
"""AES-256-GCM column encryption for provider API keys.

Key sources, in priority order:
1. OPENLIA_SECRET_KEY env var (base64-encoded 32 bytes).
2. ~/.openlia/secret.key (0600 permissions, auto-generated on first run).

Both sources yield the same 32-byte output. The module caches the key after the
first successful load so we don't re-read the file on every request.
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
```

Note: `openlia_home()` was created in Plan 1A Task 4. If that helper is missing, the implementer should stop and escalate — Plan 2 cannot ship without the Plan 1A infrastructure.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_db/test_crypto.py::TestLoadSecretKey -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/db/crypto.py packages/server/tests/test_db/test_crypto.py
git commit -m "phase-2(crypto): AES-256 key loader with env + file fallback"
```

---

## Task 3: AES-256-GCM column encryption with row-ID AAD

**Files:**
- Modify: `packages/server/src/openlia_server/db/crypto.py`
- Modify: `packages/server/tests/test_db/test_crypto.py`

- [ ] **Step 1: Write failing tests for encrypt_for_row / decrypt_for_row**

Append to `packages/server/tests/test_db/test_crypto.py`:

```python
class TestEncryptDecrypt:
    @pytest.fixture
    def setup_key(self, tmp_path, monkeypatch):
        import base64
        raw = b"\x09" * 32
        monkeypatch.setenv("OPENLIA_SECRET_KEY", base64.b64encode(raw).decode())
        monkeypatch.setenv("OPENLIA_HOME", str(tmp_path))

    def test_roundtrip(self, setup_key):
        row_id = "llm-provider-abc"
        plaintext = "sk-example-api-key"
        ciphertext = crypto.encrypt_for_row(row_id, plaintext)
        assert ciphertext != plaintext
        assert crypto.decrypt_for_row(row_id, ciphertext) == plaintext

    def test_ciphertext_is_base64(self, setup_key):
        import base64
        ciphertext = crypto.encrypt_for_row("id-1", "secret")
        # Should decode without error and be >= 12 (nonce) + 16 (tag) bytes
        raw = base64.b64decode(ciphertext, validate=True)
        assert len(raw) >= 12 + 16

    def test_different_nonces_each_call(self, setup_key):
        ct1 = crypto.encrypt_for_row("id-1", "same plaintext")
        ct2 = crypto.encrypt_for_row("id-1", "same plaintext")
        assert ct1 != ct2  # fresh nonce per encryption

    def test_aad_binds_to_row_id(self, setup_key):
        ciphertext = crypto.encrypt_for_row("correct-row", "hello")
        with pytest.raises(crypto.DecryptError):
            crypto.decrypt_for_row("different-row", ciphertext)

    def test_tampered_ciphertext_rejected(self, setup_key):
        import base64
        ciphertext = crypto.encrypt_for_row("id-1", "hello")
        raw = bytearray(base64.b64decode(ciphertext))
        raw[-1] ^= 0x01  # flip a tag byte
        tampered = base64.b64encode(bytes(raw)).decode()
        with pytest.raises(crypto.DecryptError):
            crypto.decrypt_for_row("id-1", tampered)

    def test_empty_plaintext_roundtrips(self, setup_key):
        assert crypto.decrypt_for_row("id-1", crypto.encrypt_for_row("id-1", "")) == ""
```

- [ ] **Step 2: Run the failing tests**

Run: `uv run pytest packages/server/tests/test_db/test_crypto.py::TestEncryptDecrypt -v`
Expected: attribute errors on `encrypt_for_row` / `decrypt_for_row` / `DecryptError`.

- [ ] **Step 3: Implement the cipher helpers**

Append to `packages/server/src/openlia_server/db/crypto.py`:

```python
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
    except Exception as exc:  # cryptography raises InvalidTag; wrap to our domain.
        raise DecryptError("authenticated decryption failed") from exc
    return plaintext.decode("utf-8")
```

- [ ] **Step 4: Run the tests to verify all pass**

Run: `uv run pytest packages/server/tests/test_db/test_crypto.py -v`
Expected: all tests pass (5 loader tests + 6 encrypt/decrypt tests).

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/db/crypto.py packages/server/tests/test_db/test_crypto.py
git commit -m "phase-2(crypto): encrypt_for_row / decrypt_for_row with row-id AAD"
```

---

## Task 4: Argon2id password hashing (`services/auth/passwords.py`)

**Files:**
- Create: `packages/server/src/openlia_server/services/__init__.py`
- Create: `packages/server/src/openlia_server/services/auth/__init__.py`
- Create: `packages/server/src/openlia_server/services/auth/errors.py`
- Create: `packages/server/src/openlia_server/services/auth/passwords.py`
- Create: `packages/server/tests/test_services/__init__.py`
- Create: `packages/server/tests/test_services/test_auth/__init__.py`
- Create: `packages/server/tests/test_services/test_auth/test_passwords.py`

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_services/test_auth/test_passwords.py`:

```python
"""Tests for services.auth.passwords — Argon2id hashing + dummy verify."""
from __future__ import annotations

import time

import pytest

from openlia_server.services.auth import passwords


class TestHashAndVerify:
    def test_hash_is_argon2id(self):
        hashed = passwords.hash_password("correct horse battery staple")
        assert hashed.startswith("$argon2id$")

    def test_verify_matches(self):
        hashed = passwords.hash_password("pw")
        assert passwords.verify_password(hashed, "pw") is True

    def test_verify_rejects_wrong_password(self):
        hashed = passwords.hash_password("pw")
        assert passwords.verify_password(hashed, "nope") is False

    def test_verify_rejects_none_hash(self):
        assert passwords.verify_password(None, "anything") is False

    def test_dummy_verify_returns_false_in_roughly_same_time(self):
        real_hash = passwords.hash_password("pw")
        t0 = time.perf_counter()
        passwords.verify_password(real_hash, "wrong")
        real_elapsed = time.perf_counter() - t0

        t0 = time.perf_counter()
        passwords.dummy_verify()
        dummy_elapsed = time.perf_counter() - t0
        # Allow wide tolerance; we care they are both in the same order of magnitude.
        assert 0.25 * real_elapsed < dummy_elapsed < 4.0 * real_elapsed


class TestPolicy:
    def test_min_length_default_8(self, monkeypatch):
        monkeypatch.delenv("OPENLIA_PASSWORD_MIN_LENGTH", raising=False)
        passwords.validate_password_policy("12345678")
        with pytest.raises(passwords.WeakPasswordError):
            passwords.validate_password_policy("short")

    def test_min_length_from_env(self, monkeypatch):
        monkeypatch.setenv("OPENLIA_PASSWORD_MIN_LENGTH", "12")
        with pytest.raises(passwords.WeakPasswordError):
            passwords.validate_password_policy("eleven-char")
        passwords.validate_password_policy("twelve-chars")
```

- [ ] **Step 2: Create empty package markers and run the test**

```bash
touch packages/server/src/openlia_server/services/__init__.py
touch packages/server/src/openlia_server/services/auth/__init__.py
touch packages/server/tests/test_services/__init__.py
touch packages/server/tests/test_services/test_auth/__init__.py
```

Run: `uv run pytest packages/server/tests/test_services/test_auth/test_passwords.py -v`
Expected: ImportError — `services.auth.passwords` not found.

- [ ] **Step 3: Implement the errors module**

Create `packages/server/src/openlia_server/services/auth/errors.py`:

```python
"""Auth-service error hierarchy. Routes translate these to HTTP error responses."""
from __future__ import annotations


class AuthError(Exception):
    """Base class for all services.auth errors. Carries a stable code string."""

    code: str = "auth_error"

    def __init__(self, message: str, *, code: str | None = None) -> None:
        super().__init__(message)
        if code is not None:
            self.code = code
```

- [ ] **Step 4: Implement passwords.py**

Create `packages/server/src/openlia_server/services/auth/passwords.py`:

```python
"""Argon2id password hashing and policy enforcement."""
from __future__ import annotations

import os

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError

from openlia_server.services.auth.errors import AuthError


class WeakPasswordError(AuthError):
    code = "weak_password"


_HASHER = PasswordHasher(
    time_cost=3,
    memory_cost=64 * 1024,  # 64 MiB
    parallelism=4,
)

# Precomputed hash of a throwaway password used by `dummy_verify` to pad timing.
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
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_services/test_auth/test_passwords.py -v`
Expected: 7 passed.

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/services \
        packages/server/tests/test_services
git commit -m "phase-2(auth): Argon2id password hashing with policy + timing pad"
```

---

## Task 5: Opaque session tokens (`services/auth/tokens.py`)

**Files:**
- Create: `packages/server/src/openlia_server/services/auth/tokens.py`
- Create: `packages/server/tests/test_services/test_auth/test_tokens.py`

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_services/test_auth/test_tokens.py`:

```python
"""Tests for services.auth.tokens — opaque token generation + hashing."""
from __future__ import annotations

from openlia_server.services.auth import tokens


class TestGenerateToken:
    def test_length_is_urlsafe_base64_of_32_bytes(self):
        token = tokens.generate_opaque_token()
        # 32 bytes base64url (no padding) = ceil(32*8/6) = 43 chars
        assert 42 <= len(token) <= 43
        assert token.replace("-", "").replace("_", "").isalnum()

    def test_tokens_are_unique(self):
        seen = {tokens.generate_opaque_token() for _ in range(100)}
        assert len(seen) == 100

    def test_hash_is_hex_sha256(self):
        h = tokens.hash_token("abc")
        assert len(h) == 64
        assert all(c in "0123456789abcdef" for c in h)

    def test_hash_is_deterministic(self):
        assert tokens.hash_token("abc") == tokens.hash_token("abc")

    def test_hash_different_for_different_input(self):
        assert tokens.hash_token("abc") != tokens.hash_token("abd")
```

- [ ] **Step 2: Run the failing test**

Run: `uv run pytest packages/server/tests/test_services/test_auth/test_tokens.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement tokens.py**

Create `packages/server/src/openlia_server/services/auth/tokens.py`:

```python
"""Opaque random tokens for sessions, invites, and password-reset links.

All tokens are 32 random bytes base64url-encoded. Bearer tokens are compared to
their SHA-256 hash stored in the DB (looked up by hash, not plaintext).
"""
from __future__ import annotations

import hashlib
import secrets

TOKEN_BYTE_LENGTH = 32


def generate_opaque_token() -> str:
    """32 random bytes, URL-safe base64 (no padding)."""
    return secrets.token_urlsafe(TOKEN_BYTE_LENGTH)


def hash_token(token: str) -> str:
    """Hex SHA-256 of a token. Stored in `sessions.token_hash` / `password_reset_requests.token_hash`."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_services/test_auth/test_tokens.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/services/auth/tokens.py \
        packages/server/tests/test_services/test_auth/test_tokens.py
git commit -m "phase-2(auth): opaque session/invite tokens with SHA-256 hashing"
```

---

## Task 6: Session CRUD (`services/auth/sessions.py`)

**Files:**
- Create: `packages/server/src/openlia_server/services/auth/sessions.py`
- Create: `packages/server/tests/test_services/test_auth/conftest.py`
- Create: `packages/server/tests/test_services/test_auth/test_sessions.py`

- [ ] **Step 1: Create a shared conftest with user/session factories**

Create `packages/server/tests/test_services/test_auth/conftest.py`:

```python
"""Shared fixtures for services.auth tests.

Builds on top of packages/server/tests/test_db/conftest.py, which ships an
engine + session fixture scoped to a temp SQLite DB with all Plan 1A tables
created.
"""
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from openlia_server.db.models.auth import User
from openlia_server.services.auth import passwords


@pytest.fixture
def make_user(db_session):
    """Factory returning a helper that inserts a users row and returns the User."""
    def _make(
        email: str = "alice@example.com",
        password: str | None = "correct horse battery staple",
        is_admin: bool = False,
        is_disabled: bool = False,
    ) -> User:
        user = User(
            id=f"user-{email}",
            email=email,
            display_name=email.split("@")[0],
            password_hash=passwords.hash_password(password) if password else None,
            is_admin=is_admin,
            is_disabled=is_disabled,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db_session.add(user)
        db_session.commit()
        return user

    return _make
```

Note: the `db_session` fixture is inherited from `packages/server/tests/test_db/conftest.py`. If pytest cannot discover it from this location, add a thin re-export conftest at `packages/server/tests/conftest.py` pointing at `tests/test_db/conftest.py` (see Plan 1A Task 13 which may already have done this). Confirm the layout by running `uv run pytest --collect-only packages/server/tests/test_services/test_auth/` before the next step.

- [ ] **Step 2: Write the failing test**

Create `packages/server/tests/test_services/test_auth/test_sessions.py`:

```python
"""Tests for services.auth.sessions — create, validate, revoke, prune."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from openlia_server.services.auth import sessions


class TestCreateSession:
    def test_returns_raw_token_and_row(self, db_session, make_user):
        user = make_user()
        result = sessions.create_session(
            db_session,
            user_id=user.id,
            persistent=True,
            user_agent="pytest/1.0",
            ip_address="127.0.0.1",
        )
        assert len(result.raw_token) > 40
        assert result.session.user_id == user.id
        assert result.session.expires_at > datetime.now(timezone.utc) + timedelta(days=29)
        assert result.session.revoked_at is None

    def test_persistent_sets_30d_ttl(self, db_session, make_user):
        user = make_user()
        r = sessions.create_session(db_session, user_id=user.id, persistent=True)
        delta = r.session.expires_at - datetime.now(timezone.utc)
        assert timedelta(days=29, hours=23) <= delta <= timedelta(days=30, hours=1)

    def test_non_persistent_sets_12h_ttl(self, db_session, make_user):
        user = make_user()
        r = sessions.create_session(db_session, user_id=user.id, persistent=False)
        delta = r.session.expires_at - datetime.now(timezone.utc)
        assert timedelta(hours=11) <= delta <= timedelta(hours=13)

    def test_token_hash_is_stored_not_plaintext(self, db_session, make_user):
        user = make_user()
        r = sessions.create_session(db_session, user_id=user.id, persistent=False)
        assert r.session.token_hash != r.raw_token
        assert len(r.session.token_hash) == 64


class TestValidateSession:
    def test_returns_user_on_valid_token(self, db_session, make_user):
        user = make_user()
        r = sessions.create_session(db_session, user_id=user.id, persistent=True)
        validated = sessions.validate_session(db_session, r.raw_token)
        assert validated is not None
        assert validated.user.id == user.id

    def test_returns_none_for_unknown_token(self, db_session):
        assert sessions.validate_session(db_session, "not-a-real-token") is None

    def test_returns_none_for_revoked_session(self, db_session, make_user):
        user = make_user()
        r = sessions.create_session(db_session, user_id=user.id, persistent=True)
        sessions.revoke_session(db_session, r.session.id)
        assert sessions.validate_session(db_session, r.raw_token) is None

    def test_returns_none_for_expired_session(self, db_session, make_user):
        user = make_user()
        r = sessions.create_session(db_session, user_id=user.id, persistent=False)
        r.session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db_session.commit()
        assert sessions.validate_session(db_session, r.raw_token) is None

    def test_returns_none_for_disabled_user(self, db_session, make_user):
        user = make_user()
        r = sessions.create_session(db_session, user_id=user.id, persistent=True)
        user.is_disabled = True
        db_session.commit()
        assert sessions.validate_session(db_session, r.raw_token) is None

    def test_last_seen_updates_when_stale(self, db_session, make_user):
        user = make_user()
        r = sessions.create_session(db_session, user_id=user.id, persistent=True)
        original = r.session.last_seen_at
        r.session.last_seen_at = original - timedelta(minutes=5)
        db_session.commit()
        sessions.validate_session(db_session, r.raw_token)
        db_session.refresh(r.session)
        assert r.session.last_seen_at > original - timedelta(minutes=5)

    def test_last_seen_not_updated_when_fresh(self, db_session, make_user):
        user = make_user()
        r = sessions.create_session(db_session, user_id=user.id, persistent=True)
        before = r.session.last_seen_at
        sessions.validate_session(db_session, r.raw_token)
        db_session.refresh(r.session)
        # Should not tick because it was just created (<60s ago)
        assert r.session.last_seen_at == before


class TestRevoke:
    def test_revoke_all_sessions_for_user(self, db_session, make_user):
        user = make_user()
        r1 = sessions.create_session(db_session, user_id=user.id, persistent=True)
        r2 = sessions.create_session(db_session, user_id=user.id, persistent=False)
        sessions.revoke_all_sessions(db_session, user_id=user.id)
        assert sessions.validate_session(db_session, r1.raw_token) is None
        assert sessions.validate_session(db_session, r2.raw_token) is None

    def test_prune_expired(self, db_session, make_user):
        user = make_user()
        r = sessions.create_session(db_session, user_id=user.id, persistent=False)
        r.session.expires_at = datetime.now(timezone.utc) - timedelta(days=10)
        db_session.commit()

        removed = sessions.prune_expired(db_session, older_than_days=7)
        assert removed == 1
```

- [ ] **Step 3: Run the failing test**

Run: `uv run pytest packages/server/tests/test_services/test_auth/test_sessions.py -v`
Expected: import error.

- [ ] **Step 4: Implement sessions.py**

Create `packages/server/src/openlia_server/services/auth/sessions.py`:

```python
"""Session lifecycle helpers.

Sessions are stored as SHA-256 hashes of the raw token. The raw token is only
ever returned to the caller that created the session (and set as a cookie) — it
is never stored or logged.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select, update
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.models.auth import Session as SessionRow, User
from openlia_server.services.auth import tokens

PERSISTENT_TTL = timedelta(days=30)
NON_PERSISTENT_TTL = timedelta(hours=12)
LAST_SEEN_DEBOUNCE = timedelta(seconds=60)
INACTIVITY_CAP = timedelta(days=30)


@dataclass
class CreatedSession:
    raw_token: str
    session: SessionRow


@dataclass
class ValidatedSession:
    session: SessionRow
    user: User


def create_session(
    db: DBSession,
    *,
    user_id: str,
    persistent: bool,
    user_agent: str | None = None,
    ip_address: str | None = None,
) -> CreatedSession:
    now = datetime.now(timezone.utc)
    raw = tokens.generate_opaque_token()
    ttl = PERSISTENT_TTL if persistent else NON_PERSISTENT_TTL
    row = SessionRow(
        id=str(uuid.uuid4()),
        user_id=user_id,
        token_hash=tokens.hash_token(raw),
        created_at=now,
        last_seen_at=now,
        expires_at=now + ttl,
        user_agent=(user_agent or "")[:512] or None,
        ip_address=ip_address,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return CreatedSession(raw_token=raw, session=row)


def validate_session(db: DBSession, raw_token: str) -> ValidatedSession | None:
    if not raw_token:
        return None
    hashed = tokens.hash_token(raw_token)
    stmt = select(SessionRow, User).join(User, User.id == SessionRow.user_id).where(
        SessionRow.token_hash == hashed
    )
    row = db.execute(stmt).first()
    if row is None:
        return None

    session, user = row
    now = datetime.now(timezone.utc)
    if session.revoked_at is not None:
        return None
    if session.expires_at <= now:
        return None
    if session.last_seen_at < now - INACTIVITY_CAP:
        return None
    if user.is_disabled:
        return None

    if session.last_seen_at < now - LAST_SEEN_DEBOUNCE:
        session.last_seen_at = now
        db.commit()

    return ValidatedSession(session=session, user=user)


def revoke_session(db: DBSession, session_id: str) -> None:
    db.execute(
        update(SessionRow)
        .where(SessionRow.id == session_id, SessionRow.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )
    db.commit()


def revoke_all_sessions(db: DBSession, *, user_id: str) -> None:
    db.execute(
        update(SessionRow)
        .where(SessionRow.user_id == user_id, SessionRow.revoked_at.is_(None))
        .values(revoked_at=datetime.now(timezone.utc))
    )
    db.commit()


def prune_expired(db: DBSession, *, older_than_days: int = 7) -> int:
    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
    result = db.execute(delete(SessionRow).where(SessionRow.expires_at < cutoff))
    db.commit()
    return int(result.rowcount or 0)
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_services/test_auth/test_sessions.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/services/auth/sessions.py \
        packages/server/tests/test_services/test_auth/conftest.py \
        packages/server/tests/test_services/test_auth/test_sessions.py
git commit -m "phase-2(auth): session create/validate/revoke/prune with TTL semantics"
```

---

## Task 7: Auth event logger (`services/auth/events.py`)

**Files:**
- Create: `packages/server/src/openlia_server/services/auth/events.py`
- Create: `packages/server/tests/test_services/test_auth/test_events.py`

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_services/test_auth/test_events.py`:

```python
"""Tests for services.auth.events.log_auth_event."""
from __future__ import annotations

from sqlalchemy import select

from openlia_server.db.models.auth import AuthEvent
from openlia_server.services.auth import events


def test_log_basic_event(db_session, make_user):
    user = make_user()
    events.log_auth_event(
        db_session,
        event_type="login_success",
        user_id=user.id,
        actor_user_id=user.id,
        ip_address="10.0.0.1",
        user_agent="pytest",
        metadata={"source": "web"},
    )
    rows = list(db_session.execute(select(AuthEvent)).scalars())
    assert len(rows) == 1
    assert rows[0].event_type == "login_success"
    assert rows[0].user_id == user.id
    assert rows[0].event_metadata == {"source": "web"}


def test_log_event_without_user(db_session):
    events.log_auth_event(
        db_session,
        event_type="login_failure",
        ip_address="10.0.0.1",
    )
    rows = list(db_session.execute(select(AuthEvent)).scalars())
    assert len(rows) == 1
    assert rows[0].user_id is None


def test_user_agent_truncated_to_512(db_session, make_user):
    user = make_user()
    events.log_auth_event(
        db_session,
        event_type="login_success",
        user_id=user.id,
        user_agent="x" * 1000,
    )
    rows = list(db_session.execute(select(AuthEvent)).scalars())
    assert len(rows[0].user_agent) == 512
```

- [ ] **Step 2: Run the failing test**

Run: `uv run pytest packages/server/tests/test_services/test_auth/test_events.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement events.py**

Create `packages/server/src/openlia_server/services/auth/events.py`:

```python
"""Append-only audit log writes.

Rows land in the `auth_events` table. Never include passwords, tokens, or
API keys in `metadata` — only IDs and event-shaping fields.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.orm import Session as DBSession

from openlia_server.db.models.auth import AuthEvent


def log_auth_event(
    db: DBSession,
    *,
    event_type: str,
    user_id: str | None = None,
    actor_user_id: str | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    row = AuthEvent(
        id=str(uuid.uuid4()),
        event_type=event_type,
        user_id=user_id,
        actor_user_id=actor_user_id,
        ip_address=ip_address,
        user_agent=(user_agent or "")[:512] or None,
        event_metadata=metadata,
        created_at=datetime.now(timezone.utc),
    )
    db.add(row)
    db.commit()
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_services/test_auth/test_events.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/services/auth/events.py \
        packages/server/tests/test_services/test_auth/test_events.py
git commit -m "phase-2(auth): log_auth_event helper for append-only audit trail"
```

---

## Task 8: Signup policy seeding + domain allowlist (`services/auth/signup_policy.py`)

**Files:**
- Create: `packages/server/src/openlia_server/services/auth/signup_policy.py`
- Create: `packages/server/tests/test_services/test_auth/test_signup_policy.py`
- Modify: `packages/server/src/openlia_server/db/bootstrap.py` (bootstrap function added in Plan 1A Task 11)
- Modify: `packages/server/tests/test_db/test_bootstrap.py` (if present — else skip this file)

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_services/test_auth/test_signup_policy.py`:

```python
"""Tests for services.auth.signup_policy — seeding + policy enforcement."""
from __future__ import annotations

import pytest
from sqlalchemy import select

from openlia_server.db.models.auth import SignupPolicy
from openlia_server.services.auth import signup_policy
from openlia_server.services.auth.errors import AuthError


def test_seed_personal_mode(db_session):
    signup_policy.seed_signup_policy(db_session, mode_flag="personal")
    row = db_session.execute(select(SignupPolicy)).scalar_one()
    assert row.mode == "closed"


def test_seed_company_mode(db_session):
    signup_policy.seed_signup_policy(db_session, mode_flag="company")
    row = db_session.execute(select(SignupPolicy)).scalar_one()
    assert row.mode == "invite_only"


def test_seed_is_idempotent(db_session):
    signup_policy.seed_signup_policy(db_session, mode_flag="company")
    signup_policy.seed_signup_policy(db_session, mode_flag="personal")
    rows = list(db_session.execute(select(SignupPolicy)).scalars())
    assert len(rows) == 1
    # Second call must not overwrite.
    assert rows[0].mode == "invite_only"


def test_check_email_allowed_no_restrictions(db_session):
    signup_policy.seed_signup_policy(db_session, mode_flag="company")
    signup_policy.check_email_allowed(db_session, "anyone@any.tld")


def test_check_email_allowed_allowlist(db_session):
    signup_policy.seed_signup_policy(db_session, mode_flag="company")
    row = db_session.execute(select(SignupPolicy)).scalar_one()
    row.allowed_email_domains = ["company.com"]
    db_session.commit()

    signup_policy.check_email_allowed(db_session, "ok@company.com")
    with pytest.raises(AuthError):
        signup_policy.check_email_allowed(db_session, "not@other.com")


def test_get_policy_raises_if_missing(db_session):
    with pytest.raises(RuntimeError):
        signup_policy.get_policy(db_session)
```

- [ ] **Step 2: Run the failing test**

Run: `uv run pytest packages/server/tests/test_services/test_auth/test_signup_policy.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement signup_policy.py**

Create `packages/server/src/openlia_server/services/auth/signup_policy.py`:

```python
"""Singleton signup policy row + enforcement helpers."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.models.auth import SignupPolicy
from openlia_server.services.auth.errors import AuthError


class SignupClosedError(AuthError):
    code = "signup_closed"


class EmailDomainNotAllowedError(AuthError):
    code = "email_domain_not_allowed"


def seed_signup_policy(db: DBSession, *, mode_flag: Literal["personal", "company"]) -> None:
    """Insert the singleton row if absent. Idempotent — never overwrites."""
    existing = db.execute(select(SignupPolicy).where(SignupPolicy.id == 1)).scalar_one_or_none()
    if existing is not None:
        return

    policy_mode = "closed" if mode_flag == "personal" else "invite_only"
    db.add(
        SignupPolicy(
            id=1,
            mode=policy_mode,
            allowed_email_domains=[],
            updated_at=datetime.now(timezone.utc),
        )
    )
    db.commit()


def get_policy(db: DBSession) -> SignupPolicy:
    row = db.execute(select(SignupPolicy).where(SignupPolicy.id == 1)).scalar_one_or_none()
    if row is None:
        raise RuntimeError("signup_policy row is missing; bootstrap did not run")
    return row


def check_email_allowed(db: DBSession, email: str) -> None:
    policy = get_policy(db)
    domains: list[str] = policy.allowed_email_domains or []
    if not domains:
        return
    _, _, domain = email.partition("@")
    if domain.lower() not in {d.lower() for d in domains}:
        raise EmailDomainNotAllowedError(
            f"Email domain '{domain}' is not in the allowlist."
        )


def assert_registration_open(db: DBSession) -> None:
    policy = get_policy(db)
    if policy.mode == "closed":
        raise SignupClosedError("Registration is closed.")
    if policy.mode == "open":
        raise SignupClosedError("Open mode is not supported in v1.", code="signup_closed")
```

- [ ] **Step 4: Wire into bootstrap**

Open `packages/server/src/openlia_server/db/bootstrap.py` (from Plan 1A Task 11). Inside the `bootstrap()` function, after the local-user seed and before the wizard-state seed (or wherever idempotent seeds run), add:

```python
from openlia_server.services.auth import signup_policy

mode_flag = "company" if os.environ.get("OPENLIA_MODE") == "company" else "personal"
signup_policy.seed_signup_policy(session, mode_flag=mode_flag)
```

If Plan 1A's bootstrap lives in a function that takes an explicit mode flag, reuse that instead of reading the env var here. The point is the seed happens on every `openlia serve` start-up.

- [ ] **Step 5: Run the tests**

```bash
uv run pytest packages/server/tests/test_services/test_auth/test_signup_policy.py -v
uv run pytest packages/server/tests/test_db/ -v
```

Expected: all pass (new tests + any existing bootstrap tests).

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/services/auth/signup_policy.py \
        packages/server/src/openlia_server/db/bootstrap.py \
        packages/server/tests/test_services/test_auth/test_signup_policy.py
git commit -m "phase-2(auth): seed signup_policy on bootstrap + domain allowlist check"
```

---

## Task 9: Invite-gated registration (`services/auth/registration.py`)

**Files:**
- Create: `packages/server/src/openlia_server/services/auth/registration.py`
- Create: `packages/server/tests/test_services/test_auth/test_registration.py`

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_services/test_auth/test_registration.py`:

```python
"""Tests for services.auth.registration — register(), normalize_email()."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from openlia_server.db.models.auth import SignupInvite, User
from openlia_server.services.auth import registration, signup_policy
from openlia_server.services.auth.errors import AuthError


@pytest.fixture
def make_invite(db_session):
    def _make(token: str = "invite-tok", **kwargs) -> SignupInvite:
        row = SignupInvite(
            id=f"inv-{token}",
            token=token,
            created_at=datetime.now(timezone.utc),
            **kwargs,
        )
        db_session.add(row)
        db_session.commit()
        return row
    return _make


@pytest.fixture(autouse=True)
def _seeded_policy(db_session):
    signup_policy.seed_signup_policy(db_session, mode_flag="company")


class TestNormalizeEmail:
    @pytest.mark.parametrize(
        "raw,expected",
        [
            ("  Alice@Example.COM ", "alice@example.com"),
            ("bob+tag@host.tld", "bob+tag@host.tld"),
        ],
    )
    def test_cases(self, raw, expected):
        assert registration.normalize_email(raw) == expected


class TestRegister:
    def test_success_inserts_user_and_increments_invite(self, db_session, make_invite):
        invite = make_invite(max_uses=5, use_count=0)
        user = registration.register(
            db_session,
            email="alice@example.com",
            password="correct-horse-battery-staple",
            display_name="Alice",
            invite_token=invite.token,
        )
        assert user.email == "alice@example.com"
        db_session.refresh(invite)
        assert invite.use_count == 1

    def test_missing_invite_raises(self, db_session):
        with pytest.raises(AuthError) as exc:
            registration.register(
                db_session,
                email="alice@example.com",
                password="12345678",
                display_name="Alice",
                invite_token=None,
            )
        assert exc.value.code == "invite_required"

    def test_unknown_invite_raises(self, db_session):
        with pytest.raises(AuthError) as exc:
            registration.register(
                db_session,
                email="alice@example.com",
                password="12345678",
                display_name="Alice",
                invite_token="nope",
            )
        assert exc.value.code == "invite_invalid"

    def test_revoked_invite_rejected(self, db_session, make_invite):
        invite = make_invite(
            revoked_at=datetime.now(timezone.utc) - timedelta(minutes=1),
        )
        with pytest.raises(AuthError) as exc:
            registration.register(
                db_session,
                email="alice@example.com",
                password="12345678",
                display_name="Alice",
                invite_token=invite.token,
            )
        assert exc.value.code == "invite_invalid"

    def test_expired_invite_rejected(self, db_session, make_invite):
        invite = make_invite(expires_at=datetime.now(timezone.utc) - timedelta(days=1))
        with pytest.raises(AuthError) as exc:
            registration.register(
                db_session,
                email="alice@example.com",
                password="12345678",
                display_name="Alice",
                invite_token=invite.token,
            )
        assert exc.value.code == "invite_invalid"

    def test_capped_invite_rejected(self, db_session, make_invite):
        invite = make_invite(max_uses=1, use_count=1)
        with pytest.raises(AuthError):
            registration.register(
                db_session,
                email="alice@example.com",
                password="12345678",
                display_name="Alice",
                invite_token=invite.token,
            )

    def test_duplicate_email_returns_generic_error(self, db_session, make_invite, make_user):
        make_user(email="alice@example.com")
        invite = make_invite()
        with pytest.raises(AuthError) as exc:
            registration.register(
                db_session,
                email="alice@example.com",
                password="12345678",
                display_name="Alice",
                invite_token=invite.token,
            )
        assert exc.value.code == "registration_failed"

    def test_weak_password_rejected(self, db_session, make_invite):
        invite = make_invite()
        with pytest.raises(AuthError) as exc:
            registration.register(
                db_session,
                email="alice@example.com",
                password="short",
                display_name="Alice",
                invite_token=invite.token,
            )
        assert exc.value.code == "weak_password"

    def test_closed_mode_rejects(self, db_session, make_invite):
        policy = signup_policy.get_policy(db_session)
        policy.mode = "closed"
        db_session.commit()
        invite = make_invite()
        with pytest.raises(AuthError) as exc:
            registration.register(
                db_session,
                email="alice@example.com",
                password="12345678",
                display_name="Alice",
                invite_token=invite.token,
            )
        assert exc.value.code == "signup_closed"
```

- [ ] **Step 2: Run the failing test**

Run: `uv run pytest packages/server/tests/test_services/test_auth/test_registration.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement registration.py**

Create `packages/server/src/openlia_server/services/auth/registration.py`:

```python
"""Invite-gated, email/password registration."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone

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
        # Anti-enumeration: generic error, not "email already registered".
        raise RegistrationFailedError("Registration failed.")

    now = datetime.now(timezone.utc)
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
    assert invite is not None  # _validate_invite already checked
    invite.use_count = (invite.use_count or 0) + 1
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def _validate_invite(invite: SignupInvite | None) -> None:
    if invite is None:
        raise InviteInvalidError("Invite is invalid.")
    now = datetime.now(timezone.utc)
    if invite.revoked_at is not None:
        raise InviteInvalidError("Invite is invalid.")
    if invite.expires_at is not None and invite.expires_at <= now:
        raise InviteInvalidError("Invite is invalid.")
    if invite.max_uses is not None and (invite.use_count or 0) >= invite.max_uses:
        raise InviteInvalidError("Invite is invalid.")
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/server/tests/test_services/test_auth/test_registration.py -v`
Expected: all pass (9 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/services/auth/registration.py \
        packages/server/tests/test_services/test_auth/test_registration.py
git commit -m "phase-2(auth): invite-gated registration with domain allowlist + anti-enum"
```

---

## Task 10: Login with lockout (`services/auth/login.py`)

**Files:**
- Create: `packages/server/src/openlia_server/services/auth/login.py`
- Create: `packages/server/tests/test_services/test_auth/test_login.py`

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_services/test_auth/test_login.py`:

```python
"""Tests for services.auth.login — authenticate(), lockout state machine."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from openlia_server.db.models.auth import AuthEvent, ConfigStore
from openlia_server.services.auth import login
from openlia_server.services.auth.errors import AuthError


@pytest.fixture
def enable_lockout(db_session):
    """Ensure config_store row for auth.lockout.enabled=true exists."""
    from openlia_server.db.models.infrastructure import ConfigStore
    db_session.add(ConfigStore(
        key="auth.lockout.enabled",
        value={"enabled": True},
        updated_at=datetime.now(timezone.utc),
    ))
    db_session.commit()


class TestAuthenticate:
    def test_success(self, db_session, make_user):
        u = make_user(password="correct-pw-long-enough")
        result = login.authenticate(
            db_session, email="alice@example.com", password="correct-pw-long-enough"
        )
        assert result.user.id == u.id
        assert result.must_change_password is False

    def test_wrong_password_raises_invalid_credentials(self, db_session, make_user):
        make_user()
        with pytest.raises(AuthError) as exc:
            login.authenticate(db_session, email="alice@example.com", password="wrong")
        assert exc.value.code == "invalid_credentials"

    def test_unknown_email_raises_invalid_credentials(self, db_session):
        with pytest.raises(AuthError) as exc:
            login.authenticate(db_session, email="nobody@example.com", password="whatever")
        assert exc.value.code == "invalid_credentials"

    def test_disabled_account(self, db_session, make_user):
        make_user(is_disabled=True)
        with pytest.raises(AuthError) as exc:
            login.authenticate(
                db_session, email="alice@example.com", password="correct horse battery staple"
            )
        assert exc.value.code == "account_disabled"

    def test_must_change_password_flag_returned(self, db_session, make_user):
        u = make_user()
        u.must_change_password = True
        db_session.commit()
        result = login.authenticate(
            db_session, email="alice@example.com", password="correct horse battery staple"
        )
        assert result.must_change_password is True


class TestLockout:
    def test_five_failures_lock(self, db_session, make_user, enable_lockout):
        make_user()
        for _ in range(5):
            with pytest.raises(AuthError):
                login.authenticate(db_session, email="alice@example.com", password="nope")

        with pytest.raises(AuthError) as exc:
            login.authenticate(
                db_session, email="alice@example.com", password="correct horse battery staple"
            )
        assert exc.value.code == "account_locked"

    def test_lockout_disabled_doesnt_lock(self, db_session, make_user):
        from openlia_server.db.models.infrastructure import ConfigStore
        db_session.add(ConfigStore(
            key="auth.lockout.enabled",
            value={"enabled": False},
            updated_at=datetime.now(timezone.utc),
        ))
        db_session.commit()
        make_user()
        for _ in range(6):
            with pytest.raises(AuthError):
                login.authenticate(db_session, email="alice@example.com", password="nope")
        # Valid password now still works
        result = login.authenticate(
            db_session, email="alice@example.com", password="correct horse battery staple"
        )
        assert result.user.email == "alice@example.com"

    def test_success_resets_failure_counter(self, db_session, make_user, enable_lockout):
        u = make_user()
        for _ in range(3):
            with pytest.raises(AuthError):
                login.authenticate(db_session, email="alice@example.com", password="nope")
        db_session.refresh(u)
        assert u.failed_login_attempts == 3

        login.authenticate(
            db_session, email="alice@example.com", password="correct horse battery staple"
        )
        db_session.refresh(u)
        assert u.failed_login_attempts == 0
        assert u.locked_until is None


def test_auth_events_emitted(db_session, make_user):
    make_user()
    with pytest.raises(AuthError):
        login.authenticate(db_session, email="alice@example.com", password="wrong")
    events = list(db_session.execute(select(AuthEvent)).scalars())
    assert any(e.event_type == "login_failure" for e in events)
```

- [ ] **Step 2: Run the failing test**

Run: `uv run pytest packages/server/tests/test_services/test_auth/test_login.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement login.py**

Create `packages/server/src/openlia_server/services/auth/login.py`:

```python
"""Login + lockout state machine.

`authenticate` is the single entry point: it verifies credentials, applies the
lockout policy (if enabled in config_store), and emits auth events. Session
issuance is left to the caller so the route handler can set the cookie.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

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
        # Pad timing against real verify.
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
    if lockout_enabled and user.locked_until is not None and user.locked_until > datetime.now(timezone.utc):
        retry = int((user.locked_until - datetime.now(timezone.utc)).total_seconds())
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
                user.locked_until = datetime.now(timezone.utc) + LOCKOUT_DURATION
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
    user.last_login_at = datetime.now(timezone.utc)
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
        return True  # default on
    value = row.value or {}
    return bool(value.get("enabled", True))
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/server/tests/test_services/test_auth/test_login.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/services/auth/login.py \
        packages/server/tests/test_services/test_auth/test_login.py
git commit -m "phase-2(auth): login + 5/15 lockout gated by config_store"
```

---

## Task 11: Password reset flows (`services/auth/password_reset.py`)

**Files:**
- Create: `packages/server/src/openlia_server/services/auth/password_reset.py`
- Create: `packages/server/tests/test_services/test_auth/test_password_reset.py`

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_services/test_auth/test_password_reset.py`:

```python
"""Tests for services.auth.password_reset — request/approve/reject/consume, change_password."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from openlia_server.db.models.auth import PasswordResetRequest, User
from openlia_server.services.auth import password_reset, sessions
from openlia_server.services.auth.errors import AuthError


class TestRequestReset:
    def test_creates_pending_row(self, db_session, make_user):
        u = make_user()
        password_reset.request_reset(db_session, email="alice@example.com", ip_address="1.1.1.1")
        row = db_session.execute(select(PasswordResetRequest)).scalar_one()
        assert row.user_id == u.id
        assert row.status == "pending"
        assert row.token_hash is None

    def test_unknown_email_is_silent(self, db_session):
        # Must not raise; returns normally.
        password_reset.request_reset(db_session, email="nobody@example.com")
        rows = list(db_session.execute(select(PasswordResetRequest)).scalars())
        assert rows == []

    def test_second_request_replaces_pending(self, db_session, make_user):
        make_user()
        password_reset.request_reset(db_session, email="alice@example.com")
        password_reset.request_reset(db_session, email="alice@example.com")
        pending = list(
            db_session.execute(
                select(PasswordResetRequest).where(PasswordResetRequest.status == "pending")
            ).scalars()
        )
        assert len(pending) == 1


class TestApproveReject:
    def test_approve_generates_single_use_token(self, db_session, make_user):
        u = make_user()
        admin = make_user(email="admin@example.com", is_admin=True)
        password_reset.request_reset(db_session, email="alice@example.com")
        req = db_session.execute(select(PasswordResetRequest)).scalar_one()

        raw = password_reset.approve_request(db_session, request_id=req.id, admin_user_id=admin.id)
        assert len(raw) > 40
        db_session.refresh(req)
        assert req.status == "approved"
        assert req.token_hash is not None
        assert req.expires_at is not None
        assert req.approved_by_user_id == admin.id

    def test_reject_marks_rejected(self, db_session, make_user):
        u = make_user()
        admin = make_user(email="admin@example.com", is_admin=True)
        password_reset.request_reset(db_session, email="alice@example.com")
        req = db_session.execute(select(PasswordResetRequest)).scalar_one()

        password_reset.reject_request(db_session, request_id=req.id, admin_user_id=admin.id)
        db_session.refresh(req)
        assert req.status == "rejected"


class TestConsume:
    def test_happy_path_updates_password_and_revokes_sessions(self, db_session, make_user):
        u = make_user()
        admin = make_user(email="admin@example.com", is_admin=True)
        old_hash = u.password_hash

        # Give the user a live session first.
        s = sessions.create_session(db_session, user_id=u.id, persistent=True)

        password_reset.request_reset(db_session, email="alice@example.com")
        req = db_session.execute(select(PasswordResetRequest)).scalar_one()
        token = password_reset.approve_request(db_session, request_id=req.id, admin_user_id=admin.id)

        password_reset.consume_token(db_session, token=token, new_password="new-strong-password")

        db_session.refresh(u)
        assert u.password_hash != old_hash
        assert sessions.validate_session(db_session, s.raw_token) is None

    def test_expired_token_rejected(self, db_session, make_user):
        u = make_user()
        admin = make_user(email="admin@example.com", is_admin=True)
        password_reset.request_reset(db_session, email="alice@example.com")
        req = db_session.execute(select(PasswordResetRequest)).scalar_one()
        token = password_reset.approve_request(db_session, request_id=req.id, admin_user_id=admin.id)

        req.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
        db_session.commit()

        with pytest.raises(AuthError) as exc:
            password_reset.consume_token(db_session, token=token, new_password="new-strong-password")
        assert exc.value.code == "token_expired"

    def test_unknown_token_rejected(self, db_session):
        with pytest.raises(AuthError) as exc:
            password_reset.consume_token(db_session, token="nope", new_password="new-strong-password")
        assert exc.value.code == "token_invalid"

    def test_consumed_token_cannot_replay(self, db_session, make_user):
        u = make_user()
        admin = make_user(email="admin@example.com", is_admin=True)
        password_reset.request_reset(db_session, email="alice@example.com")
        req = db_session.execute(select(PasswordResetRequest)).scalar_one()
        token = password_reset.approve_request(db_session, request_id=req.id, admin_user_id=admin.id)

        password_reset.consume_token(db_session, token=token, new_password="new-strong-password")
        with pytest.raises(AuthError):
            password_reset.consume_token(db_session, token=token, new_password="other-strong-password")


class TestAdminDirectReset:
    def test_sets_must_change_and_revokes_sessions(self, db_session, make_user):
        u = make_user()
        admin = make_user(email="admin@example.com", is_admin=True)
        s = sessions.create_session(db_session, user_id=u.id, persistent=True)

        password_reset.admin_direct_reset(
            db_session, user_id=u.id, new_password="temp-password-here", admin_user_id=admin.id
        )
        db_session.refresh(u)
        assert u.must_change_password is True
        assert sessions.validate_session(db_session, s.raw_token) is None


class TestChangePassword:
    def test_requires_current_password(self, db_session, make_user):
        u = make_user()
        with pytest.raises(AuthError):
            password_reset.change_password(
                db_session,
                user_id=u.id,
                current_password="wrong",
                new_password="new-strong-password",
            )

    def test_clears_must_change_flag(self, db_session, make_user):
        u = make_user()
        u.must_change_password = True
        db_session.commit()
        password_reset.change_password(
            db_session,
            user_id=u.id,
            current_password="correct horse battery staple",
            new_password="new-strong-password",
        )
        db_session.refresh(u)
        assert u.must_change_password is False
```

- [ ] **Step 2: Run the failing test**

Run: `uv run pytest packages/server/tests/test_services/test_auth/test_password_reset.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement password_reset.py**

Create `packages/server/src/openlia_server/services/auth/password_reset.py`:

```python
"""Admin-approved password reset + direct admin reset + self-serve change."""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.models.auth import PasswordResetRequest, User
from openlia_server.services.auth import events, passwords, registration, sessions, tokens
from openlia_server.services.auth.errors import AuthError

APPROVED_TTL = timedelta(hours=24)


class TokenInvalidError(AuthError):
    code = "token_invalid"


class TokenExpiredError(AuthError):
    code = "token_expired"


def request_reset(db: DBSession, *, email: str, ip_address: str | None = None) -> None:
    """Create a pending reset request. Silent no-op if the email is unknown."""
    email_norm = registration.normalize_email(email)
    user = db.execute(select(User).where(User.email == email_norm)).scalar_one_or_none()
    if user is None or user.is_disabled:
        return

    db.execute(
        delete(PasswordResetRequest).where(
            PasswordResetRequest.user_id == user.id,
            PasswordResetRequest.status == "pending",
        )
    )
    db.add(
        PasswordResetRequest(
            id=str(uuid.uuid4()),
            user_id=user.id,
            status="pending",
            requested_at=datetime.now(timezone.utc),
            requested_ip=ip_address,
        )
    )
    db.commit()
    events.log_auth_event(
        db,
        event_type="password_reset_requested",
        user_id=user.id,
        ip_address=ip_address,
    )


def approve_request(db: DBSession, *, request_id: str, admin_user_id: str) -> str:
    """Generate a one-time token for an admin to deliver. Returns the raw token."""
    req = db.get(PasswordResetRequest, request_id)
    if req is None or req.status != "pending":
        raise TokenInvalidError("Request not found or not pending.")

    raw = tokens.generate_opaque_token()
    req.token_hash = tokens.hash_token(raw)
    req.expires_at = datetime.now(timezone.utc) + APPROVED_TTL
    req.status = "approved"
    req.approved_by_user_id = admin_user_id
    req.approved_at = datetime.now(timezone.utc)
    db.commit()

    events.log_auth_event(
        db,
        event_type="password_reset_approved",
        user_id=req.user_id,
        actor_user_id=admin_user_id,
    )
    return raw


def reject_request(db: DBSession, *, request_id: str, admin_user_id: str) -> None:
    req = db.get(PasswordResetRequest, request_id)
    if req is None or req.status != "pending":
        raise TokenInvalidError("Request not found or not pending.")
    req.status = "rejected"
    db.commit()
    events.log_auth_event(
        db,
        event_type="password_reset_rejected",
        user_id=req.user_id,
        actor_user_id=admin_user_id,
    )


def consume_token(db: DBSession, *, token: str, new_password: str) -> None:
    passwords.validate_password_policy(new_password)
    hashed = tokens.hash_token(token)
    req = db.execute(
        select(PasswordResetRequest).where(PasswordResetRequest.token_hash == hashed)
    ).scalar_one_or_none()
    if req is None or req.status != "approved":
        raise TokenInvalidError("Reset token is invalid.")

    now = datetime.now(timezone.utc)
    if req.expires_at is None or req.expires_at <= now:
        req.status = "expired"
        db.commit()
        raise TokenExpiredError("Reset token has expired.")

    user = db.get(User, req.user_id)
    assert user is not None  # FK guarantees this

    user.password_hash = passwords.hash_password(new_password)
    user.must_change_password = False
    user.failed_login_attempts = 0
    user.locked_until = None
    user.updated_at = now

    req.status = "consumed"
    req.consumed_at = now

    db.commit()
    sessions.revoke_all_sessions(db, user_id=user.id)

    events.log_auth_event(
        db,
        event_type="password_reset_consumed",
        user_id=user.id,
        actor_user_id=user.id,
    )


def admin_direct_reset(
    db: DBSession, *, user_id: str, new_password: str, admin_user_id: str
) -> None:
    passwords.validate_password_policy(new_password)
    user = db.get(User, user_id)
    if user is None:
        raise TokenInvalidError("User not found.")

    user.password_hash = passwords.hash_password(new_password)
    user.must_change_password = True
    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    sessions.revoke_all_sessions(db, user_id=user.id)

    events.log_auth_event(
        db,
        event_type="password_reset_by_admin",
        user_id=user.id,
        actor_user_id=admin_user_id,
    )


def change_password(
    db: DBSession, *, user_id: str, current_password: str, new_password: str
) -> None:
    passwords.validate_password_policy(new_password)
    user = db.get(User, user_id)
    if user is None or not passwords.verify_password(user.password_hash, current_password):
        raise AuthError("Current password is incorrect.", code="invalid_credentials")

    user.password_hash = passwords.hash_password(new_password)
    user.must_change_password = False
    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    events.log_auth_event(db, event_type="password_changed", user_id=user.id, actor_user_id=user.id)
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/server/tests/test_services/test_auth/test_password_reset.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/services/auth/password_reset.py \
        packages/server/tests/test_services/test_auth/test_password_reset.py
git commit -m "phase-2(auth): password reset request/approve/consume + admin direct reset"
```

---

## Task 12: Rate limiter middleware (`middleware/rate_limit.py`)

**Files:**
- Create: `packages/server/src/openlia_server/middleware/__init__.py`
- Create: `packages/server/src/openlia_server/middleware/rate_limit.py`
- Create: `packages/server/tests/test_middleware/__init__.py`
- Create: `packages/server/tests/test_middleware/test_rate_limit.py`

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_middleware/test_rate_limit.py`:

```python
"""Tests for middleware.rate_limit — sliding-window counters."""
from __future__ import annotations

import time

import pytest

from openlia_server.middleware.rate_limit import SlidingWindowLimiter


class TestSlidingWindow:
    def test_allows_under_limit(self):
        lim = SlidingWindowLimiter()
        for _ in range(5):
            assert lim.check_and_tick("key", limit=5, window_seconds=60) is True

    def test_blocks_over_limit(self):
        lim = SlidingWindowLimiter()
        for _ in range(5):
            lim.check_and_tick("k", limit=5, window_seconds=60)
        assert lim.check_and_tick("k", limit=5, window_seconds=60) is False

    def test_window_resets_after_expiry(self, monkeypatch):
        lim = SlidingWindowLimiter()
        base = [1000.0]
        monkeypatch.setattr("openlia_server.middleware.rate_limit.time.monotonic", lambda: base[0])

        for _ in range(5):
            lim.check_and_tick("k", limit=5, window_seconds=60)
        base[0] += 61
        assert lim.check_and_tick("k", limit=5, window_seconds=60) is True

    def test_separate_keys_isolated(self):
        lim = SlidingWindowLimiter()
        for _ in range(5):
            lim.check_and_tick("a", limit=5, window_seconds=60)
        assert lim.check_and_tick("a", limit=5, window_seconds=60) is False
        assert lim.check_and_tick("b", limit=5, window_seconds=60) is True
```

- [ ] **Step 2: Run the failing test**

Run: `uv run pytest packages/server/tests/test_middleware/test_rate_limit.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement the limiter**

Create `packages/server/src/openlia_server/middleware/__init__.py` (empty).

Create `packages/server/src/openlia_server/middleware/rate_limit.py`:

```python
"""In-process sliding-window rate limiter.

Keyed on (route_family, identifier). Single-instance deployment only — see
AccountManagementSpec §8.3. Not safe across multiple uvicorn workers; v1
assumes a single worker and single instance.
"""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque
from typing import Final


class SlidingWindowLimiter:
    def __init__(self) -> None:
        self._windows: dict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def check_and_tick(self, key: str, *, limit: int, window_seconds: int) -> bool:
        """Return True if this tick is allowed, False if over the limit."""
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            bucket = self._windows[key]
            while bucket and bucket[0] < cutoff:
                bucket.popleft()
            if len(bucket) >= limit:
                return False
            bucket.append(now)
            return True

    def clear(self) -> None:
        with self._lock:
            self._windows.clear()


# Shared process-wide limiter for routes/auth.py and routes/admin.py.
LIMITS: Final[dict[str, tuple[int, int]]] = {
    "login_ip": (20, 5 * 60),
    "login_email": (10, 5 * 60),
    "password_reset_ip": (5, 60 * 60),
    "register_ip": (5, 60 * 60),
}


_limiter = SlidingWindowLimiter()


def limiter() -> SlidingWindowLimiter:
    return _limiter
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/server/tests/test_middleware/test_rate_limit.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/middleware \
        packages/server/tests/test_middleware
git commit -m "phase-2(auth): in-process sliding-window rate limiter"
```

---

## Task 13: `require_auth` dependency + personal-mode shim (`middleware/auth.py`)

**Files:**
- Create: `packages/server/src/openlia_server/middleware/auth.py`
- Create: `packages/server/tests/test_middleware/test_auth.py`

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_middleware/test_auth.py`:

```python
"""Tests for middleware.auth — require_auth, personal-mode shim."""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from openlia_server.middleware.auth import COOKIE_NAME, build_require_auth
from openlia_server.services.auth import sessions


@pytest.fixture
def app_factory(db_session):
    def _make(mode: str) -> FastAPI:
        app = FastAPI()
        require_auth = build_require_auth(db_session_factory=lambda: db_session, mode=mode)

        @app.get("/whoami")
        def whoami(user=require_auth):  # type: ignore[assignment]
            return {"id": user.id, "email": user.email, "is_admin": user.is_admin}

        return app

    return _make


class TestCompanyMode:
    def test_401_without_cookie(self, app_factory):
        client = TestClient(app_factory("company"))
        resp = client.get("/whoami")
        assert resp.status_code == 401

    def test_401_with_invalid_cookie(self, app_factory):
        client = TestClient(app_factory("company"))
        client.cookies.set(COOKIE_NAME, "not-a-token")
        resp = client.get("/whoami")
        assert resp.status_code == 401

    def test_200_with_valid_session(self, app_factory, db_session, make_user):
        user = make_user()
        created = sessions.create_session(db_session, user_id=user.id, persistent=True)

        client = TestClient(app_factory("company"))
        client.cookies.set(COOKIE_NAME, created.raw_token)
        resp = client.get("/whoami")
        assert resp.status_code == 200
        assert resp.json()["id"] == user.id


class TestPersonalMode:
    def test_no_cookie_still_resolves_to_local_user(self, app_factory, db_session, make_user):
        # Personal mode seeds a `local` user via bootstrap. Seed manually for tests.
        make_user(email="local@openlia.local", password=None, is_admin=True)

        client = TestClient(app_factory("personal"))
        resp = client.get("/whoami")
        assert resp.status_code == 200
        data = resp.json()
        assert data["email"] == "local@openlia.local"
        assert data["is_admin"] is True

    def test_sessions_table_not_consulted(self, app_factory, db_session, make_user):
        # Even if there are no sessions, personal mode returns local.
        make_user(email="local@openlia.local", password=None, is_admin=True)
        client = TestClient(app_factory("personal"))
        resp = client.get("/whoami")
        assert resp.status_code == 200
```

- [ ] **Step 2: Run the failing test**

Run: `uv run pytest packages/server/tests/test_middleware/test_auth.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement middleware/auth.py**

Create `packages/server/src/openlia_server/middleware/auth.py`:

```python
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
```

- [ ] **Step 4: Run the tests**

Run: `uv run pytest packages/server/tests/test_middleware/test_auth.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/middleware/auth.py \
        packages/server/tests/test_middleware/test_auth.py
git commit -m "phase-2(auth): require_auth + require_admin with personal-mode shim"
```

---

## Task 14: Auth routes (`routes/auth.py`)

**Files:**
- Create: `packages/server/src/openlia_server/routes/__init__.py`
- Create: `packages/server/src/openlia_server/routes/auth.py`
- Create: `packages/server/tests/test_routes/__init__.py`
- Create: `packages/server/tests/test_routes/conftest.py`
- Create: `packages/server/tests/test_routes/test_auth_routes.py`

- [ ] **Step 1: Create the routes conftest**

Create `packages/server/tests/test_routes/conftest.py`:

```python
"""Fixtures for HTTP-level route tests (company mode app)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from openlia_server.app import create_app


@pytest.fixture
def company_client(db_session, monkeypatch):
    monkeypatch.setenv("OPENLIA_MODE", "company")
    # Inject the test DB session into the app factory via dependency override.
    app = create_app(db_session_factory=lambda: db_session)
    return TestClient(app)


@pytest.fixture
def personal_client(db_session, make_user, monkeypatch):
    make_user(email="local@openlia.local", password=None, is_admin=True)
    monkeypatch.setenv("OPENLIA_MODE", "personal")
    app = create_app(db_session_factory=lambda: db_session)
    return TestClient(app)
```

The `create_app(db_session_factory=...)` signature is extended in Task 16. For now, this file will fail to import until that task lands — that's expected. We sequence the routes tasks before app wiring so the routes themselves can be unit-tested with their own `TestClient(app)` instances; the shared conftest above lands with the full integration test.

- [ ] **Step 2: Write the failing test**

Create `packages/server/tests/test_routes/test_auth_routes.py`:

```python
"""Integration tests for /auth/* — registration, login, logout, session."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from openlia_server.db.models.auth import SignupInvite
from openlia_server.middleware.auth import COOKIE_NAME


@pytest.fixture
def seeded_invite(db_session):
    row = SignupInvite(
        id="inv-1",
        token="valid-invite",
        created_at=datetime.now(timezone.utc),
    )
    db_session.add(row)
    db_session.commit()
    return row


class TestRegisterLoginLogout:
    def test_full_cycle(self, company_client: TestClient, seeded_invite):
        resp = company_client.post(
            "/auth/register",
            json={
                "email": "alice@example.com",
                "password": "correct-horse-battery-staple",
                "display_name": "Alice",
                "invite_token": "valid-invite",
            },
        )
        assert resp.status_code == 201
        assert COOKIE_NAME in resp.cookies

        resp = company_client.get("/auth/session")
        assert resp.status_code == 200
        assert resp.json()["email"] == "alice@example.com"

        resp = company_client.post("/auth/logout")
        assert resp.status_code == 204

        resp = company_client.get("/auth/session")
        assert resp.status_code == 401

    def test_login_with_keep_me_signed_in(self, company_client: TestClient, seeded_invite):
        company_client.post(
            "/auth/register",
            json={
                "email": "alice@example.com",
                "password": "correct-horse-battery-staple",
                "display_name": "Alice",
                "invite_token": "valid-invite",
            },
        )
        company_client.post("/auth/logout")

        resp = company_client.post(
            "/auth/login",
            json={
                "email": "alice@example.com",
                "password": "correct-horse-battery-staple",
                "persistent": True,
            },
        )
        assert resp.status_code == 200
        cookie = company_client.cookies.jar._cookies["testserver.local"]["/"][COOKIE_NAME]  # noqa: SLF001
        assert cookie.expires is not None  # persistent cookie

    def test_login_invalid_credentials(self, company_client: TestClient, seeded_invite):
        resp = company_client.post(
            "/auth/login",
            json={"email": "nobody@example.com", "password": "nope", "persistent": False},
        )
        assert resp.status_code == 401
        body = resp.json()
        assert body["code"] == "invalid_credentials"


class TestSignupPolicyEndpoint:
    def test_returns_mode(self, company_client: TestClient):
        resp = company_client.get("/auth/signup-policy")
        assert resp.status_code == 200
        data = resp.json()
        assert data["mode"] == "invite_only"
        assert data["invite_required"] is True


class TestRegisterErrors:
    def test_without_invite(self, company_client: TestClient):
        resp = company_client.post(
            "/auth/register",
            json={
                "email": "alice@example.com",
                "password": "correct-horse-battery-staple",
                "display_name": "Alice",
            },
        )
        assert resp.status_code == 403
        assert resp.json()["code"] == "invite_required"

    def test_weak_password(self, company_client: TestClient, seeded_invite):
        resp = company_client.post(
            "/auth/register",
            json={
                "email": "alice@example.com",
                "password": "short",
                "display_name": "Alice",
                "invite_token": "valid-invite",
            },
        )
        assert resp.status_code == 400
        assert resp.json()["code"] == "weak_password"


class TestPasswordResetFlow:
    def test_request_always_200(self, company_client: TestClient):
        resp = company_client.post(
            "/auth/password-reset/request", json={"email": "nobody@example.com"}
        )
        assert resp.status_code == 200


class TestPersonalModeNoAuthRoutes:
    def test_register_returns_404(self, personal_client: TestClient):
        resp = personal_client.post(
            "/auth/register",
            json={
                "email": "x@y.z",
                "password": "12345678",
                "display_name": "X",
                "invite_token": "x",
            },
        )
        assert resp.status_code == 404

    def test_session_resolves_local(self, personal_client: TestClient):
        resp = personal_client.get("/auth/session")
        # In personal mode, /auth/session is not mounted either. 404 expected.
        assert resp.status_code == 404
```

- [ ] **Step 3: Run the failing test**

Run: `uv run pytest packages/server/tests/test_routes/test_auth_routes.py -v`
Expected: ImportError on `openlia_server.app.create_app` (Task 16) or `openlia_server.routes.auth` (this task).

- [ ] **Step 4: Implement routes/auth.py**

Create `packages/server/src/openlia_server/routes/__init__.py` (empty).

Create `packages/server/src/openlia_server/routes/auth.py`:

```python
"""Company-mode auth HTTP surface.

Routes are mounted only when `OPENLIA_MODE == company`. The shared app factory
(see `app.py`) gates inclusion. In personal mode these paths return 404.
"""
from __future__ import annotations

import os
from typing import Callable

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy.orm import Session as DBSession

from openlia_server.middleware.auth import COOKIE_NAME, build_require_auth
from openlia_server.middleware.rate_limit import LIMITS, limiter
from openlia_server.services.auth import (
    login as login_service,
    password_reset as reset_service,
    registration,
    sessions,
    signup_policy,
)
from openlia_server.services.auth.errors import AuthError


def build_auth_router(*, db_session_factory: Callable[[], DBSession]) -> APIRouter:
    router = APIRouter(prefix="/auth")
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode="company")

    class RegisterIn(BaseModel):
        email: EmailStr
        password: str = Field(min_length=1)
        display_name: str = Field(min_length=1, max_length=128)
        invite_token: str | None = None

    class LoginIn(BaseModel):
        email: EmailStr
        password: str
        persistent: bool = False

    class PasswordResetRequestIn(BaseModel):
        email: EmailStr

    class PasswordResetConsumeIn(BaseModel):
        token: str
        new_password: str

    class ChangePasswordIn(BaseModel):
        current_password: str
        new_password: str

    def _cookie_secure() -> bool:
        default = "true"  # company-mode default
        return os.environ.get("OPENLIA_COOKIE_SECURE", default).lower() in ("1", "true", "yes")

    def _ip(request: Request) -> str | None:
        if os.environ.get("OPENLIA_TRUST_PROXY_HEADERS", "false").lower() in ("1", "true", "yes"):
            fwd = request.headers.get("x-forwarded-for")
            if fwd:
                return fwd.split(",")[0].strip()
        return request.client.host if request.client else None

    @router.post("/register", status_code=201)
    def register(body: RegisterIn, request: Request, response: Response):
        ip = _ip(request)
        rl_limit, rl_window = LIMITS["register_ip"]
        if not limiter().check_and_tick(f"register_ip:{ip}", limit=rl_limit, window_seconds=rl_window):
            raise HTTPException(status_code=429, detail={"code": "rate_limited", "message": "Too many requests."})

        db = db_session_factory()
        try:
            user = registration.register(
                db,
                email=body.email,
                password=body.password,
                display_name=body.display_name,
                invite_token=body.invite_token,
            )
        except AuthError as exc:
            raise HTTPException(
                status_code=_status_for(exc.code),
                detail={"code": exc.code, "message": str(exc)},
            )

        created = sessions.create_session(
            db,
            user_id=user.id,
            persistent=False,
            user_agent=request.headers.get("user-agent"),
            ip_address=ip,
        )
        _set_cookie(response, created.raw_token, persistent=False, secure=_cookie_secure())
        return {"user_id": user.id, "email": user.email, "display_name": user.display_name}

    @router.post("/login")
    def login(body: LoginIn, request: Request, response: Response):
        ip = _ip(request)
        lim = limiter()
        ip_limit, ip_window = LIMITS["login_ip"]
        email_limit, email_window = LIMITS["login_email"]
        if not lim.check_and_tick(f"login_ip:{ip}", limit=ip_limit, window_seconds=ip_window):
            raise HTTPException(status_code=429, detail={"code": "rate_limited"})
        if not lim.check_and_tick(f"login_email:{body.email.lower()}", limit=email_limit, window_seconds=email_window):
            raise HTTPException(status_code=429, detail={"code": "rate_limited"})

        db = db_session_factory()
        try:
            auth = login_service.authenticate(
                db,
                email=body.email,
                password=body.password,
                ip_address=ip,
                user_agent=request.headers.get("user-agent"),
            )
        except login_service.AccountLockedError as exc:
            raise HTTPException(
                status_code=423,
                detail={
                    "code": "account_locked",
                    "retry_after_seconds": exc.retry_after_seconds,
                },
            )
        except AuthError as exc:
            raise HTTPException(
                status_code=_status_for(exc.code),
                detail={"code": exc.code, "message": str(exc)},
            )

        created = sessions.create_session(
            db,
            user_id=auth.user.id,
            persistent=body.persistent,
            user_agent=request.headers.get("user-agent"),
            ip_address=ip,
        )
        _set_cookie(response, created.raw_token, persistent=body.persistent, secure=_cookie_secure())
        return {
            "user_id": auth.user.id,
            "email": auth.user.email,
            "display_name": auth.user.display_name,
            "is_admin": auth.user.is_admin,
            "must_change_password": auth.must_change_password,
        }

    @router.post("/logout", status_code=204)
    def logout(
        response: Response,
        openlia_session: str | None = Cookie(default=None, alias=COOKIE_NAME),
    ):
        if openlia_session:
            db = db_session_factory()
            validated = sessions.validate_session(db, openlia_session)
            if validated is not None:
                sessions.revoke_session(db, validated.session.id)
        response.delete_cookie(COOKIE_NAME, path="/")
        return Response(status_code=204)

    @router.post("/logout-all", status_code=204)
    def logout_all(response: Response, user=require_auth):
        db = db_session_factory()
        sessions.revoke_all_sessions(db, user_id=user.id)
        response.delete_cookie(COOKIE_NAME, path="/")
        return Response(status_code=204)

    @router.get("/session")
    def get_session(user=require_auth):
        return {
            "user_id": user.id,
            "email": user.email,
            "display_name": user.display_name,
            "is_admin": user.is_admin,
        }

    @router.get("/signup-policy")
    def get_signup_policy():
        db = db_session_factory()
        policy = signup_policy.get_policy(db)
        return {
            "mode": policy.mode,
            "invite_required": policy.mode == "invite_only",
        }

    @router.post("/password-reset/request")
    def password_reset_request(body: PasswordResetRequestIn, request: Request):
        ip = _ip(request)
        rl_limit, rl_window = LIMITS["password_reset_ip"]
        if not limiter().check_and_tick(
            f"password_reset_ip:{ip}", limit=rl_limit, window_seconds=rl_window
        ):
            raise HTTPException(status_code=429, detail={"code": "rate_limited"})

        db = db_session_factory()
        reset_service.request_reset(db, email=body.email, ip_address=ip)
        return {"status": "ok"}

    @router.post("/password-reset/consume")
    def password_reset_consume(body: PasswordResetConsumeIn):
        db = db_session_factory()
        try:
            reset_service.consume_token(db, token=body.token, new_password=body.new_password)
        except AuthError as exc:
            raise HTTPException(
                status_code=_status_for(exc.code),
                detail={"code": exc.code, "message": str(exc)},
            )
        return {"status": "ok"}

    @router.post("/change-password")
    def change_password(body: ChangePasswordIn, user=require_auth):
        db = db_session_factory()
        try:
            reset_service.change_password(
                db,
                user_id=user.id,
                current_password=body.current_password,
                new_password=body.new_password,
            )
        except AuthError as exc:
            raise HTTPException(
                status_code=_status_for(exc.code),
                detail={"code": exc.code, "message": str(exc)},
            )
        return {"status": "ok"}

    return router


def _set_cookie(response: Response, raw_token: str, *, persistent: bool, secure: bool) -> None:
    response.set_cookie(
        key=COOKIE_NAME,
        value=raw_token,
        max_age=sessions.PERSISTENT_TTL.total_seconds() if persistent else None,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )


_STATUS_MAP = {
    "invalid_credentials": 401,
    "account_disabled": 403,
    "account_locked": 423,
    "rate_limited": 429,
    "signup_closed": 403,
    "invite_required": 403,
    "invite_invalid": 403,
    "weak_password": 400,
    "email_in_use": 409,
    "email_domain_not_allowed": 403,
    "registration_failed": 400,
    "token_invalid": 400,
    "token_expired": 410,
    "must_change_password": 200,
}


def _status_for(code: str) -> int:
    return _STATUS_MAP.get(code, 400)
```

- [ ] **Step 5: Defer running tests**

The routes tests cannot pass until Task 16 wires `create_app` to mount this router. Leave them red for now; mark this task as "implementer-wise done" once lint is clean.

Run: `uv run ruff check packages/server/src/openlia_server/routes/auth.py`
Expected: no errors.

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/routes/__init__.py \
        packages/server/src/openlia_server/routes/auth.py \
        packages/server/tests/test_routes
git commit -m "phase-2(auth): /auth/* routes (register, login, logout, reset, change)"
```

---

## Task 15: Admin routes (`routes/admin.py`)

**Files:**
- Create: `packages/server/src/openlia_server/routes/admin.py`
- Create: `packages/server/tests/test_routes/test_admin_routes.py`

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_routes/test_admin_routes.py`:

```python
"""Integration tests for /admin/* invites, users, reset-requests."""
from __future__ import annotations

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from openlia_server.db.models.auth import PasswordResetRequest, SignupInvite
from openlia_server.middleware.auth import COOKIE_NAME
from openlia_server.services.auth import sessions


@pytest.fixture
def admin_cookie(db_session, make_user, company_client: TestClient):
    admin = make_user(email="admin@example.com", is_admin=True)
    created = sessions.create_session(db_session, user_id=admin.id, persistent=True)
    company_client.cookies.set(COOKIE_NAME, created.raw_token)
    return company_client


class TestInvites:
    def test_create_and_list(self, admin_cookie: TestClient):
        resp = admin_cookie.post("/admin/invites", json={"label": "Q2", "max_uses": 5})
        assert resp.status_code == 201
        token = resp.json()["token"]
        assert token

        resp = admin_cookie.get("/admin/invites")
        assert resp.status_code == 200
        invites = resp.json()
        assert len(invites) == 1
        assert invites[0]["label"] == "Q2"

    def test_revoke(self, admin_cookie: TestClient, db_session):
        invite = SignupInvite(id="inv-x", token="tok-x", created_at=datetime.now(timezone.utc))
        db_session.add(invite)
        db_session.commit()
        resp = admin_cookie.post(f"/admin/invites/{invite.id}/revoke")
        assert resp.status_code == 204
        db_session.refresh(invite)
        assert invite.revoked_at is not None

    def test_non_admin_rejected(self, company_client: TestClient, make_user, db_session):
        user = make_user()
        created = sessions.create_session(db_session, user_id=user.id, persistent=True)
        company_client.cookies.set(COOKIE_NAME, created.raw_token)
        resp = company_client.get("/admin/invites")
        assert resp.status_code == 403


class TestPasswordResetRequests:
    def test_list_approve(self, admin_cookie: TestClient, db_session, make_user):
        user = make_user(email="alice@example.com")
        req = PasswordResetRequest(
            id="req-1",
            user_id=user.id,
            status="pending",
            requested_at=datetime.now(timezone.utc),
        )
        db_session.add(req)
        db_session.commit()

        resp = admin_cookie.get("/admin/password-reset-requests")
        assert resp.status_code == 200
        assert len(resp.json()) == 1

        resp = admin_cookie.post(f"/admin/password-reset-requests/{req.id}/approve")
        assert resp.status_code == 200
        body = resp.json()
        assert body["reset_token"]  # one-time shown exactly once

    def test_reject(self, admin_cookie: TestClient, db_session, make_user):
        user = make_user(email="alice@example.com")
        req = PasswordResetRequest(
            id="req-2",
            user_id=user.id,
            status="pending",
            requested_at=datetime.now(timezone.utc),
        )
        db_session.add(req)
        db_session.commit()

        resp = admin_cookie.post(f"/admin/password-reset-requests/{req.id}/reject")
        assert resp.status_code == 204
        db_session.refresh(req)
        assert req.status == "rejected"


class TestUserManagement:
    def test_list(self, admin_cookie: TestClient, make_user):
        make_user(email="alice@example.com")
        resp = admin_cookie.get("/admin/users")
        assert resp.status_code == 200
        emails = {u["email"] for u in resp.json()}
        assert "alice@example.com" in emails
        assert "admin@example.com" in emails

    def test_disable_and_enable(self, admin_cookie: TestClient, make_user, db_session):
        alice = make_user(email="alice@example.com")
        resp = admin_cookie.post(f"/admin/users/{alice.id}/disable")
        assert resp.status_code == 204
        db_session.refresh(alice)
        assert alice.is_disabled is True

        resp = admin_cookie.post(f"/admin/users/{alice.id}/enable")
        assert resp.status_code == 204
        db_session.refresh(alice)
        assert alice.is_disabled is False

    def test_direct_reset_password(self, admin_cookie: TestClient, make_user, db_session):
        alice = make_user(email="alice@example.com")
        resp = admin_cookie.post(
            f"/admin/users/{alice.id}/reset-password",
            json={"new_password": "temp-strong-password"},
        )
        assert resp.status_code == 204
        db_session.refresh(alice)
        assert alice.must_change_password is True
```

- [ ] **Step 2: Run the failing test**

Run: `uv run pytest packages/server/tests/test_routes/test_admin_routes.py -v`
Expected: ImportError on `routes.admin` or `app.create_app`.

- [ ] **Step 3: Implement routes/admin.py**

Create `packages/server/src/openlia_server/routes/admin.py`:

```python
"""Admin HTTP surface for invite + user + reset-request management."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Callable

from fastapi import APIRouter, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.models.auth import PasswordResetRequest, SignupInvite, User
from openlia_server.middleware.auth import build_require_admin
from openlia_server.services.auth import password_reset as reset_service, sessions, tokens
from openlia_server.services.auth.errors import AuthError


def build_admin_router(*, db_session_factory: Callable[[], DBSession]) -> APIRouter:
    router = APIRouter(prefix="/admin")
    require_admin = build_require_admin(db_session_factory=db_session_factory, mode="company")

    class CreateInviteIn(BaseModel):
        label: str | None = None
        max_uses: int | None = Field(default=None, ge=1)
        expires_at: datetime | None = None

    class DirectResetIn(BaseModel):
        new_password: str

    @router.get("/invites")
    def list_invites(admin=require_admin):
        db = db_session_factory()
        rows = list(db.execute(select(SignupInvite).order_by(SignupInvite.created_at.desc())).scalars())
        return [
            {
                "id": r.id,
                "token": r.token,
                "label": r.label,
                "use_count": r.use_count,
                "max_uses": r.max_uses,
                "expires_at": r.expires_at,
                "revoked_at": r.revoked_at,
                "created_at": r.created_at,
            }
            for r in rows
        ]

    @router.post("/invites", status_code=201)
    def create_invite(body: CreateInviteIn, admin=require_admin):
        db = db_session_factory()
        invite = SignupInvite(
            id=str(uuid.uuid4()),
            token=tokens.generate_opaque_token(),
            label=body.label,
            max_uses=body.max_uses,
            use_count=0,
            expires_at=body.expires_at,
            created_by_user_id=admin.id,
            created_at=datetime.now(timezone.utc),
        )
        db.add(invite)
        db.commit()
        db.refresh(invite)
        return {"id": invite.id, "token": invite.token, "label": invite.label}

    @router.post("/invites/{invite_id}/revoke", status_code=204)
    def revoke_invite(invite_id: str, admin=require_admin):
        db = db_session_factory()
        invite = db.get(SignupInvite, invite_id)
        if invite is None:
            raise HTTPException(status_code=404)
        if invite.revoked_at is None:
            invite.revoked_at = datetime.now(timezone.utc)
            db.commit()
        return Response(status_code=204)

    @router.get("/users")
    def list_users(admin=require_admin):
        db = db_session_factory()
        rows = list(db.execute(select(User).order_by(User.created_at.desc())).scalars())
        return [
            {
                "id": u.id,
                "email": u.email,
                "display_name": u.display_name,
                "is_admin": u.is_admin,
                "is_disabled": u.is_disabled,
                "last_login_at": u.last_login_at,
                "must_change_password": u.must_change_password,
            }
            for u in rows
        ]

    @router.post("/users/{user_id}/disable", status_code=204)
    def disable_user(user_id: str, admin=require_admin):
        db = db_session_factory()
        user = db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=404)
        user.is_disabled = True
        user.updated_at = datetime.now(timezone.utc)
        db.commit()
        sessions.revoke_all_sessions(db, user_id=user.id)
        return Response(status_code=204)

    @router.post("/users/{user_id}/enable", status_code=204)
    def enable_user(user_id: str, admin=require_admin):
        db = db_session_factory()
        user = db.get(User, user_id)
        if user is None:
            raise HTTPException(status_code=404)
        user.is_disabled = False
        user.updated_at = datetime.now(timezone.utc)
        db.commit()
        return Response(status_code=204)

    @router.post("/users/{user_id}/reset-password", status_code=204)
    def direct_reset(user_id: str, body: DirectResetIn, admin=require_admin):
        db = db_session_factory()
        try:
            reset_service.admin_direct_reset(
                db, user_id=user_id, new_password=body.new_password, admin_user_id=admin.id
            )
        except AuthError as exc:
            raise HTTPException(status_code=400, detail={"code": exc.code, "message": str(exc)})
        return Response(status_code=204)

    @router.get("/password-reset-requests")
    def list_reset_requests(admin=require_admin):
        db = db_session_factory()
        rows = list(
            db.execute(
                select(PasswordResetRequest).where(PasswordResetRequest.status == "pending")
            ).scalars()
        )
        return [
            {
                "id": r.id,
                "user_id": r.user_id,
                "status": r.status,
                "requested_at": r.requested_at,
                "requested_ip": r.requested_ip,
            }
            for r in rows
        ]

    @router.post("/password-reset-requests/{request_id}/approve")
    def approve_reset_request(request_id: str, admin=require_admin):
        db = db_session_factory()
        try:
            raw = reset_service.approve_request(
                db, request_id=request_id, admin_user_id=admin.id
            )
        except AuthError as exc:
            raise HTTPException(status_code=404, detail={"code": exc.code})
        return {"reset_token": raw}

    @router.post("/password-reset-requests/{request_id}/reject", status_code=204)
    def reject_reset_request(request_id: str, admin=require_admin):
        db = db_session_factory()
        try:
            reset_service.reject_request(db, request_id=request_id, admin_user_id=admin.id)
        except AuthError as exc:
            raise HTTPException(status_code=404, detail={"code": exc.code})
        return Response(status_code=204)

    return router
```

- [ ] **Step 4: Commit (tests defer to Task 16)**

```bash
git add packages/server/src/openlia_server/routes/admin.py \
        packages/server/tests/test_routes/test_admin_routes.py
git commit -m "phase-2(auth): /admin/* invite/user/reset-request management"
```

---

## Task 16: App factory wiring (`app.py`)

**Files:**
- Modify: `packages/server/src/openlia_server/app.py`

- [ ] **Step 1: Read the current app.py**

Run: `cat packages/server/src/openlia_server/app.py`

Plan 0 created a minimal `create_app()` returning `FastAPI()`. Plan 1A may have extended it. This task extends it further to:

1. Accept an optional `db_session_factory` (for tests).
2. Detect mode from `OPENLIA_MODE`.
3. In company mode: mount `auth_router` + `admin_router`.
4. In personal mode: skip auth/admin routers entirely.
5. Ensure `bootstrap()` from Plan 1A runs at startup (or is assumed to have already run). If Plan 1A's bootstrap is invoked from `cli.py` pre-serve, no change is needed here.

- [ ] **Step 2: Rewrite app.py**

Replace the contents of `packages/server/src/openlia_server/app.py` with:

```python
"""FastAPI application factory."""
from __future__ import annotations

import os
from typing import Callable

from fastapi import FastAPI
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.session import SessionLocal, get_engine
from openlia_server.routes.admin import build_admin_router
from openlia_server.routes.auth import build_auth_router


def _default_session_factory() -> DBSession:
    # Ensure the engine is configured against the resolved DB URL. `get_engine`
    # is idempotent; it returns the cached engine if one was already created.
    get_engine()
    return SessionLocal()


def create_app(
    *,
    db_session_factory: Callable[[], DBSession] | None = None,
) -> FastAPI:
    factory = db_session_factory or _default_session_factory
    mode = os.environ.get("OPENLIA_MODE", "personal").lower()
    app = FastAPI(title="OpenLIA", version="0.0.0")

    if mode == "company":
        app.include_router(build_auth_router(db_session_factory=factory))
        app.include_router(build_admin_router(db_session_factory=factory))

    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "mode": mode}

    return app
```

- [ ] **Step 3: Run the end-to-end route tests**

```bash
uv run pytest packages/server/tests/test_routes -v
```

Expected: all route tests pass (auth + admin).

- [ ] **Step 4: Run the full suite**

```bash
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
```

Expected: green across the board.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/app.py
git commit -m "phase-2(auth): create_app mounts /auth + /admin routers in company mode"
```

---

## Task 17: CLI wiring for bootstrap (signup_policy seed)

**Files:**
- Modify: `packages/server/src/openlia_server/cli.py`

- [ ] **Step 1: Read current cli.py**

Run: `cat packages/server/src/openlia_server/cli.py`

Plan 1A Task 12 modified this file to call `bootstrap()` before `uvicorn.run()`. Task 8 above already extended `bootstrap()` itself to seed the signup policy. This task is a safety check — confirm `OPENLIA_MODE` is resolved before `bootstrap()` runs (so the correct policy mode is seeded) and that the bootstrap still runs on every `openlia serve`.

- [ ] **Step 2: Verify or adjust the order**

If `cli.py` already does:

```python
@app.command()
def serve(...):
    bootstrap()
    uvicorn.run(...)
```

…and `bootstrap()` reads `OPENLIA_MODE` directly, no change is needed. If not, add an explicit pass-through:

```python
@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000) -> None:
    """Run the OpenLIA FastAPI server."""
    bootstrap()  # seeds local user, signup_policy, wizard_state, config_store defaults
    uvicorn.run("openlia_server.app:create_app", factory=True, host=host, port=port)
```

- [ ] **Step 3: Run the smoke test**

```bash
OPENLIA_MODE=company uv run openlia serve --host 127.0.0.1 --port 8765 &
SERVER_PID=$!
sleep 2
curl -s http://127.0.0.1:8765/healthz | grep -q '"mode": "company"'
curl -s http://127.0.0.1:8765/auth/signup-policy | grep -q '"invite_required": true'
kill $SERVER_PID
```

Expected: both curls succeed. Kill the server, clean up.

- [ ] **Step 4: Commit**

```bash
git add packages/server/src/openlia_server/cli.py
git commit -m "phase-2(auth): verify serve CLI runs bootstrap before uvicorn"
```

---

## Task 18: Acceptance + README update

**Files:**
- Modify: `planning/implementation-plans/README.md`

- [ ] **Step 1: Run the full acceptance list**

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest -v
```

Manual smoke:

- `OPENLIA_SECRET_KEY` env override works and takes precedence over `~/.openlia/secret.key`.
- In a fresh temp dir, running the server auto-creates `secret.key` with 0600.
- Looser permissions on `secret.key` cause startup to fail with the exact message from `SecretKeyError`.
- `POST /auth/register` with a valid invite sets the cookie and the user shows up in `/auth/session`.
- `POST /auth/login` with wrong credentials five times triggers `account_locked` on the sixth attempt with `retry_after_seconds`.
- Flipping `auth.lockout.enabled` to `false` in `config_store` suppresses lockout (verified by test).
- Admin approves a password reset; raw token returned once; consuming it updates the user and revokes sessions.
- Personal mode: all `/auth/*` and `/admin/*` paths return 404; `GET /healthz` works.

Acceptance criteria:

1. `uv run ruff check .` passes.
2. `uv run ruff format --check .` passes.
3. `uv run pytest -v` passes.
4. `POST /auth/register`, `/auth/login`, `/auth/logout`, `/auth/session`, `/auth/password-reset/request`, `/auth/password-reset/consume`, `/auth/change-password`, `/auth/signup-policy` all covered by at least one integration test.
5. `POST /admin/invites`, `/admin/invites/{id}/revoke`, `GET /admin/invites`, `GET /admin/users`, `/admin/users/{id}/{disable,enable,reset-password}`, `GET /admin/password-reset-requests`, `/admin/password-reset-requests/{id}/{approve,reject}` all covered by at least one integration test.
6. In personal mode, `/auth/*` and `/admin/*` return 404.
7. `encrypt_for_row` / `decrypt_for_row` bind to row ID via AAD and reject tampering.
8. `secret.key` is auto-created with 0600 when missing; looser permissions cause startup to fail with `SecretKeyError`.
9. Lockout is gated by `config_store["auth.lockout.enabled"]` (default true); when false the counter is neither read nor written.
10. Password reset consumption revokes all active sessions for the user.
11. `log_auth_event` runs for: login_success, login_failure, account_locked, password_changed, password_reset_requested, password_reset_approved, password_reset_rejected, password_reset_consumed, password_reset_by_admin.

- [ ] **Step 2: Mark Plan 2 as Draft in the roadmap**

Edit `planning/implementation-plans/README.md` to change the Plan 2 row:

```markdown
| 2 | 1 | Secrets encryption + auth primitives | Draft | `2026-04-16-phase-2-auth-and-secrets.md` |
```

- [ ] **Step 3: Commit**

```bash
git add planning/implementation-plans/README.md
git commit -m "phase-2(auth): mark plan as Draft in roadmap"
```

---

## Notes for the implementer

- **`db_session_factory` injection.** Tests use a single shared `db_session` fixture; the `create_app(db_session_factory=...)` override swaps the normal `SessionLocal()` for the test session. Production code uses the default factory which opens a new `SessionLocal()` per request. Longer term (Plan 3+), consider a proper FastAPI dependency (`Depends(get_db)`) that manages per-request lifecycle; for this plan the factory-per-call pattern is enough.

- **Rate limiter state leaks between tests.** The module-level `_limiter` is shared across the process. Add a `@pytest.fixture(autouse=True)` in `tests/test_routes/conftest.py` that calls `limiter().clear()` between tests if flakiness appears. Not included above because tests written so far don't cross-bleed; add on demand.

- **Cookie `Secure` flag in tests.** `TestClient` doesn't care about `Secure`, so the tests pass either way. Production behavior is driven by `OPENLIA_COOKIE_SECURE`.

- **`anti-enumeration timing` is a weak test.** The dummy-verify test asserts the measured elapsed times are in the same order of magnitude, which is a low bar on purpose — we're confirming the code path runs, not measuring security properties. A proper statistical test lives with the security-hardening work in Plan 7 or later.

- **JSON column name collision on `auth_events`.** `AuthEvent.event_metadata` maps to the DB column `metadata`; this was resolved in Plan 1A Task 5. `log_auth_event` uses the attribute name, not the column name.

- **Admin CLI commands are out of scope.** Plan 7 imports from `services/auth/` directly (`login.authenticate`, `sessions.revoke_all_sessions`, etc.) — no reshaping needed.

- **projectStructure.md drift.** This plan ships `services/auth/` as a package instead of the single file the structure doc describes. Task 1 of Plan 7 should update `projectStructure.md` to match reality (or roll the update into a pre-Plan-7 cleanup commit).

## Execution handoff

Plan complete and saved to `planning/implementation-plans/2026-04-16-phase-2-auth-and-secrets.md`.

Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, two-stage review after each, fast iteration. Use `superpowers:subagent-driven-development`.
2. **Inline Execution** — batch the tasks through `superpowers:executing-plans` with checkpoints for review.

Pause to choose when ready to execute.
