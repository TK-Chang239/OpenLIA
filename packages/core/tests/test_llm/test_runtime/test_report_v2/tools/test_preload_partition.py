"""Tests for the PR 8c preload-helpers partition story.

The partition rule: per (section, helper), exactly one of
  - eager-fact  (pre-computed into the facts pack, suppressed from manifest)
  - lazy-tool   (callable via tool-use, appears in manifest)
  - absent      (neither)

PR 1 established the build-time invariant on TemplateSpec construction.
PR 8a established `ToolRegistry.available_for` honors the partition.
This file proves they compose end-to-end and locks the contract.
"""

from __future__ import annotations

import pytest
from openlia.llm.runtime.report_v2.tools import ToolRegistry, ToolResult
from openlia.llm.runtime.report_v2.tools.protocol import StaticToolHandler
from openlia.reports.frameworks.template_spec import SectionSpec, TemplateSpec


async def _exec_stub(_args: dict) -> ToolResult:
    return ToolResult(value=0)


def _h(name: str) -> StaticToolHandler:
    return StaticToolHandler(
        name=name,
        summary="x",
        use_when="x",
        complexity="simple",
        input_schema={"type": "object", "properties": {}},
        executor=_exec_stub,
    )


def test_template_construction_rejects_eager_lazy_overlap() -> None:
    bad_section = SectionSpec(
        id="x",
        title="X",
        brief="x",
        eager_helpers=("dcf", "peer_multiple"),
        lazy_helpers=("dcf",),  # overlap
    )
    with pytest.raises(ValueError, match="disjoint"):
        TemplateSpec(
            name="bad",
            global_preface="",
            body_sections=(bad_section,),
            synthesis_sections=(),
        )


def test_registry_suppresses_eager_helpers_and_exposes_lazy_only() -> None:
    registry = ToolRegistry()
    for n in ("dcf", "peer_multiple", "historical_pe_band", "net_cash"):
        registry.register(_h(n))

    template = TemplateSpec(
        name="t",
        global_preface="",
        body_sections=(
            SectionSpec(
                id="valuation",
                title="V",
                brief="v",
                eager_helpers=("peer_multiple",),
                lazy_helpers=("dcf", "historical_pe_band"),
            ),
        ),
        synthesis_sections=(),
    )

    available = {h.name for h in registry.available_for("valuation", template=template)}

    assert "peer_multiple" not in available  # eager → suppressed
    assert "dcf" in available
    assert "historical_pe_band" in available
    assert "net_cash" not in available  # not declared lazy → also suppressed


def test_section_without_lazy_declaration_exposes_all_non_eager() -> None:
    # When `lazy_helpers` is empty, the section gets every registered tool
    # except the ones it declared eager.
    registry = ToolRegistry()
    for n in ("dcf", "peer_multiple", "net_cash"):
        registry.register(_h(n))

    template = TemplateSpec(
        name="t",
        global_preface="",
        body_sections=(
            SectionSpec(
                id="catchall",
                title="C",
                brief="c",
                eager_helpers=("peer_multiple",),
            ),
        ),
        synthesis_sections=(),
    )

    available = {h.name for h in registry.available_for("catchall", template=template)}

    assert available == {"dcf", "net_cash"}
