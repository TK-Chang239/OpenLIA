"""Scenario 4 — atomic disable when the only FINANCIAL connector is deleted.

Sets up Retail Sentiment with one approved python_lib spec → RS active.
Deleting the sole financial connector must flip RS back to disabled in the
same request (no race window). Uses the same fake-need / direct-proposal
plumbing as `test_python_lib_runner_activation.py`.
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
def client(db_session):
    from openlia_server.db import session as session_mod

    app = create_app(
        db_session_factory=session_mod.SessionLocal,
        is_loopback_request=lambda _: True,
    )
    with TestClient(app) as c:
        yield c


def test_atomic_disable_on_delete(client: TestClient, monkeypatch) -> None:
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
    monkeypatch.setattr(
        "openlia.departments.health.load_needs",
        lambda dept_id: [fake_need] if dept_id == "retail_sentiment" else [],
    )

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

    # Step 1: create the python_lib financial connector.
    create = client.post(
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
    assert create.status_code == 201, create.text
    connector_id = create.json()["id"]

    # Step 2: seed proposal + approve so RS activates.
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

    health = {row["department_id"]: row for row in client.get("/api/dept-health").json()}
    assert health["retail_sentiment"]["status"] == "active"

    # Step 3: delete the connector.
    delete = client.delete(f"/api/connectors/{connector_id}")
    assert delete.status_code == 204, delete.text

    # Step 4: GET dept-health immediately — RS must be disabled now,
    # with `financial` listed as a missing category.
    health = {row["department_id"]: row for row in client.get("/api/dept-health").json()}
    assert health["retail_sentiment"]["status"] == "disabled"
    assert "financial" in health["retail_sentiment"]["missing_categories"]
