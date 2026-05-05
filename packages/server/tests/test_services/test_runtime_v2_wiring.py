"""Plan 13 — chat runtime is wired with the v2 connector dispatcher,
the runtime tool router, and the routing-context loader so Secretary
(and every other chat dept) can actually call connector tools.
"""

from __future__ import annotations

from typing import Any

import pytest
from openlia_server.db.models.connectors import Connector
from sqlalchemy.orm import Session as DBSession


def _seed_validated_eodhd(session: DBSession) -> Connector:
    row = Connector(
        id="conn-eodhd-1",
        provider_id="eodhd",
        display_name="EODHD",
        source="remote_mcp",
        category="financial",
        status="validated",
        launch={
            "modes": [{"kind": "remote_mcp", "url": "https://example.test/mcp", "headers": {}}]
        },
        secrets={},
        cached_tools=[
            {
                "name": "get_quote",
                "description": "Latest quote.",
                "input_schema": {
                    "type": "object",
                    "properties": {"symbol": {"type": "string"}},
                    "required": ["symbol"],
                },
            }
        ],
    )
    session.add(row)
    session.commit()
    return row


@pytest.fixture
def _stub_router_factory(monkeypatch):
    """Stub the router-LLM factory so the test doesn't need a real model row."""
    from openlia_server.services import runtime as svc

    class _StubRouterClient:
        async def generate_json(self, *, prompt: str):
            return []

    monkeypatch.setattr(svc, "_build_router_llm_client", lambda db: _StubRouterClient())


def test_build_chat_runner_enables_v2_when_connectors_exist(
    db_session: DBSession, _stub_router_factory
) -> None:
    _seed_validated_eodhd(db_session)
    from openlia_server.services.llm_registry import SQLModelRegistry
    from openlia_server.services.runtime import _build_chat_runner_with_registry

    registry = SQLModelRegistry(db_session)
    from openlia.llm.runtime.web_search import WebSearchResolution

    runner = _build_chat_runner_with_registry(
        registry,
        db=db_session,
        web_search=WebSearchResolution(False, None, None),
    )
    assert runner._v2_routing_enabled() is True
    candidates: list[dict[str, Any]] = runner._dispatcher.candidate_tools()
    names = {c["name"] for c in candidates}
    assert "eodhd__get_quote" in names


def test_build_chat_runner_threads_disabled_connector_ids_to_dispatcher(
    db_session: DBSession, _stub_router_factory
) -> None:
    """The chat-input "Tools" toggle: connectors in the disabled list
    must be excluded from the dispatcher's chat-routing pool."""
    _seed_validated_eodhd(db_session)
    from openlia.llm.runtime.web_search import WebSearchResolution
    from openlia_server.services.llm_registry import SQLModelRegistry
    from openlia_server.services.runtime import _build_chat_runner_with_registry

    registry = SQLModelRegistry(db_session)
    runner = _build_chat_runner_with_registry(
        registry,
        db=db_session,
        web_search=WebSearchResolution(False, None, None),
        disabled_connector_ids=("conn-eodhd-1",),
    )
    candidates = runner._dispatcher.candidate_tools()
    names = {c["name"] for c in candidates}
    assert not any(n.startswith("eodhd__") for n in names)


def test_build_chat_runner_uses_routing_context_loader_from_core(
    db_session: DBSession, _stub_router_factory
) -> None:
    """The loader must read the dept's routing_context.md from the core
    package, not a stub path. Verify by loading secretary."""
    _seed_validated_eodhd(db_session)
    from openlia_server.services.llm_registry import SQLModelRegistry
    from openlia_server.services.runtime import _build_chat_runner_with_registry

    registry = SQLModelRegistry(db_session)
    from openlia.llm.runtime.web_search import WebSearchResolution

    runner = _build_chat_runner_with_registry(
        registry,
        db=db_session,
        web_search=WebSearchResolution(False, None, None),
    )
    body = runner._routing_context_loader("secretary")
    assert "Secretary" in body
    assert "routing context" in body.lower() or "what this department does" in body.lower()
