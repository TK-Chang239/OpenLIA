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

PRIOR_REVISION = "1c6b0cda0ed9"
NEW_REVISION = "enc_secrets_0601"  # must equal the revision you assign


@pytest.fixture(autouse=True)
def _key(monkeypatch, tmp_path):
    monkeypatch.setenv("OPENLIA_SECRET_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("OPENLIA_HOME", str(tmp_path))
    sc.reset_cache()
    yield
    sc.reset_cache()


def _config(db_url: str, monkeypatch) -> Config:
    # env.py reads bootstrap.resolve_db_url() which reads OPENLIA_DB_URL
    monkeypatch.setenv("OPENLIA_DB_URL", db_url)
    cfg = Config()
    cfg.set_main_option(
        "script_location",
        "packages/server/src/openlia_server/db/migrations",
    )
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def test_migration_encrypts_existing_plaintext_row(tmp_path, monkeypatch):
    db_url = f"sqlite:///{tmp_path / 'mig.db'}"
    cfg = _config(db_url, monkeypatch)
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

    command.upgrade(cfg, NEW_REVISION)

    with engine.begin() as conn:
        stored = conn.execute(
            text("SELECT secrets FROM connectors WHERE id = :id"), {"id": row_id}
        ).scalar_one()
    assert "plain-123" not in stored
    assert sc.decrypt(stored) == plaintext
