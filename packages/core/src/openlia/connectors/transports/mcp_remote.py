"""Remote-HTTP MCP transport — implements `CallableTransport`.

Spec: docs/superpowers/specsv2/2026-04-27-connector-dataflow-design.md §4.

Wraps the MCP SDK's `streamablehttp_client` + `ClientSession` behind the
uniform transport surface. The session is opened lazily on the first call.
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Callable
from typing import Any

from openlia.connectors.types import RemoteMcpMode, ToolDefinition


def _unwrap_call_result(result: Any) -> Any:
    """Reduce an MCP `CallToolResult` to plain Python data.

    MCP servers return tool payloads in one of two shapes:
    1. `structured_content`: a parsed dict (modern path) — preferred.
    2. `content`: a list of `TextContent` blocks whose `.text` is a
       JSON-stringified payload (legacy / common path).

    Plain dicts/lists from non-MCP tests pass through unchanged.
    """
    structured = getattr(result, "structured_content", None)
    if structured is not None:
        return structured
    content = getattr(result, "content", None)
    if content:
        first = content[0]
        text = getattr(first, "text", None)
        if isinstance(text, str):
            try:
                return json.loads(text)
            except (ValueError, TypeError):
                return text
    return result


class RemoteMcpTransport:
    """`CallableTransport` for `remote_mcp` mode."""

    def __init__(
        self,
        *,
        mode: RemoteMcpMode,
        session_factory: Callable[[RemoteMcpMode], _RemoteMcpSession] | None = None,
    ) -> None:
        self._mode = mode
        self._session_factory = session_factory or _default_remote_session
        self._session: _RemoteMcpSession | None = None

    async def _ensure_open(self) -> _RemoteMcpSession:
        if self._session is None:
            self._session = self._session_factory(self._mode)
            await self._session.open()
        return self._session

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        sess = await self._ensure_open()
        return _unwrap_call_result(await sess.call_tool(name, arguments))

    async def list_tools(self) -> list[dict]:
        sess = await self._ensure_open()
        tools = await sess.list_tools()
        return [
            {"name": t.name, "description": t.description, "input_schema": t.input_schema}
            for t in tools
        ]

    async def aclose(self) -> None:
        if self._session is not None:
            await self._session.close()
            self._session = None


class _RemoteMcpSession:
    """Minimal session interface used by the transport (testing seam)."""

    async def open(self) -> None: ...
    async def close(self) -> None: ...
    async def list_tools(self) -> list[ToolDefinition]: ...
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any: ...


def _default_remote_session(mode: RemoteMcpMode) -> _RemoteMcpSession:  # pragma: no cover
    """Real session factory using the MCP SDK over streamable HTTP."""

    from mcp import ClientSession  # type: ignore[import-not-found]
    from mcp.client.streamable_http import streamablehttp_client  # type: ignore[import-not-found]

    return _SDKAdapter(
        open_client=lambda: streamablehttp_client(mode.url, headers=dict(mode.headers)),
        session_cls=ClientSession,
    )


class _SDKAdapter:  # pragma: no cover
    """Bridges the MCP SDK's async-context-manager style to flat open/close."""

    def __init__(self, *, open_client, session_cls) -> None:  # type: ignore[no-untyped-def]
        self._open_client = open_client
        self._session_cls = session_cls
        self._stack: contextlib.AsyncExitStack | None = None
        self._session: Any = None

    async def open(self) -> None:
        stack = contextlib.AsyncExitStack()
        try:
            client_streams = await stack.enter_async_context(self._open_client())
            # streamablehttp returns (read, write, _); we only need read+write.
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
