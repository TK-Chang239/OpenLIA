"""Tests for build_dispatcher_for_session."""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from openlia.connectors.types import Category
from sqlalchemy import event
from sqlalchemy.engine import Engine


@pytest.fixture
def fk_engine(engine: Engine) -> Iterator[Engine]:
    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    yield engine


def _seed_validated_connector(
    db_session,
    *,
    source,
    category,
    provider_id,
    launch,
    cached_tools=None,
    api_key_encrypted=None,
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
            api_key_encrypted=api_key_encrypted,
        )
    )
    db_session.commit()
    return cid


def test_build_dispatcher_loads_validated(db_session, fk_engine, monkeypatch):
    from openlia_server.db.models.connectors import ToolAllowlist
    from openlia_server.services.dispatcher_factory import build_dispatcher_for_session

    cid = _seed_validated_connector(
        db_session,
        source="remote_mcp",
        category="financial",
        provider_id="user_mcp",
        launch={"kind": "remote_mcp", "url": "https://x", "headers": {}},
        cached_tools=[{"name": "get_quote", "description": "d", "input_schema": {}}],
    )
    db_session.add(
        ToolAllowlist(
            id="aw-1",
            department_id="equity_research",
            connector_id=cid,
            tool_name="get_quote",
            scoped_by="llm_adapter",
        )
    )
    db_session.commit()

    def fake_session_factory(spec):  # not invoked for this test
        return None

    dispatcher = build_dispatcher_for_session(db_session, session_factory=fake_session_factory)
    out = dispatcher.tools_for_department("equity_research")
    assert any(t["name"] == "user_mcp__get_quote" for t in out)
    assert dispatcher.connector_categories[cid] == Category.FINANCIAL


def test_build_dispatcher_skips_failed(db_session, fk_engine):
    from openlia_server.db.models.connectors import Connector
    from openlia_server.services.dispatcher_factory import build_dispatcher_for_session

    db_session.add(
        Connector(
            id="failed-1",
            provider_id="user_mcp",
            source="remote_mcp",
            category="financial",
            launch={"kind": "remote_mcp", "url": "https://x", "headers": {}},
            status="failed",
        )
    )
    db_session.commit()

    dispatcher = build_dispatcher_for_session(db_session, session_factory=lambda s: None)
    assert dispatcher.connectors == {}


def test_build_dispatcher_resolves_built_in_secret(db_session, fk_engine):
    from openlia.connectors.types import ConnectorSource
    from openlia_server.db.crypto import encrypt_for_row
    from openlia_server.db.models.connectors import Connector
    from openlia_server.services.dispatcher_factory import build_dispatcher_for_session

    cid = "built-in-id"
    encrypted = encrypt_for_row(cid, "secret-key")
    db_session.add(
        Connector(
            id=cid,
            provider_id="eodhd",
            source="built_in",
            category="financial",
            launch={"kind": "built_in", "template_id": "eodhd"},
            status="validated",
            api_key_encrypted=encrypted,
        )
    )
    db_session.commit()

    # session_factory is invoked lazily on transport.open(), not at build time,
    # so we inspect the spec stored on the transport directly.
    dispatcher = build_dispatcher_for_session(db_session, session_factory=lambda s: None)
    transport = dispatcher.connectors[cid].transport
    spec = transport.spec
    assert spec.kind is ConnectorSource.CLI_MCP
    # Env var named per the EODHD template (registered in C1 stubs).
    assert "EODHD_API_KEY" in spec.env
    assert spec.env["EODHD_API_KEY"] == "secret-key"
