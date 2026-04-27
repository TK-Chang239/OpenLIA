"""Thin MCP session wrapper.

Decouples the rest of the connector package from the MCP SDK's surface so
that unit tests can inject a fake session factory.

Real session_factory implementations live in this module. Tests pass
their own factory.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Protocol

from openlia.connectors.types import ConnectorSource, MCPLaunchSpec, ToolDefinition


class MCPSession(Protocol):
    async def open(self) -> None: ...
    async def close(self) -> None: ...
    async def list_tools(self) -> list[ToolDefinition]: ...
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any: ...


SessionFactory = Callable[[MCPLaunchSpec], MCPSession]


@dataclass
class MCPTransport:
    spec: MCPLaunchSpec
    session_factory: SessionFactory
    _session: MCPSession | None = None

    async def open(self) -> None:
        self._session = self.session_factory(self.spec)
        await self._session.open()

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None

    async def list_tools(self) -> list[ToolDefinition]:
        if self._session is None:
            raise RuntimeError("transport not opened")
        return await self._session.list_tools()

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        if self._session is None:
            raise RuntimeError("transport not opened")
        return await self._session.call_tool(name, arguments)


def default_session_factory(spec: MCPLaunchSpec) -> MCPSession:  # pragma: no cover
    """Real session factory using the MCP SDK.

    HTTP for REMOTE_MCP, stdio subprocess for CLI_MCP. The BUILT_IN case
    is resolved to a CLI_MCP spec by the connector service before reaching
    here, so it raises if BUILT_IN slips through.
    """

    from mcp import ClientSession  # type: ignore[import-not-found]
    from mcp.client.stdio import (  # type: ignore[import-not-found]
        StdioServerParameters,
        stdio_client,
    )
    from mcp.client.streamable_http import streamablehttp_client  # type: ignore[import-not-found]

    if spec.kind is ConnectorSource.REMOTE_MCP:
        return _SDKAdapter(
            open_client=lambda: streamablehttp_client(spec.url, headers=dict(spec.headers)),
            session_cls=ClientSession,
        )
    if spec.kind is ConnectorSource.CLI_MCP:
        if not spec.argv:
            raise ValueError("CLI_MCP launch spec has empty argv")
        params = StdioServerParameters(
            command=spec.argv[0],
            args=list(spec.argv[1:]),
            env=dict(spec.env),
        )
        return _SDKAdapter(
            open_client=lambda: stdio_client(params),
            session_cls=ClientSession,
        )
    raise ValueError(f"BUILT_IN must be resolved to CLI_MCP before transport: {spec.kind!r}")


class _SDKAdapter:  # pragma: no cover
    """Bridges the SDK's async-context-manager style to our flat open/close interface."""

    def __init__(self, *, open_client, session_cls) -> None:  # type: ignore[no-untyped-def]
        self._open_client = open_client
        self._session_cls = session_cls
        self._stack: contextlib.AsyncExitStack | None = None
        self._session: Any = None

    async def open(self) -> None:
        stack = contextlib.AsyncExitStack()
        try:
            client_streams = await stack.enter_async_context(self._open_client())
            # streamablehttp returns (read, write, _); stdio returns (read, write).
            read, write = client_streams[0], client_streams[1]
            session = self._session_cls(read, write)
            await stack.enter_async_context(session)
            await session.initialize()
            self._session = session
            self._stack = stack
        except BaseException:
            await stack.aclose()
            raise

    async def close(self) -> None:
        if self._stack is None:
            return
        stack, self._stack = self._stack, None
        self._session = None
        await stack.aclose()

    async def list_tools(self) -> list[ToolDefinition]:
        resp = await self._session.list_tools()
        return [
            ToolDefinition(
                name=t.name, description=t.description or "", input_schema=t.inputSchema or {}
            )
            for t in resp.tools
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        return await self._session.call_tool(name, arguments)
