"""Tests for the PR 8b meta-tool + typed round telemetry + cap-hit state."""

from __future__ import annotations

from pathlib import Path

import pytest
from openlia.llm.runtime.report_v2.tools import (
    ToolRegistry,
    ToolResult,
    ToolRoundEvent,
    make_get_helper_docs,
)
from openlia.llm.runtime.report_v2.tools.protocol import StaticToolHandler
from openlia.llm.runtime.report_v2.types import SectionTerminalState


async def _exec_stub(_args: dict) -> ToolResult:
    return ToolResult(value=0)


def _handler(name: str, complexity: str, doc_path: str | None) -> StaticToolHandler:
    return StaticToolHandler(
        name=name,
        summary="x",
        use_when="x",
        complexity=complexity,  # type: ignore[arg-type]
        input_schema={"type": "object", "properties": {}},
        executor=_exec_stub,
        doc_path=doc_path,
    )


def test_get_helper_docs_returns_markdown_content(tmp_path: Path) -> None:
    doc = tmp_path / "dcf.md"
    doc.write_text("# DCF worked example\n\nWACC bounded [5,20%].")
    registry = ToolRegistry()
    registry.register(_handler("dcf", complexity="complex", doc_path=str(doc)))
    get_helper_docs = make_get_helper_docs(registry)

    out = get_helper_docs("dcf")

    assert "WACC bounded" in out


def test_get_helper_docs_raises_when_handler_is_simple() -> None:
    registry = ToolRegistry()
    registry.register(_handler("net_cash", complexity="simple", doc_path=None))
    get_helper_docs = make_get_helper_docs(registry)

    with pytest.raises(FileNotFoundError, match="simple"):
        get_helper_docs("net_cash")


def test_get_helper_docs_raises_when_doc_file_missing() -> None:
    registry = ToolRegistry()
    registry.register(_handler("dcf", complexity="complex", doc_path="/does/not/exist.md"))
    get_helper_docs = make_get_helper_docs(registry)

    with pytest.raises(FileNotFoundError, match="not found"):
        get_helper_docs("dcf")


def test_tool_round_event_carries_typed_fields() -> None:
    event = ToolRoundEvent(
        section_id="valuation_analysis",
        attempt=1,
        round_index=2,
        round_type="inspect",
        tool_name="dcf",
        args_validated=True,
        result_null=False,
        elapsed_ms=420,
        dispatch_tier="body",
    )

    assert event.round_type == "inspect"
    assert event.dispatch_tier == "body"


def test_section_terminal_state_includes_degraded_cap_hit() -> None:
    assert SectionTerminalState.DEGRADED_CAP_HIT.value == "degraded_cap_hit"
