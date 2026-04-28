"""Tests for `run_canary`."""

from __future__ import annotations

from typing import Any

import pytest

from openlia.connectors.adapter import CanaryResult, run_canary
from openlia.connectors.types import CallableSpec, ParamBinding


class _FakeTransport:
    """Minimal `CallableTransport` stub for canary tests."""

    def __init__(self, *, value: Any = None, raises: Exception | None = None) -> None:
        self._value = value
        self._raises = raises
        self.last_call: tuple[str, dict[str, Any]] | None = None

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        self.last_call = (name, arguments)
        if self._raises is not None:
            raise self._raises
        return self._value

    async def list_tools(self) -> list[dict]:
        return []

    async def aclose(self) -> None:
        return None


def _mcp_spec() -> CallableSpec:
    return CallableSpec(
        need_id="real_time_quote",
        access_mode="cli_mcp",
        tool_name="get_quote",
        method=None,
        param_bindings={"ticker": ParamBinding(to_arg="symbol", transform="upper")},
        constants={"format": "json"},
        shape="float",
    )


def _python_lib_spec(shape: str = "dict") -> CallableSpec:
    return CallableSpec(
        need_id="quote",
        access_mode="python_lib",
        tool_name=None,
        method="APIClient.real_time_quote",
        param_bindings={"ticker": ParamBinding(to_arg="symbol")},
        constants={},
        shape=shape,
    )


# --------------------------------- happy paths --------------------------------


@pytest.mark.asyncio
async def test_canary_happy_path_mcp_with_shape_match() -> None:
    transport = _FakeTransport(value=123.45)
    result = await run_canary(
        spec=_mcp_spec(),
        transport=transport,
        sample_args={"ticker": "aapl"},
    )
    assert isinstance(result, CanaryResult)
    assert result.ok is True
    assert result.value == 123.45
    assert result.error is None
    assert result.shape_match is True
    # Bindings + constants applied; transform uppercased the ticker.
    assert transport.last_call == ("get_quote", {"symbol": "AAPL", "format": "json"})


@pytest.mark.asyncio
async def test_canary_happy_path_python_lib_dict_shape() -> None:
    transport = _FakeTransport(value={"price": 9.0})
    result = await run_canary(
        spec=_python_lib_spec(shape="dict"),
        transport=transport,
        sample_args={"ticker": "aapl"},
    )
    assert result.ok is True
    assert result.shape_match is True
    assert transport.last_call == ("APIClient.real_time_quote", {"symbol": "aapl"})


# --------------------------------- shape mismatch -----------------------------


@pytest.mark.asyncio
async def test_canary_shape_mismatch_reports_ok_with_shape_match_false() -> None:
    # Spec declares `float` but transport returns a list — ok=True (call worked)
    # but shape_match=False so the wizard can flag the draft.
    transport = _FakeTransport(value=[1, 2, 3])
    result = await run_canary(
        spec=_mcp_spec(),
        transport=transport,
        sample_args={"ticker": "aapl"},
    )
    assert result.ok is True
    assert result.error is None
    assert result.shape_match is False


@pytest.mark.asyncio
async def test_canary_list_shape_matches_list_value() -> None:
    spec = CallableSpec(
        need_id="news",
        access_mode="remote_mcp",
        tool_name="search_news",
        param_bindings={},
        constants={},
        shape="list[object]",
    )
    transport = _FakeTransport(value=[{"title": "x"}])
    result = await run_canary(spec=spec, transport=transport, sample_args={})
    assert result.shape_match is True


@pytest.mark.asyncio
async def test_canary_any_shape_always_matches() -> None:
    spec = CallableSpec(
        need_id="any",
        access_mode="remote_mcp",
        tool_name="any_tool",
        shape="any",
    )
    transport = _FakeTransport(value=None)
    result = await run_canary(spec=spec, transport=transport, sample_args={})
    assert result.shape_match is True


# --------------------------------- transport raises ---------------------------


@pytest.mark.asyncio
async def test_canary_transport_raises_returns_failure() -> None:
    transport = _FakeTransport(raises=RuntimeError("upstream 503"))
    result = await run_canary(
        spec=_mcp_spec(),
        transport=transport,
        sample_args={"ticker": "aapl"},
    )
    assert result.ok is False
    assert result.value is None
    assert "upstream 503" in (result.error or "")
    assert result.shape_match is False


@pytest.mark.asyncio
async def test_canary_missing_tool_name_returns_failure() -> None:
    spec = CallableSpec(
        need_id="bad",
        access_mode="cli_mcp",
        tool_name=None,
        method=None,
        shape="float",
    )
    transport = _FakeTransport(value=1.0)
    result = await run_canary(spec=spec, transport=transport, sample_args={})
    assert result.ok is False
    assert result.error is not None
    assert "tool/method" in result.error


@pytest.mark.asyncio
async def test_canary_unknown_transform_returns_failure() -> None:
    spec = CallableSpec(
        need_id="bad_transform",
        access_mode="cli_mcp",
        tool_name="get_quote",
        param_bindings={"ticker": ParamBinding(to_arg="symbol", transform="ghost")},
        shape="float",
    )
    transport = _FakeTransport(value=1.0)
    result = await run_canary(
        spec=spec, transport=transport, sample_args={"ticker": "aapl"}
    )
    assert result.ok is False
    assert "ghost" in (result.error or "")
