"""MCPTransport composes the MCP SDK's session for our needs.

We test against an injected session factory so unit tests do not spawn
processes or talk to the network.
"""

from __future__ import annotations

import pytest
from openlia.connectors.mcp_transport import MCPTransport
from openlia.connectors.types import MCPLaunchSpec, ToolDefinition


class _FakeSession:
    def __init__(self, tools: list[ToolDefinition], call_results: dict[str, object]) -> None:
        self.tools = tools
        self.call_results = call_results
        self.opened = False
        self.closed = False
        self.calls: list[tuple[str, dict]] = []

    async def open(self) -> None:
        self.opened = True

    async def close(self) -> None:
        self.closed = True

    async def list_tools(self) -> list[ToolDefinition]:
        return list(self.tools)

    async def call_tool(self, name: str, arguments: dict) -> object:
        self.calls.append((name, arguments))
        if name not in self.call_results:
            raise RuntimeError(f"unknown tool: {name}")
        return self.call_results[name]


async def test_transport_opens_lists_calls_closes():
    fake = _FakeSession(
        tools=[ToolDefinition(name="get_quote", description="...", input_schema={})],
        call_results={"get_quote": {"price": 1.23}},
    )
    transport = MCPTransport(
        spec=MCPLaunchSpec.remote(url="https://x.example/mcp"),
        session_factory=lambda spec: fake,
    )
    await transport.open()
    tools = await transport.list_tools()
    out = await transport.call_tool("get_quote", {"ticker": "AAPL"})
    await transport.close()

    assert fake.opened is True
    assert fake.closed is True
    assert tools[0].name == "get_quote"
    assert out == {"price": 1.23}
    assert fake.calls == [("get_quote", {"ticker": "AAPL"})]


async def test_transport_call_tool_raises_propagates():
    fake = _FakeSession(tools=[], call_results={})
    transport = MCPTransport(
        spec=MCPLaunchSpec.cli(argv=["uvx", "x"]),
        session_factory=lambda s: fake,
    )
    await transport.open()
    with pytest.raises(RuntimeError, match="unknown tool"):
        await transport.call_tool("nope", {})


async def test_transport_list_tools_before_open_raises():
    transport = MCPTransport(
        spec=MCPLaunchSpec.remote(url="https://x"),
        session_factory=lambda s: _FakeSession(tools=[], call_results={}),
    )
    with pytest.raises(RuntimeError, match="not opened"):
        await transport.list_tools()


async def test_transport_close_is_idempotent():
    fake = _FakeSession(tools=[], call_results={})
    transport = MCPTransport(
        spec=MCPLaunchSpec.remote(url="https://x"),
        session_factory=lambda s: fake,
    )
    await transport.open()
    await transport.close()
    await transport.close()  # should not raise
