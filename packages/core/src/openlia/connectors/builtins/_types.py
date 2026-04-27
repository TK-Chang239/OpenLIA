"""BuiltInTemplate value type."""

from __future__ import annotations

from dataclasses import dataclass

from openlia.connectors.types import Category


@dataclass(frozen=True)
class ShippedAssignment:
    department_id: str
    tool_name: str


@dataclass(frozen=True)
class BuiltInTemplate:
    template_id: str
    display_name: str
    category: Category
    api_key_env_var: str
    """Env-var name the launched MCP server reads for credentials."""
    cli_argv: tuple[str, ...]
    """e.g. ('uvx', 'eodhd-mcp-server')."""
    canary_tool: str
    shipped_allowlist: tuple[ShippedAssignment, ...]
