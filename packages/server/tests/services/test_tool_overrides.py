"""Per-template tool overrides — merge author-supplied schema/description
overrides into the auto-derived `cached_tools` so a permissive SDK
signature can still advertise an API-strict requirement (e.g. EODHD's
`financial_news` requires `s` OR `t` even though both are kw-defaults).
"""

from __future__ import annotations

from openlia_server.services.connectors_service import _apply_tool_overrides


def test_apply_overrides_replaces_description_and_schema() -> None:
    tools = [
        {
            "name": "financial_news",
            "description": "Available args: ...",
            "input_schema": {
                "type": "object",
                "properties": {
                    "s": {},
                    "t": {},
                    "from_date": {},
                    "to_date": {},
                    "limit": {},
                    "offset": {},
                },
            },
        }
    ]
    overrides = {
        "financial_news": {
            "description": "Fetch news. Provide either `s` (ticker) or `t` (topic).",
            "input_schema": {
                "type": "object",
                "properties": {"s": {"type": "string"}, "t": {"type": "string"}},
                "anyOf": [{"required": ["s"]}, {"required": ["t"]}],
            },
        }
    }
    out = _apply_tool_overrides(tools, overrides)
    assert len(out) == 1
    fn = out[0]
    assert fn["description"].startswith("Fetch news.")
    assert fn["input_schema"]["anyOf"] == [{"required": ["s"]}, {"required": ["t"]}]


def test_apply_overrides_leaves_unrelated_tools_untouched() -> None:
    tools = [
        {"name": "quote", "description": "x", "input_schema": {"type": "object"}},
        {"name": "financial_news", "description": "y", "input_schema": {}},
    ]
    overrides = {"financial_news": {"description": "z", "input_schema": {"required": ["s"]}}}
    out = _apply_tool_overrides(tools, overrides)
    quote = next(t for t in out if t["name"] == "quote")
    assert quote == {"name": "quote", "description": "x", "input_schema": {"type": "object"}}


def test_apply_overrides_partial_override_only_changes_specified_keys() -> None:
    tools = [{"name": "a", "description": "orig", "input_schema": {"type": "object"}}]
    overrides = {"a": {"description": "new"}}  # no input_schema in override
    out = _apply_tool_overrides(tools, overrides)
    assert out[0]["description"] == "new"
    assert out[0]["input_schema"] == {"type": "object"}


def test_apply_overrides_no_op_when_overrides_empty() -> None:
    tools = [{"name": "a", "description": "x", "input_schema": {}}]
    out = _apply_tool_overrides(tools, {})
    assert out == tools


def test_apply_tool_overrides_preserves_property_enum() -> None:
    """Overrides may declare per-property enums so the Anthropic
    validator can lock the model to a fixed vocabulary (e.g. EODHD
    financial_news topic tags). The shallow merge in
    `_apply_tool_overrides` must carry the `enum` through unchanged."""
    tools = [
        {
            "name": "financial_news",
            "description": "auto",
            "input_schema": {"type": "object", "properties": {"t": {"type": "string"}}},
        }
    ]
    overrides = {
        "financial_news": {
            "input_schema": {
                "type": "object",
                "properties": {
                    "t": {"type": "string", "enum": ["earnings", "ratings"]},
                },
            },
        }
    }
    out = _apply_tool_overrides(tools, overrides)
    assert out[0]["input_schema"]["properties"]["t"]["enum"] == ["earnings", "ratings"]
