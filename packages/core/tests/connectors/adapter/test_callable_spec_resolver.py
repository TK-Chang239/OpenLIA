"""Tests for `resolve_callable_spec`."""

from __future__ import annotations

from typing import Any

import pytest

from openlia.connectors.adapter import (
    LlmClient,
    ResolverError,
    resolve_callable_spec,
)
from openlia.connectors.types import (
    CallableDefinition,
    InstanceFactory,
    NeedParameter,
    RunnerNeed,
    ToolDefinition,
)


class _StubLlm:
    """Minimal `LlmClient` stub that returns a canned JSON object."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload
        self.last_prompt: str | None = None

    async def generate_json(self, *, prompt: str) -> dict[str, Any]:
        self.last_prompt = prompt
        return self._payload


def _need() -> RunnerNeed:
    return RunnerNeed(
        id="real_time_quote",
        description="Latest trade price for a US-listed equity.",
        parameters=[
            NeedParameter(
                name="ticker", description="Ticker symbol", type="str", required=True
            )
        ],
        shape="float",
    )


# ----------------------------- isinstance Protocol ----------------------------


def test_stub_satisfies_llm_client_protocol() -> None:
    assert isinstance(_StubLlm({}), LlmClient)


# ----------------------------- happy path: MCP --------------------------------


@pytest.mark.asyncio
async def test_resolve_mcp_happy_path() -> None:
    inventory = [
        ToolDefinition(
            name="get_quote",
            description="Quote tool",
            input_schema={
                "type": "object",
                "properties": {"symbol": {"type": "string"}},
                "required": ["symbol"],
            },
        )
    ]
    llm = _StubLlm(
        {
            "tool_name": "get_quote",
            "method": None,
            "param_bindings": {
                "ticker": {"to_arg": "symbol", "transform": "upper"},
            },
            "constants": {},
        }
    )
    spec = await resolve_callable_spec(
        need=_need(),
        connector_inventory=inventory,
        access_mode="cli_mcp",
        instance_factory=None,
        llm_client=llm,
    )
    assert spec.access_mode == "cli_mcp"
    assert spec.tool_name == "get_quote"
    assert spec.method is None
    assert spec.shape == "float"
    assert spec.param_bindings["ticker"].to_arg == "symbol"
    assert spec.param_bindings["ticker"].transform == "upper"
    # Prompt should reference the need + inventory.
    assert "real_time_quote" in (llm.last_prompt or "")
    assert "get_quote" in (llm.last_prompt or "")


# -------------------------- happy path: python_lib ----------------------------


@pytest.mark.asyncio
async def test_resolve_python_lib_happy_path() -> None:
    inventory = [
        CallableDefinition(
            qualname="APIClient.real_time_quote",
            signature="(self, symbol: str) -> dict",
            doc="Real-time quote",
        )
    ]
    factory = InstanceFactory(cls="APIClient", args={"api_key": "$EODHD_API_KEY"})
    llm = _StubLlm(
        {
            "tool_name": None,
            "method": "APIClient.real_time_quote",
            "param_bindings": {
                "ticker": {"to_arg": "symbol", "transform": None},
            },
            "constants": {},
        }
    )
    spec = await resolve_callable_spec(
        need=_need(),
        connector_inventory=inventory,
        access_mode="python_lib",
        instance_factory=factory,
        llm_client=llm,
    )
    assert spec.access_mode == "python_lib"
    assert spec.tool_name is None
    assert spec.method == "APIClient.real_time_quote"
    assert spec.instance_factory is factory
    assert spec.param_bindings["ticker"].to_arg == "symbol"
    assert spec.param_bindings["ticker"].transform is None


# ---------------------------- validation: unknowns ----------------------------


@pytest.mark.asyncio
async def test_unknown_tool_raises() -> None:
    inventory = [
        ToolDefinition(
            name="get_quote",
            description="Quote tool",
            input_schema={"type": "object", "properties": {"symbol": {"type": "string"}}},
        )
    ]
    llm = _StubLlm(
        {
            "tool_name": "ghost_tool",
            "param_bindings": {},
            "constants": {},
        }
    )
    with pytest.raises(ResolverError, match="ghost_tool"):
        await resolve_callable_spec(
            need=_need(),
            connector_inventory=inventory,
            access_mode="remote_mcp",
            instance_factory=None,
            llm_client=llm,
        )


@pytest.mark.asyncio
async def test_unknown_method_raises() -> None:
    inventory = [
        CallableDefinition(
            qualname="APIClient.real_time_quote",
            signature="(self, symbol: str) -> dict",
            doc="",
        )
    ]
    llm = _StubLlm(
        {
            "method": "APIClient.ghost",
            "param_bindings": {},
            "constants": {},
        }
    )
    with pytest.raises(ResolverError, match="ghost"):
        await resolve_callable_spec(
            need=_need(),
            connector_inventory=inventory,
            access_mode="python_lib",
            instance_factory=None,
            llm_client=llm,
        )


@pytest.mark.asyncio
async def test_unknown_transform_raises() -> None:
    inventory = [
        ToolDefinition(
            name="get_quote",
            description="Quote tool",
            input_schema={"type": "object", "properties": {"symbol": {"type": "string"}}},
        )
    ]
    llm = _StubLlm(
        {
            "tool_name": "get_quote",
            "param_bindings": {
                "ticker": {"to_arg": "symbol", "transform": "rot13_obfuscate"},
            },
            "constants": {},
        }
    )
    with pytest.raises(ResolverError, match="ALLOWED_TRANSFORMS"):
        await resolve_callable_spec(
            need=_need(),
            connector_inventory=inventory,
            access_mode="cli_mcp",
            instance_factory=None,
            llm_client=llm,
        )


@pytest.mark.asyncio
async def test_wrong_arg_binding_raises() -> None:
    inventory = [
        ToolDefinition(
            name="get_quote",
            description="Quote tool",
            input_schema={"type": "object", "properties": {"symbol": {"type": "string"}}},
        )
    ]
    llm = _StubLlm(
        {
            "tool_name": "get_quote",
            "param_bindings": {
                "ticker": {"to_arg": "ticker_symbol", "transform": None},
            },
            "constants": {},
        }
    )
    with pytest.raises(ResolverError, match="ticker_symbol"):
        await resolve_callable_spec(
            need=_need(),
            connector_inventory=inventory,
            access_mode="cli_mcp",
            instance_factory=None,
            llm_client=llm,
        )


@pytest.mark.asyncio
async def test_wrong_arg_binding_python_lib_raises() -> None:
    inventory = [
        CallableDefinition(
            qualname="APIClient.real_time_quote",
            signature="(self, symbol: str) -> dict",
            doc="",
        )
    ]
    llm = _StubLlm(
        {
            "method": "APIClient.real_time_quote",
            "param_bindings": {
                "ticker": {"to_arg": "ghost_arg", "transform": None},
            },
            "constants": {},
        }
    )
    with pytest.raises(ResolverError, match="ghost_arg"):
        await resolve_callable_spec(
            need=_need(),
            connector_inventory=inventory,
            access_mode="python_lib",
            instance_factory=None,
            llm_client=llm,
        )


@pytest.mark.asyncio
async def test_non_serializable_constant_raises() -> None:
    inventory = [
        ToolDefinition(
            name="get_quote",
            description="Quote tool",
            input_schema={"type": "object", "properties": {"symbol": {"type": "string"}}},
        )
    ]
    llm = _StubLlm(
        {
            "tool_name": "get_quote",
            "param_bindings": {},
            "constants": {"symbol": object()},
        }
    )
    with pytest.raises(ResolverError, match="JSON-serializable"):
        await resolve_callable_spec(
            need=_need(),
            connector_inventory=inventory,
            access_mode="cli_mcp",
            instance_factory=None,
            llm_client=llm,
        )
