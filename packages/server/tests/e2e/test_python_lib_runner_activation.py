"""Scenario 2 — `python_lib` runner activation lifts Retail Sentiment from disabled to active.

Drives the wizard-time adapter flow with a stubbed need-set so the test
doesn't have to approve all production RS needs:

  1. Inject a single fake need into `runner_specs_service` via the
     test-only registry override.
  2. Create a `python_lib` connector (validation stubbed).
  3. Seed a proposed spec directly into the in-memory cache.
  4. POST `/api/connectors/{id}/proposed-specs/approve` to persist it.
  5. GET `/api/dept-health` and assert `retail_sentiment` is active.
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


def test_python_lib_runner_activation(client: TestClient, monkeypatch) -> None:
    # 1. Override RS's need set to a single placeholder need so the dept
    #    activates after one approval.
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

    # The pure dept-health checker reads needs straight from YAML; for this
    # test we want it to see the same fake-need slate so RS can flip from
    # disabled to active after a single approval.
    def _fake_load_needs(dept_id: str) -> list[RunnerNeed]:
        return [fake_need] if dept_id == "retail_sentiment" else []

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

    # Create a python_lib financial connector — RS requires FINANCIAL.
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

    # RS should still be disabled at this point — categories OK but
    # the need has no spec.
    health = {row["department_id"]: row for row in client.get("/api/dept-health").json()}
    assert health["retail_sentiment"]["status"] == "disabled"
    assert health["retail_sentiment"]["unresolved_needs"] == ["social_posts"]

    # 3. Seed a proposed spec directly into the cache. (Bypassing the
    #    adapter-LLM canary keeps this test independent of any real
    #    LLM provider.)
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

    # 4. Approve.
    approve = client.post(
        f"/api/connectors/{connector_id}/proposed-specs/approve",
        json={"department_id": "retail_sentiment", "need_id": "social_posts"},
    )
    assert approve.status_code == 201, approve.text

    # 5. RS should now be active.
    health = {row["department_id"]: row for row in client.get("/api/dept-health").json()}
    assert health["retail_sentiment"]["status"] == "active", health["retail_sentiment"]
