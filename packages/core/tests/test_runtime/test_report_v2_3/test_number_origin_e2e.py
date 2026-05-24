"""End-to-end: WRITE -> mint -> VERIFY pipeline preserves number-origin discipline.

Drives a single iteration of WriteStage followed by VerifyStage with a
fake writer that emits all three marker shapes, and asserts:
  - DERIVE/ESTIMATE markers are resolved into bundle facts of the
    correct Provenance variants
  - the post-WRITE body contains only {{CITE:...}} markers (no naked
    numbers, no DERIVE/ESTIMATE remnants)
  - VERIFY surfaces zero UNCITED_NUMBER issues
  - render_citation produces "Estimate: ..." for estimate facts and
    "Author calculation: ..." for computed facts
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from openlia.llm.runtime.report_v2_3.clients.verifier import FakeVerifierClient
from openlia.llm.runtime.report_v2_3.clients.writer import FakeWriterClient, WriterRequest
from openlia.llm.runtime.report_v2_3.schemas import (
    BundleFact,
    CanonicalFigure,
    ComputedSource,
    DataProviderSource,
    EstimateSource,
    IssueKind,
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
    render_citation,
)
from openlia.llm.runtime.report_v2_3.stages import VerifyStage, WriteStage
from openlia.llm.runtime.report_v2_3.stages.base import StageContext
from openlia.llm.runtime.report_v2_3.state import ReportState


def _src() -> DataProviderSource:
    return DataProviderSource(
        provider="EODHD",
        endpoint="fundamentals/income_statement",
        period="FY2025",
        retrieved_at=datetime.now(UTC),
    )


def _ctx() -> StageContext:
    return StageContext(clients={}, tools={}, extras={})


def test_number_origin_discipline_holds_through_write_and_verify():
    bundle = ResearchBundle(
        tickers=["NVDA"],
        facts={
            "rev_fy25": BundleFact(id="rev_fy25", label="Revenue FY25", value=125.0, source=_src()),
            "rev_fy24": BundleFact(id="rev_fy24", label="Revenue FY24", value=100.0, source=_src()),
        },
    )
    outline = Outline(
        tickers=["NVDA"],
        report_type=ReportType.INITIATION,
        sections=[OutlineSection(id="financials", title="Financials")],
    )
    thesis = ReportThesis(
        language=Language.EN,
        central_argument="Growth durable.",
        key_takeaways=["beat", "raise"],
        valuation_stance="fair",
        valuation_plan=ValuationPlan(),
        canonical_figures=[CanonicalFigure(fact_id="rev_fy25", display="$125.0M")],
        mandates=[
            SectionMandate(
                section_id="financials",
                covers="financial line items",
                does_not_cover="overview",
                chart_ids=[],
                relevant_fact_ids=["rev_fy25", "rev_fy24"],
            )
        ],
        charts=[],
    )
    state = ReportState(
        run_id="r",
        user_id="u",
        raw_prompt="initiate on NVDA",
        language=Language.EN,
        report_type=ReportType.INITIATION,
        tickers=["NVDA"],
    )
    state.bundle = bundle
    state.outline = outline
    state.thesis = thesis

    def responder(req: WriterRequest) -> WrittenSection:
        return WrittenSection(
            section_id="financials",
            title="Financials",
            body=(
                "Revenue {{CITE:rev_fy25}} grew "
                "{{DERIVE:growth_rate|rev_fy25,rev_fy24|rev_growth_yoy}} YoY, "
                "and we see {{ESTIMATE:upside_pct|0.10|percent|"
                "margin expansion against current multiple}} of upside."
            ),
        )

    WriteStage(FakeWriterClient(responder=responder)).run(state, _ctx())

    body = state.sections[0].body
    assert "{{DERIVE:" not in body
    assert "{{ESTIMATE:" not in body
    assert body.count("{{CITE:") == 3
    assert "rev_fy25" in body
    assert "rev_growth_yoy" in body
    assert "upside_pct" in body

    minted_derived = state.bundle.facts["rev_growth_yoy"]
    assert isinstance(minted_derived.source, ComputedSource)
    assert minted_derived.value == pytest.approx(0.25)
    assert minted_derived.source.derived_from == ["rev_fy25", "rev_fy24"]
    assert render_citation(minted_derived) == "Author calculation: growth_rate."

    minted_estimate = state.bundle.facts["upside_pct"]
    assert isinstance(minted_estimate.source, EstimateSource)
    assert render_citation(minted_estimate) == (
        "Estimate: margin expansion against current multiple."
    )

    VerifyStage(FakeVerifierClient(result=VerifyResult(issues=[]))).run(state, _ctx())

    uncited = [i for i in state.verify_result.issues if i.kind == IssueKind.UNCITED_NUMBER]
    assert uncited == []
    assert state.verify_result.must_rewrite is False
