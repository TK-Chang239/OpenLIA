"""Phase 0 exit gate smoke test.

Verifies that all v2.2 foundations work end-to-end with canned/stubbed data:
- Registry boots; artifact_types.yaml resolves.
- Helper registry loads all 8 migrated helpers.
- Stage 7a (materialize) produces deterministic markdown.
- Stage 7b prompt builder produces a non-empty well-formed prompt.
- Stage 8 verifier completes without crashing.
- SectionPlan + ReportSectionPlan schema round-trips.
- Stage 5 planner: stubbed call returns valid PlannerOutput.
- Sector routing: tech GICS codes fall back to default template.
- Template defaults: 3-layer merge works end-to-end.

No live LLM calls. All inputs are canned/stubbed.
"""

from __future__ import annotations

import asyncio
import json

from openlia.llm.runtime.report_v2_2.artifact_types import _registry as art_registry
from openlia.llm.runtime.report_v2_2.drafter_prompt import build_drafter_prompt
from openlia.llm.runtime.report_v2_2.enums import Fidelity
from openlia.llm.runtime.report_v2_2.materialize import (
    materialize,
    materialize_section,
    resolve_section_plan,
)
from openlia.llm.runtime.report_v2_2.planner import (
    Planner,
    PlannerOutput,
)
from openlia.llm.runtime.report_v2_2.section_plan import (
    PlannerOverrides,
    ReportSectionPlan,
    SectionArtifactRef,
    SectionPlan,
    SectionPlanOverride,
)
from openlia.llm.runtime.report_v2_2.sector_router import (
    clear_routing_cache,
    route_to_sector_template,
)
from openlia.llm.runtime.report_v2_2.template_defaults import (
    SEED_DEFAULTS,
    load_template_defaults,
)
from openlia.llm.runtime.report_v2_2.tools.library_helpers import list_helpers
from openlia.llm.runtime.report_v2_2.verifier import Verifier

# ---- Canned MSFT fixture data ----

_MSFT_DCF_OUTPUT = {
    "ticker": "MSFT",
    "wacc": 9.8,
    "terminal_growth_rate": 2.5,
    "dcf_equity_value_per_share": 312.0,
    "dcf_range_low": 260.0,
    "dcf_range_high": 365.0,
    "enterprise_value": 2450000.0,
    "equity_value": 2420000.0,
    "fcf_projections": [85000.0, 92000.0, 100000.0, 108000.0, 117000.0],
}

_MSFT_RATIO_OUTPUT = {
    "ticker": "MSFT",
    "pe_forward": 28.5,
    "ev_ebitda": 22.1,
    "price_to_book": 12.3,
    "revenue_growth_yoy": 0.17,
}

_MSFT_PEER_OUTPUT = {
    "ticker": "MSFT",
    "peers": [
        {"ticker": "GOOGL", "pe_forward": 24.0, "ev_ebitda": 18.5},
        {"ticker": "AAPL", "pe_forward": 30.0, "ev_ebitda": 20.0},
    ],
}

_CANNED_ARTIFACTS = {
    "dcf_output": _MSFT_DCF_OUTPUT,
    "ratio_output": _MSFT_RATIO_OUTPUT,
    "peer_output": _MSFT_PEER_OUTPUT,
}

_CANNED_PLAN = ReportSectionPlan(
    template_id="stock_initiation_v2",
    sections=[
        SectionPlan(
            section_id="executive_summary",
            title="Executive Summary",
            artifacts=[
                SectionArtifactRef(artifact_id="dcf_output", fidelity=Fidelity.HEADLINE),
                SectionArtifactRef(artifact_id="ratio_output", fidelity=Fidelity.HEADLINE),
            ],
            drafter_brief="Lead with the buy case. DCF and multiples support upside.",
        ),
        SectionPlan(
            section_id="valuation_dcf",
            title="Discounted Cash Flow Valuation",
            artifacts=[
                SectionArtifactRef(artifact_id="dcf_output", fidelity=Fidelity.FULL),
            ],
        ),
        SectionPlan(
            section_id="relative_valuation",
            title="Relative Valuation",
            artifacts=[
                SectionArtifactRef(artifact_id="ratio_output", fidelity=Fidelity.SUMMARY),
                SectionArtifactRef(artifact_id="peer_output", fidelity=Fidelity.FULL),
            ],
        ),
    ],
)


# ---- Stage 1: Registry boots ----


def test_artifact_registry_boots() -> None:
    types = art_registry.list_all()
    assert len(types) > 0, "ArtifactTypeRegistry loaded no types"


def test_artifact_registry_dag_valid() -> None:
    art_registry.validate_dag()  # should not raise


# ---- Stage 2: Helper registry ----


def test_helper_registry_loads() -> None:
    helpers = list_helpers()
    assert len(helpers) >= 8, f"Expected ≥8 helpers, got {len(helpers)}"


def test_helper_names_include_migrated_helpers() -> None:
    names = {h.schema.directory.name for h in list_helpers()}
    expected = {
        "dcf_valuation",
        "ratio_calculator",
        "chart_builder",
        "saas_metrics",
        "budget_variance",
        "business_investment",
        "forecast_builder",
        "excel_builder",
    }
    missing = expected - names
    assert not missing, f"Missing migrated helpers: {missing}"


# ---- Stage 5: SectionPlan round-trips ----


def test_section_plan_schema_round_trips() -> None:
    dumped = _CANNED_PLAN.model_dump()
    restored = ReportSectionPlan.model_validate(dumped)
    assert restored.template_id == _CANNED_PLAN.template_id
    assert len(restored.sections) == len(_CANNED_PLAN.sections)


# ---- Stage 7a: Materialization is deterministic ----


def test_stage_7a_materialize_deterministic() -> None:
    result1 = materialize(_CANNED_PLAN, _CANNED_ARTIFACTS)
    result2 = materialize(_CANNED_PLAN, _CANNED_ARTIFACTS)
    assert result1.markdown == result2.markdown, "materialize() is not deterministic"


def test_stage_7a_markdown_non_empty() -> None:
    result = materialize(_CANNED_PLAN, _CANNED_ARTIFACTS)
    assert len(result.markdown.strip()) > 100, "Materialized markdown is too short"


def test_stage_7a_all_sections_present() -> None:
    result = materialize(_CANNED_PLAN, _CANNED_ARTIFACTS)
    for section in _CANNED_PLAN.sections:
        assert section.title in result.markdown, f"Section {section.title!r} missing from markdown"


def test_stage_7a_dedup_highest_fidelity() -> None:
    """dcf_output: HEADLINE in exec_summary, FULL in valuation_dcf.
    Canonical render is in exec_summary at FULL; valuation_dcf back-references.
    """
    result = materialize(_CANNED_PLAN, _CANNED_ARTIFACTS)
    # 'dcf_equity_value_per_share' is a FULL field — should appear exactly once.
    assert result.markdown.count("dcf_equity_value_per_share") == 1


def test_stage_7a_no_blocking_materialization_errors() -> None:
    result = materialize(_CANNED_PLAN, _CANNED_ARTIFACTS)
    # No section should have blocking materialization warnings.
    blocking = [
        w
        for section in result.sections
        for w in section.materialization_warnings
        if w.severity == "blocking"
    ]
    assert not blocking, f"Unexpected blocking warnings: {blocking}"


def test_stage_7a_resolve_no_overrides_returns_same() -> None:
    resolved = resolve_section_plan(_CANNED_PLAN, None)
    assert resolved.template_id == _CANNED_PLAN.template_id
    assert len(resolved.sections) == len(_CANNED_PLAN.sections)
    assert resolved.overrides_applied == []


# ---- Stage 7b: Drafter prompt is non-empty and well-formed ----


def test_stage_7b_prompt_non_empty() -> None:
    # Materialize section 0 to get a MaterializedSection for testing.
    exec_section_plan = _CANNED_PLAN.sections[0]
    ms = materialize_section(exec_section_plan, _CANNED_ARTIFACTS)
    prompt = build_drafter_prompt(
        section=ms,
        template_section_meta={"title": exec_section_plan.title},
        thesis="MSFT is undervalued. DCF fair value $312 vs market $290.",
        themes=["Cloud acceleration", "AI monetisation"],
        threading_summaries=[],
    )
    assert len(prompt.strip()) > 200, "Drafter prompt is too short"


def test_stage_7b_prompt_contains_thesis() -> None:
    exec_section_plan = _CANNED_PLAN.sections[0]
    ms = materialize_section(exec_section_plan, _CANNED_ARTIFACTS)
    thesis = "MSFT is undervalued. DCF fair value $312 vs market $290."
    prompt = build_drafter_prompt(
        section=ms,
        template_section_meta={"title": exec_section_plan.title},
        thesis=thesis,
        themes=["Cloud acceleration"],
    )
    assert "MSFT is undervalued" in prompt
    assert "Cloud acceleration" in prompt


def test_stage_7b_prompt_contains_artifacts() -> None:
    exec_section_plan = _CANNED_PLAN.sections[0]
    ms = materialize_section(exec_section_plan, _CANNED_ARTIFACTS)
    prompt = build_drafter_prompt(
        section=ms,
        template_section_meta={"title": exec_section_plan.title},
        thesis="T.",
        themes=[],
    )
    # Rendered artifact content should appear in the prompt.
    assert "dcf_output" in prompt or "wacc" in prompt or "312" in prompt


# ---- Stage 8: Verifier completes ----


def test_stage_8_verifier_completes() -> None:
    exec_section_plan = _CANNED_PLAN.sections[0]
    ms = materialize_section(exec_section_plan, _CANNED_ARTIFACTS)
    draft = (
        "dcf_output shows MSFT DCF fair value at $312 per share, "
        "with WACC of 9.8% and terminal growth of 2.5%. "
        "ratio_output confirms a forward P/E of 28.5x. " + " ".join(["Analysis point."] * 40)
    )
    verifier = Verifier()
    issues = verifier.verify(ms, draft, _CANNED_ARTIFACTS)
    # Verifier must complete without raising.
    assert isinstance(issues, list)


def test_stage_8_verifier_no_blocking_for_well_formed_draft() -> None:
    exec_section_plan = _CANNED_PLAN.sections[0]
    ms = materialize_section(exec_section_plan, _CANNED_ARTIFACTS)
    # Draft references both artifacts and has reasonable word count.
    draft = (
        "dcf_output: MSFT DCF fair value is $312.0. "
        "ratio_output: forward P/E 28.5. " + " ".join(["Analysis."] * 80)
    )
    verifier = Verifier()
    issues = verifier.verify(ms, draft, _CANNED_ARTIFACTS, min_words=50)
    blocking = [i for i in issues if i.severity == "blocking"]
    assert len(blocking) == 0, f"Unexpected blocking issues: {blocking}"


# ---- Full pipeline plumbing ----


def test_full_pipeline_plumbing() -> None:
    """End-to-end: plan → resolve → materialize → prompt → verify for all sections."""
    resolved_plan = resolve_section_plan(_CANNED_PLAN, None)
    report = materialize(resolved_plan, _CANNED_ARTIFACTS)

    assert report.template_id == "stock_initiation_v2"
    assert len(report.sections) == 3
    assert len(report.markdown) > 0

    verifier = Verifier()
    for section in report.sections:
        # Build a minimal but plausible draft.
        art_refs = " ".join(a.artifact_id for a in section.rendered_artifacts)
        draft = f"{art_refs} analysis. " + " ".join(["Prose."] * 30)
        prompt = build_drafter_prompt(
            section=section,
            template_section_meta={"title": section.title},
            thesis="MSFT buy at $312.",
            themes=["Cloud"],
        )
        issues = verifier.verify(section, draft, _CANNED_ARTIFACTS)

        assert isinstance(prompt, str)
        assert len(prompt) > 0
        assert isinstance(issues, list)


# ---- Gate: Sector routing (PR 0.4) ----


def test_exit_gate_msft_tech_gics_falls_back_to_default() -> None:
    """MSFT-like GICS tech code (451020 = IT Services) has no sector module → default."""
    clear_routing_cache()
    result = route_to_sector_template("451020")
    assert result == "stock_initiation_v2"


def test_exit_gate_none_gics_falls_back_to_default() -> None:
    clear_routing_cache()
    result = route_to_sector_template(None)
    assert result == "stock_initiation_v2"


def test_exit_gate_banks_gics_routes_correctly() -> None:
    """Known sector code must not fall back to default."""
    clear_routing_cache()
    result = route_to_sector_template("401010")
    assert result == "banks_v2_2"


# ---- Gate: Stage 5 planner (PR 0.4) ----


class _StubLLMForExitGate:
    """Minimal stub returning a valid PlannerOutput JSON."""

    def __init__(self, response_dict: dict) -> None:
        self._response_dict = response_dict

    async def generate(self, request):
        from openlia.llm.types import LLMResponse

        return LLMResponse(
            text=json.dumps(self._response_dict),
            finish_reason="stop",
            input_tokens=50,
            output_tokens=100,
        )


_STUB_PLANNER_RESPONSE = {
    "helper_selection": [
        {
            "section_id": "executive_summary",
            "helpers": [
                {
                    "helper_name": "dcf_valuation",
                    "params": {},
                    "artifact_id": "dcf_output",
                }
            ],
        }
    ],
    "planner_overrides": [],
    "open_questions": [],
    "cross_section_themes": ["Cloud growth", "AI monetisation"],
}


def test_exit_gate_planner_stubbed_returns_valid_output() -> None:
    """Stubbed Stage 5 LLM call produces a valid PlannerOutput."""
    stub = _StubLLMForExitGate(_STUB_PLANNER_RESPONSE)
    planner = Planner(
        llm=stub,  # type: ignore[arg-type]
        ticker="MSFT",
        template_sections=[
            {
                "section_id": "executive_summary",
                "title": "Executive Summary",
                "default_artifacts": [{"artifact_id": "dcf_output", "fidelity": "headline"}],
            }
        ],
        template_id="stock_initiation_v2",
    )
    output = asyncio.run(planner.aplan())
    assert isinstance(output, PlannerOutput)
    assert len(output.helper_selection) == 1
    assert output.helper_selection[0].section_id == "executive_summary"
    assert output.cross_section_themes == ["Cloud growth", "AI monetisation"]


# ---- Gate: Template defaults 3-layer merge (PR 0.4) ----


def test_exit_gate_template_defaults_three_layer_merge() -> None:
    """Resolved SectionPlan reflects 3-layer merge: template default → planner override."""
    # Layer 2: template defaults (SEED_DEFAULTS has valuation_comps with SUMMARY for
    # historical_multiple_trends).
    # Layer 3: planner override upgrades it to FULL.
    overrides = PlannerOverrides(
        template_id="stock_initiation_v2",
        overrides=[
            SectionPlanOverride(
                section_id="valuation_comps",
                operation="change_fidelity",
                artifact_id="historical_multiple_trends",
                fidelity=Fidelity.FULL,
            )
        ],
        rationale="User wants full peer trend detail.",
    )
    resolved = resolve_section_plan(SEED_DEFAULTS, overrides)

    comps = next(s for s in resolved.sections if s.section_id == "valuation_comps")
    hist = next(a for a in comps.artifacts if a.artifact_id == "historical_multiple_trends")
    # Layer 3 wins.
    assert hist.fidelity == Fidelity.FULL
    # Non-overridden artifact still at template default (FULL from SEED_DEFAULTS).
    dcf = next(s for s in resolved.sections if s.section_id == "valuation_dcf")
    dcf_art = next(a for a in dcf.artifacts if a.artifact_id == "dcf_base_valuation")
    assert dcf_art.fidelity == Fidelity.FULL
    # Audit trail populated.
    assert len(resolved.overrides_applied) == 1


def test_exit_gate_load_template_defaults_fallback() -> None:
    """load_template_defaults falls back to SEED_DEFAULTS for stock_initiation_v2."""
    defaults = load_template_defaults("stock_initiation_v2")
    assert defaults.template_id == "stock_initiation_v2"
    assert len(defaults.sections) >= 4
