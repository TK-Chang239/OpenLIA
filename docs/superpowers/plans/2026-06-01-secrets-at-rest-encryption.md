# Connector secrets-at-rest encryption Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Encrypt the `connectors.secrets` column at rest with Fernet, transparently via a SQLAlchemy `TypeDecorator`, with operator-supplied or auto-provisioned key management and an eager migration of existing rows.

**Architecture:** A new `secrets_crypto` module resolves a Fernet key (`OPENLIA_SECRET_KEY` env, else a personal-mode key file, else fail in company mode) and exposes `encrypt`/`decrypt`. A new `EncryptedJSON` `TypeDecorator` (sibling of the existing `UTCDateTime`) makes the `connectors.secrets` column store ciphertext while every Python call site keeps seeing a plaintext dict. An Alembic migration encrypts existing rows; the read path tolerates legacy plaintext as a safety net.

**Tech Stack:** Python 3.13, SQLAlchemy, Alembic, `cryptography`/Fernet (already a server dep), pytest. Frontend: React/TS (wording-only change).

**Spec:** `docs/superpowers/specs/2026-06-01-secrets-at-rest-encryption-design.md`

---

## File Structure

- Create `packages/server/src/openlia_server/db/secrets_crypto.py` — key resolution + Fernet `encrypt`/`decrypt` + error types. No SQLAlchemy imports. Single responsibility: the cipher and its key.
- Modify `packages/server/src/openlia_server/db/base.py` — add `EncryptedJSON(TypeDecorator)` next to `UTCDateTime`. Imports `secrets_crypto` lazily inside its methods to avoid an import cycle / pulling crypto into every model import.
- Modify `packages/server/src/openlia_server/db/models/connectors.py` — change the `secrets` column type from `JSON` to `EncryptedJSON`.
- Create `packages/server/src/openlia_server/db/migrations/versions/2026-06-01-1130_encrypt_connector_secrets.py` — data-migrate existing rows + alter column type.
- Modify `packages/server/src/openlia_server/db/bootstrap.py` — eager `ensure_key_available()` call so company-mode misconfiguration fails at startup.
- Modify `frontend/src/setup/steps/SmartPasteMcpForm.tsx` and `frontend/src/setup/steps/AddConnectorForm.tsx` — restore the truthful "encrypted" wording.
- Tests: `packages/server/tests/test_secrets_crypto.py`, `test_encrypted_json.py`, `test_connectors_secrets_encrypted.py`, `test_secrets_encryption_migration.py`.

---

## Task 1: `secrets_crypto` module (key + cipher)

**Files:**
- Create: `packages/server/src/openlia_server/db/secrets_crypto.py`
- Test: `packages/server/tests/test_secrets_crypto.py`

- [ ] **Step 1: Write the failing tests**

Create `packages/server/tests/test_secrets_crypto.py`:

```python
"""Tests for connector secret key resolution + Fernet encrypt/decrypt."""
from __future__ import annotations

import os

import pytest
from cryptography.fernet import Fernet

from openlia_server.db import secrets_crypto as sc


@pytest.fixture(autouse=True)
def _reset(monkeypatch, tmp_path):
    # Isolate every test: clean env + a temp OPENLIA_HOME + fresh cipher cache.
    monkeypatch.delenv("OPENLIA_SECRET_KEY", raising=False)
    monkeypatch.delenv("OPENLIA_MODE", raising=False)
    monkeypatch.setenv("OPENLIA_HOME", str(tmp_path))
    sc.reset_cache()
    yield
    sc.reset_cache()


def test_round_trip_with_env_key(monkeypatch):
    monkeypatch.setenv("OPENLIA_SECRET_KEY", Fernet.generate_key().decode())
    token = sc.encrypt("hello")
    assert token != "hello"
    assert sc.decrypt(token) == "hello"


def test_personal_mode_autogenerates_key_file(tmp_path):
    # No env key, default (personal) mode -> a key file is created chmod 600.
    token = sc.encrypt("secret")
    key_file = tmp_path / sc.KEY_FILENAME
    assert key_file.exists()
    assert (key_file.stat().st_mode & 0o777) == 0o600
    assert sc.decrypt(token) == "secret"


def test_company_mode_without_key_raises(monkeypatch):
    monkeypatch.setenv("OPENLIA_MODE", "company")
    with pytest.raises(sc.SecretKeyMissingError):
        sc.ensure_key_available()


def test_invalid_env_key_raises(monkeypatch):
    monkeypatch.setenv("OPENLIA_SECRET_KEY", "not-a-valid-fernet-key")
    with pytest.raises(sc.SecretKeyInvalidError):
        sc.ensure_key_available()


def test_decrypt_with_wrong_key_raises(monkeypatch):
    monkeypatch.setenv("OPENLIA_SECRET_KEY", Fernet.generate_key().decode())
    token = sc.encrypt("hello")
    # Swap to a different key and try to decrypt the old token.
    monkeypatch.setenv("OPENLIA_SECRET_KEY", Fernet.generate_key().decode())
    sc.reset_cache()
    with pytest.raises(sc.SecretDecryptError):
        sc.decrypt(token)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_secrets_crypto.py -v`
Expected: FAIL — module `secrets_crypto` does not exist.
(If `uv run` errors with `/Users/tkchang/.cache/uv ... Operation not permitted`, that's a sandbox restriction — retry the command with the sandbox disabled.)

- [ ] **Step 3: Write the implementation**

Create `packages/server/src/openlia_server/db/secrets_crypto.py`:

```python
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
    path.write_bytes(key)
    os.chmod(path, 0o600)
    return key


def get_fernet() -> Fernet:
    global _fernet
    if _fernet is None:
        key = resolve_key()
        try:
            _fernet = Fernet(key)
        except (ValueError, TypeError) as exc:
            raise SecretKeyInvalidError(
                f"OPENLIA_SECRET_KEY is not a valid Fernet key. {_GENERATE_HINT}"
            ) from exc
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_secrets_crypto.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/db/secrets_crypto.py packages/server/tests/test_secrets_crypto.py
git commit -m "feat(db): add secrets_crypto key resolution + Fernet encrypt/decrypt"
```

---

## Task 2: `EncryptedJSON` TypeDecorator

**Files:**
- Modify: `packages/server/src/openlia_server/db/base.py`
- Test: `packages/server/tests/test_encrypted_json.py`

- [ ] **Step 1: Write the failing tests**

Create `packages/server/tests/test_encrypted_json.py`:

```python
"""Tests for the EncryptedJSON TypeDecorator (bind/result round-trip)."""
from __future__ import annotations

import json

import pytest
from cryptography.fernet import Fernet

from openlia_server.db import secrets_crypto as sc
from openlia_server.db.base import EncryptedJSON


@pytest.fixture(autouse=True)
def _key(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENLIA_SECRET_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("OPENLIA_HOME", str(tmp_path))
    sc.reset_cache()
    yield
    sc.reset_cache()


def test_bind_produces_ciphertext_not_plaintext():
    col = EncryptedJSON()
    stored = col.process_bind_param({"API_KEY": "super-secret-value"}, dialect=None)
    assert isinstance(stored, str)
    assert "super-secret-value" not in stored
    assert "API_KEY" not in stored


def test_result_decrypts_back_to_dict():
    col = EncryptedJSON()
    stored = col.process_bind_param({"K": "v"}, dialect=None)
    assert col.process_result_value(stored, dialect=None) == {"K": "v"}


def test_none_binds_none_and_reads_empty_dict():
    col = EncryptedJSON()
    assert col.process_bind_param(None, dialect=None) is None
    assert col.process_result_value(None, dialect=None) == {}
    assert col.process_result_value("", dialect=None) == {}


def test_result_tolerates_legacy_plaintext_json():
    col = EncryptedJSON()
    legacy = json.dumps({"OLD": "plaintext"})
    assert col.process_result_value(legacy, dialect=None) == {"OLD": "plaintext"}


def test_result_with_wrong_key_raises_decrypt_error(monkeypatch):
    col = EncryptedJSON()
    stored = col.process_bind_param({"K": "v"}, dialect=None)
    monkeypatch.setenv("OPENLIA_SECRET_KEY", Fernet.generate_key().decode())
    sc.reset_cache()
    with pytest.raises(sc.SecretDecryptError):
        col.process_result_value(stored, dialect=None)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest packages/server/tests/test_encrypted_json.py -v`
Expected: FAIL — `cannot import name 'EncryptedJSON'`.

- [ ] **Step 3: Write the implementation**

In `packages/server/src/openlia_server/db/base.py`, add `Text` to the sqlalchemy import block:

```python
from sqlalchemy import (
    DateTime,  # kept for TypeDecorator impl
    MetaData,
    Text,
    func,
    types,
)
```

Then add this class immediately after the `UTCDateTime` class (before `class Base`):

```python
class EncryptedJSON(types.TypeDecorator):
    """JSON dict column encrypted at rest with Fernet.

    Stores ciphertext as `Text`; the Python-side value is always a plaintext
    `dict`. Read tolerates legacy plaintext JSON (rows written before
    encryption was introduced, or inserted out-of-band) as a safety net.

    `secrets_crypto` is imported lazily inside the methods so importing this
    module (which every ORM model does) does not pull in the key/cipher
    machinery or the bootstrap import chain until a value is actually
    encrypted or decrypted.
    """

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: dict | None, dialect) -> str | None:
        if value is None:
            return None
        import json

        from openlia_server.db.secrets_crypto import encrypt

        return encrypt(json.dumps(value))

    def process_result_value(self, value: str | None, dialect) -> dict:
        if value is None or value == "":
            return {}
        import json

        from openlia_server.db.secrets_crypto import SecretDecryptError, decrypt

        try:
            return json.loads(decrypt(value))
        except SecretDecryptError as dec_err:
            # Safety net: a pre-encryption plaintext-JSON row decrypts as
            # InvalidToken; if the raw value parses as JSON, return it. A real
            # ciphertext under the wrong key is not valid JSON, so re-raise the
            # clear decrypt error instead of a confusing JSON error.
            try:
                return json.loads(value)
            except (ValueError, TypeError):
                raise dec_err
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_encrypted_json.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/db/base.py packages/server/tests/test_encrypted_json.py
git commit -m "feat(db): add EncryptedJSON TypeDecorator"
```

---

## Task 3: Switch `Connector.secrets` to `EncryptedJSON`

**Files:**
- Modify: `packages/server/src/openlia_server/db/models/connectors.py`
- Test: `packages/server/tests/test_connectors_secrets_encrypted.py`

- [ ] **Step 1: Write the failing test**

First open `packages/server/tests/services/test_connectors_service.py` and note the fixture it uses to get a SQLAlchemy `Session` (e.g. a `db` fixture from `conftest.py`). Use that SAME fixture name in the new test below — replace `db_session` with whatever the sibling tests use.

Create `packages/server/tests/test_connectors_secrets_encrypted.py`:

```python
"""The connectors.secrets column is stored encrypted but reads back plaintext."""
from __future__ import annotations

import uuid

import pytest
from cryptography.fernet import Fernet
from sqlalchemy import text

from openlia_server.db import secrets_crypto as sc
from openlia_server.db.models.connectors import Connector


@pytest.fixture(autouse=True)
def _key(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENLIA_SECRET_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("OPENLIA_HOME", str(tmp_path))
    sc.reset_cache()
    yield
    sc.reset_cache()


def test_secrets_round_trip_and_ciphertext_at_rest(db_session):
    row = Connector(
        id=str(uuid.uuid4()),
        provider_id="acme",
        display_name="Acme",
        source="remote_mcp",
        category="financial",
        launch={"modes": []},
        secrets={"ACME_API_KEY": "top-secret-123"},
        status="validated",
    )
    db_session.add(row)
    db_session.commit()
    db_session.expire_all()

    # ORM read returns plaintext dict.
    loaded = db_session.get(Connector, row.id)
    assert loaded.secrets == {"ACME_API_KEY": "top-secret-123"}

    # Raw column value at rest is ciphertext (no plaintext substring).
    raw = db_session.execute(
        text("SELECT secrets FROM connectors WHERE id = :id"), {"id": row.id}
    ).scalar_one()
    assert "top-secret-123" not in raw
    assert "ACME_API_KEY" not in raw
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/server/tests/test_connectors_secrets_encrypted.py -v`
Expected: FAIL — the raw value still contains the plaintext (column is plain `JSON`).

- [ ] **Step 3: Write the implementation**

In `packages/server/src/openlia_server/db/models/connectors.py`:

Add `EncryptedJSON` to the base import:

```python
from openlia_server.db.base import Base, EncryptedJSON
```

(If the file imports other names from `db.base`, keep them and add `EncryptedJSON` to the same import.)

Change the `secrets` column declaration from:

```python
    secrets: Mapped[dict] = mapped_column(
        JSON, nullable=False, default=dict, server_default=text("'{}'")
    )
```

to:

```python
    secrets: Mapped[dict] = mapped_column(
        EncryptedJSON, nullable=False, default=dict, server_default=text("'{}'")
    )
```

Leave `server_default=text("'{}'")` as-is: it only applies to raw inserts that omit the column, and the read path tolerates that plaintext `{}`. Do not remove the `JSON` import if other columns still use it.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest packages/server/tests/test_connectors_secrets_encrypted.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/db/models/connectors.py packages/server/tests/test_connectors_secrets_encrypted.py
git commit -m "feat(connectors): encrypt the secrets column via EncryptedJSON"
```

---

## Task 4: Alembic migration — encrypt existing rows

**Files:**
- Create: `packages/server/src/openlia_server/db/migrations/versions/2026-06-01-1130_encrypt_connector_secrets.py`
- Test: `packages/server/tests/test_secrets_encryption_migration.py`

- [ ] **Step 1: Write the failing test**

First check for an existing migration-test helper: `grep -rn "command.upgrade\|alembic" packages/server/tests`. If a sibling test already builds an Alembic `Config` against a temp DB, mirror that setup. Otherwise use the self-contained approach below.

Create `packages/server/tests/test_secrets_encryption_migration.py`:

```python
"""The encryption migration converts existing plaintext secret rows to ciphertext."""
from __future__ import annotations

import json
import uuid

import pytest
from alembic import command
from alembic.config import Config
from cryptography.fernet import Fernet
from sqlalchemy import create_engine, text

from openlia_server.db import secrets_crypto as sc

PRIOR_REVISION = "1c6b0cda0ed9"  # head before this migration
NEW_REVISION = "enc_secrets_0601"


def _alembic_config(db_url: str) -> Config:
    # alembic.ini lives at the server package root.
    cfg = Config("packages/server/alembic.ini")
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


@pytest.fixture(autouse=True)
def _key(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENLIA_SECRET_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("OPENLIA_HOME", str(tmp_path))
    sc.reset_cache()
    yield
    sc.reset_cache()


def test_migration_encrypts_existing_plaintext_row(tmp_path):
    db_file = tmp_path / "mig.db"
    db_url = f"sqlite:///{db_file}"
    cfg = _alembic_config(db_url)

    # Build schema up to the revision just before this migration.
    command.upgrade(cfg, PRIOR_REVISION)

    engine = create_engine(db_url)
    row_id = str(uuid.uuid4())
    plaintext = json.dumps({"ACME_API_KEY": "plain-123"})
    with engine.begin() as conn:
        conn.execute(
            text(
                "INSERT INTO connectors "
                "(id, provider_id, display_name, source, category, launch, secrets, status) "
                "VALUES (:id, 'acme', 'Acme', 'remote_mcp', 'financial', '{\"modes\": []}', :s, 'validated')"
            ),
            {"id": row_id, "s": plaintext},
        )

    # Run the encryption migration.
    command.upgrade(cfg, NEW_REVISION)

    with engine.begin() as conn:
        stored = conn.execute(
            text("SELECT secrets FROM connectors WHERE id = :id"), {"id": row_id}
        ).scalar_one()

    assert "plain-123" not in stored
    assert sc.decrypt(stored) == plaintext
```

NOTE: set `NEW_REVISION` to the exact `revision` string you assign in Step 3. If `Config("packages/server/alembic.ini")` is not found from the test's working directory, resolve it relative to the repo root (the implementer should confirm the path the existing suite uses, e.g. via `from openlia_server.db import bootstrap` helpers).

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/server/tests/test_secrets_encryption_migration.py -v`
Expected: FAIL — revision `enc_secrets_0601` does not exist.

- [ ] **Step 3: Write the migration**

Create `packages/server/src/openlia_server/db/migrations/versions/2026-06-01-1130_encrypt_connector_secrets.py`:

```python
"""encrypt connector secrets at rest

Revision ID: enc_secrets_0601
Revises: 1c6b0cda0ed9
Create Date: 2026-06-01 11:30:00.000000+00:00
"""
from __future__ import annotations

import json
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "enc_secrets_0601"
down_revision: str | Sequence[str] | None = "1c6b0cda0ed9"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _is_plaintext_json(raw: str) -> bool:
    """Plaintext rows are JSON; Fernet tokens are not JSON-parseable."""
    try:
        json.loads(raw)
        return True
    except (ValueError, TypeError):
        return False


def upgrade() -> None:
    from openlia_server.db import secrets_crypto

    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, secrets FROM connectors")).fetchall()
    for row_id, raw in rows:
        if not raw:
            continue
        if not _is_plaintext_json(raw):
            continue  # already encrypted (idempotent re-run)
        token = secrets_crypto.encrypt(raw)
        bind.execute(
            sa.text("UPDATE connectors SET secrets = :s WHERE id = :id"),
            {"s": token, "id": row_id},
        )
    with op.batch_alter_table("connectors", schema=None) as batch_op:
        batch_op.alter_column("secrets", type_=sa.Text())


def downgrade() -> None:
    from openlia_server.db import secrets_crypto

    bind = op.get_bind()
    rows = bind.execute(sa.text("SELECT id, secrets FROM connectors")).fetchall()
    for row_id, raw in rows:
        if not raw or _is_plaintext_json(raw):
            continue  # already plaintext
        plain = secrets_crypto.decrypt(raw)
        bind.execute(
            sa.text("UPDATE connectors SET secrets = :s WHERE id = :id"),
            {"s": plain, "id": row_id},
        )
    with op.batch_alter_table("connectors", schema=None) as batch_op:
        batch_op.alter_column("secrets", type_=sa.JSON())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_secrets_encryption_migration.py -v`
Expected: PASS.
Then confirm the migration chain is linear: `uv run alembic -c packages/server/alembic.ini heads` should report a single head `enc_secrets_0601`.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/db/migrations/versions/2026-06-01-1130_encrypt_connector_secrets.py packages/server/tests/test_secrets_encryption_migration.py
git commit -m "feat(db): migrate existing connector secrets to encrypted at rest"
```

---

## Task 5: Eager key check at startup

**Files:**
- Modify: `packages/server/src/openlia_server/db/bootstrap.py`
- Test: `packages/server/tests/test_bootstrap_key_check.py`

- [ ] **Step 1: Write the failing test**

First read `bootstrap.py` and find the top-level `bootstrap(...)` entry function (the one `cli.py` imports as `from openlia_server.db.bootstrap import bootstrap`). Note its signature. The test calls it in company mode with no key and expects the key error BEFORE it would try anything else. If `bootstrap()` requires args (e.g. a db url), pass a temp sqlite url like the other bootstrap tests do — mirror an existing `bootstrap`-calling test if present.

Create `packages/server/tests/test_bootstrap_key_check.py`:

```python
"""Bootstrap fails loudly in company mode when no encryption key is configured."""
from __future__ import annotations

import pytest

from openlia_server.db import secrets_crypto as sc


@pytest.fixture(autouse=True)
def _env(monkeypatch, tmp_path):
    monkeypatch.delenv("OPENLIA_SECRET_KEY", raising=False)
    monkeypatch.setenv("OPENLIA_HOME", str(tmp_path))
    sc.reset_cache()
    yield
    sc.reset_cache()


def test_company_mode_bootstrap_requires_key(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENLIA_MODE", "company")
    monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path / 'b.db'}")
    from openlia_server.db.bootstrap import bootstrap

    with pytest.raises(sc.SecretKeyMissingError):
        bootstrap()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest packages/server/tests/test_bootstrap_key_check.py -v`
Expected: FAIL — `bootstrap()` currently runs migrations/seed without checking the key first (it may fail later or differently, not with `SecretKeyMissingError` at the top).

- [ ] **Step 3: Write the implementation**

In `bootstrap.py`, add an early call inside the `bootstrap(...)` function, BEFORE the Alembic upgrade step, so the key is validated first:

```python
    from openlia_server.db import secrets_crypto

    secrets_crypto.ensure_key_available()
```

Place it as the first action after `ensure_openlia_dir()` (so the data dir exists for personal-mode key-file creation) and before the Alembic `upgrade head` call. In personal mode this provisions the key file; in company mode it raises `SecretKeyMissingError` immediately. Match the exact structure of the existing `bootstrap()` body — insert the call, do not reorder unrelated steps.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest packages/server/tests/test_bootstrap_key_check.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/db/bootstrap.py packages/server/tests/test_bootstrap_key_check.py
git commit -m "feat(db): validate encryption key at bootstrap (loud failure in company mode)"
```

---

## Task 6: Restore truthful "encrypted" UI wording

**Files:**
- Modify: `frontend/src/setup/steps/SmartPasteMcpForm.tsx`
- Modify: `frontend/src/setup/steps/AddConnectorForm.tsx`

- [ ] **Step 1: Update SmartPasteMcpForm wording**

In `frontend/src/setup/steps/SmartPasteMcpForm.tsx`, find the "Detected secrets" hint paragraph:

```tsx
            Stored on the server, never sent to the LLM. Toggle off anything that
            is not a secret.
```

Change to:

```tsx
            Stored encrypted on the server, never sent to the LLM. Toggle off
            anything that is not a secret.
```

- [ ] **Step 2: Update AddConnectorForm wording**

In `frontend/src/setup/steps/AddConnectorForm.tsx`, find:

```tsx
          Stored on the server, never sent to the LLM. Key is the env var
          name; value is the actual secret.
```

Change to:

```tsx
          Stored encrypted on the server, never sent to the LLM. Key is the env
          var name; value is the actual secret.
```

- [ ] **Step 3: Verify typecheck + existing tests**

Run: `cd frontend && npx tsc --noEmit && npx vitest run src/setup/steps/__tests__`
Expected: clean typecheck; all step tests pass (no test asserts on this hint text; if one does, update its expected string to match).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/setup/steps/SmartPasteMcpForm.tsx frontend/src/setup/steps/AddConnectorForm.tsx
git commit -m "feat(connectors): restore encrypted-at-rest wording now that it is true"
```

---

## Task 7: Integration verification

**Files:** none (verification only)

- [ ] **Step 1: Full connector + db suites**

Run: `uv run pytest packages/server/tests/test_secrets_crypto.py packages/server/tests/test_encrypted_json.py packages/server/tests/test_connectors_secrets_encrypted.py packages/server/tests/test_secrets_encryption_migration.py packages/server/tests/test_bootstrap_key_check.py packages/server/tests/services/test_connectors_service.py packages/server/tests/test_services/test_dispatcher_factory_substitutions.py packages/core/tests/connectors -v`
Expected: PASS. The pre-existing connector tests must still pass with the encrypted column (they exercise create/validate/read paths through the ORM, which now round-trips via `EncryptedJSON`).

- [ ] **Step 2: EODHD wiring read path**

Run: `uv run pytest packages/server/tests -k "eu_v2_wiring or data_sources" -v`
Expected: PASS — `eu_v2_wiring.resolve_eodhd_api_key` reads `connector.secrets["EODHD_API_KEY"]` through the decrypted ORM value.

- [ ] **Step 3: Lint + full server test sweep**

Run: `uv run ruff check packages/server/src/openlia_server/db/secrets_crypto.py packages/server/src/openlia_server/db/base.py packages/server/src/openlia_server/db/bootstrap.py packages/server/src/openlia_server/db/models/connectors.py`
Then: `uv run pytest packages/server -q`
Expected: ruff clean; full server suite green (watch for any test that seeded plaintext secrets and reads them via raw SQL — such a test must go through the ORM or set `OPENLIA_SECRET_KEY`).

- [ ] **Step 4: Frontend typecheck + build**

Run: `cd frontend && npx tsc --noEmit && npm run build`
Expected: clean typecheck, successful build.

- [ ] **Step 5: Manual smoke (document only — needs a running server)**

Not automated. When a server is available:
- Personal mode, no `OPENLIA_SECRET_KEY`: start the server; confirm `~/.openlia/secret.key` is created `0600`; add a connector; inspect the DB — `connectors.secrets` is a Fernet token, not plaintext.
- Company mode (`OPENLIA_MODE=company`) with no key: startup fails with the `SecretKeyMissingError` message naming `OPENLIA_SECRET_KEY`.
- Existing install upgrade: run `alembic upgrade head` against a DB with plaintext connector secrets; confirm rows become ciphertext and connectors still work (tool calls authenticate).

- [ ] **Step 6: Commit (if any fixups were needed)**

```bash
git add -A
git commit -m "chore(connectors): secrets-at-rest encryption integration fixups"
```

---

## Self-Review notes

- **Spec coverage:** cipher + key resolution (T1); transparent column (T2); column swap (T3); eager migration of existing rows + tolerant read (T2 read path + T4 migration); startup key check / loud failure (T5); UI wording restore (T6); verification incl. EODHD wiring and the `secret_keys` listing (T7). All spec sections map to a task. `packages/core` is untouched (boundary preserved).
- **Type/name consistency:** `secrets_crypto` exports `KEY_FILENAME`, `reset_cache`, `resolve_key`, `get_fernet`, `ensure_key_available`, `encrypt`, `decrypt`, and errors `SecretKeyMissingError`/`SecretKeyInvalidError`/`SecretDecryptError` — used verbatim in T2/T3/T4/T5 tests and the migration. `EncryptedJSON` defined in T2 (`db/base.py`), imported in T3 (model). Migration `revision = "enc_secrets_0601"` matches the test's `NEW_REVISION` and `down_revision = "1c6b0cda0ed9"` (current head).
- **Known plan-time check:** T3/T4/T5 tests depend on the repo's existing pytest DB/session fixtures and Alembic test path; each task instructs the implementer to mirror the sibling tests' fixture/config rather than assume a name. The provided `db_session`/`Config(...)` references are explicit fallbacks to adjust if the established harness differs.
```
