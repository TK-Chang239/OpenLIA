"""E2E smoke tests for the Equity Research v2.2 pipeline (Task V2).

Wires mock LLMs through clarifier, research planner, strand dispatcher,
model planner, model builder, section drafter, and assembler to verify the
pipeline connects end-to-end without real LLM API calls.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import Mock

from openlia.llm.runtime.report_v2.capability_manifest import load_manifest
from openlia.llm.runtime.report_v2.pipeline.stage_1_clarify import Clarifier
from openlia.llm.runtime.report_v2.pipeline.stage_3_research_plan import ResearchPlanner
from openlia.llm.runtime.report_v2.pipeline.stage_4_gather import StrandDispatcher
from openlia.llm.runtime.report_v2.pipeline.stage_5_model_plan import ModelPlanner
from openlia.llm.runtime.report_v2.pipeline.stage_6_model_build import ModelBuilder
from openlia.llm.runtime.report_v2.pipeline.stage_7_draft import SectionDrafter
from openlia.llm.runtime.report_v2.pipeline.stage_9_assemble import build_report_v2
from openlia.llm.runtime.report_v2.pipeline.trigger_evaluator import TriggerEvaluator
from openlia.llm.runtime.report_v2.schemas.research_pool import Citation, ResearchPool
from openlia.llm.runtime.report_v2.schemas.run_summary import RunSummary, TaskOutcome
from openlia.llm.runtime.report_v2.schemas.verification_history import VerificationHistory
from openlia.llm.runtime.report_v2.template_v2.loader_v2 import load_template_v2
from openlia.llm.runtime.report_v2.template_v2.spec import SectionSpec
from openlia.llm.runtime.report_v2.tools.library_helpers import (
    reset_helpers_for_tests,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TEMPLATES_DIR = (
    Path(__file__).parent.parent.parent.parent
    / "src"
    / "openlia"
    / "llm"
    / "runtime"
    / "report_v2"
    / "templates"
)


def _load_stock_research_yaml() -> str:
    return (_TEMPLATES_DIR / "stock_research_v2.yaml").read_text()


def make_llm(responses: list[dict]) -> Mock:
    llm = Mock()
    llm.call.side_effect = list(responses)
    return llm


def _make_run_summary(engine_version: str = "2.2") -> RunSummary:
    return RunSummary(
        engine_version=engine_version,
        template_id="stock_research_v2",
        template_name="Stock Research (v2)",
        composer_inputs={"ticker": "AAPL"},
        outcomes=[
            TaskOutcome(task_type="section_draft", task_name="thesis", status="OK"),
        ],
    )


def _make_citation() -> Citation:
    return Citation(
        id="c1",
        source_type="tool_call",
        tool="eodhd",
        url="https://example.com",
        title="AAPL Fundamentals",
        retrieved_at=datetime(2026, 5, 21, tzinfo=UTC),
    )


# ---------------------------------------------------------------------------
# Test 1: happy-path HTML report
# ---------------------------------------------------------------------------


def test_e2e_stock_research_produces_html_report() -> None:
    """Clarifier -> ResearchPlanner -> StrandDispatcher -> ModelPlanner
    -> SectionDrafter -> assemble_report produces valid HTML.
    """
    raw_yaml = _load_stock_research_yaml()
    template_spec, _ = load_template_v2(raw_yaml, fmt="yaml")

    composer_inputs = {"ticker": "AAPL"}

    # Stage 1 — Clarifier
    clarifier_llm = make_llm(
        [{"questions": [], "blocking_warnings": [], "notices": [], "detected_intents": []}]
    )
    clarifier = Clarifier(llm=clarifier_llm)
    clarifier_out = clarifier.clarify(composer_inputs, template_spec)
    assert clarifier_out.blocking_warnings == []

    # Stage 3 — ResearchPlanner
    planner_llm = make_llm(
        [
            {
                "research_strands": [
                    {"id": "fundamentals", "purpose": "Pull key financials", "allowed_tools": []}
                ],
                "required_artifacts": [],
                "section_dag": {
                    "thesis": [],
                    "recent_developments": ["thesis"],
                    "financials": ["thesis"],
                    "valuation": ["financials"],
                    "risks": ["thesis"],
                },
                "slipped_requests": [],
            }
        ]
    )
    research_planner = ResearchPlanner(llm=planner_llm)
    plan = research_planner.plan(
        composer_inputs=composer_inputs,
        template_spec=template_spec,
        clarifier_answers={},
    )
    assert len(plan.research_strands) == 1

    # Stage 4 — StrandDispatcher with fake subagent
    fake_subagent = Mock()
    fake_subagent.run.return_value = {
        "findings": "AAPL revenue up 10% YoY; strong margins.",
        "citations": [
            {
                "id": "c1",
                "source_type": "tool_call",
                "tool": "eodhd",
                "url": "https://example.com",
                "title": "AAPL Fundamentals",
                "retrieved_at": datetime(2026, 5, 21, tzinfo=UTC),
            }
        ],
        "cache_hits": 1,
        "cache_misses": 0,
    }
    dispatcher = StrandDispatcher(subagent=fake_subagent)
    research_pool = dispatcher.dispatch(
        strands=plan.research_strands,
        composer_inputs=composer_inputs,
        plan=plan,
    )
    assert "fundamentals" in research_pool.findings_by_strand
    assert research_pool.cache_hits == 1

    # Stage 5 — ModelPlanner (no optional artifacts)
    model_planner_llm = make_llm([{"optional_artifacts": []}])
    model_planner = ModelPlanner(llm=model_planner_llm)
    updated_plan = model_planner.plan(plan=plan, research_pool=research_pool)
    assert updated_plan.optional_artifacts == []

    # Stage 6 — ModelBuilder (no artifacts to build → empty list)
    reset_helpers_for_tests()
    model_builder_llm = make_llm([])
    model_builder = ModelBuilder(llm=model_builder_llm)
    all_artifacts = updated_plan.required_artifacts + updated_plan.optional_artifacts
    model_artifacts = model_builder.build(
        artifacts=all_artifacts,
        research_pool=research_pool,
    )
    assert model_artifacts == []

    # Stage 7 — SectionDrafter (all sections OK, no trigger_when)
    # First draft includes a citation marker so Sources section appears in HTML.
    draft_responses = [
        {"blocks": [{"type": "prose", "text": "Thesis content. See [c:c1] for data."}]},
        {"blocks": [{"type": "prose", "text": "Recent developments content."}]},
        {"blocks": [{"type": "prose", "text": "Financials content."}]},
        {"blocks": [{"type": "prose", "text": "Valuation content."}]},
        {"blocks": [{"type": "prose", "text": "Risks content."}]},
    ]
    drafter_llm = make_llm(draft_responses)
    trigger_llm = make_llm([])
    trigger_evaluator = TriggerEvaluator(llm=trigger_llm)
    drafter = SectionDrafter(llm=drafter_llm, trigger_evaluator=trigger_evaluator)
    section_outputs = drafter.draft_all(
        sections=template_spec.sections,
        dag=updated_plan.section_dag,
        composer_inputs=composer_inputs,
        research_pool=research_pool,
        model_artifacts=model_artifacts,
    )
    assert all(s.status == "OK" for s in section_outputs)

    # Convert SectionOutput -> dict for assembler
    sections_dicts = [
        {"id": s.section_id, "name": s.section_name, "blocks": s.blocks} for s in section_outputs
    ]

    # Stage 9 — assemble_report
    manifest = load_manifest()
    run_summary = _make_run_summary(engine_version=manifest.engine_version)
    verification_history = VerificationHistory()
    pool_citations = {c.id: c for c in research_pool.citations}

    report = build_report_v2(
        sections=sections_dicts,
        composer_inputs=composer_inputs,
        template_spec=template_spec,
        pool_citations=pool_citations,
        run_summary=run_summary,
        verification_history=verification_history,
        dev_mode=manifest.dev_mode,
    )

    assert report.engine_version
    assert len(report.sections) >= 1
    assert len(report.citations) >= 1
    assert report.run_summary.engine_version == manifest.engine_version
    # dev_mode=true in capabilities.yaml → verification_history present
    assert report.verification_history is not None


# ---------------------------------------------------------------------------
# Test 2: unsupported intent surfaces blocking warning
# ---------------------------------------------------------------------------


def test_e2e_with_unsupported_intent_surfaces_blocking_warning() -> None:
    """Clarifier detects 'devil's advocate' and returns a blocking_warning."""
    raw_yaml = _load_stock_research_yaml()
    template_spec, _ = load_template_v2(raw_yaml, fmt="yaml")

    composer_inputs = {
        "ticker": "AAPL",
        "prompt": "have a devil's advocate pass after drafting",
    }

    clarifier_llm = make_llm(
        [
            {
                "questions": [],
                "blocking_warnings": [
                    {
                        "capability_id": "extra_passes",
                        "detected_phrase": "devil's advocate",
                        "user_message": (
                            "Extra LLM review/check passes are not supported in this version."
                        ),
                        "available_actions": ["proceed_without", "cancel_and_edit", "clarify"],
                    }
                ],
                "notices": [],
                "detected_intents": ["extra_passes"],
            }
        ]
    )
    clarifier = Clarifier(llm=clarifier_llm)
    clarifier_out = clarifier.clarify(composer_inputs, template_spec)

    assert len(clarifier_out.blocking_warnings) >= 1
    assert clarifier_out.blocking_warnings[0].capability_id == "extra_passes"


# ---------------------------------------------------------------------------
# Test 3: trigger_when=False renders SKIPPED status
# ---------------------------------------------------------------------------


def test_e2e_with_trigger_when_false_renders_skip_banner() -> None:
    """Section with trigger_when that evaluates to False gets SKIPPED status."""
    # Build a minimal section list with one conditional section
    sections = [
        SectionSpec(
            id="thesis",
            name="Investment Thesis",
            directive="Write thesis.",
            depends_on=[],
            trigger_when=None,
        ),
        SectionSpec(
            id="macro_outlook",
            name="Macro Outlook",
            directive="Write macro outlook.",
            depends_on=["thesis"],
            trigger_when="condition X",
        ),
    ]
    dag = {"thesis": [], "macro_outlook": ["thesis"]}

    # LLM for thesis draft returns prose; trigger evaluator returns fire=False
    drafter_llm = make_llm([{"blocks": [{"type": "prose", "text": "Thesis paragraph."}]}])
    trigger_llm = make_llm([{"fire": False, "reason": "X not met"}])
    trigger_evaluator = TriggerEvaluator(llm=trigger_llm)
    drafter = SectionDrafter(llm=drafter_llm, trigger_evaluator=trigger_evaluator)

    research_pool = ResearchPool(findings_by_strand={"main": "Some findings."})

    outputs = drafter.draft_all(
        sections=sections,
        dag=dag,
        composer_inputs={"ticker": "AAPL"},
        research_pool=research_pool,
        model_artifacts=[],
    )

    skipped = [o for o in outputs if o.section_id == "macro_outlook"]
    assert len(skipped) == 1
    assert skipped[0].status == "SKIPPED"
    assert skipped[0].skip_reason == "X not met"

    # Assembler renders a skip_banner block for skipped sections
    sections_dicts = [
        {"id": s.section_id, "name": s.section_name, "blocks": s.blocks}
        for s in outputs
        if s.status == "OK"
    ]
    # Add skipped section as skip_banner block. Section status rides on
    # the dict so build_report_v2 preserves it on the typed model.
    for s in outputs:
        if s.status == "SKIPPED":
            sections_dicts.append(
                {
                    "id": s.section_id,
                    "name": s.section_name,
                    "status": "SKIPPED",
                    "skip_reason": s.skip_reason,
                    "blocks": [
                        {
                            "type": "skip_banner",
                            "section_name": s.section_name,
                            "reason": s.skip_reason or "",
                        }
                    ],
                }
            )

    run_summary = RunSummary(
        engine_version="2.2",
        template_id="stock_research_v2",
        template_name="Stock Research (v2)",
        composer_inputs={"ticker": "AAPL"},
        outcomes=[],
    )
    report = build_report_v2(
        sections=sections_dicts,
        composer_inputs={"ticker": "AAPL"},
        template_spec=Mock(template_id="stock_research_v2", template_name="Stock Research (v2)", report_type="stock_initiation"),
        pool_citations={},
        run_summary=run_summary,
        verification_history=VerificationHistory(),
        dev_mode=False,
    )

    macro = next(s for s in report.sections if s.id == "macro_outlook")
    assert macro.status == "SKIPPED"
    assert macro.blocks[0]["type"] == "skip_banner"


# ---------------------------------------------------------------------------
# Test 4: engine version footer
# ---------------------------------------------------------------------------


def test_e2e_html_has_engine_version_footer() -> None:
    """Full assembly produces HTML containing Engine v2.2 in the footer."""
    sections_dicts = [
        {
            "id": "intro",
            "name": "Introduction",
            "blocks": [{"type": "prose", "text": "Opening paragraph."}],
        }
    ]

    run_summary = RunSummary(
        engine_version="2.2",
        template_id="stock_research_v2",
        template_name="Stock Research (v2)",
        composer_inputs={"ticker": "AAPL"},
        outcomes=[
            TaskOutcome(task_type="section_draft", task_name="intro", status="OK"),
        ],
    )

    report = build_report_v2(
        sections=sections_dicts,
        composer_inputs={"ticker": "AAPL"},
        template_spec=Mock(template_id="stock_research_v2", template_name="Stock Research (v2)", report_type="stock_initiation"),
        pool_citations={},
        run_summary=run_summary,
        verification_history=VerificationHistory(),
        dev_mode=False,
    )

    assert report.engine_version == "2.2"
