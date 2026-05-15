"""Tests for slim_tool_schema — vertical TDD slices.

Each test targets one spec requirement; they are numbered to mirror the
implementation spec (PR2.1).
"""

from __future__ import annotations

import json

import pytest
from openlia.llm.runtime.report import _submit_report_tool
from openlia.llm.runtime.schema_slim import (
    PROPERTY_DESCRIPTION_MAX_CHARS,
    TOOL_DESCRIPTION_MAX_CHARS,
    slim_tool_schema,
)
from openlia.llm.runtime.tools import (
    _REQUEST_ADDITIONAL_TOOLS_SCHEMA,
    _WEB_SEARCH_SCHEMA,
    LOAD_SKILL_SCHEMA,
)
from openlia.llm.types import ToolSchema

# ---------------------------------------------------------------------------
# 1. Empty schema passthrough
# ---------------------------------------------------------------------------


def test_empty_schema_passthrough() -> None:
    tool = ToolSchema(name="t", description="", parameters={})
    result = slim_tool_schema(tool)
    assert result.name == "t"
    assert result.description == ""
    assert result.parameters == {}


# ---------------------------------------------------------------------------
# 2. Tool description truncation — sentence-boundary aware
# ---------------------------------------------------------------------------


def test_tool_description_truncation_sentence_boundary() -> None:
    # Build a description that has a sentence boundary inside the 200-char window.
    # First sentence ends at position < 200. Second sentence pushes total > 200.
    first_sentence = "A" * 90 + ". "  # 92 chars, ends with ". "
    # Remaining chars to push total > 200
    rest = "B" * 120
    long_desc = first_sentence + rest  # 212 chars total
    assert len(long_desc) > TOOL_DESCRIPTION_MAX_CHARS

    tool = ToolSchema(name="t", description=long_desc, parameters={})
    result = slim_tool_schema(tool)

    assert len(result.description) <= TOOL_DESCRIPTION_MAX_CHARS
    # Should end with the sentence-ending punctuation (period), stripped of trailing space
    assert result.description.endswith(".")
    assert "A" * 90 in result.description


# ---------------------------------------------------------------------------
# 3. Tool description hard truncate — no sentence boundary
# ---------------------------------------------------------------------------


def test_tool_description_hard_truncate_no_boundary() -> None:
    # 300 chars with no . / ! / ? anywhere
    long_desc = "X" * 300
    tool = ToolSchema(name="t", description=long_desc, parameters={})
    result = slim_tool_schema(tool)

    # Hard truncate: 199 chars + ellipsis char
    assert result.description == "X" * 199 + "…"
    assert len(result.description) == 200


# ---------------------------------------------------------------------------
# 4. Strip `examples`, `title`, `$comment` from parameters root
# ---------------------------------------------------------------------------


def test_strip_noise_fields_from_parameters_root() -> None:
    tool = ToolSchema(
        name="t",
        description="desc",
        parameters={
            "type": "object",
            "title": "My Tool",
            "$comment": "internal note",
            "examples": [{"x": 1}],
            "properties": {"q": {"type": "string"}},
        },
    )
    result = slim_tool_schema(tool)
    assert "title" not in result.parameters
    assert "$comment" not in result.parameters
    assert "examples" not in result.parameters
    assert result.parameters["type"] == "object"
    assert "properties" in result.parameters


# ---------------------------------------------------------------------------
# 5. Strip per-property verbose docs
# ---------------------------------------------------------------------------


def test_strip_per_property_verbose_docs() -> None:
    tool = ToolSchema(
        name="t",
        description="desc",
        parameters={
            "type": "object",
            "properties": {
                "q": {
                    "type": "string",
                    "description": "A short description.",
                    "examples": ["foo", "bar"],
                    "title": "Query",
                    "$comment": "internal",
                    "readOnly": True,
                    "writeOnly": False,
                    "deprecated": True,
                }
            },
        },
    )
    result = slim_tool_schema(tool)
    prop = result.parameters["properties"]["q"]
    assert "examples" not in prop
    assert "title" not in prop
    assert "$comment" not in prop
    assert "readOnly" not in prop
    assert "writeOnly" not in prop
    assert "deprecated" not in prop
    # description is kept (it's a property-level description)
    assert prop["description"] == "A short description."
    assert prop["type"] == "string"


# ---------------------------------------------------------------------------
# 6. Keep enum verbatim — 50-value enum unchanged
# ---------------------------------------------------------------------------


def test_keep_enum_verbatim() -> None:
    big_enum = [f"value_{i:03d}_with_some_extra_text" for i in range(50)]
    tool = ToolSchema(
        name="t",
        description="desc",
        parameters={
            "type": "object",
            "properties": {
                "country": {
                    "type": "string",
                    "enum": big_enum,
                }
            },
        },
    )
    result = slim_tool_schema(tool)
    assert result.parameters["properties"]["country"]["enum"] == big_enum


# ---------------------------------------------------------------------------
# 7. Strip `enumDescriptions` and `x-enumNames` but keep `enum`
# ---------------------------------------------------------------------------


def test_strip_enum_docs_but_keep_enum() -> None:
    enum_vals = ["a", "b", "c"]
    tool = ToolSchema(
        name="t",
        description="desc",
        parameters={
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": enum_vals,
                    "enumDescriptions": ["First", "Second", "Third"],
                    "x-enumNames": ["Alpha", "Bravo", "Charlie"],
                }
            },
        },
    )
    result = slim_tool_schema(tool)
    prop = result.parameters["properties"]["mode"]
    assert prop["enum"] == enum_vals
    assert "enumDescriptions" not in prop
    assert "x-enumNames" not in prop


# ---------------------------------------------------------------------------
# 8. Per-property description truncation — sentence-boundary aware
# ---------------------------------------------------------------------------


def test_per_property_description_truncation() -> None:
    # Build a 200-char property description with a sentence boundary inside 150-char window
    first = "P" * 60 + ". "  # 62 chars
    rest = "Q" * 150  # pushes total well past 150
    long_prop_desc = first + rest
    assert len(long_prop_desc) > PROPERTY_DESCRIPTION_MAX_CHARS

    tool = ToolSchema(
        name="t",
        description="desc",
        parameters={
            "type": "object",
            "properties": {
                "x": {
                    "type": "string",
                    "description": long_prop_desc,
                }
            },
        },
    )
    result = slim_tool_schema(tool)
    prop_desc = result.parameters["properties"]["x"]["description"]
    assert len(prop_desc) <= PROPERTY_DESCRIPTION_MAX_CHARS
    assert prop_desc.endswith(".")


# ---------------------------------------------------------------------------
# 9. Recurse into properties — nested property stripped
# ---------------------------------------------------------------------------


def test_recurse_into_properties_nested() -> None:
    tool = ToolSchema(
        name="t",
        description="desc",
        parameters={
            "type": "object",
            "properties": {
                "outer": {
                    "type": "object",
                    "properties": {
                        "inner": {
                            "type": "string",
                            "examples": ["hello"],
                            "title": "Inner Field",
                        }
                    },
                }
            },
        },
    )
    result = slim_tool_schema(tool)
    inner = result.parameters["properties"]["outer"]["properties"]["inner"]
    assert "examples" not in inner
    assert "title" not in inner
    assert inner["type"] == "string"


# ---------------------------------------------------------------------------
# 10. Recurse into items
# ---------------------------------------------------------------------------


def test_recurse_into_items() -> None:
    long_desc = "D" * 200  # well over 150 chars, no sentence boundary
    tool = ToolSchema(
        name="t",
        description="desc",
        parameters={
            "type": "object",
            "properties": {
                "tags": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "description": long_desc,
                        "examples": ["tag1", "tag2"],
                    },
                }
            },
        },
    )
    result = slim_tool_schema(tool)
    items = result.parameters["properties"]["tags"]["items"]
    assert "examples" not in items
    assert items["type"] == "string"
    # description truncated (hard cap since no sentence boundary)
    assert len(items["description"]) <= PROPERTY_DESCRIPTION_MAX_CHARS
    assert items["description"].endswith("…")


# ---------------------------------------------------------------------------
# 11. Recurse into oneOf / anyOf / allOf
# ---------------------------------------------------------------------------


def test_recurse_into_oneof_anyof_allof() -> None:
    noisy_branch = {
        "type": "string",
        "examples": ["x"],
        "title": "A branch",
        "description": "Some description.",
    }
    tool = ToolSchema(
        name="t",
        description="desc",
        parameters={
            "type": "object",
            "properties": {
                "value": {
                    "oneOf": [
                        dict(noisy_branch),
                        {"type": "integer", "examples": [1, 2], "title": "Int branch"},
                    ],
                    "anyOf": [dict(noisy_branch)],
                    "allOf": [dict(noisy_branch)],
                }
            },
        },
    )
    result = slim_tool_schema(tool)
    value_prop = result.parameters["properties"]["value"]

    for combiner in ("oneOf", "anyOf", "allOf"):
        for branch in value_prop[combiner]:
            assert "examples" not in branch, f"{combiner} branch still has examples"
            assert "title" not in branch, f"{combiner} branch still has title"


# ---------------------------------------------------------------------------
# 12. Keep numeric constraints and metadata fields
# ---------------------------------------------------------------------------


def test_keep_numeric_constraints_and_metadata() -> None:
    tool = ToolSchema(
        name="t",
        description="desc",
        parameters={
            "type": "object",
            "properties": {
                "score": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 100,
                    "exclusiveMinimum": -1,
                    "exclusiveMaximum": 101,
                    "multipleOf": 0.5,
                },
                "label": {
                    "type": "string",
                    "minLength": 1,
                    "maxLength": 50,
                    "pattern": "^[a-z]+$",
                    "format": "email",
                    "const": "fixed",
                    "default": "hello",
                },
            },
        },
    )
    result = slim_tool_schema(tool)
    score = result.parameters["properties"]["score"]
    assert score["minimum"] == 0
    assert score["maximum"] == 100
    assert score["exclusiveMinimum"] == -1
    assert score["exclusiveMaximum"] == 101
    assert score["multipleOf"] == 0.5

    label = result.parameters["properties"]["label"]
    assert label["minLength"] == 1
    assert label["maxLength"] == 50
    assert label["pattern"] == "^[a-z]+$"
    assert label["format"] == "email"
    assert label["const"] == "fixed"
    assert label["default"] == "hello"


# ---------------------------------------------------------------------------
# 13. Keep `required` and `additionalProperties`
# ---------------------------------------------------------------------------


def test_keep_required_and_additional_properties() -> None:
    tool = ToolSchema(
        name="t",
        description="desc",
        parameters={
            "type": "object",
            "properties": {
                "a": {"type": "string"},
                "b": {
                    "type": "object",
                    "properties": {"c": {"type": "integer"}},
                    "required": ["c"],
                    "additionalProperties": False,
                },
            },
            "required": ["a", "b"],
            "additionalProperties": False,
        },
    )
    result = slim_tool_schema(tool)
    assert result.parameters["required"] == ["a", "b"]
    assert result.parameters["additionalProperties"] is False
    nested = result.parameters["properties"]["b"]
    assert nested["required"] == ["c"]
    assert nested["additionalProperties"] is False


# ---------------------------------------------------------------------------
# 14. `parameters.description` at root stripped; property-level description kept
# ---------------------------------------------------------------------------


def test_root_description_stripped_property_description_kept() -> None:
    tool = ToolSchema(
        name="t",
        description="top-level tool description",
        parameters={
            "type": "object",
            "description": "This root description should be stripped.",
            "properties": {
                "q": {
                    "type": "string",
                    "description": "Per-property description kept.",
                }
            },
        },
    )
    result = slim_tool_schema(tool)
    assert "description" not in result.parameters
    assert result.parameters["properties"]["q"]["description"] == "Per-property description kept."


# ---------------------------------------------------------------------------
# 15. Idempotent: slim(slim(x)) == slim(x)
# ---------------------------------------------------------------------------


def test_idempotent() -> None:
    tool = ToolSchema(
        name="complex",
        description="A" * 250 + ". More text here.",
        parameters={
            "type": "object",
            "title": "Complex Schema",
            "$comment": "internal",
            "description": "Root-level description to strip.",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": ["a", "b", "c"],
                    "enumDescriptions": ["First", "Second", "Third"],
                    "examples": ["a"],
                    "description": "P" * 200 + ". Longer text.",
                },
                "count": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                    "title": "Count",
                    "readOnly": True,
                },
            },
            "required": ["mode"],
        },
    )
    slimmed_once = slim_tool_schema(tool)
    slimmed_twice = slim_tool_schema(slimmed_once)
    assert slimmed_once == slimmed_twice


# ---------------------------------------------------------------------------
# 16. Reduction ratio assertion on a fat fixture
# ---------------------------------------------------------------------------


def _build_fat_schema() -> ToolSchema:
    """Fat fixture: long descriptions, examples everywhere, enumDescriptions, nested."""
    props: dict = {}
    for i in range(10):
        props[f"field_{i}"] = {
            "type": "string",
            "description": "This is a very verbose property description that goes on and on. "
            "It has multiple sentences. Each sentence adds tokens. More tokens. Even more.",
            "examples": [f"example_{j}" for j in range(10)],
            "title": f"Field {i}",
            "$comment": f"Comment for field {i}",
            "readOnly": False,
            "deprecated": False,
        }
    props["status"] = {
        "type": "string",
        "enum": ["active", "inactive", "pending"],
        "enumDescriptions": [
            "The resource is active and ready.",
            "The resource is inactive.",
            "The resource is pending activation.",
        ],
        "x-enumNames": ["Active", "Inactive", "Pending"],
        "title": "Status field",
        "examples": ["active"],
    }
    props["nested"] = {
        "type": "object",
        "title": "Nested object",
        "$comment": "nested comment",
        "properties": {
            "deep": {
                "type": "array",
                "title": "Deep array",
                "items": {
                    "type": "string",
                    "examples": ["x", "y", "z"],
                    "title": "Array item",
                    "description": "A long item description. With multiple sentences. "
                    "Even more text here to ensure it is verbose.",
                },
            }
        },
    }

    long_tool_desc = (
        "This tool does something very important. "
        "It fetches data from multiple sources. "
        "Then it aggregates and normalizes. "
        "Finally it returns a rich payload. "
        "All of this is done asynchronously. "
        "Performance is excellent. More details follow."
    )

    return ToolSchema(
        name="fat_tool",
        description=long_tool_desc,
        parameters={
            "type": "object",
            "title": "Fat Tool Parameters",
            "$schema": "http://json-schema.org/draft-07/schema#",
            "$comment": "This schema is very verbose.",
            "description": "Root description that gets stripped.",
            "examples": [{"field_0": "val"}],
            "properties": props,
            "required": [f"field_{i}" for i in range(5)],
            "additionalProperties": False,
        },
    )


def _schema_json_size(tool: ToolSchema) -> int:
    return len(
        json.dumps(
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
            }
        )
    )


def test_reduction_ratio() -> None:
    fat = _build_fat_schema()
    slimmed = slim_tool_schema(fat)
    fat_size = _schema_json_size(fat)
    slim_size = _schema_json_size(slimmed)
    assert slim_size <= 0.5 * fat_size, (
        f"Expected slim size <= 50% of fat; got {slim_size} vs {fat_size} "
        f"({100 * slim_size / fat_size:.1f}%)"
    )


# ---------------------------------------------------------------------------
# 17. Malformed: parameters not a dict
# ---------------------------------------------------------------------------


def test_malformed_parameters_not_a_dict() -> None:
    tool = ToolSchema(name="t", description="d", parameters=["not", "a", "dict"])  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="must be a dict"):
        slim_tool_schema(tool)


# ---------------------------------------------------------------------------
# 18. Malformed: enum not a list
# ---------------------------------------------------------------------------


def test_malformed_enum_not_a_list() -> None:
    tool = ToolSchema(
        name="t",
        description="d",
        parameters={
            "type": "object",
            "properties": {
                "x": {
                    "type": "string",
                    "enum": "should_be_a_list",  # malformed
                }
            },
        },
    )
    with pytest.raises(ValueError, match="'enum' must be a list"):
        slim_tool_schema(tool)


# ---------------------------------------------------------------------------
# 19. Golden no-op tests on builtins
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "builtin",
    [
        pytest.param(_REQUEST_ADDITIONAL_TOOLS_SCHEMA, id="request_additional_tools"),
        pytest.param(_WEB_SEARCH_SCHEMA, id="web_search"),
        pytest.param(LOAD_SKILL_SCHEMA, id="load_skill"),
    ],
)
def test_golden_noop_builtins(builtin: ToolSchema) -> None:
    """Hand-crafted builtins are terse — slim must be a no-op on them.

    If this test fails after a builtin is modified, the author must either
    tighten the prose at source or accept the slim result (meaning the
    builtin had become fat).
    """
    slimmed = slim_tool_schema(builtin)
    before_json = json.dumps(
        {"description": builtin.description, "parameters": builtin.parameters}, indent=2
    )
    after_json = json.dumps(
        {"description": slimmed.description, "parameters": slimmed.parameters}, indent=2
    )
    assert slimmed == builtin, (
        f"slim_tool_schema({builtin.name!r}) changed the schema — "
        f"either the builtin grew fat or slim has a bug.\n"
        f"Before: {before_json}\n"
        f"After:  {after_json}"
    )


def test_golden_noop_submit_report() -> None:
    """submit_report is Pydantic-generated so slim always strips `title` fields.

    We verify idempotency (slim(slim(x)) == slim(x)) rather than no-op equality,
    since the machine-generated schema legitimately contains `title` annotations
    that slim correctly removes — making true no-op equality unreachable here.
    """
    builtin = _submit_report_tool()
    slimmed_once = slim_tool_schema(builtin)
    slimmed_twice = slim_tool_schema(slimmed_once)
    assert slimmed_once == slimmed_twice, (
        "slim_tool_schema(submit_report) is not idempotent — slim has a bug."
    )
    # Description must be ≤200 chars at source so slim doesn't truncate it.
    assert len(builtin.description) <= 200, (
        f"submit_report description ({len(builtin.description)} chars) exceeds 200 — "
        "tighten _SUBMIT_REPORT_DESCRIPTION at source."
    )
