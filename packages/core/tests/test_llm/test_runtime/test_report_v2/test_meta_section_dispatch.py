"""Tests for the PR 12 meta-section dispatch tier.

The architectural minimum: SectionSpec.dispatch_tier flag, TemplateSpec
.meta_sections property, and `assemble_meta_section_prompt` that injects
the full report markdown into the meta section's prompt. The actual
dispatcher integration (runner's third loop after synthesis completes) is
the v2 wiring — PR 12 delivers the assembler + spec scaffolding it
plugs into.
"""

from __future__ import annotations

from datetime import UTC, datetime

from openlia.llm.runtime.report_v2.manifest.manifest import Manifest
from openlia.llm.runtime.report_v2.sections.prompts import (
    assemble_meta_section_prompt,
)
from openlia.llm.runtime.report_v2.types import Fact
from openlia.reports.frameworks.template_spec import SectionSpec, TemplateSpec


def _empty_manifest() -> Manifest:
    return Manifest(entries=[])


def _fact(name: str) -> Fact:
    return Fact(
        name=name,
        value=1.0,
        source_ids=[0],
        extractor="deterministic",
        data_as_of=datetime.now(UTC),
    )


def test_template_spec_exposes_meta_sections_property() -> None:
    template = TemplateSpec(
        name="t",
        global_preface="",
        body_sections=(SectionSpec(id="body_a", title="A", brief="a"),),
        synthesis_sections=(
            SectionSpec(id="synth_a", title="S", brief="s"),
            SectionSpec(
                id="self_audit",
                title="Self Audit",
                brief="audit",
                dispatch_tier="meta",
            ),
        ),
    )

    meta = template.meta_sections

    assert len(meta) == 1
    assert meta[0].id == "self_audit"


def test_template_spec_meta_sections_empty_when_no_section_opts_in() -> None:
    template = TemplateSpec(
        name="default",
        global_preface="",
        body_sections=(SectionSpec(id="a", title="A", brief="a"),),
        synthesis_sections=(SectionSpec(id="b", title="B", brief="b"),),
    )

    assert template.meta_sections == ()


def test_assemble_meta_section_prompt_includes_full_report_context() -> None:
    prompt = assemble_meta_section_prompt(
        system_role="You are a research analyst.",
        style_guide="Be precise.",
        framework_brief=(
            "You are now a Goldman analyst. Forget what you wrote. "
            "List at least 7 blind spots, attack the strongest pillar, ..."
        ),
        manifest=_empty_manifest(),
        report_markdown=(
            "# Company Overview\nAAPL is a tech company.\n\n"
            "# Valuation\nTrading at 28x forward earnings."
        ),
        facts_slice={"current_price": _fact("current_price")},
        word_target=1500,
    )

    assert "FULL REPORT CONTEXT" in prompt
    assert "AAPL is a tech company" in prompt
    assert "Trading at 28x forward earnings" in prompt
    # Persona reset instructions flow through verbatim from the brief
    assert "Goldman analyst" in prompt
    assert "blind spots" in prompt


def test_assemble_meta_section_prompt_honors_word_target() -> None:
    prompt = assemble_meta_section_prompt(
        system_role="r",
        style_guide="g",
        framework_brief="b",
        manifest=_empty_manifest(),
        report_markdown="",
        facts_slice={},
        word_target=1800,
    )

    assert "Word target: 1800" in prompt
