"""Regression tests for the PR10 self-review findings.

1. SynthesizeStage must reject a mandate that references a chart_id not in
   thesis.charts. Without this, WriteStage would let writers emit
   {{FIG:phantom}} (writer figs subset of mandate.chart_ids = {phantom}),
   and ASSEMBLE's resolve() would raise late instead of early.

2. ComputeStage must reject duplicate fact ids — both within a single
   COMPUTE call and against the existing bundle. A silent dict-merge
   overwrite would defeat the ResearchBundle uniqueness invariant.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from openlia.llm.runtime.report_v2_3.clients.compute import FakeComputeClient
from openlia.llm.runtime.report_v2_3.clients.synthesizer import FakeSynthesizerClient
from openlia.llm.runtime.report_v2_3.schemas import (
    BundleFact,
    CanonicalFigure,
    ChartSeries,
    ChartSpec,
    ChartType,
    ComputedSource,
    DataProviderSource,
    DCFInputs,
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
from openlia.llm.runtime.report_v2_3.stages import (
    ComputeStage,
    StageContext,
    SynthesizeStage,
)
from openlia.llm.runtime.report_v2_3.state import ReportState


def _src() -> DataProviderSource:
    return DataProviderSource(
        provider="EODHD",
        endpoint="fundamentals/income_statement",
        period="TTM",
        retrieved_at=datetime.now(UTC),
    )


def _ctx() -> StageContext:
    return StageContext(clients={}, tools={}, extras={})


# ---------------------------------------------------------------------------
# Issue 1: SynthesizeStage rejects mandate referencing a phantom chart
# ---------------------------------------------------------------------------


def _state_for_synth() -> ReportState:
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
        facts={
            "rev_ttm": BundleFact(id="rev_ttm", label="Revenue TTM", value=100.0, source=_src()),
        },
    )
    s.outline = Outline(
        tickers=["NVDA"],
        report_type=ReportType.INITIATION,
        sections=[OutlineSection(id="overview", title="Overview")],
    )
    return s


def test_synthesize_rejects_mandate_referencing_phantom_chart() -> None:
    thesis = ReportThesis(
        language=Language.EN,
        central_argument="growth",
        key_takeaways=["x"],
        valuation_stance="fair",
        valuation_plan=ValuationPlan(),
        canonical_figures=[CanonicalFigure(fact_id="rev_ttm", display="$100M")],
        mandates=[
            SectionMandate(
                section_id="overview",
                covers="business",
                does_not_cover="financials",
                chart_ids=["ghost_chart"],  # not in thesis.charts
                relevant_fact_ids=["rev_ttm"],
            )
        ],
        charts=[],  # empty — no chart spec for ghost_chart
    )
    with pytest.raises(RuntimeError, match="unknown charts"):
        SynthesizeStage(FakeSynthesizerClient(result=thesis)).run(_state_for_synth(), _ctx())


def test_synthesize_accepts_mandate_with_valid_chart_id() -> None:
    """Sanity-check: when mandate.chart_ids matches a real ChartSpec.id, no error."""
    thesis = ReportThesis(
        language=Language.EN,
        central_argument="growth",
        key_takeaways=["x"],
        valuation_stance="fair",
        valuation_plan=ValuationPlan(),
        canonical_figures=[CanonicalFigure(fact_id="rev_ttm", display="$100M")],
        mandates=[
            SectionMandate(
                section_id="overview",
                covers="business",
                does_not_cover="financials",
                chart_ids=["rev_chart"],
                relevant_fact_ids=["rev_ttm"],
            )
        ],
        charts=[
            ChartSpec(
                id="rev_chart",
                section_id="overview",
                claim="revenue rising",
                chart_type=ChartType.LINE,
                title="Revenue",
                category_labels=["Q1"],
                series=[ChartSeries(name="rev", value_fact_ids=["rev_ttm"])],
            )
        ],
    )
    state = SynthesizeStage(FakeSynthesizerClient(result=thesis)).run(
        _state_for_synth(), _ctx()
    )
    assert state.thesis is thesis


# ---------------------------------------------------------------------------
# Issue 2: ComputeStage rejects duplicate fact ids
# ---------------------------------------------------------------------------


def _state_for_compute() -> ReportState:
    s = ReportState(
        run_id="r",
        user_id="u",
        raw_prompt="initiate on NVDA",
        language=Language.EN,
        report_type=ReportType.INITIATION,
        tickers=["NVDA"],
    )
    rev_fact = BundleFact(id="rev_ttm", label="Revenue TTM", value=100.0, source=_src())
    s.bundle = ResearchBundle(tickers=["NVDA"], facts={"rev_ttm": rev_fact})
    s.outline = Outline(
        tickers=["NVDA"],
        report_type=ReportType.INITIATION,
        sections=[OutlineSection(id="overview", title="Overview")],
        valuation_plan=ValuationPlan(methods=[ValuationMethod.DCF]),
    )
    return s


def test_compute_rejects_fact_id_colliding_with_existing_bundle() -> None:
    """If COMPUTE produces a fact whose id already exists in the bundle —
    e.g. RESEARCH (in PR11+) had already produced a 'dcf_fair_value' from
    a third-party source — we must NOT silently overwrite it."""
    state = _state_for_compute()
    state.bundle = ResearchBundle(
        tickers=["NVDA"],
        facts={
            "rev_ttm": state.bundle.facts["rev_ttm"],
            # Pre-seed a fact with the same id COMPUTE would produce.
            "dcf_fair_value": BundleFact(
                id="dcf_fair_value",
                label="Pre-existing DCF",
                value=999.0,
                source=ComputedSource(method="external", derived_from=["rev_ttm"]),
            ),
        },
    )

    inputs = DCFInputs(
        revenue_base_fact_id="rev_ttm",
        revenue_growth_path=[0.10],
        margin_path=[0.30],
        wacc=0.10,
        terminal_growth=0.02,
        tax_rate=0.20,
    )
    fake = FakeComputeClient(inputs_by_method={ValuationMethod.DCF: inputs})

    with pytest.raises(RuntimeError, match="collides with an existing bundle fact"):
        ComputeStage(fake).run(state, _ctx())


def test_compute_rejects_duplicate_fact_id_within_one_call() -> None:
    """If a future client-driven decomposition emitted two facts with the
    same id within a single COMPUTE call, that must also fail loud rather
    than letting one silently win."""

    def _responder(req) -> object:
        # Returning the same DCFInputs twice via methods=[DCF, DCF] would
        # produce dcf_fair_value twice. But the schema doesn't allow that
        # ordering. Instead we patch _run_method indirectly by returning
        # two methods that both decompose to a colliding id — for now,
        # the within-call collision path is exercised by configuring the
        # plan to request DCF twice via duplicate methods in the list.
        raise NotImplementedError  # unused; we use inputs_by_method below

    # Plan with two DCF entries — both produce 'dcf_fair_value' + 'dcf_enterprise_value'.
    state = _state_for_compute()
    state.outline = Outline(
        tickers=["NVDA"],
        report_type=ReportType.INITIATION,
        sections=[OutlineSection(id="overview", title="Overview")],
        valuation_plan=ValuationPlan(methods=[ValuationMethod.DCF, ValuationMethod.DCF]),
    )

    inputs = DCFInputs(
        revenue_base_fact_id="rev_ttm",
        revenue_growth_path=[0.10],
        margin_path=[0.30],
        wacc=0.10,
        terminal_growth=0.02,
        tax_rate=0.20,
    )
    fake = FakeComputeClient(inputs_by_method={ValuationMethod.DCF: inputs})

    with pytest.raises(RuntimeError, match="duplicate fact id"):
        ComputeStage(fake).run(state, _ctx())
