"""Token-diet for tool schemas.

`slim_tool_schema(tool)` returns a new ToolSchema with verbose JSON-Schema
fields stripped or truncated. Pure function: raises on malformed input.

EXPLICIT NON-GOAL: enum values are never modified. Pathological enums
(50+ values of long strings) must be addressed at the connector boundary,
not here. Truncating enum values would silently break the model's
understanding of valid inputs.
"""

from __future__ import annotations

import re
from typing import Any

from openlia.llm.types import ToolSchema


class SchemaSlimSystemicFailure(Exception):
    """Raised by ToolDispatcher (not this module) when slim fails on too many
    schemas in a single build (>=5 failures AND >20% ratio). Distinct from
    LLMProviderError — this is an inventory/connector hygiene problem, not a
    network or provider issue."""


# Truncation caps
TOOL_DESCRIPTION_MAX_CHARS = 200
PROPERTY_DESCRIPTION_MAX_CHARS = 150
GENERIC_STRING_MAX_CHARS = 500

# Fields to strip unconditionally from any schema node
_STRIP_ALWAYS = frozenset(
    {
        "examples",
        "title",
        "$comment",
        "$id",
        "$schema",
        "enumDescriptions",
        "x-enumNames",
        "readOnly",
        "writeOnly",
        "deprecated",
    }
)

# Fields to strip only at the parameters root level
_STRIP_ROOT_ONLY = frozenset({"description"})

# Fields that hold sub-schemas to recurse into (list-valued)
_RECURSE_LIST_KEYS = frozenset({"oneOf", "anyOf", "allOf"})

_SENTENCE_END = re.compile(r"[.!?]\s")


def _truncate(text: str, max_chars: int) -> str:
    if len(text) <= max_chars:
        return text
    window = text[:max_chars]
    last = None
    for match in _SENTENCE_END.finditer(window):
        last = match
    if last is not None:
        return text[: last.end()].rstrip()
    return text[: max_chars - 1] + "…"


def _slim_schema(schema: Any, *, is_root: bool) -> dict[str, Any]:
    if not isinstance(schema, dict):
        raise ValueError(f"schema must be a dict, got {type(schema).__name__}")

    out: dict[str, Any] = {}

    for key, value in schema.items():
        # Always strip these fields
        if key in _STRIP_ALWAYS:
            continue

        # Strip description only at root level
        if key == "description":
            if is_root:
                continue
            # Per-property: keep but truncate
            if isinstance(value, str):
                out[key] = _truncate(value, PROPERTY_DESCRIPTION_MAX_CHARS)
            elif value is not None:
                out[key] = value
            continue

        # Validate and recurse into properties
        if key == "properties":
            if not isinstance(value, dict):
                raise ValueError(f"'properties' must be a dict, got {type(value).__name__}")
            out[key] = {
                prop_name: _slim_schema(prop_schema, is_root=False)
                for prop_name, prop_schema in value.items()
            }
            continue

        # Validate and recurse into items
        if key == "items":
            if isinstance(value, dict):
                out[key] = _slim_schema(value, is_root=False)
            elif isinstance(value, list):
                # Tuple-items form: list of schemas
                slimmed = []
                for item in value:
                    if not isinstance(item, dict):
                        raise ValueError(
                            f"'items' list elements must be dicts, got {type(item).__name__}"
                        )
                    slimmed.append(_slim_schema(item, is_root=False))
                out[key] = slimmed
            else:
                raise ValueError(
                    f"'items' must be a dict or list of dicts, got {type(value).__name__}"
                )
            continue

        # Recurse into oneOf / anyOf / allOf
        if key in _RECURSE_LIST_KEYS:
            if isinstance(value, list):
                out[key] = [
                    _slim_schema(branch, is_root=False) if isinstance(branch, dict) else branch
                    for branch in value
                ]
            else:
                out[key] = value
            continue

        # Validate enum — keep verbatim but raise on bad shape
        if key == "enum":
            if not isinstance(value, list):
                raise ValueError(f"'enum' must be a list, got {type(value).__name__}")
            out[key] = value
            continue

        # Defensive: truncate any unexpected string fields
        if isinstance(value, str):
            out[key] = _truncate(value, GENERIC_STRING_MAX_CHARS)
            continue

        # Everything else (type, required, additionalProperties, const, default,
        # format, pattern, minimum, maximum, etc.) passes through unchanged.
        out[key] = value

    return out


def slim_tool_schema(tool: ToolSchema) -> ToolSchema:
    """Return a new ToolSchema with verbose fields stripped/truncated.

    Pure function: raises on malformed input. No internal exception handling.
    """
    description = _truncate(tool.description, TOOL_DESCRIPTION_MAX_CHARS)
    parameters = _slim_schema(tool.parameters, is_root=True)
    return ToolSchema(name=tool.name, description=description, parameters=parameters)
