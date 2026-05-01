"""Pure value types for the built-in template registry (v2 redesign).

See docs/superpowers/specsv2/2026-04-27-connector-dataflow-design.md
sections §3.4 and §13.5 (locked: empty day-1 catalog).

Stays consistent with the connector v2 type-system convention of
frozen dataclasses with tuple-shaped collections so values are
hashable and immutable.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from openlia.connectors.types import Category


@dataclass(frozen=True)
class CliMcpRecipe:
    kind: Literal["cli_mcp"]
    argv: tuple[str, ...]
    env_keys: tuple[str, ...]


@dataclass(frozen=True)
class RemoteMcpRecipe:
    kind: Literal["remote_mcp"]
    url: str
    headers: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class PythonLibRecipe:
    kind: Literal["python_lib"]
    pip_name: str
    pip_version: str
    import_module: str
    instance_factory_cls: str
    instance_factory_args: tuple[tuple[str, str], ...]


ModeRecipe = CliMcpRecipe | RemoteMcpRecipe | PythonLibRecipe


@dataclass(frozen=True)
class BuiltInTemplate:
    template_id: str
    display_name: str
    category: Category
    api_key_env_var: str
    available_modes: tuple[ModeRecipe, ...]
    canary_tool: str | None
