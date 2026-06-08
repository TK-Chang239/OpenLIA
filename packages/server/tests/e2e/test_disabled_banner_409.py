"""Scenario 3 — disabled dept banner + mutating endpoint returns 409.

With no connectors configured, `macro_research` is disabled (missing
required `web_search` category). Hitting its mutating refresh endpoint
must short-circuit with HTTP 409 and the structured
`{"error": "dept_disabled", "reason": ...}` body.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from openlia_server.app import create_app
from openlia_server.middleware.rate_limit import limiter


@pytest.fixture(autouse=True)
def _clear_rate_limiter():
    limiter().clear()
    yield
    limiter().clear()


@pytest.fixture
def client(db_session):
    """Use TestClient as a context manager so the lifespan populates
    `app.state.dept_health` on startup. Personal-mode auth requires a
    seeded `local` user, so plant one before yielding the client."""
    from openlia_server.db import session as session_mod
    from openlia_server.db.models.auth import User
    from openlia_server.middleware.auth import LOCAL_USER_ID

    db_session.merge(
        User(
            id=LOCAL_USER_ID,
            email="local@openlia.local",
            display_name="Local",
            password_hash=None,
            is_admin=False,
            is_disabled=False,
        )
    )
    db_session.commit()

    app = create_app(
        db_session_factory=session_mod.SessionLocal,
        is_loopback_request=lambda _: True,
    )
    with TestClient(app) as c:
        yield c


def test_dept_health_marks_macro_research_disabled(client: TestClient) -> None:
    """Sanity: with empty DB, /api/dept-health flags MR disabled."""
    by_id = {row["department_id"]: row for row in client.get("/api/dept-health").json()}
    assert by_id["macro_research"]["status"] == "disabled"
    # MR now requires only web_search; financial/news are optional.
    assert "web_search" in by_id["macro_research"]["missing_categories"]
    assert by_id["macro_research"]["missing_categories"] != []


def test_macro_research_run_assessment_returns_409_when_disabled(
    client: TestClient,
) -> None:
    resp = client.post(
        "/departments/macro_research/dashboards/world_order/refresh",
        json={},
    )
    assert resp.status_code == 409, resp.text
    detail = resp.json()["detail"]
    assert detail["error"] == "dept_disabled"
    assert detail["reason"]
