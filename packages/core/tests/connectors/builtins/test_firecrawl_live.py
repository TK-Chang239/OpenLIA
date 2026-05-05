"""Live Firecrawl smoke tests.

The original failure that motivated these: `Object of type SearchData
is not JSON serializable`. firecrawl-py >=4 returns pydantic-style
objects (SearchData, Document) from `search` and `scrape`, and the v2
chat dispatcher used to `json.dumps(payload)` directly with no `default=`
serializer, which crashed the whole chat turn.

These tests run against the real Firecrawl API and assert that two of
the most-used SDK methods produce results the dispatch boundary can
JSON-encode via `to_jsonable`.

Skipped by default. Opt in with `pytest -m live_api` and FIRECRAWL_API_KEY set.
"""

from __future__ import annotations

import json
import os

import pytest
from openlia.connectors.dispatch import Dispatcher, PreparedConnector
from openlia.connectors.serialization import to_jsonable
from openlia.connectors.transports.python_lib import PythonLibTransport
from openlia.connectors.types import (
    Category,
    ConnectorStatus,
    InstanceFactory,
    ToolDefinition,
)

pytestmark = [
    pytest.mark.live_api,
    pytest.mark.asyncio,
    pytest.mark.skipif(
        not os.environ.get("FIRECRAWL_API_KEY"),
        reason="FIRECRAWL_API_KEY not set",
    ),
]


async def _build_dispatcher() -> Dispatcher:
    transport = PythonLibTransport(
        module="firecrawl",
        instance_factory=InstanceFactory(
            cls="Firecrawl", args={"api_key": "$FIRECRAWL_API_KEY"}
        ),
        secrets={"FIRECRAWL_API_KEY": os.environ["FIRECRAWL_API_KEY"]},
    )
    discovered = await transport.list_tools()
    tools = {
        t["name"]: ToolDefinition(
            name=t["name"],
            description=t.get("description", ""),
            input_schema=t.get("input_schema") or {},
        )
        for t in discovered
    }
    prep = PreparedConnector(
        connector_id="live-firecrawl",
        provider_id="firecrawl",
        category=Category.WEB_SEARCH,
        status=ConnectorStatus.VALIDATED,
        transport=transport,
        tools=tools,
    )
    return Dispatcher(connectors={prep.connector_id: prep})


async def test_firecrawl_search_result_is_json_serializable_via_dispatch() -> None:
    """Reproduces the original SearchData serialization bug at the
    dispatch boundary. Without the to_jsonable fix this would die with
    `TypeError: Object of type SearchData is not JSON serializable`."""
    dispatcher = await _build_dispatcher()
    raw = await dispatcher.dispatch_tool_use(
        "firecrawl__search", {"query": "openai", "limit": 3}
    )
    coerced = to_jsonable(raw)
    # If this raises, the dispatch path would have crashed in production.
    json.dumps(coerced)


async def test_firecrawl_scrape_result_is_json_serializable_via_dispatch() -> None:
    """`scrape` returns a `Document` object — also pydantic-shaped."""
    dispatcher = await _build_dispatcher()
    raw = await dispatcher.dispatch_tool_use(
        "firecrawl__scrape", {"url": "https://example.com"}
    )
    coerced = to_jsonable(raw)
    json.dumps(coerced)
