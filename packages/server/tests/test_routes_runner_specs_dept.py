"""Per-department resolve routes (Phase B step 3).

`POST /api/departments/{id}/proposed-specs/resolve` and
`GET  /api/departments/{id}/proposed-specs` mount the dept-level
resolver service (`runner_specs_service.propose_specs_for_department`)
behind HTTP. Empty/no-overlap cases return [] (or `unsatisfiable`).
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
from openlia_server.db.models.connectors import Connector
from openlia_server.routes.runner_specs import build_dept_proposed_specs_router
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
    runner_specs_service._DEPT_PROPOSALS.clear()
    yield
    runner_specs_service.set_dept_needs_for_testing({})
    runner_specs_service.set_dept_categories_for_testing({})
    runner_specs_service._DEPT_PROPOSALS.clear()


def _client(db_session_factory, llm_payload: dict[str, Any] | None = None) -> TestClient:
    app = FastAPI()

    def _factory():
        return _StubLlm(llm_payload or {})

    app.include_router(
        build_dept_proposed_specs_router(
            db_session_factory=db_session_factory,
            llm_client_factory=_factory,
        ),
        prefix="/api",
    )
    return TestClient(app)


def _seed_connector(session: DBSession) -> Connector:
    row = Connector(
        id=str(uuid.uuid4()),
        provider_id="eodhd",
        display_name="EODHD",
        source="cli_mcp",
        category="financial",
        launch={
            "modes": [
                {"kind": "cli_mcp", "argv": ["eodhd-mcp"], "env_keys": ["EODHD_API_KEY"]}
            ]
        },
        secrets={},
        cached_tools=[
            {
                "name": "get_quote",
                "description": "Quote",
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


def test_get_proposed_specs_returns_empty_when_no_cache(
    engine: Engine, db_session_factory, db_session: DBSession
) -> None:
    client = _client(db_session_factory)
    resp = client.get("/api/departments/macro_research/proposed-specs")
    assert resp.status_code == 200
    assert resp.json() == []


def test_resolve_returns_proposal_with_connector_id(
    engine: Engine, db_session_factory, db_session: DBSession
) -> None:
    conn = _seed_connector(db_session)
    runner_specs_service.set_dept_needs_for_testing(
        {
            "macro_research": [
                RunnerNeed(
                    id="real_time_quote",
                    description="quote",
                    parameters=[
                        NeedParameter(
                            name="ticker", description="t", type="str", required=True
                        )
                    ],
                    shape="dict",
                )
            ]
        }
    )
    runner_specs_service.set_dept_categories_for_testing(
        {"macro_research": ({Category.FINANCIAL}, set())}
    )

    client = _client(
        db_session_factory,
        llm_payload={
            "tool_name": "get_quote",
            "param_bindings": {"ticker": {"to_arg": "symbol", "transform": "upper"}},
            "constants": {},
        },
    )

    resp = client.post("/api/departments/macro_research/proposed-specs/resolve")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert len(body) == 1
    assert body[0]["department_id"] == "macro_research"
    assert body[0]["need_id"] == "real_time_quote"
    assert body[0]["connector_id"] == conn.id
    assert body[0]["unsatisfiable"] is False


def test_approve_dept_spec_persists_chosen_connector(
    engine: Engine, db_session_factory, db_session: DBSession
) -> None:
    conn = _seed_connector(db_session)
    runner_specs_service._DEPT_PROPOSALS["macro_research"] = [
        runner_specs_service.ProposedSpec(
            department_id="macro_research",
            need_id="real_time_quote",
            proposed_spec={
                "need_id": "real_time_quote",
                "access_mode": "cli_mcp",
                "tool_name": "get_quote",
                "module": None,
                "instance_factory": None,
                "method": None,
                "param_bindings": {},
                "constants": {},
                "shape": "dict",
            },
            canary_value={"price": 1.0},
            canary_ok=True,
            shape_match=True,
            error=None,
            connector_id=conn.id,
            unsatisfiable=False,
        )
    ]
    client = _client(db_session_factory)
    resp = client.post(
        "/api/departments/macro_research/proposed-specs/approve",
        json={"need_id": "real_time_quote"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["department_id"] == "macro_research"
    assert body["need_id"] == "real_time_quote"
    assert body["connector_id"] == conn.id
    assert body["access_mode"] == "cli_mcp"


def test_approve_dept_spec_404_for_unknown_need(
    engine: Engine, db_session_factory, db_session: DBSession
) -> None:
    client = _client(db_session_factory)
    resp = client.post(
        "/api/departments/macro_research/proposed-specs/approve",
        json={"need_id": "ghost"},
    )
    assert resp.status_code == 404


def test_approve_dept_spec_400_for_unsatisfiable(
    engine: Engine, db_session_factory, db_session: DBSession
) -> None:
    runner_specs_service._DEPT_PROPOSALS["macro_research"] = [
        runner_specs_service.ProposedSpec(
            department_id="macro_research",
            need_id="exotic",
            proposed_spec={},
            canary_value=None,
            canary_ok=False,
            shape_match=False,
            error="no connector covers this",
            connector_id=None,
            unsatisfiable=True,
        )
    ]
    client = _client(db_session_factory)
    resp = client.post(
        "/api/departments/macro_research/proposed-specs/approve",
        json={"need_id": "exotic"},
    )
    assert resp.status_code == 400


def test_get_after_resolve_returns_cached(
    engine: Engine, db_session_factory, db_session: DBSession
) -> None:
    conn = _seed_connector(db_session)
    runner_specs_service.set_dept_needs_for_testing(
        {
            "macro_research": [
                RunnerNeed(
                    id="real_time_quote",
                    description="t",
                    parameters=[
                        NeedParameter(name="ticker", description="t", type="str", required=True)
                    ],
                    shape="dict",
                )
            ]
        }
    )
    runner_specs_service.set_dept_categories_for_testing(
        {"macro_research": ({Category.FINANCIAL}, set())}
    )
    client = _client(
        db_session_factory,
        llm_payload={
            "tool_name": "get_quote",
            "param_bindings": {"ticker": {"to_arg": "symbol", "transform": None}},
            "constants": {},
        },
    )
    client.post("/api/departments/macro_research/proposed-specs/resolve")

    resp = client.get("/api/departments/macro_research/proposed-specs")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body) == 1
    assert body[0]["connector_id"] == conn.id
