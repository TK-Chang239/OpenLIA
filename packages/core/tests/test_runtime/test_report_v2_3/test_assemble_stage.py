"""Unit tests for AssembleStage — deterministic resolve + graceful no-op."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from openlia.llm.runtime.report_v2_3.schemas import (
    BundleFact,
    CanonicalFigure,
    ChartSeries,
    ChartSpec,
    ChartType,
    DataProviderSource,
    Language,
    Outline,
    OutlineSection,
    ReportThesis,
    ReportType,
    ResearchBundle,
    SectionMandate,
    ValuationPlan,
    WrittenSection,
)
from openlia.llm.runtime.report_v2_3.stages import StageContext
from openlia.llm.runtime.report_v2_3.stages.assemble import AssembleStage
from openlia.llm.runtime.report_v2_3.state import ReportState
from openlia.llm.runtime.report_v2_3.templates import get_builtin


def _src() -> DataProviderSource:
    return DataProviderSource(
        provider="EODHD",
        endpoint="fundamentals/income_statement",
        period="TTM",
        retrieved_at=datetime.now(UTC),
    )


def _bundle() -> ResearchBundle:
    return ResearchBundle(
        tickers=["NVDA"],
        facts={
            "rev_ttm": BundleFact(id="rev_ttm", label="Revenue TTM", value=100.0, source=_src()),
            "gm": BundleFact(id="gm", label="Gross margin", value=0.65, source=_src()),
        },
    )


def _outline() -> Outline:
    return Outline(
        tickers=["NVDA"],
        report_type=ReportType.INITIATION,
        sections=[
            OutlineSection(id="overview", title="Overview"),
            OutlineSection(id="financials", title="Financials"),
        ],
    )


def _thesis() -> ReportThesis:
    return ReportThesis(
        language=Language.EN,
        central_argument="Durable growth.",
        key_takeaways=["beat"],
        valuation_stance="fair",
        valuation_plan=ValuationPlan(),
        canonical_figures=[CanonicalFigure(fact_id="gm", display="65.0%")],
        mandates=[
            SectionMandate(
                section_id="overview",
                covers="overview",
                does_not_cover="financials",
                relevant_fact_ids=["rev_ttm"],
            ),
            SectionMandate(
                section_id="financials",
                covers="financials",
                does_not_cover="overview",
                chart_ids=["rev_chart"],
                relevant_fact_ids=["rev_ttm", "gm"],
            ),
        ],
        charts=[
            ChartSpec(
                id="rev_chart",
                section_id="financials",
                claim="revenue rising",
                chart_type=ChartType.LINE,
                title="Revenue",
                category_labels=["Q1", "Q2"],
                series=[ChartSeries(name="rev", value_fact_ids=["rev_ttm"])],
            )
        ],
    )


def _full_state() -> ReportState:
    s = ReportState(
        run_id="r",
        user_id="u",
        raw_prompt="initiate on NVDA",
        language=Language.EN,
        report_type=ReportType.INITIATION,
        tickers=["NVDA"],
        template=get_builtin(ReportType.INITIATION),
    )
    s.bundle = _bundle()
    s.outline = _outline()
    s.thesis = _thesis()
    s.sections = [
        WrittenSection(section_id="overview", title="Overview", body="Rev was {{CITE:rev_ttm}}."),
        WrittenSection(
            section_id="financials",
            title="Financials",
            body="See {{FIG:rev_chart}}; margin {{CITE:gm}}.",
        ),
    ]
    return s


def _ctx() -> StageContext:
    return StageContext(clients={}, tools={}, extras={})


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_happy_path_resolves_placeholders_in_document_order() -> None:
    state = AssembleStage().run(_full_state(), _ctx())
    assert state.resolved is not None
    # Footnotes are numbered in section order, deduped by fact_id.
    assert state.resolved.figure_labels == {"rev_chart": 1}
    overview_body = state.resolved.section_bodies["overview"]
    financials_body = state.resolved.section_bodies["financials"]
    assert "[^1]" in overview_body
    assert "Figure 1" in financials_body
    assert len(state.resolved.footnotes) == 2  # rev_ttm + gm


def test_resolution_is_deterministic_across_runs() -> None:
    """Running ASSEMBLE twice on the same inputs must produce identical
    ResolvedReport content — figure numbers, footnote ordering, dedupe."""
    first = AssembleStage().run(_full_state(), _ctx()).resolved
    second = AssembleStage().run(_full_state(), _ctx()).resolved
    assert first == second


# ---------------------------------------------------------------------------
# Graceful no-op when upstream stages haven't populated state
# ---------------------------------------------------------------------------


def test_noop_when_sections_empty() -> None:
    state = _full_state()
    state.sections = []
    result = AssembleStage().run(state, _ctx())
    assert result.resolved is None


def test_noop_when_bundle_missing() -> None:
    state = _full_state()
    state.bundle = None
    result = AssembleStage().run(state, _ctx())
    assert result.resolved is None


def test_noop_when_thesis_missing() -> None:
    state = _full_state()
    state.thesis = None
    result = AssembleStage().run(state, _ctx())
    assert result.resolved is None


def test_noop_when_outline_missing() -> None:
    state = _full_state()
    state.outline = None
    result = AssembleStage().run(state, _ctx())
    assert result.resolved is None


# ---------------------------------------------------------------------------
# Failures surface (dangling refs from resolve())
# ---------------------------------------------------------------------------


def test_dangling_citation_raises_via_resolve() -> None:
    state = _full_state()
    state.sections[0] = WrittenSection(
        section_id="overview", title="Overview", body="ghost {{CITE:not_in_bundle}}"
    )
    with pytest.raises(ValueError, match="Dangling citation"):
        AssembleStage().run(state, _ctx())
