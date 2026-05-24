"""Unit tests for SynthesizeStage — preconditions + cross-validation."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from openlia.llm.runtime.report_v2_3.clients.synthesizer import (
    FakeSynthesizerClient,
)
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
    ValuationMethod,
    ValuationPlan,
)
from openlia.llm.runtime.report_v2_3.stages import StageContext, SynthesizeStage
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


def _state(*, language: Language = Language.EN) -> ReportState:
    s = ReportState(
        run_id="r",
        user_id="u",
        raw_prompt="initiate on NVDA",
        language=language,
        report_type=ReportType.INITIATION,
        tickers=["NVDA"],
        template=get_builtin(ReportType.INITIATION),
    )
    s.bundle = _bundle()
    s.outline = _outline()
    return s


def _ctx() -> StageContext:
    return StageContext(clients={}, tools={}, extras={})


def _thesis(
    *,
    language: Language = Language.EN,
    mandates: list[SectionMandate] | None = None,
    canonical: list[CanonicalFigure] | None = None,
    charts: list[ChartSpec] | None = None,
) -> ReportThesis:
    return ReportThesis(
        language=language,
        central_argument="Growth durable.",
        key_takeaways=["beat", "raise"],
        valuation_stance="fair",
        valuation_plan=ValuationPlan(methods=[ValuationMethod.DCF]),
        canonical_figures=canonical
        if canonical is not None
        else [CanonicalFigure(fact_id="gm", display="65.0%")],
        mandates=mandates
        if mandates is not None
        else [
            SectionMandate(
                section_id="overview",
                covers="business overview",
                does_not_cover="valuation details",
                relevant_fact_ids=["rev_ttm"],
            ),
            SectionMandate(
                section_id="financials",
                covers="financial line items",
                does_not_cover="overview",
                relevant_fact_ids=["gm"],
            ),
        ],
        charts=charts if charts is not None else [],
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_happy_path_writes_thesis_to_state() -> None:
    expected = _thesis()
    client = FakeSynthesizerClient(result=expected)
    stage = SynthesizeStage(client)

    state = stage.run(_state(), _ctx())
    assert state.thesis is expected
    assert len(client.calls) == 1
    request = client.calls[0]
    assert request.raw_prompt == "initiate on NVDA"
    assert request.language == Language.EN
    assert request.bundle is state.bundle
    assert request.outline is state.outline


# ---------------------------------------------------------------------------
# Precondition errors
# ---------------------------------------------------------------------------


def test_missing_bundle_raises() -> None:
    state = _state()
    state.bundle = None
    stage = SynthesizeStage(FakeSynthesizerClient(result=_thesis()))
    with pytest.raises(RuntimeError, match=r"state\.bundle"):
        stage.run(state, _ctx())


def test_missing_outline_raises() -> None:
    state = _state()
    state.outline = None
    stage = SynthesizeStage(FakeSynthesizerClient(result=_thesis()))
    with pytest.raises(RuntimeError, match=r"state\.outline"):
        stage.run(state, _ctx())


# ---------------------------------------------------------------------------
# Cross-validation errors
# ---------------------------------------------------------------------------


def test_language_mismatch_raises() -> None:
    stage = SynthesizeStage(FakeSynthesizerClient(result=_thesis(language=Language.ZH_TW)))
    with pytest.raises(RuntimeError, match="language"):
        stage.run(_state(language=Language.EN), _ctx())


def test_missing_mandate_for_outline_section_raises() -> None:
    mandates = [
        SectionMandate(
            section_id="overview",
            covers="overview only — missing financials",
            does_not_cover="x",
        )
    ]
    stage = SynthesizeStage(FakeSynthesizerClient(result=_thesis(mandates=mandates)))
    with pytest.raises(RuntimeError, match="missing mandates"):
        stage.run(_state(), _ctx())


def test_stray_mandate_not_in_outline_raises() -> None:
    mandates = [
        SectionMandate(section_id="overview", covers="x", does_not_cover="y"),
        SectionMandate(section_id="financials", covers="x", does_not_cover="y"),
        SectionMandate(section_id="ghost", covers="x", does_not_cover="y"),
    ]
    stage = SynthesizeStage(FakeSynthesizerClient(result=_thesis(mandates=mandates)))
    with pytest.raises(RuntimeError, match="not in outline"):
        stage.run(_state(), _ctx())


def test_canonical_figure_for_unknown_fact_is_dropped() -> None:
    # The LLM routinely names plausible-sounding fact ids the bundle
    # doesn't carry. Dropping the entry is the right tradeoff — failing
    # the whole run for one stray cover metric loses the entire report.
    canonical = [
        CanonicalFigure(fact_id="rev_ttm", display="$60.9B"),
        CanonicalFigure(fact_id="not_in_bundle", display="x"),
    ]
    stage = SynthesizeStage(FakeSynthesizerClient(result=_thesis(canonical=canonical)))
    out = stage.run(_state(), _ctx())
    assert out.thesis is not None
    assert [cf.fact_id for cf in out.thesis.canonical_figures] == ["rev_ttm"]


def test_chart_referencing_unknown_fact_is_dropped() -> None:
    # A chart with any phantom fact id would mis-plot, so we drop the
    # entire chart (with a warning) rather than render a partial.
    charts = [
        ChartSpec(
            id="rev_chart",
            section_id="overview",
            claim="revenue rising",
            chart_type=ChartType.LINE,
            title="Revenue",
            category_labels=["Q1", "Q2"],
            series=[ChartSeries(name="rev", value_fact_ids=["ghost_fact"])],
        )
    ]
    stage = SynthesizeStage(FakeSynthesizerClient(result=_thesis(charts=charts)))
    out = stage.run(_state(), _ctx())
    assert out.thesis is not None
    assert out.thesis.charts == []


def test_mandate_referencing_unknown_fact_strips_the_phantom() -> None:
    mandates = [
        SectionMandate(
            section_id="overview",
            covers="x",
            does_not_cover="y",
            relevant_fact_ids=["rev_ttm", "ghost"],
        ),
        SectionMandate(section_id="financials", covers="x", does_not_cover="y"),
    ]
    stage = SynthesizeStage(FakeSynthesizerClient(result=_thesis(mandates=mandates)))
    out = stage.run(_state(), _ctx())
    assert out.thesis is not None
    overview = next(m for m in out.thesis.mandates if m.section_id == "overview")
    assert overview.relevant_fact_ids == ["rev_ttm"]
