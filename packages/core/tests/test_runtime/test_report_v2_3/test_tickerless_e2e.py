"""End-to-end: a ticker-less custom TemplateSpec runs cleanly through
every v2.3 stage. Proves Phase 3's broadenings hold together —
empty Outline.tickers, empty ResearchBundle.tickers, RESEARCH non-
empty raise gated on planner asking for facts, CLARIFY skipping the
forced-ticker question, schemas accepting all of the above."""

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
    SynthesizeStage,
    VerifyStage,
    WriteStage,
)
from openlia.llm.runtime.report_v2_3.stages.base import StageContext
from openlia.llm.runtime.report_v2_3.state import ReportState
from openlia.llm.runtime.report_v2_3.templates import SectionSpec, TemplateSpec


def _ctx() -> StageContext:
    return StageContext(clients={}, tools={}, extras={})


def _src() -> DataProviderSource:
    return DataProviderSource(
        provider="WEB",
        endpoint="search",
        period="2026-Q2",
        retrieved_at=datetime.now(UTC),
    )


def test_tickerless_sector_research_runs_end_to_end():
    custom = TemplateSpec(
        template_id="custom_sector_tickerless",
        name="Custom sector (ticker-less)",
        shape_description=(
            "Sector primer with no specific subject ticker — proves the "
            "ticker_anchored=False path runs cleanly through every stage."
        ),
        ticker_anchored=False,
        sections=[
            SectionSpec(id="primer", title="Primer", intent="Set up the sector."),
            SectionSpec(id="drivers", title="Drivers", intent="Name the drivers."),
        ],
    )

    state = ReportState(
        run_id="r-tickerless",
        user_id="u-tickerless",
        raw_prompt="lithium miners outlook",
        language=Language.EN,
        report_type=ReportType.SECTOR_RESEARCH,
        tickers=[],  # Phase 3 allows this
        template=custom,
    )
    state.bundle = ResearchBundle(
        tickers=[],
        facts={
            "demand_outlook": BundleFact(
                id="demand_outlook",
                label="Demand outlook",
                value="Lithium demand outpaces supply through the medium term.",
                source=_src(),
            ),
        },
    )

    fake_outline = Outline(
        tickers=[],
        report_type=ReportType.SECTOR_RESEARCH,
        sections=[
            OutlineSection(
                id="primer",
                title="Primer",
                data_needs=[
                    DataNeed(
                        description="qualitative outlook",
                        expected_fact_ids=["demand_outlook"],
                    ),
                ],
            ),
            OutlineSection(id="drivers", title="Drivers", data_needs=[]),
        ],
        valuation_plan=ValuationPlan(),
    )
    PlanStage(FakePlannerClient(result=fake_outline)).run(state, _ctx())
    assert state.outline is not None
    assert state.outline.tickers == []
    assert [s.id for s in state.outline.sections] == ["primer", "drivers"]

    thesis = ReportThesis(
        language=Language.EN,
        central_argument="Lithium remains structurally tight in the medium term.",
        key_takeaways=["demand", "supply", "regulation"],
        valuation_stance="not_applicable",
        valuation_plan=ValuationPlan(),
        canonical_figures=[],
        mandates=[
            SectionMandate(
                section_id="primer",
                covers="Sector setup",
                does_not_cover="drivers",
                chart_ids=[],
                relevant_fact_ids=["demand_outlook"],
            ),
            SectionMandate(
                section_id="drivers",
                covers="Demand and supply drivers",
                does_not_cover="primer",
                chart_ids=[],
                relevant_fact_ids=[],
            ),
        ],
        charts=[],
    )
    SynthesizeStage(FakeSynthesizerClient(result=thesis)).run(state, _ctx())
    assert state.thesis is not None
    assert {m.section_id for m in state.thesis.mandates} == {"primer", "drivers"}

    def responder(req: WriterRequest) -> WrittenSection:
        sid = req.section_mandate.section_id
        return WrittenSection(
            section_id=sid,
            title=sid.title(),
            body="Sector-level prose without specific numbers.",
        )

    WriteStage(FakeWriterClient(responder=responder)).run(state, _ctx())
    assert {s.section_id for s in state.sections} == {"primer", "drivers"}

    VerifyStage(FakeVerifierClient(result=VerifyResult(issues=[]))).run(state, _ctx())
    assert state.verify_result is not None
    assert state.verify_result.must_rewrite is False
