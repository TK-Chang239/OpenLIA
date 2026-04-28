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
            "credentials_ref": "secret://eodhd/key",
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


def test_revalidate_404_for_unknown(client):
    resp = client.post("/api/connectors/no-such-id/validate")
    assert resp.status_code == 404
