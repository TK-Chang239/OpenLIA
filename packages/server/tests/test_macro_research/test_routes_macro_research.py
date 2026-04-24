from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openlia.macro_research.schemas import DashboardResult
from openlia_server.routes.departments.macro_research import build_macro_research_router


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    runner = MagicMock()
    runner.run.return_value = DashboardResult(
        slug="debt_cycle",
        display_name="Debt Cycle",
        severity="amber",
        tiers=[],
        headline="Plateau",
        generated_at=datetime.now(UTC),
        smart_mode_active=False,
    )
    dashboard_svc = MagicMock()
    dashboard_svc.list_for_user.return_value = []
    dashboard_svc.get_or_create.return_value = MagicMock(view_config={}, threshold_overrides={})
    dashboard_svc.update_config.return_value = MagicMock(
        view_config={"auto_refresh": "5m"},
        threshold_overrides={"debt_gdp_warn": 95},
    )

    def _override_auth():
        return MagicMock(id="u-1", email="a@b", is_admin=False)

    router = build_macro_research_router(
        db_session_factory=lambda: None,
        mode="personal",
        mr_runner=runner,
        dashboard_service=dashboard_svc,
        require_auth_override=_override_auth,
    )
    app.include_router(router)
    return TestClient(app)


def test_list_dashboards(client: TestClient) -> None:
    r = client.get("/departments/macro_research/dashboards")
    assert r.status_code == 200
    body = r.json()
    assert "dashboards" in body
    assert len(body["dashboards"]) == 5


def test_get_dashboard(client: TestClient) -> None:
    r = client.get("/departments/macro_research/dashboards/debt_cycle")
    assert r.status_code == 200
    assert r.json()["slug"] == "debt_cycle"


def test_get_dashboard_404_for_unknown(client: TestClient) -> None:
    r = client.get("/departments/macro_research/dashboards/not_real")
    assert r.status_code == 404


def test_update_config(client: TestClient) -> None:
    r = client.put(
        "/departments/macro_research/dashboards/debt_cycle/config",
        json={
            "view_config": {"auto_refresh": "5m"},
            "threshold_overrides": {"debt_gdp_warn": 95},
        },
    )
    assert r.status_code == 200


def test_run_assessment(client: TestClient) -> None:
    r = client.post(
        "/departments/macro_research/dashboards/world_order/assessment/run",
        json={},
    )
    assert r.status_code == 202
    assert "job_run_id" in r.json()


def test_run_assessment_404_for_unknown(client: TestClient) -> None:
    r = client.post(
        "/departments/macro_research/dashboards/not_real/assessment/run",
        json={},
    )
    assert r.status_code == 404
