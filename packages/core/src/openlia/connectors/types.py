"""Pure value types for connector subsystem (v2 redesign).

See docs/superpowers/specsv2/2026-04-27-connector-dataflow-design.md
sections §3.1, §6.1, §6.4, §6.5.

This module MUST stay free of FastAPI, SQLAlchemy, and HTTP clients.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any, Literal


class Category(StrEnum):
    FINANCIAL = "financial"
    NEWS = "news"
    SOCIAL = "social"
    WEB_SEARCH = "web_search"


class ConnectorSource(StrEnum):
    BUILT_IN = "built_in"
    REMOTE_MCP = "remote_mcp"
    CLI_MCP = "cli_mcp"
    PYTHON_LIB = "python_lib"
    SKILL = "skill"  # reserved for Layer 2


class ConnectorStatus(StrEnum):
    PENDING = "pending"
    VALIDATED = "validated"
    FAILED = "failed"


@dataclass(frozen=True)
class CliMcpMode:
    kind: Literal["cli_mcp"]
    argv: list[str]
    env_keys: list[str]


@dataclass(frozen=True)
class RemoteMcpMode:
    kind: Literal["remote_mcp"]
    url: str
    headers: dict[str, str]


@dataclass(frozen=True)
class InstanceFactory:
    cls: str
    args: dict[str, Any]  # values may be `$ENV_VAR_NAME` or `${ENV_VAR_NAME}` placeholders


@dataclass(frozen=True)
class PythonLibMode:
    kind: Literal["python_lib"]
    pip_name: str
    pip_version: str
    import_module: str
    instance_factory: InstanceFactory


LaunchMode = CliMcpMode | RemoteMcpMode | PythonLibMode


@dataclass(frozen=True)
class LaunchSpec:
    """Multi-mode launch spec persisted as JSON on Connector.launch.

    A single connector row may expose more than one runtime mode
    (e.g. eodhd as both `cli_mcp` and `python_lib`). The wizard-time
    adapter LLM picks one mode per RunnerNeed when authoring CallableSpecs.
    """

    modes: list[LaunchMode]


@dataclass(frozen=True)
class ToolDefinition:
    """Single tool as returned by `list_tools()` from an MCP server."""

    name: str
    description: str
    input_schema: dict[str, Any]


@dataclass(frozen=True)
class CallableDefinition:
    """Single callable surfaced by a python_lib connector."""

    qualname: str  # e.g. "APIClient.real_time_quote"
    signature: str  # "(symbol: str) -> dict"
    doc: str


@dataclass(frozen=True)
class NeedParameter:
    name: str
    description: str
    type: str
    required: bool
    default: Any = None


@dataclass(frozen=True)
class RunnerNeed:
    """Department-declared data need, resolved at wizard time."""

    id: str
    description: str
    parameters: list[NeedParameter]
    shape: str  # type hint string, e.g. "float", "list[dict]"


@dataclass(frozen=True)
class ParamBinding:
    to_arg: str
    transform: str | None = None  # named entry in TRANSFORMS, or None


@dataclass(frozen=True)
class CallableSpec:
    """Persisted resolution from a RunnerNeed to a concrete connector callable."""

    need_id: str
    access_mode: Literal["cli_mcp", "remote_mcp", "python_lib"]
    # MCP fields:
    tool_name: str | None = None
    # python_lib fields:
    module: str | None = None
    instance_factory: InstanceFactory | None = None
    method: str | None = None
    # shared fields:
    param_bindings: dict[str, ParamBinding] = field(default_factory=dict)
    constants: dict[str, Any] = field(default_factory=dict)
    shape: str = "any"
    result_path: tuple[str, ...] = ()


TRANSFORMS: dict[str, Callable[[Any], Any]] = {
    "upper": str.upper,
    "lower": str.lower,
    "iso_to_eodhd": lambda code: f"{code}.NYSE",  # placeholder; finalize during adapter authoring
}

ALLOWED_TRANSFORMS: frozenset[str] = frozenset(TRANSFORMS.keys())
