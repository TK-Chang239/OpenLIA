"""Tests for GET /api/connectors/review."""

from __future__ import annotations

import uuid
from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import event
from sqlalchemy.engine import Engine


@pytest.fixture
def client(engine: Engine, db_session_factory) -> Iterator[TestClient]:
    @event.listens_for(engine, "connect")
    def _fk_on(dbapi_conn, _):
        cur = dbapi_conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.close()

    from openlia_server.routes.connectors import build_connectors_router

    app = FastAPI()
    app.include_router(
        build_connectors_router(db_session_factory=db_session_factory), prefix="/api"
    )
    yield TestClient(app)


def _seed(db_session, connectors, allowlist):
    from openlia_server.db.models.connectors import Connector, ToolAllowlist

    for c in connectors:
        db_session.add(Connector(**c))
    for a in allowlist:
        db_session.add(ToolAllowlist(**a))
    db_session.commit()


def _dep(body, dep_id):
    return next(d for d in body["departments"] if d["department_id"] == dep_id)


def _cat(dep, cat):
    return next(c for c in dep["categories"] if c["category"] == cat)


def test_readiness_ready_when_required_category_filled(client, db_session):
    cid = str(uuid.uuid4())
    _seed(
        db_session,
        connectors=[
            dict(
                id=cid,
                provider_id="eodhd",
                source="built_in",
                category="financial",
                launch={"kind": "built_in", "template_id": "eodhd"},
                status="validated",
            ),
            # add a news provider so equity_research's news requirement is satisfied too
            dict(
                id="news-1",
                provider_id="newsapi_ai",
                source="built_in",
                category="news",
                launch={"kind": "built_in", "template_id": "newsapi_ai"},
                status="validated",
            ),
        ],
        allowlist=[
            dict(
                id=str(uuid.uuid4()),
                department_id="equity_research",
                connector_id=cid,
                tool_name="t1",
                scoped_by="built_in_map",
            ),
            dict(
                id=str(uuid.uuid4()),
                department_id="equity_research",
                connector_id="news-1",
                tool_name="search_articles",
                scoped_by="built_in_map",
            ),
        ],
    )
    resp = client.get("/api/connectors/review")
    assert resp.status_code == 200
    body = resp.json()
    er = _dep(body, "equity_research")
    assert er["ready"] is True
    fin = _cat(er, "financial")
    assert fin["status"] == "ok"
    assert fin["tool_count"] == 1
    assert "eodhd" in fin["providers"]
    news = _cat(er, "news")
    assert news["status"] == "ok"


def test_readiness_not_ready_when_required_missing(client, db_session):
    cid = str(uuid.uuid4())
    _seed(
        db_session,
        connectors=[
            dict(
                id=cid,
                provider_id="eodhd",
                source="built_in",
                category="financial",
                launch={"kind": "built_in", "template_id": "eodhd"},
                status="validated",
            ),
        ],
        allowlist=[
            dict(
                id=str(uuid.uuid4()),
                department_id="earnings_update",
                connector_id=cid,
                tool_name="t1",
                scoped_by="built_in_map",
            ),
        ],
    )
    resp = client.get("/api/connectors/review")
    assert resp.status_code == 200
    body = resp.json()
    eu = _dep(body, "earnings_update")
    assert eu["ready"] is False
    news = _cat(eu, "news")
    assert news["status"] == "missing"
    assert news["tool_count"] == 0


def test_readiness_optional_basic_when_empty(client, db_session):
    """Optional category with no tools shows 'basic' but does not block readiness."""

    cid = str(uuid.uuid4())
    _seed(
        db_session,
        connectors=[
            dict(
                id=cid,
                provider_id="eodhd",
                source="built_in",
                category="financial",
                launch={"kind": "built_in", "template_id": "eodhd"},
                status="validated",
            ),
            dict(
                id="news-1",
                provider_id="newsapi_ai",
                source="built_in",
                category="news",
                launch={"kind": "built_in", "template_id": "newsapi_ai"},
                status="validated",
            ),
        ],
        allowlist=[
            dict(
                id=str(uuid.uuid4()),
                department_id="equity_research",
                connector_id=cid,
                tool_name="t",
                scoped_by="built_in_map",
            ),
            dict(
                id=str(uuid.uuid4()),
                department_id="equity_research",
                connector_id="news-1",
                tool_name="t",
                scoped_by="built_in_map",
            ),
        ],
    )
    resp = client.get("/api/connectors/review")
    body = resp.json()
    er = _dep(body, "equity_research")
    social = _cat(er, "social")
    assert social["required"] is False
    assert social["status"] == "basic"


def test_readiness_optional_enhanced_when_filled(client, db_session):
    cid = str(uuid.uuid4())
    sid = str(uuid.uuid4())
    _seed(
        db_session,
        connectors=[
            dict(
                id=cid,
                provider_id="eodhd",
                source="built_in",
                category="financial",
                launch={"kind": "built_in", "template_id": "eodhd"},
                status="validated",
            ),
            dict(
                id="news-1",
                provider_id="newsapi_ai",
                source="built_in",
                category="news",
                launch={"kind": "built_in", "template_id": "newsapi_ai"},
                status="validated",
            ),
            dict(
                id=sid,
                provider_id="my_x_mcp",
                source="remote_mcp",
                category="social",
                launch={"kind": "remote_mcp", "url": "https://x", "headers": {}},
                status="validated",
            ),
        ],
        allowlist=[
            dict(
                id=str(uuid.uuid4()),
                department_id="equity_research",
                connector_id=cid,
                tool_name="t",
                scoped_by="built_in_map",
            ),
            dict(
                id=str(uuid.uuid4()),
                department_id="equity_research",
                connector_id="news-1",
                tool_name="t",
                scoped_by="built_in_map",
            ),
            dict(
                id=str(uuid.uuid4()),
                department_id="equity_research",
                connector_id=sid,
                tool_name="search_x",
                scoped_by="llm_adapter",
            ),
        ],
    )
    resp = client.get("/api/connectors/review")
    body = resp.json()
    er = _dep(body, "equity_research")
    social = _cat(er, "social")
    assert social["status"] == "enhanced"
    assert "my_x_mcp" in social["providers"]


def test_readiness_ignores_non_validated_connectors(client, db_session):
    cid = str(uuid.uuid4())
    _seed(
        db_session,
        connectors=[
            dict(
                id=cid,
                provider_id="eodhd",
                source="built_in",
                category="financial",
                launch={"kind": "built_in", "template_id": "eodhd"},
                status="failed",
            ),
        ],
        allowlist=[
            # Stale row pointing at a failed connector.
            dict(
                id=str(uuid.uuid4()),
                department_id="equity_research",
                connector_id=cid,
                tool_name="t",
                scoped_by="built_in_map",
            ),
        ],
    )
    resp = client.get("/api/connectors/review")
    body = resp.json()
    er = _dep(body, "equity_research")
    fin = _cat(er, "financial")
    assert fin["tool_count"] == 0
    assert fin["status"] == "missing"
    assert er["ready"] is False
