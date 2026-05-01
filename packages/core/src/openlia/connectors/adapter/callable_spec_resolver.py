"""Wizard-time adapter LLM resolver.

Spec: docs/superpowers/specsv2/2026-04-27-connector-dataflow-design.md §7.

Single quick-tier LLM call. Maps a department-declared `RunnerNeed` onto a
concrete callable exposed by a connector — either an MCP tool (cli_mcp /
remote_mcp) or a python_lib class method. The LLM is asked for strict JSON
matching the `CallableSpec` shape; the resolver validates the response before
returning it as a `CallableSpec` value object.

Validation gate (post-LLM, pre-return):

1. The chosen `tool_name` (MCP) / `qualname` (python_lib) must exist in the
   inventory.
2. Every declared `param_binding.to_arg` must match a real parameter on the
   chosen tool/method.
3. Every declared `transform` must be in `ALLOWED_TRANSFORMS`.
4. Every constant must be JSON-serializable.

The actual LLM client wiring lives in `openlia.llm`; this module only depends
on the minimal `LlmClient` Protocol below so tests can mock it.
"""

from __future__ import annotations

import inspect
import json
from typing import Any, Literal, Protocol, runtime_checkable

from openlia.connectors.types import (
    ALLOWED_TRANSFORMS,
    CallableDefinition,
    CallableSpec,
    InstanceFactory,
    ParamBinding,
    RunnerNeed,
    ToolDefinition,
)


class ResolverError(RuntimeError):
    """Raised when the LLM proposal fails the validation gate."""


@runtime_checkable
class LlmClient(Protocol):
    """Minimal contract for the wizard-time adapter LLM call.

    Phase 9 wires a real provider (OpenRouter quick tier per spec §7); for
    Phase 6 the resolver is exercised with a mock client returning canned JSON.
    """

    async def generate_json(self, *, prompt: str) -> dict[str, Any]: ...


_PROMPT_TEMPLATE = """\
You are resolving a department's data need to a concrete callable on an
already-validated connector. Output STRICT JSON only — no prose, no markdown.

The connector exposes its surface in {access_mode!r} mode.

Need:
  id: {need_id}
  description: {need_description}
  shape (return-type hint): {need_shape}
  parameters:
{need_parameters}

Inventory:
{inventory}

Allowed transforms (use the literal name or null):
  {allowed_transforms}

Respond with a JSON object of the form:
{{
  "tool_name": "<MCP tool name, or null for python_lib>",
  "method": "<python_lib method qualname, or null for MCP>",
  "param_bindings": {{
    "<need parameter name>": {{
      "to_arg": "<actual arg on the tool/method>",
      "transform": "<transform name or null>"
    }}
  }},
  "constants": {{"<arg name>": <JSON value>}}
}}
"""


def _format_parameters(need: RunnerNeed) -> str:
    if not need.parameters:
        return "    (none)"
    lines: list[str] = []
    for p in need.parameters:
        req = "required" if p.required else "optional"
        lines.append(f"    - {p.name} ({p.type}, {req}): {p.description}")
    return "\n".join(lines)


def _format_inventory(
    access_mode: str,
    inventory: list[CallableDefinition] | list[ToolDefinition],
) -> str:
    if not inventory:
        return "    (empty)"
    lines: list[str] = []
    if access_mode in ("cli_mcp", "remote_mcp"):
        for item in inventory:
            assert isinstance(item, ToolDefinition)
            lines.append(f"  - tool {item.name}: {item.description}")
            lines.append(f"    input_schema: {json.dumps(item.input_schema)}")
    else:
        for item in inventory:
            assert isinstance(item, CallableDefinition)
            lines.append(f"  - {item.qualname}{item.signature}")
            if item.doc:
                lines.append(f"    doc: {item.doc.splitlines()[0]}")
    return "\n".join(lines)


def _build_prompt(
    need: RunnerNeed,
    access_mode: str,
    inventory: list[CallableDefinition] | list[ToolDefinition],
) -> str:
    return _PROMPT_TEMPLATE.format(
        access_mode=access_mode,
        need_id=need.id,
        need_description=need.description,
        need_shape=need.shape,
        need_parameters=_format_parameters(need),
        inventory=_format_inventory(access_mode, inventory),
        allowed_transforms=", ".join(sorted(ALLOWED_TRANSFORMS)) or "(none)",
    )


def _tool_args_from_schema(schema: dict[str, Any]) -> set[str]:
    props = schema.get("properties") if isinstance(schema, dict) else None
    if isinstance(props, dict):
        return set(props.keys())
    return set()


def _python_method_args(qualname: str, defs: list[CallableDefinition]) -> set[str]:
    for d in defs:
        if d.qualname == qualname:
            try:
                # `signature` is the stringified inspect.Signature; parse via
                # eval-free helper: extract the parameter names from "( ... )".
                return _parse_signature_args(d.signature)
            except Exception as exc:
                raise ResolverError(f"could not parse signature for {qualname!r}: {exc}") from exc
    raise ResolverError(f"qualname {qualname!r} not found in inventory")


def _parse_signature_args(sig_str: str) -> set[str]:
    """Extract argument names from a stringified `inspect.Signature`.

    Handles the typical `(self, foo: int, bar: str = 'x') -> Y` shape. We
    use `inspect.Parameter` parsing by re-creating the signature via the
    `inspect` module's parser — but only the names matter, so a simple
    string parser is sufficient here.
    """
    inside = sig_str.strip()
    if inside.startswith("("):
        inside = inside[1:]
    if ") -> " in inside:
        inside = inside.split(") -> ", 1)[0]
    elif inside.endswith(")"):
        inside = inside[:-1]
    args: set[str] = set()
    depth = 0
    current = ""
    parts: list[str] = []
    for ch in inside:
        if ch in "[(":
            depth += 1
            current += ch
        elif ch in "])":
            depth -= 1
            current += ch
        elif ch == "," and depth == 0:
            parts.append(current)
            current = ""
        else:
            current += ch
    if current.strip():
        parts.append(current)
    for raw in parts:
        token = raw.strip()
        if not token:
            continue
        # Strip leading * and ** for variadic markers.
        token = token.lstrip("*").strip()
        # Drop default value.
        if "=" in token:
            token = token.split("=", 1)[0].strip()
        # Drop type annotation.
        if ":" in token:
            token = token.split(":", 1)[0].strip()
        if not token or token in {"/", ""}:
            continue
        args.add(token)
    args.discard("self")
    args.discard("cls")
    return args


def _validate_constants(constants: dict[str, Any]) -> None:
    try:
        json.dumps(constants)
    except (TypeError, ValueError) as exc:
        raise ResolverError(f"constants are not JSON-serializable: {exc}") from exc


def _coerce_param_bindings(raw: Any) -> dict[str, ParamBinding]:
    if not isinstance(raw, dict):
        raise ResolverError("`param_bindings` must be an object")
    out: dict[str, ParamBinding] = {}
    for caller_name, binding in raw.items():
        if not isinstance(binding, dict) or "to_arg" not in binding:
            raise ResolverError(f"`param_bindings.{caller_name}` must be an object with `to_arg`")
        out[caller_name] = ParamBinding(
            to_arg=str(binding["to_arg"]),
            transform=(binding.get("transform") or None),
        )
    return out


async def resolve_callable_spec(
    *,
    need: RunnerNeed,
    connector_inventory: list[CallableDefinition] | list[ToolDefinition],
    access_mode: Literal["cli_mcp", "remote_mcp", "python_lib"],
    instance_factory: InstanceFactory | None,
    llm_client: LlmClient,
) -> CallableSpec:
    """Single LLM call. Strict JSON response. Validate proposed bindings."""

    prompt = _build_prompt(need, access_mode, connector_inventory)
    raw = await llm_client.generate_json(prompt=prompt)
    if inspect.isawaitable(raw):
        raw = await raw  # type: ignore[assignment]
    if not isinstance(raw, dict):
        raise ResolverError("LLM response was not a JSON object")
    if raw.get("unsatisfiable") is True:
        reason = raw.get("reason") or "no covering tool/slug found"
        raise ResolverError(f"unsatisfiable: {reason}")

    tool_name = raw.get("tool_name")
    method = raw.get("method")
    constants = raw.get("constants") or {}
    if not isinstance(constants, dict):
        raise ResolverError("`constants` must be an object")
    param_bindings = _coerce_param_bindings(raw.get("param_bindings") or {})

    # Step 2: validation gate.
    valid_args: set[str]
    if access_mode in ("cli_mcp", "remote_mcp"):
        if not isinstance(tool_name, str) or not tool_name:
            raise ResolverError("MCP resolution requires a non-empty `tool_name`")
        match = next(
            (
                t
                for t in connector_inventory
                if isinstance(t, ToolDefinition) and t.name == tool_name
            ),
            None,
        )
        if match is None:
            raise ResolverError(f"tool_name {tool_name!r} not found in connector inventory")
        valid_args = _tool_args_from_schema(match.input_schema)
        method = None
    elif access_mode == "python_lib":
        if not isinstance(method, str) or not method:
            raise ResolverError("python_lib resolution requires a non-empty `method`")
        # Inventory is list[CallableDefinition] for python_lib.
        defs = [d for d in connector_inventory if isinstance(d, CallableDefinition)]
        valid_args = _python_method_args(method, defs)
        tool_name = None
    else:
        raise ResolverError(f"unknown access_mode {access_mode!r}")

    # Bindings: every declared `to_arg` must be a real parameter.
    if valid_args:
        for caller_name, binding in param_bindings.items():
            if binding.to_arg not in valid_args:
                raise ResolverError(
                    f"param_binding {caller_name!r} -> to_arg {binding.to_arg!r} "
                    f"does not match any parameter of the chosen callable"
                )

    # Transforms: every non-null transform must be allow-listed.
    for caller_name, binding in param_bindings.items():
        if binding.transform is not None and binding.transform not in ALLOWED_TRANSFORMS:
            raise ResolverError(
                f"transform {binding.transform!r} (on param_binding "
                f"{caller_name!r}) is not in ALLOWED_TRANSFORMS"
            )

    # Constants must be JSON-serializable. (Also reject any constant whose
    # name isn't a real argument, when we have a known arg set.)
    _validate_constants(constants)
    if valid_args:
        for const_arg in constants:
            if const_arg not in valid_args:
                raise ResolverError(
                    f"constant {const_arg!r} does not match any parameter of the chosen callable"
                )

    return CallableSpec(
        need_id=need.id,
        access_mode=access_mode,
        tool_name=tool_name,
        module=None,
        instance_factory=instance_factory if access_mode == "python_lib" else None,
        method=method,
        param_bindings=param_bindings,
        constants=dict(constants),
        shape=need.shape,
    )


__all__ = [
    "LlmClient",
    "ResolverError",
    "resolve_callable_spec",
]
