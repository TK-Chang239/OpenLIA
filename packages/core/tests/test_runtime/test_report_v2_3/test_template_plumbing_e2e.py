"""End-to-end: a custom TemplateSpec drives every stage of the v2.3
pipeline.

Mirrors `test_number_origin_e2e.py` from Phase 0 in structure. The test
uses a CUSTOM (non-builtin) template with three unique section ids so a
passing assertion proves the rails actually carry the user's template
through PLAN -> SYNTHESIZE -> WRITE -> VERIFY -> ASSEMBLE rather than
silently substituting a builtin.

Skips RESEARCH and COMPUTE (pre-populates `state.bundle`) — those stages
are noisy for an integration shape check, and SynthesizeStage's
preconditions only require bundle + outline + matching mandate ids.
"""

from __future__ import annotations

from datetime import UTC, datetime

from openlia.llm.runtime.report_v2_3.clients.planner import FakePlannerClient
from openlia.llm.runtime.report_v2_3.clients.synthesizer import (
    FakeSynthesizerClient,
)
from openlia.llm.runtime.report_v2_3.clients.verifier import FakeVerifierClient
from openlia.llm.runtime.report_v2_3.clients.writer import (
    FakeWriterClient,
    WriterRequest,
)
from openlia.llm.runtime.report_v2_3.schemas import (
    BundleFact,
    CanonicalFigure,
    DataNeed,
    DataProviderSource,
    Language,
    Outline,
    OutlineSection,
    ReportThesis,
    ReportType,
    ResearchBundle,
    SectionMandate,
    ValuationPlan,
    VerifyResult,
    WrittenSection,
)
from openlia.llm.runtime.report_v2_3.stages import (
    PlanStage,
    RealAssembleStage,
    SynthesizeStage,
    VerifyStage,
    WriteStage,
)
from openlia.llm.runtime.report_v2_3.stages.base import StageContext
from openlia.llm.runtime.report_v2_3.state import ReportState
from openlia.llm.runtime.report_v2_3.templates import SectionSpec, TemplateSpec


def _src() -> DataProviderSource:
    return DataProviderSource(
        provider="EODHD",
        endpoint="fundamentals/income_statement",
        period="FY2025",
        retrieved_at=datetime.now(UTC),
    )


def _ctx() -> StageContext:
    return StageContext(clients={}, tools={}, extras={})


def test_custom_template_drives_full_pipeline():
    # Custom template — 3 sections with ids that don't appear in any builtin.
    custom = TemplateSpec(
        template_id="custom_e2e",
        name="Custom E2E",
        shape_description="Three-section custom template for the e2e test.",
        sections=[
            SectionSpec(
                id="thesis_e2e",
                title="Thesis",
                intent="State the central thesis.",
            ),
            SectionSpec(
                id="evidence_e2e",
                title="Evidence",
                intent="Marshal supporting evidence.",
            ),
            SectionSpec(
                id="risks_e2e",
                title="Risks",
                intent="List load-bearing risks.",
            ),
        ],
    )

    state = ReportState(
        run_id="r-e2e",
        user_id="u-e2e",
        raw_prompt="Custom template e2e",
        language=Language.EN,
        report_type=ReportType.INITIATION,
        tickers=["NVDA"],
        template=custom,
    )
    # Pre-populate the bundle so SYNTHESIZE / WRITE / VERIFY / ASSEMBLE
    # have something to chew on without running RESEARCH or COMPUTE.
    state.bundle = ResearchBundle(
        tickers=["NVDA"],
        facts={
            "rev_ttm": BundleFact(
                id="rev_ttm",
                label="Revenue TTM",
                value=125.0,
                source=_src(),
            ),
        },
    )

    # PLAN: fake returns the WRONG section ids; the coercer must reshape
    # the outline to match the template before validation runs.
    wrong_outline = Outline(
        tickers=["NVDA"],
        report_type=ReportType.INITIATION,
        sections=[
            OutlineSection(
                id="wrong_id",
                title="Wrong",
                data_needs=[
                    DataNeed(description="x", expected_fact_ids=["rev_ttm"]),
                ],
            ),
        ],
        valuation_plan=ValuationPlan(),
    )
    PlanStage(FakePlannerClient(result=wrong_outline)).run(state, _ctx())

    # Coercer must have reshaped the outline to match the template.
    assert state.outline is not None
    assert [s.id for s in state.outline.sections] == [
        "thesis_e2e",
        "evidence_e2e",
        "risks_e2e",
    ]

    # SYNTHESIZE: fake returns a thesis whose mandates align with the
    # template's section ids (this is what the real synthesizer would
    # produce after PLAN's coercer fixed the outline).
    thesis = ReportThesis(
        language=Language.EN,
        central_argument="Custom template drives the pipeline.",
        key_takeaways=["thesis", "evidence", "risks"],
        valuation_stance="fair",
        valuation_plan=ValuationPlan(),
        canonical_figures=[
            CanonicalFigure(fact_id="rev_ttm", display="$125M"),
        ],
        mandates=[
            SectionMandate(
                section_id="thesis_e2e",
                covers="Central thesis statement",
                does_not_cover="evidence, risks",
                chart_ids=[],
                relevant_fact_ids=["rev_ttm"],
            ),
            SectionMandate(
                section_id="evidence_e2e",
                covers="Supporting evidence",
                does_not_cover="thesis, risks",
                chart_ids=[],
                relevant_fact_ids=["rev_ttm"],
            ),
            SectionMandate(
                section_id="risks_e2e",
                covers="Load-bearing risks",
                does_not_cover="thesis, evidence",
                chart_ids=[],
                relevant_fact_ids=["rev_ttm"],
            ),
        ],
        charts=[],
    )
    SynthesizeStage(FakeSynthesizerClient(result=thesis)).run(state, _ctx())

    assert state.thesis is not None
    assert {m.section_id for m in state.thesis.mandates} == {
        "thesis_e2e",
        "evidence_e2e",
        "risks_e2e",
    }

    # WRITE: fake returns a clean body per mandate. Plain prose with no
    # DERIVE / ESTIMATE markers and no naked numbers — keeps VERIFY's
    # uncited-number check happy. (The literal section id is omitted
    # from the body because it contains a digit — the uncited-number
    # check would otherwise flag it.)
    def responder(req: WriterRequest) -> WrittenSection:
        sid = req.section_mandate.section_id
        return WrittenSection(
            section_id=sid,
            title=sid.replace("_", " ").title(),
            body="Plain prose body for the custom template section.",
        )

    WriteStage(FakeWriterClient(responder=responder)).run(state, _ctx())

    assert {s.section_id for s in state.sections} == {
        "thesis_e2e",
        "evidence_e2e",
        "risks_e2e",
    }

    # VERIFY: clean — no LLM-side issues, no deterministic violations.
    VerifyStage(FakeVerifierClient(result=VerifyResult(issues=[]))).run(state, _ctx())
    assert state.verify_result is not None
    assert state.verify_result.must_rewrite is False

    # ASSEMBLE: produces resolved bodies keyed by the template's section ids.
    RealAssembleStage().run(state, _ctx())
    assert state.resolved is not None
    assert set(state.resolved.section_bodies.keys()) == {
        "thesis_e2e",
        "evidence_e2e",
        "risks_e2e",
    }
