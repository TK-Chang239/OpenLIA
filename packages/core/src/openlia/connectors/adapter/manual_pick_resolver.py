"""Wizard-time manual-pick resolver (Phase 5 redesign).

Spec: docs/superpowers/specsv2/2026-05-02-resolver-redesign-manual-pick.md
Plan: docs/superpowers/plans/2026-05-02-resolver-redesign.md §Phase 5.

Flow change vs. the legacy `resolve_callable_spec`:
- The user picks the connector + endpoint (or URL for websearch). The
  resolver does NOT choose the callable.
- The LLM only authors the binding: `param_bindings`, `constants`, and
  for `list[dict]`-shaped needs, a per-spec `field_map` whose keys
  cover the need's `canonical_keys`.
- The LLM may emit a `warning` string when the picked endpoint fits
  the need only loosely; the resolver returns it alongside the spec
  for the UI to surface a confirm/cancel modal.

The validation gate proper (extended transform allowlist, field_map
checks, etc.) lives in Phase 6's `validation.py`. This module performs
only the structural parsing needed to construct a `CallableSpec`.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Literal

from openlia.connectors.adapter.callable_spec_resolver import (
    LlmClient,
    ResolverError,
    UnsatisfiableNeed,
)
from openlia.connectors.adapter.validation import (
    ValidationError,
    validate_resolved_spec,
)
from openlia.connectors.types import (
    CallableDefinition,
    CallableSpec,
    Category,
    InstanceFactory,
    ParamBinding,
    RunnerNeed,
    ToolDefinition,
)


@dataclass(frozen=True)
class ResolverResult:
    """Output envelope for the manual-pick resolver."""

    spec: CallableSpec
    warning: str | None


_BASE_PROMPT = """\
You are authoring the parameter binding for a department-declared data
need against a callable the USER picked on a connector. Output STRICT
JSON only — no prose, no markdown.

You DO NOT choose the callable. The user already picked it. Your job:
fill in `param_bindings`, `constants`, and (for list[dict] shapes) the
`field_map` that maps each canonical item-key to its source path on the
endpoint's per-item response.

Connector access mode: {access_mode!r}
Connector category:    {category}

User-picked endpoint:
  {user_picked_endpoint}

User hint (verbatim, may be empty):
{user_hint_block}

Need:
  id:          {need_id}
  description: {need_description}
  shape:       {need_shape}
  parameters:
{need_parameters}
{canonical_keys_block}
Inventory (full callable surface for context — DO NOT change the picked
endpoint, even if you think a different one fits better):
{inventory}

Allowed transforms (use the literal name or null):
  {allowed_transforms}

Respond with a JSON object of the form:
{{
  "spec": {{
    "param_bindings": {{
      "<need parameter name>": {{
        "to_arg": "<actual arg on the picked endpoint>",
        "transform": "<transform name or null>"
      }}
    }},
    "constants": {{"<arg name>": <JSON value>}},
    "result_path": [<dotted path segments>] OR null,
    "field_map": {{"<canonical key>": "<source path>"}} OR null
  }},
  "warning": "<short note OR null>"
}}

`field_map` is REQUIRED when shape is list[dict]; its keys MUST cover
the canonical_keys above. Use null OR omit when shape is not list[dict].
Use the empty object `{{}}` ONLY when the endpoint already returns items
keyed exactly with the canonical names.
"""

_WEBSEARCH_BLURB = """\
WEBSEARCH SUB-MODE
The connector category is `web_search` and the user supplied a target
URL. Author a Firecrawl-style scrape spec:
  - constants.url       = the user URL
  - constants.formats   = [{{"type": "json", "schema": <schema>}}]
  - The JSON schema describes the shape you want extracted from the
    rendered page text. Match the need's `shape` and (for list[dict])
    its canonical_keys.
  - result_path peels the wrapper (typically ["json", "<root>"]).

User-supplied URL: {websearch_url}
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


def _format_canonical_keys_block(need: RunnerNeed) -> str:
    if need.canonical_keys is None:
        return ""
    lines = ["  canonical_keys (each item-dict MUST have these keys after field_map):"]
    for k, v in need.canonical_keys.items():
        lines.append(f"    - {k}: {v}")
    return "\n" + "\n".join(lines) + "\n"


def _build_prompt(
    *,
    need: RunnerNeed,
    access_mode: str,
    category: Category,
    inventory: list[CallableDefinition] | list[ToolDefinition],
    user_picked_endpoint: str,
    user_hint: str | None,
    websearch_url: str | None,
) -> str:
    from openlia.connectors.types import ALLOWED_TRANSFORMS

    hint_block = f"  {user_hint.strip()}" if user_hint and user_hint.strip() else "  (none)"
    base = _BASE_PROMPT.format(
        access_mode=access_mode,
        category=category.value,
        user_picked_endpoint=user_picked_endpoint,
        user_hint_block=hint_block,
        need_id=need.id,
        need_description=need.description,
        need_shape=need.shape,
        need_parameters=_format_parameters(need),
        canonical_keys_block=_format_canonical_keys_block(need),
        inventory=_format_inventory(access_mode, inventory),
        allowed_transforms=", ".join(sorted(ALLOWED_TRANSFORMS)) or "(none)",
    )
    if category == Category.WEB_SEARCH and websearch_url:
        base = base + "\n" + _WEBSEARCH_BLURB.format(websearch_url=websearch_url)
    return base


def _coerce_param_bindings(raw: Any) -> dict[str, ParamBinding]:
    if not isinstance(raw, dict):
        raise ResolverError("`spec.param_bindings` must be an object")
    out: dict[str, ParamBinding] = {}
    for caller_name, binding in raw.items():
        if not isinstance(binding, dict) or "to_arg" not in binding:
            raise ResolverError(
                f"`spec.param_bindings.{caller_name}` must be an object with `to_arg`"
            )
        out[caller_name] = ParamBinding(
            to_arg=str(binding["to_arg"]),
            transform=(binding.get("transform") or None),
        )
    return out


def _coerce_field_map(
    raw: Any,
) -> dict[str, str | tuple[str, ...]] | None:
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise ResolverError("`spec.field_map` must be an object or null")
    out: dict[str, str | tuple[str, ...]] = {}
    for k, v in raw.items():
        if isinstance(v, list):
            out[str(k)] = tuple(str(seg) for seg in v)
        else:
            out[str(k)] = str(v)
    return out


def _coerce_result_path(raw: Any) -> tuple[str, ...]:
    if raw is None:
        return ()
    if not isinstance(raw, list):
        raise ResolverError("`spec.result_path` must be a list of strings or null")
    return tuple(str(seg) for seg in raw)


async def resolve_user_picked_spec(
    *,
    need: RunnerNeed,
    connector_inventory: list[CallableDefinition] | list[ToolDefinition],
    access_mode: Literal["cli_mcp", "remote_mcp", "python_lib"],
    connector_category: Category,
    instance_factory: InstanceFactory | None,
    llm_client: LlmClient,
    user_picked_endpoint: str,
    user_hint: str | None = None,
    websearch_url: str | None = None,
) -> ResolverResult:
    """Resolve a need to a CallableSpec using a user-picked endpoint.

    The LLM must populate the param/constant bindings (and field_map for
    list[dict] shapes). It MAY emit a `warning` string when the fit is
    loose; the caller surfaces that string for confirm/cancel.

    Raises `ValueError` for caller errors (websearch URL on a non-web-
    search connector, empty endpoint, etc.) and `ResolverError` for
    malformed LLM responses.
    """
    if not user_picked_endpoint:
        raise ValueError("user_picked_endpoint is required")
    if websearch_url is not None and connector_category != Category.WEB_SEARCH:
        raise ValueError(
            "websearch_url is only valid when connector_category is web_search; "
            f"got {connector_category!r}"
        )

    # Pre-flight: the picked endpoint must exist in the inventory.
    if access_mode in ("cli_mcp", "remote_mcp"):
        names = {t.name for t in connector_inventory if isinstance(t, ToolDefinition)}
        if user_picked_endpoint not in names:
            raise ResolverError(
                f"user_picked_endpoint {user_picked_endpoint!r} not in connector tool inventory"
            )
    else:
        quals = {d.qualname for d in connector_inventory if isinstance(d, CallableDefinition)}
        if user_picked_endpoint not in quals:
            raise ResolverError(
                f"user_picked_endpoint {user_picked_endpoint!r} not in connector method inventory"
            )

    prompt = _build_prompt(
        need=need,
        access_mode=access_mode,
        category=connector_category,
        inventory=connector_inventory,
        user_picked_endpoint=user_picked_endpoint,
        user_hint=user_hint,
        websearch_url=websearch_url,
    )
    raw = await llm_client.generate_json(prompt=prompt)
    if not isinstance(raw, dict):
        raise ResolverError("LLM response was not a JSON object")
    if raw.get("unsatisfiable") is True:
        raise UnsatisfiableNeed(raw.get("reason") or "no covering binding")

    spec_raw = raw.get("spec")
    if not isinstance(spec_raw, dict):
        raise ResolverError("`spec` must be an object in the LLM response")

    param_bindings = _coerce_param_bindings(spec_raw.get("param_bindings") or {})
    constants_raw = spec_raw.get("constants") or {}
    if not isinstance(constants_raw, dict):
        raise ResolverError("`spec.constants` must be an object")
    field_map = _coerce_field_map(spec_raw.get("field_map"))
    result_path = _coerce_result_path(spec_raw.get("result_path"))

    # Build the CallableSpec. The user's pick determines tool_name vs method.
    tool_name = user_picked_endpoint if access_mode in ("cli_mcp", "remote_mcp") else None
    method = user_picked_endpoint if access_mode == "python_lib" else None

    spec = CallableSpec(
        need_id=need.id,
        access_mode=access_mode,
        tool_name=tool_name,
        module=None,
        instance_factory=instance_factory if access_mode == "python_lib" else None,
        method=method,
        param_bindings=param_bindings,
        constants=dict(constants_raw),
        shape=need.shape,
        result_path=result_path,
        field_map=field_map,
    )

    warning = raw.get("warning")
    if warning is not None and not isinstance(warning, str):
        raise ResolverError("`warning` must be a string or null")

    # Validation gate (Phase 6): transforms allowlist + field_map rules.
    try:
        validate_resolved_spec(spec=spec, need=need)
    except ValidationError as exc:
        raise ResolverError(str(exc)) from exc

    return ResolverResult(spec=spec, warning=warning)


__all__ = [
    "ResolverResult",
    "resolve_user_picked_spec",
]
