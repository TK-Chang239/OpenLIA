"""Tests for `CliMcpTransport`.

Covers:
- Protocol membership against `CallableTransport`.
- Env projection via `mode.env_keys` (only listed keys leak from `secrets`).
- `call_tool` + `list_tools` round-tripping through the injected fake session.
- `aclose` resets the session.
"""

from __future__ import annotations

from typing import Any

import pytest
from openlia.connectors.transports import CallableTransport
from openlia.connectors.transports.mcp_cli import CliMcpTransport
from openlia.connectors.types import CliMcpMode, ToolDefinition


class _FakeSession:
    def __init__(self, argv: list[str], env: dict[str, str]) -> None:
        self.argv = argv
        self.env = env
        self.opened = False
        self.closed = False
        self.calls: list[tuple[str, dict[str, Any]]] = []

    async def open(self) -> None:
        self.opened = True

    async def close(self) -> None:
        self.closed = True

    async def list_tools(self) -> list[ToolDefinition]:
        return [ToolDefinition(name="quote", description="d", input_schema={"type": "object"})]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        self.calls.append((name, arguments))
        return {"name": name, "args": arguments}


def _factory_capture(holder: dict[str, _FakeSession]):
    def factory(argv: list[str], env: dict[str, str]) -> _FakeSession:
        sess = _FakeSession(argv, env)
        holder["sess"] = sess
        return sess

    return factory


def _make_transport(
    *,
    secrets: dict[str, str],
    env_keys: list[str],
    holder: dict[str, _FakeSession],
) -> CliMcpTransport:
    mode = CliMcpMode(kind="cli_mcp", argv=["uvx", "fixture-mcp"], env_keys=env_keys)
    return CliMcpTransport(mode=mode, secrets=secrets, session_factory=_factory_capture(holder))


def test_implements_callable_transport_protocol() -> None:
    holder: dict[str, _FakeSession] = {}
    t = _make_transport(secrets={}, env_keys=[], holder=holder)
    assert isinstance(t, CallableTransport)


@pytest.mark.asyncio
async def test_env_projection_includes_only_listed_keys() -> None:
    holder: dict[str, _FakeSession] = {}
    t = _make_transport(
        secrets={"EODHD_API_KEY": "k1", "OPENAI_KEY": "should-not-leak"},
        env_keys=["EODHD_API_KEY"],
        holder=holder,
    )
    await t.call_tool("quote", {"symbol": "AAPL"})
    sess = holder["sess"]
    assert sess.env == {"EODHD_API_KEY": "k1"}
    assert "OPENAI_KEY" not in sess.env


@pytest.mark.asyncio
async def test_missing_secret_key_is_skipped() -> None:
    holder: dict[str, _FakeSession] = {}
    t = _make_transport(
        secrets={"EODHD_API_KEY": "k1"},
        env_keys=["EODHD_API_KEY", "ABSENT"],
        holder=holder,
    )
    await t.call_tool("quote", {})
    sess = holder["sess"]
    assert sess.env == {"EODHD_API_KEY": "k1"}


@pytest.mark.asyncio
async def test_call_tool_round_trips_through_session() -> None:
    holder: dict[str, _FakeSession] = {}
    t = _make_transport(secrets={"K": "v"}, env_keys=["K"], holder=holder)
    result = await t.call_tool("quote", {"symbol": "MSFT"})
    assert result == {"name": "quote", "args": {"symbol": "MSFT"}}
    assert holder["sess"].calls == [("quote", {"symbol": "MSFT"})]


@pytest.mark.asyncio
async def test_list_tools_returns_mcp_dicts() -> None:
    holder: dict[str, _FakeSession] = {}
    t = _make_transport(secrets={}, env_keys=[], holder=holder)
    listed = await t.list_tools()
    assert listed == [{"name": "quote", "description": "d", "input_schema": {"type": "object"}}]


@pytest.mark.asyncio
async def test_aclose_closes_and_resets_session() -> None:
    holder: dict[str, _FakeSession] = {}
    t = _make_transport(secrets={}, env_keys=[], holder=holder)
    await t.call_tool("quote", {})
    await t.aclose()
    assert holder["sess"].closed is True
    assert t._session is None


@pytest.mark.asyncio
async def test_empty_argv_raises() -> None:
    holder: dict[str, _FakeSession] = {}
    mode = CliMcpMode(kind="cli_mcp", argv=[], env_keys=[])
    t = CliMcpTransport(mode=mode, secrets={}, session_factory=_factory_capture(holder))
    with pytest.raises(ValueError, match="empty argv"):
        await t.call_tool("quote", {})
