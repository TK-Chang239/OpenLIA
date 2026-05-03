"""Tests for `resolve_user_picked_spec` (Phase 5 manual-pick resolver).

The legacy `resolve_callable_spec` lets the LLM choose the tool/method.
The new flow flips that: the user picks the endpoint, the LLM only
authors the binding (param_bindings, constants, field_map for list
shapes) and may emit a warning string.
"""

from __future__ import annotations

from typing import Any

import pytest
from openlia.connectors.adapter.manual_pick_resolver import (
    ResolverResult,
    resolve_user_picked_spec,
)
from openlia.connectors.types import (
    CallableDefinition,
    Category,
    InstanceFactory,
    NeedParameter,
    RunnerNeed,
    ToolDefinition,
)


class _StubLlm:
    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.last_prompt: str | None = None

    async def generate_json(self, *, prompt: str) -> dict[str, Any]:
        self.last_prompt = prompt
        return self._payload


def _scalar_need() -> RunnerNeed:
    return RunnerNeed(
        id="stock_quote",
        description="Latest closing price for an equity given its ticker.",
        parameters=[
            NeedParameter(name="ticker", description="Ticker symbol", type="str", required=True),
        ],
        shape="float",
    )


def _list_dict_need() -> RunnerNeed:
    return RunnerNeed(
        id="geopolitical_news",
        description="Recent geopolitical headlines.",
        parameters=[
            NeedParameter(
                name="window_days",
                description="Lookback days",
                type="int",
                required=False,
                default=7,
            )
        ],
        shape="list[dict]",
        canonical_keys={
            "title": "str",
            "url": "str",
            "source": "str",
            "published_at": "str",
            "summary": "str",
        },
    )


# --------------------------- happy path: user-picked tool --------------------


@pytest.mark.asyncio
async def test_resolver_accepts_user_endpoint_pick_and_emits_param_bindings() -> None:
    inventory = [
        ToolDefinition(
            name="quote",
            description="Quote tool",
            input_schema={
                "type": "object",
                "properties": {
                    "symbol": {"type": "string"},
                    "endpoint": {"type": "string"},
                },
                "required": ["symbol"],
            },
        ),
        ToolDefinition(name="news", description="News tool", input_schema={}),
    ]
    llm = _StubLlm(
        {
            "spec": {
                "param_bindings": {
                    "ticker": {"to_arg": "symbol", "transform": "upper"},
                },
                "constants": {"endpoint": "quote"},
            },
            "warning": None,
        }
    )
    result = await resolve_user_picked_spec(
        need=_scalar_need(),
        connector_inventory=inventory,
        access_mode="remote_mcp",
        connector_category=Category.FINANCIAL,
        instance_factory=None,
        llm_client=llm,
        user_picked_endpoint="quote",
        user_hint=None,
    )
    assert isinstance(result, ResolverResult)
    assert result.warning is None
    assert result.spec.tool_name == "quote"
    assert result.spec.method is None
    assert result.spec.param_bindings["ticker"].to_arg == "symbol"
    assert result.spec.param_bindings["ticker"].transform == "upper"
    assert result.spec.constants == {"endpoint": "quote"}
    # Prompt must convey the user pick to the LLM.
    assert "quote" in (llm.last_prompt or "")
    assert "user picked" in (llm.last_prompt or "").lower()


# --------------------------- field_map for list[dict] shape ------------------


@pytest.mark.asyncio
async def test_resolver_emits_field_map_for_list_dict_shape() -> None:
    inventory = [
        CallableDefinition(
            qualname="Client.headlines",
            signature="(self, window_days: int = 7) -> list",
            doc="Recent headlines",
        )
    ]
    llm = _StubLlm(
        {
            "spec": {
                "param_bindings": {
                    "window_days": {"to_arg": "window_days", "transform": None},
                },
                "constants": {},
                "field_map": {
                    "title": "headline",
                    "url": "link",
                    "source": "publisher",
                    "published_at": "ts",
                    "summary": "blurb",
                },
            },
            "warning": None,
        }
    )
    factory = InstanceFactory(cls="Client", args={})
    result = await resolve_user_picked_spec(
        need=_list_dict_need(),
        connector_inventory=inventory,
        access_mode="python_lib",
        connector_category=Category.NEWS,
        instance_factory=factory,
        llm_client=llm,
        user_picked_endpoint="Client.headlines",
        user_hint=None,
    )
    assert result.spec.method == "Client.headlines"
    assert result.spec.field_map == {
        "title": "headline",
        "url": "link",
        "source": "publisher",
        "published_at": "ts",
        "summary": "blurb",
    }
    # Prompt must surface canonical_keys to the LLM for list[dict] shapes.
    prompt = llm.last_prompt or ""
    assert "canonical_keys" in prompt
    assert "title" in prompt and "summary" in prompt
    assert "field_map" in prompt


# --------------------------- websearch mode ----------------------------------


@pytest.mark.asyncio
async def test_resolver_websearch_mode_pins_connector_to_web_search_category() -> None:
    inventory = [
        CallableDefinition(
            qualname="Firecrawl.scrape",
            signature="(self, url: str, formats: list = []) -> dict",
            doc="Scrape a URL",
        )
    ]
    llm = _StubLlm(
        {
            "spec": {
                "param_bindings": {},
                "constants": {
                    "url": "https://example.com/macro",
                    "formats": [
                        {
                            "type": "json",
                            "schema": {
                                "type": "object",
                                "properties": {"value": {"type": "number"}},
                                "required": ["value"],
                            },
                        }
                    ],
                },
                "result_path": ["json", "value"],
            },
            "warning": None,
        }
    )
    factory = InstanceFactory(cls="Firecrawl", args={"api_key": "$KEY"})
    result = await resolve_user_picked_spec(
        need=_scalar_need(),
        connector_inventory=inventory,
        access_mode="python_lib",
        connector_category=Category.WEB_SEARCH,
        instance_factory=factory,
        llm_client=llm,
        user_picked_endpoint="Firecrawl.scrape",
        websearch_url="https://example.com/macro",
        user_hint="The current price is on the right sidebar",
    )
    assert result.spec.method == "Firecrawl.scrape"
    assert result.spec.constants["url"] == "https://example.com/macro"
    assert result.spec.result_path == ("json", "value")
    prompt = llm.last_prompt or ""
    # Websearch sub-mode prompt: user URL and JSON-extraction guidance.
    assert "https://example.com/macro" in prompt
    assert "websearch" in prompt.lower() or "scrape" in prompt.lower()
    # User hint surfaces verbatim.
    assert "right sidebar" in prompt


@pytest.mark.asyncio
async def test_resolver_websearch_requires_web_search_category() -> None:
    inventory = [
        CallableDefinition(
            qualname="Other.method",
            signature="(self, url: str) -> dict",
            doc="",
        )
    ]
    llm = _StubLlm({"spec": {}, "warning": None})
    with pytest.raises(ValueError, match="web_search"):
        await resolve_user_picked_spec(
            need=_scalar_need(),
            connector_inventory=inventory,
            access_mode="python_lib",
            connector_category=Category.NEWS,  # wrong category
            instance_factory=None,
            llm_client=llm,
            user_picked_endpoint="Other.method",
            websearch_url="https://example.com",
        )


# --------------------------- warning propagation -----------------------------


@pytest.mark.asyncio
async def test_resolver_warning_field_propagates() -> None:
    inventory = [
        ToolDefinition(
            name="quote",
            description="Quote tool",
            input_schema={
                "type": "object",
                "properties": {"symbol": {"type": "string"}},
            },
        )
    ]
    llm = _StubLlm(
        {
            "spec": {
                "param_bindings": {"ticker": {"to_arg": "symbol", "transform": None}},
                "constants": {},
            },
            "warning": "Endpoint returns intraday price; treat as approximate close.",
        }
    )
    result = await resolve_user_picked_spec(
        need=_scalar_need(),
        connector_inventory=inventory,
        access_mode="cli_mcp",
        connector_category=Category.FINANCIAL,
        instance_factory=None,
        llm_client=llm,
        user_picked_endpoint="quote",
    )
    assert result.warning == "Endpoint returns intraday price; treat as approximate close."
    assert result.spec.tool_name == "quote"
