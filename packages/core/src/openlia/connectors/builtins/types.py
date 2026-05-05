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

from openlia.connectors.types import CallableSpec, Category


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
    runner_specs: tuple[CallableSpec, ...] = ()
    # Sample args to pass when invoking `canary_tool` at install time.
    # `None` means skip canary (list_tools alone is the auth check).
    # Tuple form keeps the dataclass hashable. Each entry is (arg, value).
    canary_args: tuple[tuple[str, object], ...] | None = None
    # Per-tool overrides applied to `cached_tools` after auto-discovery.
    # Lets a template fix tools whose SDK signature understates the
    # upstream API's actual contract (e.g. EODHD's `financial_news`
    # accepts all-None Python kwargs but the API requires `s` or `t`).
    # Each entry is (tool_name, override_dict). Override keys (typically
    # `description` and `input_schema`) replace those fields on the
    # matching tool; other fields pass through unchanged.
    tool_overrides: tuple[tuple[str, dict], ...] = ()
    # Pre-dispatch argument constraints. Each entry is
    # (tool_name, "require_one_of", (("s", "t"),)). Anthropic's tool
    # input_schema validator forbids JSON-Schema combinators (anyOf /
    # oneOf), so we can't express "exactly one of these is required" at
    # the schema layer. The dispatcher consults these constraints before
    # calling the transport and short-circuits with a structured error
    # payload the model can recover from on the next turn.
    tool_argument_constraints: tuple[tuple[str, str, tuple[tuple[str, ...], ...]], ...] = ()
