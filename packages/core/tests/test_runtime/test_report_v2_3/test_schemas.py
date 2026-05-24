"""Unit tests for report_v2_3 schemas — validators, resolution, and helpers."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from openlia.llm.runtime.report_v2_3.schemas import (
    DERIVE_RE,
    ESTIMATE_RE,
    BundleFact,
    BundleSeries,
    BundleSeriesPoint,
    CanonicalFigure,
    ChartSeries,
    ChartSpec,
    ChartType,
    ClarifyAnswers,
    ClarifyQuestion,
    CompPeer,
    CompsInputs,
    ComputedSource,
    DataProviderSource,
    DCFInputs,
    DCFResult,
    EstimateSource,
    FilingSource,
    Language,
    Outline,
    OutlineSection,
    ReportThesis,
    ReportType,
    ResearchBundle,
    SectionMandate,
    SensitivityInputs,
    SourceType,
    ValuationMethod,
    ValuationPlan,
    WebSource,
    WrittenSection,
    dcf_result_to_facts,
    render_citation,
    resolve,
)
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# Provenance + BundleFact
# ---------------------------------------------------------------------------


def _data_source() -> DataProviderSource:
    return DataProviderSource(
        provider="EODHD",
        endpoint="fundamentals/income_statement",
        statement="income_statement",
        period="TTM",
        retrieved_at=datetime.now(UTC),
    )


def _web_source() -> WebSource:
    return WebSource(
        url="https://example.com/article",
        title="Example",
        publisher="Example News",
        snippet="margins expanded materially in Q4.",
        retrieved_at=datetime.now(UTC),
    )


def _filing_source(page: int | None = 42) -> FilingSource:
    return FilingSource(
        company="NVDA",
        form_type="10-K",
        fiscal_period="FY2025",
        page=page,
        retrieved_at=datetime.now(UTC),
    )


def test_bundle_fact_scalar_and_series() -> None:
    scalar = BundleFact(id="x", label="X", value=12.5, source=_data_source())
    assert scalar.is_quantitative

    series = BundleFact(
        id="rev_qtr",
        label="Revenue (quarterly)",
        value=BundleSeries(
            points=[
                BundleSeriesPoint(period="2025-Q1", value=10.0),
                BundleSeriesPoint(period="2025-Q2", value=11.0),
            ],
            unit="USD_billions",
        ),
        source=_data_source(),
    )
    assert series.is_quantitative

    categorical = BundleFact(id="moat", label="Moat type", value="network", source=_data_source())
    assert not categorical.is_quantitative


def test_research_bundle_derived_chain_must_resolve() -> None:
    bundle = ResearchBundle(
        tickers=["NVDA"],
        facts={
            "ebitda": BundleFact(id="ebitda", label="EBITDA", value=100.0, source=_data_source()),
            "ev": BundleFact(id="ev", label="EV", value=1100.0, source=_data_source()),
            "ev_ebitda": BundleFact(
                id="ev_ebitda",
                label="EV / EBITDA",
                value=11.0,
                source=ComputedSource(method="EV / EBITDA", derived_from=["ev", "ebitda"]),
            ),
        },
    )
    assert bundle.get("ev_ebitda").value == 11.0


def test_research_bundle_rejects_dangling_derived_from() -> None:
    with pytest.raises(ValidationError) as exc:
        ResearchBundle(
            tickers=["NVDA"],
            facts={
                "x": BundleFact(
                    id="x",
                    label="X",
                    value=1.0,
                    source=ComputedSource(method="missing", derived_from=["ghost"]),
                ),
            },
        )
    assert "ghost" in str(exc.value)


def test_research_bundle_add_rejects_duplicate_ids() -> None:
    bundle = ResearchBundle(tickers=["NVDA"])
    bundle.add(BundleFact(id="x", label="X", value=1.0, source=_data_source()))
    with pytest.raises(ValueError, match="Duplicate fact id"):
        bundle.add(BundleFact(id="x", label="X again", value=2.0, source=_data_source()))


def test_research_bundle_requires_at_least_one_ticker() -> None:
    with pytest.raises(ValidationError):
        ResearchBundle(tickers=[])


# ---------------------------------------------------------------------------
# Valuation inputs / outputs
# ---------------------------------------------------------------------------


def test_dcf_inputs_paths_must_align() -> None:
    with pytest.raises(ValidationError, match="same horizon"):
        DCFInputs(
            revenue_base_fact_id="rev_ttm",
            revenue_growth_path=[0.1, 0.1, 0.1],
            margin_path=[0.3, 0.3],
            wacc=0.09,
            terminal_growth=0.025,
            tax_rate=0.21,
        )


def test_sensitivity_inputs_distinct_drivers() -> None:
    base = DCFInputs(
        revenue_base_fact_id="rev_ttm",
        revenue_growth_path=[0.1],
        margin_path=[0.3],
        wacc=0.09,
        terminal_growth=0.025,
        tax_rate=0.21,
    )
    with pytest.raises(ValidationError, match="different drivers"):
        SensitivityInputs(
            base=base,
            row_driver="wacc",
            col_driver="wacc",
            row_values=[0.08, 0.09],
            col_values=[0.08, 0.09],
        )


def test_dcf_result_to_facts_carries_derived_chain() -> None:
    inputs = DCFInputs(
        revenue_base_fact_id="rev_ttm",
        revenue_growth_path=[0.15, 0.12],
        margin_path=[0.30, 0.32],
        wacc=0.09,
        terminal_growth=0.025,
        tax_rate=0.21,
        grounding_fact_ids=["wacc_input", "tax_rate_input"],
    )
    result = DCFResult(enterprise_value=1500.0, equity_value=1400.0, fair_value_per_share=140.0)
    facts = dcf_result_to_facts(result, inputs)
    assert {f.id for f in facts} == {"dcf_enterprise_value", "dcf_fair_value"}
    for f in facts:
        assert isinstance(f.source, ComputedSource)
        assert "rev_ttm" in f.source.derived_from
        assert "wacc_input" in f.source.derived_from


def test_comps_inputs_requires_peers_and_multiples() -> None:
    with pytest.raises(ValidationError):
        CompsInputs(subject_ticker="NVDA", peers=[], multiples=["ev_ebitda"])
    with pytest.raises(ValidationError):
        CompsInputs(
            subject_ticker="NVDA",
            peers=[CompPeer(ticker="AMD", metric_fact_ids={"ev_ebitda": "amd_ev_ebitda"})],
            multiples=[],
        )


# ---------------------------------------------------------------------------
# Outline / Thesis
# ---------------------------------------------------------------------------


def test_report_thesis_rejects_chart_for_unknown_section() -> None:
    with pytest.raises(ValidationError, match="unknown section"):
        ReportThesis(
            language=Language.EN,
            central_argument="growth durable",
            key_takeaways=["beat"],
            valuation_stance="fair",
            valuation_plan=ValuationPlan(methods=[ValuationMethod.DCF]),
            canonical_figures=[CanonicalFigure(fact_id="x", display="1.0x")],
            mandates=[
                SectionMandate(
                    section_id="overview",
                    covers="business overview",
                    does_not_cover="valuation details",
                )
            ],
            charts=[
                ChartSpec(
                    id="ghost_chart",
                    section_id="missing_section",
                    claim="trend up",
                    chart_type=ChartType.LINE,
                    title="Rev trend",
                    category_labels=["Q1", "Q2"],
                    series=[ChartSeries(name="rev", value_fact_ids=["x"])],
                )
            ],
        )


def test_chart_spec_referenced_fact_ids() -> None:
    chart = ChartSpec(
        id="rev_chart",
        section_id="overview",
        claim="revenue rising",
        chart_type=ChartType.LINE,
        title="Revenue",
        category_labels=["Q1", "Q2"],
        series=[
            ChartSeries(name="actual", value_fact_ids=["rev_q1", "rev_q2"]),
            ChartSeries(name="consensus", value_fact_ids=["cons_q1", "cons_q2"]),
        ],
    )
    assert chart.referenced_fact_ids() == {"rev_q1", "rev_q2", "cons_q1", "cons_q2"}


def test_outline_carries_report_type() -> None:
    outline = Outline(
        tickers=["NVDA"],
        report_type=ReportType.INITIATION,
        sections=[OutlineSection(id="overview", title="Overview")],
    )
    assert outline.report_type == ReportType.INITIATION


# ---------------------------------------------------------------------------
# Clarify
# ---------------------------------------------------------------------------


def test_clarify_answers_resolve_falls_back_to_defaults() -> None:
    questions = [
        ClarifyQuestion(
            id="horizon", question="horizon?", why_blocking="affects model", default="12 months"
        ),
        ClarifyQuestion(
            id="audience", question="audience?", why_blocking="affects depth", default="PM"
        ),
    ]
    answers = ClarifyAnswers(answers={"horizon": "24 months"})
    resolved = answers.resolve(questions)
    assert resolved == {"horizon": "24 months", "audience": "PM"}


# ---------------------------------------------------------------------------
# WrittenSection placeholders
# ---------------------------------------------------------------------------


def test_written_section_extracts_placeholder_ids() -> None:
    s = WrittenSection(
        section_id="overview",
        title="Overview",
        body="Revenue rose {{CITE:rev_growth}} as shown in {{FIG:rev_chart}}.",
    )
    assert s.cited_fact_ids() == ["rev_growth"]
    assert s.figure_ids() == ["rev_chart"]


# ---------------------------------------------------------------------------
# Citation rendering
# ---------------------------------------------------------------------------


def test_render_citation_per_provenance_variant() -> None:
    data = BundleFact(id="x", label="X", value=1.0, source=_data_source())
    assert "EODHD" in render_citation(data)
    assert "income_statement" in render_citation(data)

    web = BundleFact(id="w", label="W", value="qual", source=_web_source())
    assert "Example News" in render_citation(web)
    assert "https://example.com/article" in render_citation(web)

    filing = BundleFact(id="f", label="F", value="x", source=_filing_source(page=42))
    assert "10-K" in render_citation(filing)
    assert "p. 42" in render_citation(filing)

    filing_no_page = BundleFact(id="f2", label="F2", value="x", source=_filing_source(page=None))
    assert "p." not in render_citation(filing_no_page)

    computed = BundleFact(
        id="c",
        label="C",
        value=2.0,
        source=ComputedSource(method="EV / EBITDA", derived_from=["x"]),
    )
    assert render_citation(computed) == "Author calculation: EV / EBITDA."


def test_estimate_source_round_trips_through_provenance_union():
    fact = BundleFact(
        id="upside_pct",
        label="Implied upside",
        value=0.10,
        unit="percent",
        source=EstimateSource(
            basis="projection from margin-expansion thesis",
            derived_from=[],
            stage="write",
        ),
    )
    dumped = fact.model_dump_json()
    restored = BundleFact.model_validate_json(dumped)
    assert isinstance(restored.source, EstimateSource)
    assert restored.source.type == SourceType.ESTIMATE
    assert restored.source.basis == "projection from margin-expansion thesis"


def test_render_citation_handles_estimate_source():
    fact = BundleFact(
        id="upside_pct",
        label="Implied upside",
        value=0.10,
        unit="percent",
        source=EstimateSource(
            basis="margin-expansion thesis",
            derived_from=[],
            stage="write",
        ),
    )
    assert render_citation(fact) == "Estimate: margin-expansion thesis."


def test_estimate_source_records_derived_from_when_supplied():
    fact = BundleFact(
        id="upside_to_target",
        label="Upside to target",
        value=0.15,
        unit="percent",
        source=EstimateSource(
            basis="target $120 vs current price",
            derived_from=["price_target", "px_last"],
            stage="write",
        ),
    )
    assert fact.source.derived_from == ["price_target", "px_last"]


def test_research_bundle_rejects_estimate_with_dangling_derived_from():
    """EstimateSource.derived_from must be subject to the same integrity
    check as ComputedSource.derived_from — dangling fact_ids should fail
    bundle construction."""
    bad_fact = BundleFact(
        id="upside_to_target",
        label="Upside to target",
        value=0.15,
        unit="percent",
        source=EstimateSource(
            basis="target $120 vs current price",
            derived_from=["nonexistent_fact"],
            stage="write",
        ),
    )
    with pytest.raises(ValueError, match="derives from missing facts"):
        ResearchBundle(tickers=["NVDA"], facts={"upside_to_target": bad_fact})


# ---------------------------------------------------------------------------
# resolve() — the deterministic ASSEMBLE pass
# ---------------------------------------------------------------------------


def _bundle_with(*facts: BundleFact) -> ResearchBundle:
    return ResearchBundle(tickers=["NVDA"], facts={f.id: f for f in facts})


def _chart(chart_id: str, section_id: str, fact_id: str) -> ChartSpec:
    return ChartSpec(
        id=chart_id,
        section_id=section_id,
        claim="claim",
        chart_type=ChartType.LINE,
        title="t",
        category_labels=["a"],
        series=[ChartSeries(name="s", value_fact_ids=[fact_id])],
    )


def test_resolve_numbers_figures_and_footnotes_in_document_order() -> None:
    fact_a = BundleFact(id="a", label="A", value=1.0, source=_data_source())
    fact_b = BundleFact(id="b", label="B", value=2.0, source=_data_source())
    bundle = _bundle_with(fact_a, fact_b)

    chart_a = _chart("chart_a", "s1", "a")
    chart_b = _chart("chart_b", "s2", "b")

    s1 = WrittenSection(
        section_id="s1", title="S1", body="A is {{CITE:a}} and see {{FIG:chart_a}}."
    )
    s2 = WrittenSection(
        section_id="s2", title="S2", body="B is {{CITE:b}} and see {{FIG:chart_b}}."
    )

    resolved = resolve([s1, s2], bundle, [chart_a, chart_b], ["s1", "s2"])

    assert resolved.figure_labels == {"chart_a": 1, "chart_b": 2}
    assert "[^1]" in resolved.section_bodies["s1"]
    assert "Figure 1" in resolved.section_bodies["s1"]
    assert "[^2]" in resolved.section_bodies["s2"]
    assert "Figure 2" in resolved.section_bodies["s2"]
    assert len(resolved.footnotes) == 2


def test_resolve_dedupes_footnotes_for_same_fact_id() -> None:
    fact_a = BundleFact(id="a", label="A", value=1.0, source=_data_source())
    bundle = _bundle_with(fact_a)
    s1 = WrittenSection(section_id="s1", title="S1", body="X {{CITE:a}} and again {{CITE:a}}.")
    resolved = resolve([s1], bundle, [], ["s1"])
    assert resolved.section_bodies["s1"].count("[^1]") == 2
    assert len(resolved.footnotes) == 1


def test_resolve_raises_on_dangling_citation() -> None:
    bundle = _bundle_with(BundleFact(id="a", label="A", value=1.0, source=_data_source()))
    s1 = WrittenSection(section_id="s1", title="S1", body="ghost {{CITE:nope}}")
    with pytest.raises(ValueError, match="Dangling citation"):
        resolve([s1], bundle, [], ["s1"])


def test_resolve_raises_on_unknown_figure_ref() -> None:
    bundle = _bundle_with(BundleFact(id="a", label="A", value=1.0, source=_data_source()))
    s1 = WrittenSection(section_id="s1", title="S1", body="see {{FIG:ghost}}")
    with pytest.raises(ValueError, match="no ChartSpec"):
        resolve([s1], bundle, [], ["s1"])


def test_derive_re_matches_three_pipe_separated_fields():
    body = "Revenue grew {{DERIVE:growth_rate|rev_fy25,rev_fy24|rev_growth_yoy}} year over year."
    matches = DERIVE_RE.findall(body)
    assert matches == [("growth_rate", "rev_fy25,rev_fy24", "rev_growth_yoy")]


def test_derive_re_rejects_uppercase_method_name():
    # Methods are lowercase identifiers; uppercase should not match.
    body = "X {{DERIVE:GROWTH_RATE|a,b|c}}"
    assert DERIVE_RE.findall(body) == []


def test_estimate_re_matches_four_pipe_separated_fields():
    body = (
        "We see {{ESTIMATE:upside_pct|0.10|percent|"
        "projection from margin-expansion thesis}} of upside."
    )
    matches = ESTIMATE_RE.findall(body)
    assert matches == [
        ("upside_pct", "0.10", "percent", "projection from margin-expansion thesis")
    ]


def test_estimate_re_accepts_empty_unit():
    body = "{{ESTIMATE:rating_score|7.5||composite of qual factors}}"
    matches = ESTIMATE_RE.findall(body)
    assert matches == [("rating_score", "7.5", "", "composite of qual factors")]


def test_estimate_re_accepts_negative_values():
    body = "{{ESTIMATE:downside_pct|-0.15|percent|bear case 12mo}}"
    matches = ESTIMATE_RE.findall(body)
    assert matches == [("downside_pct", "-0.15", "percent", "bear case 12mo")]
