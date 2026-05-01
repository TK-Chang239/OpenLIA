"""Tests for `RemoteMcpTransport`.

Covers Protocol membership and a round trip through an injected fake session.
"""

from __future__ import annotations

from typing import Any

import pytest
from openlia.connectors.transports import CallableTransport
from openlia.connectors.transports.mcp_remote import RemoteMcpTransport
from openlia.connectors.types import RemoteMcpMode, ToolDefinition


class _FakeSession:
    def __init__(self, mode: RemoteMcpMode) -> None:
        self.mode = mode
        self.opened = False
        self.closed = False

    async def open(self) -> None:
        self.opened = True

    async def close(self) -> None:
        self.closed = True

    async def list_tools(self) -> list[ToolDefinition]:
        return [ToolDefinition(name="search", description="d", input_schema={})]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        return {"name": name, "args": arguments, "url": self.mode.url}


def _make(holder: dict[str, _FakeSession]) -> RemoteMcpTransport:
    mode = RemoteMcpMode(kind="remote_mcp", url="https://x.example/mcp", headers={"X-K": "v"})

    def factory(m: RemoteMcpMode) -> _FakeSession:
        sess = _FakeSession(m)
        holder["sess"] = sess
        return sess

    return RemoteMcpTransport(mode=mode, session_factory=factory)


def test_implements_callable_transport_protocol() -> None:
    holder: dict[str, _FakeSession] = {}
    assert isinstance(_make(holder), CallableTransport)


@pytest.mark.asyncio
async def test_call_tool_round_trips_through_session() -> None:
    holder: dict[str, _FakeSession] = {}
    t = _make(holder)
    result = await t.call_tool("search", {"q": "hello"})
    assert result == {"name": "search", "args": {"q": "hello"}, "url": "https://x.example/mcp"}
    assert holder["sess"].opened is True


@pytest.mark.asyncio
async def test_list_tools_returns_mcp_dicts() -> None:
    holder: dict[str, _FakeSession] = {}
    t = _make(holder)
    listed = await t.list_tools()
    assert listed == [{"name": "search", "description": "d", "input_schema": {}}]


@pytest.mark.asyncio
async def test_aclose_closes_and_resets_session() -> None:
    holder: dict[str, _FakeSession] = {}
    t = _make(holder)
    await t.call_tool("search", {})
    await t.aclose()
    assert holder["sess"].closed is True
    assert t._session is None
