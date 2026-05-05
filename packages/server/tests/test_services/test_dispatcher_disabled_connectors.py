"""build_dispatcher honors a session-scoped disabled_connector_ids list:
disabled connectors are excluded from candidate_tools() so the runtime
router never sees them and the model can never call them.
"""

from __future__ import annotations

import pytest
from openlia_server.db.models.connectors import Connector
from openlia_server.services.dispatcher_factory import build_dispatcher
from sqlalchemy.orm import Session as DBSession


def _seed(session: DBSession, *, cid: str, provider_id: str) -> None:
    session.add(
        Connector(
            id=cid,
            provider_id=provider_id,
            display_name=provider_id,
            source="built_in",
            category="financial",
            status="validated",
            launch={"modes": [{"kind": "remote_mcp", "url": "https://x.test", "headers": {}}]},
            secrets={},
            cached_tools=[
                {
                    "name": "quote",
                    "description": "x",
                    "input_schema": {
                        "type": "object",
                        "properties": {"symbol": {"type": "string"}},
                        "required": ["symbol"],
                    },
                }
            ],
        )
    )
    session.commit()


@pytest.fixture(autouse=True)
def _tables(create_tables) -> None:
    return None


def test_disabled_connector_excluded_from_candidate_tools(db_session: DBSession) -> None:
    _seed(db_session, cid="c-eodhd", provider_id="eodhd")
    _seed(db_session, cid="c-newsapi", provider_id="newsapi_ai")
    dispatcher = build_dispatcher(db_session, disabled_connector_ids=("c-eodhd",))
    names = {c["name"] for c in dispatcher.candidate_tools()}
    assert "newsapi_ai__quote" in names
    assert not any(n.startswith("eodhd__") for n in names)


def test_default_no_disabled_returns_full_pool(db_session: DBSession) -> None:
    _seed(db_session, cid="c-eodhd", provider_id="eodhd")
    _seed(db_session, cid="c-newsapi", provider_id="newsapi_ai")
    dispatcher = build_dispatcher(db_session)
    names = {c["name"] for c in dispatcher.candidate_tools()}
    assert "eodhd__quote" in names
    assert "newsapi_ai__quote" in names


def test_disabled_connectors_still_dispatchable_for_existing_runner_specs(
    db_session: DBSession,
) -> None:
    """Disabling a connector hides it from chat tool routing, but a
    previously persisted RunnerCallableSpec on a deterministic dept
    must still dispatch (e.g. Macro Research's pre-bound EODHD spec
    isn't affected by Secretary's chat toggle)."""
    _seed(db_session, cid="c-eodhd", provider_id="eodhd")
    dispatcher = build_dispatcher(db_session, disabled_connector_ids=("c-eodhd",))
    # The connector is still in `dispatcher.connectors` so fetch_need
    # can route to it; only candidate_tools() filters.
    assert "c-eodhd" in dispatcher.connectors
