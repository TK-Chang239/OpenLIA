"""Unit tests for VisualizeStage — chart renderability validation."""

from __future__ import annotations

from datetime import UTC, datetime

from openlia.llm.runtime.report_v2_3.schemas import (
    BundleFact,
    BundleSeries,
    BundleSeriesPoint,
    CanonicalFigure,
    ChartSeries,
    ChartSpec,
    ChartType,
    DataProviderSource,
    Language,
    ReportThesis,
    ReportType,
    ResearchBundle,
    SectionMandate,
    ValuationPlan,
)
from openlia.llm.runtime.report_v2_3.stages import StageContext, VisualizeStage
from openlia.llm.runtime.report_v2_3.state import ReportState


def _src() -> DataProviderSource:
    return DataProviderSource(
        provider="EODHD",
        endpoint="fundamentals/income_statement",
        period="TTM",
        retrieved_at=datetime.now(UTC),
    )


def _series_fact(fact_id: str, points: list[tuple[str, float]]) -> BundleFact:
    return BundleFact(
        id=fact_id,
        label=fact_id,
        value=BundleSeries(
            points=[BundleSeriesPoint(period=p, value=v) for p, v in points],
        ),
        source=_src(),
    )


def _scalar(fact_id: str, value: float) -> BundleFact:
    return BundleFact(id=fact_id, label=fact_id, value=value, source=_src())


def _state(
    *,
    facts: dict[str, BundleFact] | None = None,
    charts: list[ChartSpec] | None = None,
) -> ReportState:
    s = ReportState(
        run_id="r",
        user_id="u",
        raw_prompt="initiate on NVDA",
        language=Language.EN,
        report_type=ReportType.INITIATION,
        tickers=["NVDA"],
    )
    s.bundle = ResearchBundle(
        tickers=["NVDA"],
        facts=facts if facts is not None else {"rev_ttm": _scalar("rev_ttm", 100.0)},
    )
    s.thesis = ReportThesis(
        language=Language.EN,
        central_argument="growth",
        key_takeaways=["x"],
        valuation_stance="fair",
        valuation_plan=ValuationPlan(),
        canonical_figures=[CanonicalFigure(fact_id="rev_ttm", display="$100M")],
        mandates=[
            SectionMandate(
                section_id="financials",
                covers="financials",
                does_not_cover="overview",
                chart_ids=[c.id for c in (charts or [])],
                relevant_fact_ids=["rev_ttm"],
            )
        ],
        charts=charts if charts is not None else [],
    )
    return s


def _ctx() -> StageContext:
    return StageContext(clients={}, tools={}, extras={})


def _series_chart(*, n_categories: int, value_fact_ids: list[str]) -> ChartSpec:
    return ChartSpec(
        id="rev_chart",
        section_id="financials",
        claim="rising",
        chart_type=ChartType.LINE,
        title="Revenue",
        category_labels=[f"P{i}" for i in range(n_categories)],
        series=[ChartSeries(name="rev", value_fact_ids=value_fact_ids)],
    )


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_chart_with_matching_series_length_passes() -> None:
    facts = {"rev_q": _series_fact("rev_q", [("Q1", 10.0), ("Q2", 11.0)])}
    state = VisualizeStage().run(
        _state(facts=facts, charts=[_series_chart(n_categories=2, value_fact_ids=["rev_q"])]),
        _ctx(),
    )
    # No state mutation; stage just validates.
    assert state.thesis is not None
    assert state.thesis.charts[0].id == "rev_chart"


def test_chart_with_multi_fact_series_matches_categories() -> None:
    facts = {
        "rev_q1": _scalar("rev_q1", 10.0),
        "rev_q2": _scalar("rev_q2", 11.0),
    }
    state = _state(
        facts=facts,
        charts=[_series_chart(n_categories=2, value_fact_ids=["rev_q1", "rev_q2"])],
    )
    VisualizeStage().run(state, _ctx())


def test_empty_charts_list_is_noop() -> None:
    VisualizeStage().run(_state(charts=[]), _ctx())


# ---------------------------------------------------------------------------
# Graceful no-op (incomplete pipeline)
# ---------------------------------------------------------------------------


def test_missing_thesis_is_noop() -> None:
    state = _state()
    state.thesis = None
    # Should not raise even though bundle has no chart-friendly facts.
    result = VisualizeStage().run(state, _ctx())
    assert result.thesis is None


def test_missing_bundle_is_noop() -> None:
    state = _state(charts=[_series_chart(n_categories=2, value_fact_ids=["rev_q"])])
    state.bundle = None
    # Even though the chart references a fact that doesn't exist, missing
    # bundle short-circuits — that's the incomplete-pipeline shape.
    VisualizeStage().run(state, _ctx())


# ---------------------------------------------------------------------------
# Validation errors
# ---------------------------------------------------------------------------


def test_chart_referencing_unknown_fact_is_dropped() -> None:
    # When the only fact_id in a series doesn't exist, the chart has
    # nothing to plot — dropped (not raised on) so the whole report
    # still ships.
    state = _state(
        facts={"other_fact": _scalar("other_fact", 1.0)},
        charts=[_series_chart(n_categories=1, value_fact_ids=["ghost"])],
    )
    out = VisualizeStage().run(state, _ctx())
    assert out.thesis is not None
    assert out.thesis.charts == []


def test_series_with_too_few_points_is_truncated() -> None:
    # 1-point BundleSeries + 3 categories → chart truncated to 1 category
    # instead of failing the run.
    facts = {"rev_q": _series_fact("rev_q", [("Q1", 10.0)])}
    state = _state(
        facts=facts,
        charts=[_series_chart(n_categories=3, value_fact_ids=["rev_q"])],
    )
    out = VisualizeStage().run(state, _ctx())
    assert out.thesis is not None
    assert len(out.thesis.charts) == 1
    assert len(out.thesis.charts[0].category_labels) == 1


def test_multi_fact_series_with_too_few_fact_ids_is_truncated() -> None:
    facts = {
        "rev_q1": _scalar("rev_q1", 10.0),
        "rev_q2": _scalar("rev_q2", 11.0),
    }
    state = _state(
        facts=facts,
        charts=[_series_chart(n_categories=3, value_fact_ids=["rev_q1", "rev_q2"])],
    )
    out = VisualizeStage().run(state, _ctx())
    assert out.thesis is not None
    assert len(out.thesis.charts) == 1
    assert len(out.thesis.charts[0].category_labels) == 2
    assert out.thesis.charts[0].series[0].value_fact_ids == ["rev_q1", "rev_q2"]
