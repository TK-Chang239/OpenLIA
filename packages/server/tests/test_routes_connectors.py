"""Tests for /api/connectors CRUD + V2 validate."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openlia.connectors.types import ToolDefinition
from openlia_server.services import connectors_service
from sqlalchemy import event
from sqlalchemy.engine import Engine


@pytest.fixture
def client(engine: Engine, db_session_factory) -> Iterator[TestClient]:
    from openlia_server.routes.connectors import build_connectors_router

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


def _patch_validation_ok(monkeypatch, tools=None, callables=None):
    async def fake(launch, secrets):
        return connectors_service.ValidationOk(
            tools=tools
            or [
                {
                    "name": t.name,
                    "description": t.description,
                    "input_schema": t.input_schema,
                }
                for t in [ToolDefinition(name="get_quote", description="d", input_schema={})]
            ],
            python_callables=callables or [],
        )

    monkeypatch.setattr("openlia_server.services.connectors_service._validate_launch", fake)


def _patch_validation_failure(monkeypatch, message="bad key"):
    async def fake(launch, secrets):
        return connectors_service.ValidationFailure(error=message)

    monkeypatch.setattr("openlia_server.services.connectors_service._validate_launch", fake)


def test_create_connector_validated(client, monkeypatch):
    _patch_validation_ok(monkeypatch)
    resp = client.post(
        "/api/connectors",
        json={
            "source": "cli_mcp",
            "category": "financial",
            "provider_id": "eodhd",
            "display_name": "EODHD",
            "launch": {
                "modes": [{"kind": "cli_mcp", "argv": ["uvx", "eodhd-mcp"], "env_keys": []}]
            },
            "secrets": {"EODHD_API_KEY": "k"},
        },
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["status"] == "validated"
    assert body["cached_tools_count"] == 1


def test_create_connector_failed(client, monkeypatch):
    _patch_validation_failure(monkeypatch, "bad key")
    resp = client.post(
        "/api/connectors",
        json={
            "source": "remote_mcp",
            "category": "news",
            "provider_id": "user_mcp_news1",
            "display_name": "Custom News MCP",
            "launch": {"modes": [{"kind": "remote_mcp", "url": "https://x", "headers": {}}]},
        },
    )
    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "failed"
    assert "bad key" in body["last_error"]


def test_list_connectors(client, monkeypatch):
    _patch_validation_ok(monkeypatch, tools=[])
    client.post(
        "/api/connectors",
        json={
            "source": "cli_mcp",
            "category": "financial",
            "provider_id": "eodhd",
            "display_name": "EODHD",
            "launch": {
                "modes": [{"kind": "cli_mcp", "argv": ["uvx", "eodhd-mcp"], "env_keys": []}]
            },
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


def test_get_connector_detail_returns_launch_and_secret_keys(client, monkeypatch):
    _patch_validation_ok(monkeypatch, tools=[])
    create = client.post(
        "/api/connectors",
        json={
            "source": "cli_mcp",
            "category": "financial",
            "provider_id": "eodhd",
            "display_name": "EODHD",
            "launch": {
                "modes": [
                    {"kind": "cli_mcp", "argv": ["uvx", "eodhd-mcp"], "env_keys": ["EODHD_API_KEY"]}
                ]
            },
            "secrets": {"EODHD_API_KEY": "secret-value"},
        },
    )
    cid = create.json()["id"]

    resp = client.get(f"/api/connectors/{cid}")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["id"] == cid
    assert body["provider_id"] == "eodhd"
    assert body["launch"]["modes"][0]["argv"] == ["uvx", "eodhd-mcp"]
    assert body["secret_keys"] == ["EODHD_API_KEY"]
    assert "secrets" not in body  # values must never leak


def test_get_connector_detail_404_for_unknown(client):
    resp = client.get("/api/connectors/no-such-id")
    assert resp.status_code == 404


def test_update_connector_revalidates_and_replaces_launch(client, monkeypatch):
    _patch_validation_ok(monkeypatch, tools=[])
    create = client.post(
        "/api/connectors",
        json={
            "source": "cli_mcp",
            "category": "financial",
            "provider_id": "eodhd",
            "display_name": "EODHD",
            "launch": {
                "modes": [{"kind": "cli_mcp", "argv": ["old"], "env_keys": []}]
            },
            "secrets": {"EODHD_API_KEY": "old-value"},
        },
    )
    cid = create.json()["id"]

    resp = client.put(
        f"/api/connectors/{cid}",
        json={
            "source": "cli_mcp",
            "category": "financial",
            "provider_id": "eodhd",
            "display_name": "EODHD (renamed)",
            "launch": {
                "modes": [{"kind": "cli_mcp", "argv": ["new", "argv"], "env_keys": []}]
            },
        },
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["display_name"] == "EODHD (renamed)"
    assert body["status"] == "validated"

    detail = client.get(f"/api/connectors/{cid}").json()
    assert detail["launch"]["modes"][0]["argv"] == ["new", "argv"]
    # secrets omitted in PUT body -> existing secrets preserved
    assert detail["secret_keys"] == ["EODHD_API_KEY"]


def test_update_connector_replaces_secrets_when_provided(client, monkeypatch):
    _patch_validation_ok(monkeypatch, tools=[])
    create = client.post(
        "/api/connectors",
        json={
            "source": "cli_mcp",
            "category": "financial",
            "provider_id": "eodhd",
            "display_name": "EODHD",
            "launch": {"modes": [{"kind": "cli_mcp", "argv": ["x"], "env_keys": []}]},
            "secrets": {"OLD_KEY": "v"},
        },
    )
    cid = create.json()["id"]

    client.put(
        f"/api/connectors/{cid}",
        json={
            "source": "cli_mcp",
            "category": "financial",
            "provider_id": "eodhd",
            "display_name": "EODHD",
            "launch": {"modes": [{"kind": "cli_mcp", "argv": ["x"], "env_keys": []}]},
            "secrets": {"NEW_KEY": "v2"},
        },
    )
    detail = client.get(f"/api/connectors/{cid}").json()
    assert detail["secret_keys"] == ["NEW_KEY"]


def test_update_connector_404_for_unknown(client):
    resp = client.put(
        "/api/connectors/no-such-id",
        json={
            "source": "cli_mcp",
            "category": "financial",
            "provider_id": "x",
            "display_name": "x",
            "launch": {"modes": [{"kind": "cli_mcp", "argv": ["x"], "env_keys": []}]},
        },
    )
    assert resp.status_code == 404
