from __future__ import annotations

from openlia.llm.runtime.report_v2.sections.synthesis_hooks import (
    SynthesisHook,
    SynthesisHooksBundle,
    extract_hooks_from_section_result,
)
from openlia.llm.runtime.report_v2.types import SectionResult, SectionTerminalState

_SECTION_WITH_HOOKS = '''\
---
section_id: industry_overview
title: Industry Overview
sources_used: [1, 12]
synthesis_hooks:
  thesis_contribution: "Edge platform TAM expanding."
  bull_case_inputs:
    - "Market 28% CAGR [12]"
  bear_case_inputs:
    - "Hyperscalers compressing margins [3]"
---

## Body

Prose here.
'''


def test_extract_hooks_returns_typed_hook() -> None:
    result = SectionResult(
        section_id="industry_overview",
        state=SectionTerminalState.SUCCESS,
        attempts=1,
        markdown=_SECTION_WITH_HOOKS,
    )
    hook = extract_hooks_from_section_result(result)
    assert hook is not None
    assert hook.section_id == "industry_overview"
    assert hook.thesis_contribution.startswith("Edge")
    assert hook.bull_case_inputs == ["Market 28% CAGR [12]"]
    assert hook.bear_case_inputs == ["Hyperscalers compressing margins [3]"]


def test_extract_hooks_missing_returns_none() -> None:
    result = SectionResult(
        section_id="x",
        state=SectionTerminalState.EXHAUSTED,
        attempts=2,
        markdown=None,
    )
    assert extract_hooks_from_section_result(result) is None


def test_bundle_renders_compact_for_synthesis_prompt() -> None:
    hooks = [
        SynthesisHook(
            section_id="industry_overview",
            thesis_contribution="Edge expanding",
            bull_case_inputs=["28% CAGR [12]"],
            bear_case_inputs=["Hyperscaler pressure [3]"],
        ),
        SynthesisHook(
            section_id="financial_analysis",
            thesis_contribution="Revenue growth strong",
            bull_case_inputs=["23% CAGR 3y [1]"],
            bear_case_inputs=[],
        ),
    ]
    bundle = SynthesisHooksBundle(hooks=hooks)
    rendered = bundle.render()
    assert "industry_overview:" in rendered
    assert "Edge expanding" in rendered
    assert "financial_analysis:" in rendered
