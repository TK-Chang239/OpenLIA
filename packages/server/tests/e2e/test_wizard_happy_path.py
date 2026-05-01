"""Scenario 1 — wizard happy path with one financial + one news connector.

Asserts that creating one validated financial connector and one validated
news connector lights up every chat-flow department (Secretary, Equity
Research, Earnings Update, Morning Briefing, Panic Thermometer). The
runner-driven departments (Macro Research, Retail Sentiment) remain
`disabled` until a runner-callable spec is approved — that flow is
covered separately in `test_python_lib_runner_activation.py`.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from openlia_server.app import create_app
from openlia_server.middleware.rate_limit import limiter
from openlia_server.services import connectors_service


@pytest.fixture(autouse=True)
def _clear_rate_limiter():
    limiter().clear()
    yield
    limiter().clear()


@pytest.fixture
def client(db_session) -> TestClient:
    from openlia_server.db import session as session_mod

    app = create_app(
        db_session_factory=session_mod.SessionLocal,
        is_loopback_request=lambda _: True,
    )
    return TestClient(app)


def _patch_validation_ok(monkeypatch) -> None:
    async def fake(_launch, _secrets):
        return connectors_service.ValidationOk(
            tools=[{"name": "get_quote", "description": "quote", "input_schema": {}}],
            python_callables=[],
        )

    monkeypatch.setattr(connectors_service, "_validate_launch", fake)


def test_wizard_happy_path_lights_up_chat_flow_depts(client: TestClient, monkeypatch) -> None:
    _patch_validation_ok(monkeypatch)

    # Financial connector via cli_mcp.
    fin = client.post(
        "/api/connectors",
        json={
            "source": "cli_mcp",
            "category": "financial",
            "provider_id": "eodhd",
            "display_name": "EODHD",
            "launch": {
                "modes": [{"kind": "cli_mcp", "argv": ["uvx", "eodhd-mcp"], "env_keys": []}]
            },
            "secrets": {},
        },
    )
    assert fin.status_code == 201, fin.text

    # News connector via remote_mcp.
    news = client.post(
        "/api/connectors",
        json={
            "source": "remote_mcp",
            "category": "news",
            "provider_id": "newsapi",
            "display_name": "NewsAPI",
            "launch": {
                "modes": [
                    {
                        "kind": "remote_mcp",
                        "url": "https://example.test/mcp",
                        "headers": {},
                    }
                ]
            },
            "secrets": {},
        },
    )
    assert news.status_code == 201, news.text

    # GET /api/dept-health: every chat-flow dept must be active.
    resp = client.get("/api/dept-health")
    assert resp.status_code == 200
    by_id = {row["department_id"]: row for row in resp.json()}

    chat_flow_depts = [
        "secretary",
        "equity_research",
        "earnings_update",
        "morning_briefing",
        "panic_thermometer",
    ]
    for dept_id in chat_flow_depts:
        assert dept_id in by_id, f"{dept_id} missing from /dept-health"
        assert by_id[dept_id]["status"] == "active", (
            f"{dept_id} expected active, got {by_id[dept_id]}"
        )

    # MR + RS require a runner; without approved specs they stay disabled
    # (they have unresolved needs even though categories are satisfied).
    for runner_dept in ("macro_research", "retail_sentiment"):
        assert by_id[runner_dept]["status"] == "disabled"
        assert by_id[runner_dept]["unresolved_needs"], f"{runner_dept} should have unresolved needs"
