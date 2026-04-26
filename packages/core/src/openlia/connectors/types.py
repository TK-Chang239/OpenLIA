"""Pure value types for connector subsystem.

See docs/superpowers/specs/2026-04-26-connector-redesign-design.md §4.

This module MUST stay free of FastAPI, SQLAlchemy, and HTTP clients.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class Category(StrEnum):
    FINANCIAL = "financial"
    NEWS = "news"
    SOCIAL = "social"
    WEB_SEARCH = "web_search"


class ConnectorSource(StrEnum):
    BUILT_IN = "built_in"
    REMOTE_MCP = "remote_mcp"
    CLI_MCP = "cli_mcp"


class ConnectorStatus(StrEnum):
    PENDING = "pending"
    VALIDATED = "validated"
    FAILED = "failed"


class ScopedBy(StrEnum):
    BUILT_IN_MAP = "built_in_map"
    LLM_ADAPTER = "llm_adapter"


@dataclass(frozen=True)
class MCPLaunchSpec:
    """Tagged-union launch spec persisted as JSON on Connector.launch."""

    kind: ConnectorSource
    url: str | None = None
    headers: dict[str, str] = field(default_factory=dict)
    argv: tuple[str, ...] = ()
    env: dict[str, str] = field(default_factory=dict)
    template_id: str | None = None

    @staticmethod
    def remote(url: str, headers: dict[str, str] | None = None) -> MCPLaunchSpec:
        return MCPLaunchSpec(kind=ConnectorSource.REMOTE_MCP, url=url, headers=dict(headers or {}))

    @staticmethod
    def cli(argv: list[str] | tuple[str, ...], env: dict[str, str] | None = None) -> MCPLaunchSpec:
        return MCPLaunchSpec(kind=ConnectorSource.CLI_MCP, argv=tuple(argv), env=dict(env or {}))

    @staticmethod
    def built_in(template_id: str) -> MCPLaunchSpec:
        return MCPLaunchSpec(kind=ConnectorSource.BUILT_IN, template_id=template_id)

    def to_json(self) -> dict[str, Any]:
        if self.kind is ConnectorSource.REMOTE_MCP:
            return {"kind": self.kind.value, "url": self.url, "headers": dict(self.headers)}
        if self.kind is ConnectorSource.CLI_MCP:
            return {"kind": self.kind.value, "argv": list(self.argv), "env": dict(self.env)}
        if self.kind is ConnectorSource.BUILT_IN:
            return {"kind": self.kind.value, "template_id": self.template_id}
        raise ValueError(f"unknown kind {self.kind!r}")  # pragma: no cover - exhaustive

    @staticmethod
    def from_json(raw: dict[str, Any]) -> MCPLaunchSpec:
        kind = raw.get("kind")
        if kind == ConnectorSource.REMOTE_MCP.value:
            if "url" not in raw:
                raise ValueError(f"remote_mcp launch spec missing 'url': {raw!r}")
            return MCPLaunchSpec.remote(url=raw["url"], headers=raw.get("headers", {}))
        if kind == ConnectorSource.CLI_MCP.value:
            if "argv" not in raw:
                raise ValueError(f"cli_mcp launch spec missing 'argv': {raw!r}")
            return MCPLaunchSpec.cli(argv=raw["argv"], env=raw.get("env", {}))
        if kind == ConnectorSource.BUILT_IN.value:
            if "template_id" not in raw:
                raise ValueError(f"built_in launch spec missing 'template_id': {raw!r}")
            return MCPLaunchSpec.built_in(template_id=raw["template_id"])
        raise ValueError(f"unknown kind {kind!r}")


@dataclass(frozen=True)
class ToolDefinition:
    """Single tool as returned by `list_tools()` from an MCP server."""

    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class ScopedTool:
    """Result row produced by built-in maps or the adapter LLM."""

    department_id: str
    connector_id: str
    tool_name: str
