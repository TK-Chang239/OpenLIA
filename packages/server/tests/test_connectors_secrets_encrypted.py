"""The connectors.secrets column is stored encrypted but reads back plaintext."""

from __future__ import annotations

import uuid

import pytest
from cryptography.fernet import Fernet
from openlia_server.db import secrets_crypto as sc
from openlia_server.db.models.connectors import Connector
from sqlalchemy import text


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

    loaded = db_session.get(Connector, row.id)
    assert loaded.secrets == {"ACME_API_KEY": "top-secret-123"}

    raw = db_session.execute(
        text("SELECT secrets FROM connectors WHERE id = :id"), {"id": row.id}
    ).scalar_one()
    assert "top-secret-123" not in raw
    assert "ACME_API_KEY" not in raw
