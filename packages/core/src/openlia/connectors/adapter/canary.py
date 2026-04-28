"""Canary execution for the wizard-time adapter LLM.

Spec: docs/superpowers/specsv2/2026-04-27-connector-dataflow-design.md §7.3 (steps 3-4).

Given a draft `CallableSpec` produced by the resolver, run the call once with
sample arguments, capture the result (or the exception), and compare the
result's top-level type against the need's declared `shape`.

Compared to `Dispatcher._invoke_spec`, `run_canary` is intentionally simpler:
it builds the bound argument dict directly from `param_bindings` + `constants`
and dispatches to `transport.call_tool(name, bound_args)`. Wizard-time runs
do not depend on the `_current_dept` ContextVar.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from openlia.connectors.transports import CallableTransport
from openlia.connectors.types import (
    ALLOWED_TRANSFORMS,
    TRANSFORMS,
    CallableSpec,
)


@dataclass(frozen=True)
class CanaryResult:
    ok: bool
    value: Any
    error: str | None
    shape_match: bool


def _bind_args(spec: CallableSpec, sample_args: dict[str, Any]) -> dict[str, Any]:
    bound: dict[str, Any] = {}
    for caller_name, value in sample_args.items():
        binding = spec.param_bindings.get(caller_name)
        if binding is None:
            bound[caller_name] = value
            continue
        if binding.transform is not None:
            if binding.transform not in ALLOWED_TRANSFORMS:
                raise ValueError(
                    f"unknown transform {binding.transform!r} on need "
                    f"{spec.need_id!r}"
                )
            value = TRANSFORMS[binding.transform](value)
        bound[binding.to_arg] = value
    for k, v in spec.constants.items():
        bound[k] = v
    return bound


def _shape_matches(value: Any, shape: str) -> bool:
    """Approximate top-level type check for a `CallableSpec.shape` string.

    Matches:
      - `any`            -> True
      - `float` / `int`  -> isinstance(value, (int, float)) bool exclusion
      - `bool`           -> isinstance(value, bool)
      - `str`            -> isinstance(value, str)
      - `list[...]`      -> isinstance(value, list)
      - `dict[...]`      -> isinstance(value, dict)
    Anything else: True (we cannot verify; defer to canary value inspection).
    """
    s = shape.strip()
    if s == "" or s == "any":
        return True
    base = s.split("[", 1)[0].strip().lower()
    if base == "bool":
        return isinstance(value, bool)
    if base == "int":
        return isinstance(value, int) and not isinstance(value, bool)
    if base == "float":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if base == "str":
        return isinstance(value, str)
    if base == "list":
        return isinstance(value, list)
    if base == "dict":
        return isinstance(value, dict)
    return True


async def run_canary(
    *,
    spec: CallableSpec,
    transport: CallableTransport,
    sample_args: dict[str, Any],
) -> CanaryResult:
    """Execute `spec` once and report shape match.

    On exception, returns `ok=False, error=<message>, shape_match=False`. Never
    re-raises transport errors — the wizard surfaces them as draft warnings.
    """

    if spec.access_mode in ("cli_mcp", "remote_mcp"):
        target = spec.tool_name
    elif spec.access_mode == "python_lib":
        target = spec.method
    else:
        return CanaryResult(
            ok=False,
            value=None,
            error=f"unknown access_mode {spec.access_mode!r}",
            shape_match=False,
        )
    if not target:
        return CanaryResult(
            ok=False,
            value=None,
            error=f"spec for need {spec.need_id!r} has no tool/method name",
            shape_match=False,
        )

    try:
        bound = _bind_args(spec, sample_args)
    except Exception as exc:
        return CanaryResult(ok=False, value=None, error=str(exc), shape_match=False)

    try:
        value = await transport.call_tool(target, bound)
    except Exception as exc:
        return CanaryResult(
            ok=False,
            value=None,
            error=f"{type(exc).__name__}: {exc}",
            shape_match=False,
        )

    return CanaryResult(
        ok=True,
        value=value,
        error=None,
        shape_match=_shape_matches(value, spec.shape),
    )


__all__ = ["CanaryResult", "run_canary"]
