"""Scenario 2 — `python_lib` connector creation + spec approval flow.

Drives the wizard-time adapter flow:

  1. Create a `python_lib` connector (validation stubbed).
  2. Seed a proposed spec directly into the in-memory cache.
  3. POST `/api/connectors/{id}/proposed-specs/approve` to persist it.
  4. GET `/api/dept-health` and assert `equity_research` is active
     (FINANCIAL category now satisfied by the validated connector).

The runner-spec activation was previously gated on `requires_runner` and
`unresolved_needs` — both removed in refactor/rescope-need-resolution-portfolio.
Health is now driven purely by category coverage.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from openlia.connectors.types import Category, RunnerNeed
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


def test_python_lib_connector_activates_equity_research(client: TestClient, monkeypatch) -> None:
    """Creating and approving a python_lib financial connector activates
    Equity Research (which requires the FINANCIAL category)."""
    fake_need = RunnerNeed(
        id="social_posts",
        description="Social media posts for sentiment analysis.",
        parameters=[],
        shape="list[dict]",
    )
    runner_specs_service.set_dept_needs_for_testing({"retail_sentiment": [fake_need]})
    runner_specs_service.set_dept_categories_for_testing(
        {"retail_sentiment": ({Category.FINANCIAL}, set())}
    )

    # Stub validation to succeed and surface a python_lib callable.
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

    # ER requires FINANCIAL — confirm it starts disabled.
    health = {row["department_id"]: row for row in client.get("/api/dept-health").json()}
    assert health["equity_research"]["status"] == "disabled"
    assert "financial" in health["equity_research"]["missing_categories"]

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

    # Seed a proposed spec and approve it.
    runner_specs_service._PROPOSALS[connector_id] = [  # type: ignore[attr-defined]
        runner_specs_service.ProposedSpec(
            department_id="retail_sentiment",
            need_id="social_posts",
            proposed_spec={
                "need_id": "social_posts",
                "access_mode": "python_lib",
                "module": "financialmodelingprep",
                "instance_factory": {"cls": "APIClient", "args": {}},
                "method": "APIClient.real_time_quote",
                "param_bindings": {},
                "constants": {},
                "shape": "list[dict]",
            },
            canary_value=[],
            canary_ok=True,
            shape_match=True,
            error=None,
        )
    ]
    approve = client.post(
        f"/api/connectors/{connector_id}/proposed-specs/approve",
        json={"department_id": "retail_sentiment", "need_id": "social_posts"},
    )
    assert approve.status_code == 201, approve.text

    # ER should now be active — FINANCIAL category satisfied.
    health = {row["department_id"]: row for row in client.get("/api/dept-health").json()}
    assert health["equity_research"]["status"] == "active", health["equity_research"]
