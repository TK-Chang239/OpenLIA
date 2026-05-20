"""Tests for the PR 8a ToolHandler protocol, registry, and manifest rendering."""

from __future__ import annotations

import pytest
from openlia.llm.runtime.report_v2.tools import (
    ToolRegistry,
    ToolResult,
    render_manifest,
)
from openlia.llm.runtime.report_v2.tools.protocol import StaticToolHandler


async def _exec_one(args: dict) -> ToolResult:
    return ToolResult(value=args.get("x", 0) * 2, citations=[])


def _make_handler(name: str = "double_it", complexity: str = "simple") -> StaticToolHandler:
    return StaticToolHandler(
        name=name,
        summary="double the input",
        use_when="when a value needs doubling",
        complexity=complexity,  # type: ignore[arg-type]
        input_schema={"type": "object", "properties": {"x": {"type": "number"}}},
        executor=_exec_one,
        doc_path="docs/helpers/double_it.md" if complexity == "complex" else None,
    )


def test_tool_result_carries_citations() -> None:
    result = ToolResult(value=42, citations=[{"source": "test", "url": "https://x"}])

    assert result.value == 42
    assert result.citations == [{"source": "test", "url": "https://x"}]


def test_registry_register_and_get() -> None:
    registry = ToolRegistry()
    handler = _make_handler()
    registry.register(handler)

    assert registry.get("double_it") is handler


def test_registry_rejects_duplicate_registration() -> None:
    registry = ToolRegistry()
    registry.register(_make_handler())

    with pytest.raises(ValueError, match="already registered"):
        registry.register(_make_handler())


def test_registry_available_for_returns_all_when_no_template() -> None:
    registry = ToolRegistry()
    registry.register(_make_handler())

    tools = registry.available_for("any_section", template=None)

    assert len(tools) == 1


def test_registry_available_for_respects_section_eager_helpers() -> None:
    from openlia.reports.frameworks.template_spec import SectionSpec, TemplateSpec

    registry = ToolRegistry()
    registry.register(_make_handler("simple_one"))
    registry.register(_make_handler("complex_one", complexity="complex"))

    template = TemplateSpec(
        name="t",
        global_preface="",
        body_sections=(
            SectionSpec(
                id="s1",
                title="S1",
                brief="b",
                eager_helpers=("simple_one",),
            ),
        ),
        synthesis_sections=(),
    )

    tools = registry.available_for("s1", template=template)
    names = {h.name for h in tools}

    assert "simple_one" not in names  # suppressed because eager
    assert "complex_one" in names


def test_manifest_renders_simple_helpers_with_signature() -> None:
    text = render_manifest([_make_handler()])

    assert "double_it(x)" in text
    assert "Use when: when a value needs doubling" in text
    assert "get_helper_docs" not in text


def test_manifest_renders_complex_helpers_with_inspect_pointer() -> None:
    text = render_manifest([_make_handler("dcf", complexity="complex")])

    assert "dcf(...)" in text
    assert "get_helper_docs" in text


def test_manifest_renders_empty_string_for_no_handlers() -> None:
    assert render_manifest([]) == ""
