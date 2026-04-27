"""Tests for /api/connectors/review/scope."""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openlia.connectors.scope import ScopedTool
from sqlalchemy import event
from sqlalchemy.engine import Engine


@pytest.fixture
def client(engine: Engine, db_session_factory) -> Iterator[TestClient]:
    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):  # type: ignore[no-untyped-def]
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    from openlia_server.routes.connectors import build_connectors_router

    app = FastAPI()
    app.include_router(
        build_connectors_router(db_session_factory=db_session_factory), prefix="/api"
    )
    yield TestClient(app)


def _create_validated_connector(
    db_session, source, category, provider_id, launch, cached_tools=None
):
    from openlia_server.db.models.connectors import Connector

    cid = str(uuid.uuid4())
    db_session.add(
        Connector(
            id=cid,
            provider_id=provider_id,
            source=source,
            category=category,
            launch=launch,
            status="validated",
            cached_tools=cached_tools or [],
        )
    )
    db_session.commit()
    return cid


def test_scope_built_in_copies_shipped_allowlist(client, db_session):
    cid = _create_validated_connector(
        db_session,
        source="built_in",
        category="financial",
        provider_id="eodhd",
        launch={"kind": "built_in", "template_id": "eodhd"},
    )
    resp = client.post("/api/connectors/review/scope", json={})
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["scoped"] >= 1
    assert any(r["connector_id"] == cid and r["rows_written"] >= 1 for r in body["per_connector"])

    from openlia_server.db.models.connectors import ToolAllowlist

    db_session.expire_all()
    rows = db_session.query(ToolAllowlist).filter_by(connector_id=cid).all()
    assert len(rows) >= 1
    assert all(r.scoped_by == "built_in_map" for r in rows)


def test_scope_user_mcp_uses_llm(client, db_session, monkeypatch):
    cid = _create_validated_connector(
        db_session,
        source="remote_mcp",
        category="financial",
        provider_id="user_mcp_x",
        launch={"kind": "remote_mcp", "url": "https://x", "headers": {}},
        cached_tools=[{"name": "some_tool", "description": "d", "input_schema": {}}],
    )

    async def fake_scope(*, connector_id, provider_id, category, tools, requirements, llm):
        return [
            ScopedTool(
                department_id="equity_research",
                connector_id=connector_id,
                tool_name="some_tool",
            ),
        ]

    monkeypatch.setattr(
        "openlia_server.services.connectors_service.scope_connector",
        fake_scope,
    )

    resp = client.post("/api/connectors/review/scope", json={"connector_ids": [cid]})
    assert resp.status_code == 200, resp.text

    from openlia_server.db.models.connectors import ToolAllowlist

    db_session.expire_all()
    rows = db_session.query(ToolAllowlist).filter_by(connector_id=cid).all()
    assert len(rows) == 1
    assert rows[0].scoped_by == "llm_adapter"
    assert rows[0].department_id == "equity_research"


def test_scope_skips_unvalidated_connectors(client, db_session):
    from openlia_server.db.models.connectors import Connector

    db_session.add(
        Connector(
            id="failed-1",
            provider_id="eodhd",
            source="built_in",
            category="financial",
            launch={"kind": "built_in", "template_id": "eodhd"},
            status="failed",
        )
    )
    db_session.commit()

    resp = client.post("/api/connectors/review/scope", json={})
    assert resp.status_code == 200
    body = resp.json()
    assert all(r["connector_id"] != "failed-1" for r in body["per_connector"])


def test_scope_wipes_existing_allowlist_for_targeted_connector(client, db_session):
    from openlia_server.db.models.connectors import ToolAllowlist

    cid = _create_validated_connector(
        db_session,
        source="built_in",
        category="financial",
        provider_id="eodhd",
        launch={"kind": "built_in", "template_id": "eodhd"},
    )
    # Seed a stale allowlist row.
    db_session.add(
        ToolAllowlist(
            id="stale",
            department_id="equity_research",
            connector_id=cid,
            tool_name="stale_tool",
            scoped_by="llm_adapter",
        )
    )
    db_session.commit()

    resp = client.post("/api/connectors/review/scope", json={"connector_ids": [cid]})
    assert resp.status_code == 200

    db_session.expire_all()
    rows = db_session.query(ToolAllowlist).filter_by(connector_id=cid).all()
    assert all(r.tool_name != "stale_tool" for r in rows)
