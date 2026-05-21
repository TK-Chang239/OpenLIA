from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal, Protocol

ToolKind = Literal["mcp", "python_sdk", "openapi", "web", "internal"]


@dataclass(frozen=True)
class ToolMeta:
    name: str
    description: str
    cacheable: bool = False


@dataclass(frozen=True)
class ToolResult:
    content: Any
    metadata: dict = field(default_factory=dict)
    served_from_cache: bool = False


class ConnectorAdapter(Protocol):
    name: str
    tool_kind: ToolKind
    cacheable: bool

    def list_tools(self) -> list[ToolMeta]: ...
    def call(self, tool: str, params: dict) -> ToolResult: ...
