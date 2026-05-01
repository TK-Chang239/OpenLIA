"""Unified transport Protocol shared across MCP + python_lib modes.

Spec: docs/superpowers/specsv2/2026-04-27-connector-dataflow-design.md §4.

Per the redesign every Connector launch mode is reduced to a single uniform
runtime surface so the dispatcher can route a `tool_use` event or a
`fetch_need(...)` call without caring about the underlying transport.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class CallableTransport(Protocol):
    """Uniform transport interface implemented by every launch-mode adapter.

    Implementations:
    - `python_lib.PythonLibTransport` (in-process Python objects)
    - `mcp_remote.RemoteMcpTransport`  (HTTP MCP server)
    - `mcp_cli.CliMcpTransport`        (stdio MCP subprocess)
    """

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any: ...
    async def list_tools(self) -> list[dict]: ...
    async def aclose(self) -> None: ...
