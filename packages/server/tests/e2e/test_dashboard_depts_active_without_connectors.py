"""Scenario — dashboard depts run on native web search, no connector required.

With no connectors configured, `macro_research` and `retail_sentiment` are
ACTIVE: both dashboard engines use the model's native web search, so a
WEB_SEARCH (scraping) connector such as Firecrawl is optional enrichment, not a
hard requirement. This guards the connector-requirement relaxation end to end
through the app lifespan (compute_all -> dept_health cache -> /api/dept-health).

The route-level `dept_disabled` 409 gate itself is covered by
`test_dept_health_api.py` and `test_routes/departments/test_retail_sentiment.py`
(both drive a synthetic disabled state directly).
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


def test_dashboard_depts_active_without_connectors(client: TestClient) -> None:
    """With an empty DB, /api/dept-health flags MR and RS active — no required
    connector category, both run on the model's native web search."""
    by_id = {row["department_id"]: row for row in client.get("/api/dept-health").json()}

    assert by_id["macro_research"]["status"] == "active"
    assert by_id["macro_research"]["missing_categories"] == []
    assert by_id["retail_sentiment"]["status"] == "active"
    assert by_id["retail_sentiment"]["missing_categories"] == []
