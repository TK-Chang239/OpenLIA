"""Scenario 4 — atomic disable when the only FINANCIAL connector is deleted.

Sets up Equity Research (which requires FINANCIAL) with one validated
python_lib connector → ER active. Deleting the sole financial connector
must flip ER back to disabled in the same request (no race window).

The runner-spec activation path (requires_runner / unresolved_needs) was
removed in refactor/rescope-need-resolution-portfolio. Health is now
driven purely by category coverage.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
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
    """Deleting the only FINANCIAL connector atomically disables Equity Research."""

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

    # Step 1: confirm ER is disabled before any connector exists.
    health = {row["department_id"]: row for row in client.get("/api/dept-health").json()}
    assert health["equity_research"]["status"] == "disabled"
    assert "financial" in health["equity_research"]["missing_categories"]

    # Step 2: create the python_lib financial connector — ER requires FINANCIAL.
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

    # ER should now be active.
    health = {row["department_id"]: row for row in client.get("/api/dept-health").json()}
    assert health["equity_research"]["status"] == "active"

    # Step 3: delete the connector.
    delete = client.delete(f"/api/connectors/{connector_id}")
    assert delete.status_code == 204, delete.text

    # Step 4: GET dept-health immediately — ER must be disabled now,
    # with `financial` listed as a missing category.
    health = {row["department_id"]: row for row in client.get("/api/dept-health").json()}
    assert health["equity_research"]["status"] == "disabled"
    assert "financial" in health["equity_research"]["missing_categories"]
