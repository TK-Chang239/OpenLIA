"""Phase 3: executor honors CallableSpec.result_path + field_map.

result_path peels a wrapper off the transport response (tuple form,
e.g. ``("data", "posts")``); field_map renames each item's keys to the
canonical set declared on the need. field_map values may be strings
(top-level key) or tuples (nested-path extraction).
"""

from __future__ import annotations

import pytest
from openlia.connectors.dispatch import Dispatcher, FieldMapError, PreparedConnector
from openlia.connectors.types import (
    CallableSpec,
    Category,
    ConnectorStatus,
    ToolDefinition,
)


class _FakeTransport:
    def __init__(self, response: object) -> None:
        self._response = response
        self.calls: list[tuple[str, dict]] = []

    async def call_tool(self, name: str, arguments: dict) -> object:
        self.calls.append((name, arguments))
        return self._response


def _conn(response: object) -> PreparedConnector:
    return PreparedConnector(
        connector_id="c1",
        provider_id="fakeprov",
        category=Category.SOCIAL,
        status=ConnectorStatus.VALIDATED,
        transport=_FakeTransport(response),
        tools={"posts": ToolDefinition(name="posts", description="", input_schema={})},
    )


@pytest.mark.asyncio
async def test_field_map_renames_keys_per_item_for_list_dict_shape() -> None:
    response = [
        {"post_id": "1", "ticker_symbol": "AAPL", "body": "hi", "channel": "twitter"},
        {"post_id": "2", "ticker_symbol": "AAPL", "body": "bye", "channel": "reddit"},
    ]
    spec = CallableSpec(
        need_id="social_posts",
        access_mode="cli_mcp",
        tool_name="posts",
        shape="list[dict]",
        field_map={
            "id": "post_id",
            "ticker": "ticker_symbol",
            "text": "body",
            "source": "channel",
        },
    )
    d = Dispatcher(
        connectors={"c1": _conn(response)},
        callable_specs={("retail_sentiment", "social_posts"): spec},
    )
    async with d.in_department("retail_sentiment"):
        out = await d.fetch_need("social_posts")
    assert out == [
        {"id": "1", "ticker": "AAPL", "text": "hi", "source": "twitter"},
        {"id": "2", "ticker": "AAPL", "text": "bye", "source": "reddit"},
    ]


@pytest.mark.asyncio
async def test_result_path_extracts_nested_list_then_field_map_renames() -> None:
    response = {
        "status": "ok",
        "data": {
            "posts": [
                {"pid": "x", "sym": "T"},
                {"pid": "y", "sym": "T"},
            ]
        },
    }
    spec = CallableSpec(
        need_id="social_posts",
        access_mode="cli_mcp",
        tool_name="posts",
        shape="list[dict]",
        result_path=("data", "posts"),
        field_map={"id": "pid", "ticker": "sym"},
    )
    d = Dispatcher(
        connectors={"c1": _conn(response)},
        callable_specs={("retail_sentiment", "social_posts"): spec},
    )
    async with d.in_department("retail_sentiment"):
        out = await d.fetch_need("social_posts")
    assert out == [{"id": "x", "ticker": "T"}, {"id": "y", "ticker": "T"}]


@pytest.mark.asyncio
async def test_field_map_tuple_value_extracts_nested_per_item() -> None:
    response = [
        {"id": "1", "user": {"handle": "alice"}, "msg": "hi"},
    ]
    spec = CallableSpec(
        need_id="social_posts",
        access_mode="cli_mcp",
        tool_name="posts",
        shape="list[dict]",
        field_map={"id": "id", "author": ("user", "handle"), "text": "msg"},
    )
    d = Dispatcher(
        connectors={"c1": _conn(response)},
        callable_specs={("retail_sentiment", "social_posts"): spec},
    )
    async with d.in_department("retail_sentiment"):
        out = await d.fetch_need("social_posts")
    assert out == [{"id": "1", "author": "alice", "text": "hi"}]


@pytest.mark.asyncio
async def test_field_map_missing_canonical_key_raises_field_map_error() -> None:
    response = [{"post_id": "1"}]  # body field missing
    spec = CallableSpec(
        need_id="social_posts",
        access_mode="cli_mcp",
        tool_name="posts",
        shape="list[dict]",
        field_map={"id": "post_id", "text": "body"},
    )
    d = Dispatcher(
        connectors={"c1": _conn(response)},
        callable_specs={("retail_sentiment", "social_posts"): spec},
    )
    with pytest.raises(FieldMapError, match="body"):
        async with d.in_department("retail_sentiment"):
            await d.fetch_need("social_posts")


@pytest.mark.asyncio
async def test_field_map_ignored_for_scalar_shape() -> None:
    spec = CallableSpec(
        need_id="debt_gdp",
        access_mode="cli_mcp",
        tool_name="posts",
        shape="float",
        field_map={"unused": "x"},  # ignored; scalar shape
    )
    d = Dispatcher(
        connectors={"c1": _conn(110.5)},
        callable_specs={("macro_research", "debt_gdp"): spec},
    )
    async with d.in_department("macro_research"):
        out = await d.fetch_need("debt_gdp")
    assert out == 110.5


@pytest.mark.asyncio
async def test_no_field_map_returns_items_as_is() -> None:
    response = [{"id": "1", "ticker": "A"}, {"id": "2", "ticker": "B"}]
    spec = CallableSpec(
        need_id="social_posts",
        access_mode="cli_mcp",
        tool_name="posts",
        shape="list[dict]",
        field_map=None,
    )
    d = Dispatcher(
        connectors={"c1": _conn(response)},
        callable_specs={("retail_sentiment", "social_posts"): spec},
    )
    async with d.in_department("retail_sentiment"):
        out = await d.fetch_need("social_posts")
    assert out == response


@pytest.mark.asyncio
async def test_empty_field_map_returns_items_as_is() -> None:
    response = [{"id": "1", "ticker": "A"}]
    spec = CallableSpec(
        need_id="social_posts",
        access_mode="cli_mcp",
        tool_name="posts",
        shape="list[dict]",
        field_map={},
    )
    d = Dispatcher(
        connectors={"c1": _conn(response)},
        callable_specs={("retail_sentiment", "social_posts"): spec},
    )
    async with d.in_department("retail_sentiment"):
        out = await d.fetch_need("social_posts")
    assert out == response
