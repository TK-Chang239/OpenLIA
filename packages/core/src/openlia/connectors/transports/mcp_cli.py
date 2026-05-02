"""CLI-stdio MCP transport — implements `CallableTransport`.

Spec: docs/superpowers/specsv2/2026-04-27-connector-dataflow-design.md §4.

Wraps the MCP SDK's stdio client. At spawn time the env passed to the
subprocess is built from `secrets[k]` for every `k` in `mode.env_keys` —
only the explicitly-listed keys leak into the child process; the rest of
the connector's secret bag stays in-process.
"""

from __future__ import annotations

import contextlib
from collections.abc import Callable
from typing import Any

from openlia.connectors.types import CliMcpMode, ToolDefinition


class CliMcpTransport:
    """`CallableTransport` for `cli_mcp` mode."""

    def __init__(
        self,
        *,
        mode: CliMcpMode,
        secrets: dict[str, str],
        session_factory: Callable[[list[str], dict[str, str]], _CliMcpSession] | None = None,
    ) -> None:
        self._mode = mode
        self._secrets = secrets
        self._session_factory = session_factory or _default_cli_session
        self._session: _CliMcpSession | None = None

    def _build_env(self) -> dict[str, str]:
        """Project the secrets bag through `env_keys`.

        Only keys explicitly listed on the launch mode are exported into the
        child process env. Missing keys are skipped (the validator catches
        misconfigured connectors before they reach runtime).
        """
        return {k: self._secrets[k] for k in self._mode.env_keys if k in self._secrets}

    async def _ensure_open(self) -> _CliMcpSession:
        if self._session is None:
            argv = list(self._mode.argv)
            if not argv:
                raise ValueError("cli_mcp launch mode has empty argv")
            self._session = self._session_factory(argv, self._build_env())
            await self._session.open()
        return self._session

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any:
        from openlia.connectors.transports.mcp_remote import _unwrap_call_result

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


class _CliMcpSession:
    """Minimal session interface used by the transport (testing seam)."""

    async def open(self) -> None: ...
    async def close(self) -> None: ...
    async def list_tools(self) -> list[ToolDefinition]: ...
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any: ...


def _default_cli_session(
    argv: list[str], env: dict[str, str]
) -> _CliMcpSession:  # pragma: no cover
    """Real session factory: stdio MCP subprocess over the MCP SDK."""

    from mcp import ClientSession  # type: ignore[import-not-found]
    from mcp.client.stdio import (  # type: ignore[import-not-found]
        StdioServerParameters,
        stdio_client,
    )

    params = StdioServerParameters(command=argv[0], args=list(argv[1:]), env=dict(env))
    return _SDKAdapter(
        open_client=lambda: stdio_client(params),
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
