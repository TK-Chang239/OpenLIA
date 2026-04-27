"""Tests for /api/connectors CRUD + V2 validate."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openlia.connectors.types import ToolDefinition
from openlia.connectors.validate import ValidationFailure, ValidationOk
from sqlalchemy import event
from sqlalchemy.engine import Engine


@pytest.fixture
def client(engine: Engine, db_session_factory) -> Iterator[TestClient]:
    from openlia_server.routes.connectors import build_connectors_router

    # SQLite needs FK enforcement enabled per-connection for cascade delete to fire.
    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):  # type: ignore[no-untyped-def]
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    app = FastAPI()
    app.include_router(
        build_connectors_router(db_session_factory=db_session_factory), prefix="/api"
    )
    yield TestClient(app)


def test_create_connector_validated(client, monkeypatch):
    async def fake_validate(*, spec, canary_tool, session_factory):
        return ValidationOk(
            tools=[ToolDefinition(name="get_quote", description="d", input_schema={})]
        )

    monkeypatch.setattr(
        "openlia_server.services.connectors_service.validate_connector",
        fake_validate,
    )

    resp = client.post(
        "/api/connectors",
        json={
            "source": "built_in",
            "category": "financial",
            "provider_id": "eodhd",
            "launch": {"kind": "built_in", "template_id": "eodhd"},
            "api_key": "real-secret",
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "validated"
    assert body["cached_tools_count"] == 1


def test_create_connector_failed(client, monkeypatch):
    async def fake_validate(**kwargs):
        return ValidationFailure(error="bad key")

    monkeypatch.setattr(
        "openlia_server.services.connectors_service.validate_connector",
        fake_validate,
    )

    resp = client.post(
        "/api/connectors",
        json={
            "source": "remote_mcp",
            "category": "news",
            "provider_id": "user_mcp_news1",
            "launch": {"kind": "remote_mcp", "url": "https://x", "headers": {}},
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "failed"
    assert "bad key" in body["last_error"]


def test_list_connectors(client, monkeypatch):
    async def fake_validate(**kwargs):
        return ValidationOk(tools=[])

    monkeypatch.setattr(
        "openlia_server.services.connectors_service.validate_connector",
        fake_validate,
    )

    client.post(
        "/api/connectors",
        json={
            "source": "built_in",
            "category": "financial",
            "provider_id": "eodhd",
            "launch": {"kind": "built_in", "template_id": "eodhd"},
        },
    )
    resp = client.get("/api/connectors")
    assert resp.status_code == 200
    rows = resp.json()
    assert len(rows) == 1
    assert rows[0]["provider_id"] == "eodhd"


def test_delete_cascades_allowlist(client, monkeypatch, db_session):
    async def fake_validate(**kwargs):
        return ValidationOk(tools=[])

    monkeypatch.setattr(
        "openlia_server.services.connectors_service.validate_connector",
        fake_validate,
    )

    resp = client.post(
        "/api/connectors",
        json={
            "source": "built_in",
            "category": "financial",
            "provider_id": "eodhd",
            "launch": {"kind": "built_in", "template_id": "eodhd"},
        },
    )
    cid = resp.json()["id"]

    from openlia_server.db.models.connectors import ToolAllowlist

    db_session.add(
        ToolAllowlist(
            id="alw-1",
            department_id="equity_research",
            connector_id=cid,
            tool_name="t",
            scoped_by="built_in_map",
        )
    )
    db_session.commit()

    resp = client.delete(f"/api/connectors/{cid}")
    assert resp.status_code == 204

    # Cascade is enforced by the SQL FK; confirm via a fresh session.
    db_session.expire_all()
    assert db_session.query(ToolAllowlist).count() == 0


def test_revalidate_404_for_unknown(client):
    resp = client.post("/api/connectors/no-such-id/validate")
    assert resp.status_code == 404


def test_create_connector_encrypts_api_key(client, monkeypatch, db_session):
    async def fake_validate(**kwargs):
        return ValidationOk(tools=[])

    monkeypatch.setattr(
        "openlia_server.services.connectors_service.validate_connector",
        fake_validate,
    )

    plaintext = "real-secret"
    resp = client.post(
        "/api/connectors",
        json={
            "source": "built_in",
            "category": "financial",
            "provider_id": "eodhd",
            "launch": {"kind": "built_in", "template_id": "eodhd"},
            "api_key": plaintext,
        },
    )
    assert resp.status_code == 201, resp.text
    cid = resp.json()["id"]

    from openlia_server.db.crypto import decrypt_for_row
    from openlia_server.db.models.connectors import Connector

    db_session.expire_all()
    row = db_session.get(Connector, cid)
    assert row is not None
    assert row.api_key_encrypted is not None
    assert row.api_key_encrypted != plaintext
    assert decrypt_for_row(row.id, row.api_key_encrypted) == plaintext
