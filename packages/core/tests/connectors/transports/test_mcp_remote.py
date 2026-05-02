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
async def test_call_tool_unwraps_text_content_to_parsed_json() -> None:
    """MCP servers (e.g. FMP, Firecrawl) return tool payloads as
    JSON-stringified text wrapped in a CallToolResult-shaped object:
    `{content: [{type:"text", text:"..."}], structured_content: None}`.

    The transport unwraps this to the parsed Python value before handing
    it to dispatch's `_walk_result_path` — otherwise specs with non-empty
    result_path would fail to traverse the wrapper.
    """

    class _TextBlock:
        def __init__(self, text: str) -> None:
            self.type = "text"
            self.text = text

    class _CallResult:
        def __init__(self, text: str) -> None:
            self.content = [_TextBlock(text)]
            self.structured_content = None
            self.is_error = False

    class _UnwrapSession:
        def __init__(self, mode: RemoteMcpMode) -> None:
            self.mode = mode

        async def open(self) -> None:
            pass

        async def close(self) -> None:
            pass

        async def list_tools(self) -> list[ToolDefinition]:
            return []

        async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
            return _CallResult('{"data": [{"symbol": "AAPL", "price": 280.14}]}')

    mode = RemoteMcpMode(kind="remote_mcp", url="https://x", headers={})
    t = RemoteMcpTransport(mode=mode, session_factory=lambda m: _UnwrapSession(m))
    result = await t.call_tool("quote", {"symbol": "AAPL"})
    assert result == {"data": [{"symbol": "AAPL", "price": 280.14}]}


@pytest.mark.asyncio
async def test_call_tool_prefers_structured_content_when_populated() -> None:
    """When the MCP server populates `structured_content` (the modern
    path), the transport returns that directly — no JSON parsing needed.
    """

    class _CallResult:
        def __init__(self, payload: dict[str, Any]) -> None:
            self.content = []
            self.structured_content = payload
            self.is_error = False

    class _StructuredSession:
        def __init__(self, mode: RemoteMcpMode) -> None:
            self.mode = mode

        async def open(self) -> None:
            pass

        async def close(self) -> None:
            pass

        async def list_tools(self) -> list[ToolDefinition]:
            return []

        async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
            return _CallResult({"x": 1})

    mode = RemoteMcpMode(kind="remote_mcp", url="https://x", headers={})
    t = RemoteMcpTransport(mode=mode, session_factory=lambda m: _StructuredSession(m))
    assert await t.call_tool("any", {}) == {"x": 1}


@pytest.mark.asyncio
async def test_call_tool_raises_when_result_marked_is_error() -> None:
    """MCP servers don't necessarily raise on upstream auth failures —
    they return CallToolResult(isError=True, content=[TextContent(text='401 ...')]).
    The transport surfaces this as a Python exception so install-time
    canary checks can demote the connector to FAILED.
    """

    class _ErrBlock:
        def __init__(self, text: str) -> None:
            self.text = text

    class _ErrResult:
        def __init__(self) -> None:
            self.isError = True
            self.content = [_ErrBlock("Request failed with status code 401")]
            self.structured_content = None

    class _ErrSession:
        def __init__(self, mode: RemoteMcpMode) -> None:
            self.mode = mode

        async def open(self) -> None:
            pass

        async def close(self) -> None:
            pass

        async def list_tools(self) -> list[ToolDefinition]:
            return []

        async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
            return _ErrResult()

    mode = RemoteMcpMode(kind="remote_mcp", url="https://x", headers={})
    t = RemoteMcpTransport(mode=mode, session_factory=lambda m: _ErrSession(m))
    with pytest.raises(RuntimeError, match="401"):
        await t.call_tool("any", {})


@pytest.mark.asyncio
async def test_aclose_closes_and_resets_session() -> None:
    holder: dict[str, _FakeSession] = {}
    t = _make(holder)
    await t.call_tool("search", {})
    await t.aclose()
    assert holder["sess"].closed is True
    assert t._session is None
