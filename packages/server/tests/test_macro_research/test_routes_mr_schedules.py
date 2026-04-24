from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from openlia_server.routes.mr_schedules import build_mr_schedule_router


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    svc = MagicMock()
    svc.get.return_value = MagicMock(assessment_schedule="0 0 * * 0", last_assessment_at=None)
    svc.upsert = AsyncMock(return_value=MagicMock(assessment_schedule="0 0 1 */3 *"))
    svc.delete = AsyncMock(return_value=None)

    def _override_auth():
        return MagicMock(id="u-1", email="a@b", is_admin=False)

    router = build_mr_schedule_router(
        db_session_factory=lambda: None,
        mode="personal",
        mr_schedule_service=svc,
        require_auth_override=_override_auth,
    )
    app.include_router(router)
    return TestClient(app)


def test_get_schedule(client: TestClient) -> None:
    r = client.get("/departments/macro_research/schedule")
    assert r.status_code == 200
    assert r.json()["cron_expression"] == "0 0 * * 0"


def test_put_schedule(client: TestClient) -> None:
    r = client.put(
        "/departments/macro_research/schedule",
        json={"cron_expression": "0 0 1 */3 *"},
    )
    assert r.status_code == 200
    assert r.json()["cron_expression"] == "0 0 1 */3 *"


def test_put_schedule_rejects_blank(client: TestClient) -> None:
    r = client.put(
        "/departments/macro_research/schedule",
        json={"cron_expression": "   "},
    )
    assert r.status_code == 400


def test_delete_schedule(client: TestClient) -> None:
    r = client.delete("/departments/macro_research/schedule")
    assert r.status_code == 204
