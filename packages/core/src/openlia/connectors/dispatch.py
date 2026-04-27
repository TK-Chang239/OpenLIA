"""Runtime dispatch for the connector subsystem.

Loads each department's allowlist from the connector registry, prefixes
tool names with `<provider_id>__`, and routes tool_use back to the right
connector transport.

This module is pure logic; the registry and allowlist data are passed in
so the server layer can hydrate them from SQLAlchemy.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from openlia.connectors.types import ToolDefinition

PREFIX_SEP = "__"


class CallableTransport(Protocol):
    async def call_tool(self, name: str, arguments: dict[str, Any]) -> Any: ...


class DispatchError(RuntimeError):
    pass


@dataclass(frozen=True)
class PreparedConnector:
    connector_id: str
    provider_id: str
    transport: CallableTransport
    tools: dict[str, ToolDefinition]
    """Maps unprefixed tool_name -> ToolDefinition."""


@dataclass
class Dispatcher:
    connectors: dict[str, PreparedConnector]
    """Keyed by connector_id."""
    allowlist: dict[str, list[tuple[str, str]]]
    """department_id -> list of (connector_id, tool_name)."""

    def tools_for_department(self, department_id: str) -> list[dict[str, Any]]:
        rows = self.allowlist.get(department_id, [])
        out: list[dict[str, Any]] = []
        for connector_id, tool_name in rows:
            conn = self.connectors.get(connector_id)
            if conn is None:
                continue
            td = conn.tools.get(tool_name)
            if td is None:
                continue
            out.append(
                {
                    "name": f"{conn.provider_id}{PREFIX_SEP}{tool_name}",
                    "description": td.description,
                    "input_schema": td.input_schema,
                }
            )
        return out

    async def dispatch_tool_use(self, prefixed_name: str, arguments: dict[str, Any]) -> Any:
        if PREFIX_SEP not in prefixed_name:
            raise DispatchError(f"missing prefix in {prefixed_name!r}")
        provider_id, _, raw_name = prefixed_name.partition(PREFIX_SEP)
        for conn in self.connectors.values():
            if conn.provider_id == provider_id and raw_name in conn.tools:
                return await conn.transport.call_tool(raw_name, arguments)
        raise DispatchError(f"no connector for {prefixed_name!r}")
