"""Tests for the per-connector wizard-time proposed-specs endpoints + service.

Covers:
- empty-list response when no dept needs are registered.
- proposal generation when dept needs/categories are seeded via the test helper.
- approval persists a `runner_callable_specs` row and returns its id.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openlia.connectors.types import (
    Category,
    ConnectorStatus,
    NeedParameter,
    RunnerNeed,
)
from openlia_server.db.models.connectors import Connector, RunnerCallableSpec
from openlia_server.routes.runner_specs import build_runner_specs_router
from openlia_server.services import runner_specs_service
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session as DBSession


class _StubLlm:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    async def generate_json(self, *, prompt: str) -> dict[str, Any]:
        return self._payload


@pytest.fixture(autouse=True)
def _reset_state() -> Iterator[None]:
    runner_specs_service.set_dept_needs_for_testing({})
    runner_specs_service.set_dept_categories_for_testing({})
    runner_specs_service._PROPOSALS.clear()
    yield
    runner_specs_service.set_dept_needs_for_testing({})
    runner_specs_service.set_dept_categories_for_testing({})
    runner_specs_service._PROPOSALS.clear()


def test_hydrate_dept_registries_loads_real_macro_research_needs() -> None:
    """The hydration helper must populate `_DEPT_NEEDS` for runner-bearing
    departments — without it, every macro_research need stays unresolved."""
    runner_specs_service.hydrate_dept_registries()
    needs = runner_specs_service._DEPT_NEEDS.get("macro_research", [])
    need_ids = {n.id for n in needs}
    # Smoke-check a handful of needs declared in macro_research.needs.yaml.
    assert "stock_quote" in need_ids
    assert "cpi_yoy" in need_ids
    assert "geopolitical_news" in need_ids
    cats = runner_specs_service._DEPT_CATEGORIES.get("macro_research")
    assert cats is not None
    required, optional = cats
    assert Category.FINANCIAL in required
    assert Category.NEWS in optional


def _client(
    db_session_factory,
    llm_payload: dict[str, Any] | None = None,
) -> TestClient:
    app = FastAPI()

    def _factory():
        return _StubLlm(llm_payload or {})

    app.include_router(
        build_runner_specs_router(
            db_session_factory=db_session_factory,
            llm_client_factory=_factory,
        ),
        prefix="/api",
    )
    return TestClient(app)


def _seed_connector(
    session: DBSession,
    *,
    cid: str | None = None,
    category: str = "financial",
    cached_tools: list[dict] | None = None,
) -> Connector:
    row = Connector(
        id=cid or str(uuid.uuid4()),
        provider_id="eodhd",
        display_name="EODHD",
        source="cli_mcp",
        category=category,
        launch={
            "modes": [
                {
                    "kind": "cli_mcp",
                    "argv": ["eodhd-mcp"],
                    "env_keys": ["EODHD_API_KEY"],
                }
            ]
        },
        secrets={},
        cached_tools=cached_tools
        or [
            {
                "name": "get_quote",
                "description": "Quote tool",
                "input_schema": {
                    "type": "object",
                    "properties": {"symbol": {"type": "string"}},
                },
            }
        ],
        status=ConnectorStatus.VALIDATED.value,
    )
    session.add(row)
    session.commit()
    session.refresh(row)
    return row


def test_proposed_specs_empty_when_no_dept_needs(
    engine: Engine, db_session_factory, db_session: DBSession
) -> None:
    """Default state: no dept needs registered -> resolve produces no proposals."""
    conn = _seed_connector(db_session)
    client = _client(db_session_factory)

    resp = client.get(f"/api/connectors/{conn.id}/proposed-specs")
    assert resp.status_code == 200
    assert resp.json() == []

    resp = client.post(f"/api/connectors/{conn.id}/proposed-specs/resolve")
    assert resp.status_code == 200
    assert resp.json() == []


def test_resolve_returns_proposal_for_overlapping_dept(
    engine: Engine, db_session_factory, db_session: DBSession
) -> None:
    conn = _seed_connector(db_session)
    runner_specs_service.set_dept_needs_for_testing(
        {
            "equity_research": [
                RunnerNeed(
                    id="real_time_quote",
                    description="latest trade",
                    parameters=[
                        NeedParameter(
                            name="ticker",
                            description="ticker",
                            type="str",
                            required=True,
                        )
                    ],
                    shape="dict",
                )
            ]
        }
    )
    runner_specs_service.set_dept_categories_for_testing(
        {"equity_research": ({Category.FINANCIAL}, set())}
    )
    client = _client(
        db_session_factory,
        llm_payload={
            "tool_name": "get_quote",
            "method": None,
            "param_bindings": {"ticker": {"to_arg": "symbol", "transform": "upper"}},
            "constants": {},
        },
    )

    resp = client.post(f"/api/connectors/{conn.id}/proposed-specs/resolve")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 1
    p = body[0]
    assert p["department_id"] == "equity_research"
    assert p["need_id"] == "real_time_quote"
    assert p["proposed_spec"]["tool_name"] == "get_quote"
    assert p["proposed_spec"]["param_bindings"]["ticker"]["to_arg"] == "symbol"
    # Canary will fail because the stub transport isn't real (legacy/no-op):
    # the test just asserts the proposal carries through.
    assert "canary_ok" in p


def test_resolve_skips_dept_when_categories_dont_overlap(
    engine: Engine, db_session_factory, db_session: DBSession
) -> None:
    conn = _seed_connector(db_session, category="financial")
    runner_specs_service.set_dept_needs_for_testing(
        {
            "macro_research": [
                RunnerNeed(
                    id="news",
                    description="x",
                    parameters=[],
                    shape="list",
                )
            ]
        }
    )
    runner_specs_service.set_dept_categories_for_testing(
        # macro_research wants news/social, not financial.
        {"macro_research": ({Category.NEWS}, {Category.SOCIAL})}
    )
    client = _client(db_session_factory, llm_payload={})

    resp = client.post(f"/api/connectors/{conn.id}/proposed-specs/resolve")
    assert resp.status_code == 200
    assert resp.json() == []


def test_approve_persists_runner_callable_spec(
    engine: Engine, db_session_factory, db_session: DBSession
) -> None:
    conn = _seed_connector(db_session)
    # Seed an in-memory proposal directly so we don't need a working transport
    # for the canary call.
    runner_specs_service._PROPOSALS[conn.id] = [
        runner_specs_service.ProposedSpec(
            department_id="equity_research",
            need_id="real_time_quote",
            proposed_spec={
                "need_id": "real_time_quote",
                "access_mode": "cli_mcp",
                "tool_name": "get_quote",
                "module": None,
                "instance_factory": None,
                "method": None,
                "param_bindings": {"ticker": {"to_arg": "symbol", "transform": "upper"}},
                "constants": {},
                "shape": "dict",
            },
            canary_value={"price": 1.0},
            canary_ok=True,
            shape_match=True,
            error=None,
        )
    ]
    client = _client(db_session_factory)

    resp = client.post(
        f"/api/connectors/{conn.id}/proposed-specs/approve",
        json={"department_id": "equity_research", "need_id": "real_time_quote"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["department_id"] == "equity_research"
    assert body["need_id"] == "real_time_quote"
    assert body["connector_id"] == conn.id
    assert body["access_mode"] == "cli_mcp"

    # Row exists in DB.
    rows = db_session.query(RunnerCallableSpec).all()
    assert len(rows) == 1
    persisted = rows[0]
    assert persisted.department_id == "equity_research"
    assert persisted.need_id == "real_time_quote"
    assert persisted.spec["tool_name"] == "get_quote"
    assert persisted.canary_value == {"value": {"price": 1.0}, "shape_match": True}


def test_approve_replaces_existing_row_for_same_dept_need(
    engine: Engine, db_session_factory, db_session: DBSession
) -> None:
    conn = _seed_connector(db_session)
    db_session.add(
        RunnerCallableSpec(
            id="old-id",
            department_id="equity_research",
            need_id="real_time_quote",
            connector_id=conn.id,
            access_mode="cli_mcp",
            spec={"need_id": "real_time_quote", "access_mode": "cli_mcp"},
            canary_value=None,
        )
    )
    db_session.commit()

    runner_specs_service._PROPOSALS[conn.id] = [
        runner_specs_service.ProposedSpec(
            department_id="equity_research",
            need_id="real_time_quote",
            proposed_spec={
                "need_id": "real_time_quote",
                "access_mode": "cli_mcp",
                "tool_name": "fresh_tool",
                "param_bindings": {},
                "constants": {},
                "shape": "dict",
            },
            canary_value=None,
            canary_ok=False,
            shape_match=False,
            error=None,
        )
    ]
    client = _client(db_session_factory)
    resp = client.post(
        f"/api/connectors/{conn.id}/proposed-specs/approve",
        json={"department_id": "equity_research", "need_id": "real_time_quote"},
    )
    assert resp.status_code == 201, resp.text
    db_session.expire_all()
    rows = db_session.query(RunnerCallableSpec).all()
    assert len(rows) == 1
    assert rows[0].id == "old-id"
    assert rows[0].spec["tool_name"] == "fresh_tool"


def test_approve_404_when_no_matching_proposal(
    engine: Engine, db_session_factory, db_session: DBSession
) -> None:
    conn = _seed_connector(db_session)
    client = _client(db_session_factory)
    resp = client.post(
        f"/api/connectors/{conn.id}/proposed-specs/approve",
        json={"department_id": "ghost", "need_id": "x"},
    )
    assert resp.status_code == 404
