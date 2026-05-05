"""Scenario 2 — `python_lib` runner activation lifts MR from disabled to active.

Drives the wizard-time adapter flow with a stubbed need-set so the test
doesn't have to approve all 11 production MR needs:

  1. Inject a single fake need into `runner_specs_service` via the
     test-only registry override.
  2. Create a `python_lib` connector (validation stubbed).
  3. Seed a proposed spec directly into the in-memory cache.
  4. POST `/api/connectors/{id}/proposed-specs/approve` to persist it.
  5. GET `/api/dept-health` and assert `macro_research` is active.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from openlia.connectors.types import Category, NeedParameter, RunnerNeed
from openlia_server.app import create_app
from openlia_server.middleware.rate_limit import limiter
from openlia_server.services import connectors_service, runner_specs_service


@pytest.fixture(autouse=True)
def _clear_rate_limiter():
    limiter().clear()
    yield
    limiter().clear()


@pytest.fixture(autouse=True)
def _reset_runner_specs_state():
    yield
    runner_specs_service.set_dept_needs_for_testing({})
    runner_specs_service.set_dept_categories_for_testing({})
    runner_specs_service._PROPOSALS.clear()  # type: ignore[attr-defined]


@pytest.fixture
def client(db_session) -> TestClient:
    from openlia_server.db import session as session_mod

    app = create_app(
        db_session_factory=session_mod.SessionLocal,
        is_loopback_request=lambda _: True,
    )
    return TestClient(app)


def test_python_lib_runner_activation(client: TestClient, monkeypatch) -> None:
    # 1. Override MR's need set to a single placeholder need so the dept
    #    activates after one approval. (Real MR has ~11 needs.)
    fake_need = RunnerNeed(
        id="debt_gdp",
        description="Government debt as % of GDP.",
        parameters=[
            NeedParameter(
                name="country",
                description="ISO code",
                type="str",
                required=False,
                default="US",
            )
        ],
        shape="float",
    )
    runner_specs_service.set_dept_needs_for_testing({"macro_research": [fake_need]})
    runner_specs_service.set_dept_categories_for_testing(
        {"macro_research": ({Category.FINANCIAL}, set())}
    )

    # The pure dept-health checker reads needs straight from YAML; for this
    # test we want it to see the same fake-need slate so MR can flip from
    # disabled to active after a single approval.
    def _fake_load_needs(dept_id: str) -> list[RunnerNeed]:
        return [fake_need] if dept_id == "macro_research" else []

    monkeypatch.setattr("openlia.departments.health.load_needs", _fake_load_needs)

    # 2. Stub validation to succeed and surface a python_lib callable.
    async def fake_validate(_launch, _secrets, *, tool_overrides=None):
        return connectors_service.ValidationOk(
            tools=[],
            python_callables=[
                {
                    "qualname": "APIClient.real_time_quote",
                    "signature": "(self, symbol: str) -> dict",
                    "doc": "Latest quote.",
                }
            ],
        )

    monkeypatch.setattr(connectors_service, "_validate_launch", fake_validate)

    # Create a python_lib financial connector.
    resp = client.post(
        "/api/connectors",
        json={
            "source": "python_lib",
            "category": "financial",
            "provider_id": "fmp",
            "display_name": "FMP",
            "launch": {
                "modes": [
                    {
                        "kind": "python_lib",
                        "pip_name": "financialmodelingprep",
                        "pip_version": "1.0.0",
                        "import_module": "financialmodelingprep",
                        "instance_factory": {"cls": "APIClient", "args": {}},
                    }
                ]
            },
            "secrets": {},
        },
    )
    assert resp.status_code == 201, resp.text
    connector_id = resp.json()["id"]

    # Seed a validated WEB_SEARCH connector so MR's category gate is
    # satisfied — MR now requires both FINANCIAL and WEB_SEARCH.
    ws_resp = client.post(
        "/api/connectors",
        json={
            "source": "remote_mcp",
            "category": "web_search",
            "provider_id": "firecrawl",
            "display_name": "Firecrawl",
            "launch": {
                "modes": [
                    {
                        "kind": "remote_mcp",
                        "url": "https://example.invalid/mcp",
                        "headers": {},
                    }
                ]
            },
            "secrets": {},
        },
    )
    assert ws_resp.status_code == 201, ws_resp.text

    # MR should still be disabled at this point — categories OK but
    # the need has no spec.
    health = {row["department_id"]: row for row in client.get("/api/dept-health").json()}
    assert health["macro_research"]["status"] == "disabled"
    assert health["macro_research"]["unresolved_needs"] == ["debt_gdp"]

    # 3. Seed a proposed spec directly into the cache. (Bypassing the
    #    adapter-LLM canary keeps this test independent of any real
    #    LLM provider.)
    runner_specs_service._PROPOSALS[connector_id] = [  # type: ignore[attr-defined]
        runner_specs_service.ProposedSpec(
            department_id="macro_research",
            need_id="debt_gdp",
            proposed_spec={
                "need_id": "debt_gdp",
                "access_mode": "python_lib",
                "module": "financialmodelingprep",
                "instance_factory": {"cls": "APIClient", "args": {}},
                "method": "APIClient.real_time_quote",
                "param_bindings": {"country": {"to_arg": "symbol", "transform": None}},
                "constants": {},
                "shape": "float",
            },
            canary_value=110.0,
            canary_ok=True,
            shape_match=True,
            error=None,
        )
    ]

    # 4. Approve.
    approve = client.post(
        f"/api/connectors/{connector_id}/proposed-specs/approve",
        json={"department_id": "macro_research", "need_id": "debt_gdp"},
    )
    assert approve.status_code == 201, approve.text

    # 5. MR should now be active.
    health = {row["department_id"]: row for row in client.get("/api/dept-health").json()}
    assert health["macro_research"]["status"] == "active", health["macro_research"]
