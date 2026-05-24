"""Unit tests for ComputeStage — plan dispatch + bundle augmentation."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from openlia.llm.runtime.report_v2_3.clients.compute import (
    ComputeRequest,
    FakeComputeClient,
)
from openlia.llm.runtime.report_v2_3.schemas import (
    BundleFact,
    CompPeer,
    CompsInputs,
    ComputedSource,
    DataProviderSource,
    DCFInputs,
    Language,
    Outline,
    OutlineSection,
    ReportType,
    ResearchBundle,
    ValuationMethod,
    ValuationPlan,
)
from openlia.llm.runtime.report_v2_3.stages import ComputeStage, StageContext
from openlia.llm.runtime.report_v2_3.state import ReportState
from openlia.llm.runtime.report_v2_3.templates import get_builtin


def _src() -> DataProviderSource:
    return DataProviderSource(
        provider="EODHD",
        endpoint="fundamentals/income_statement",
        period="TTM",
        retrieved_at=datetime.now(UTC),
    )


def _scalar(fact_id: str, value: float) -> BundleFact:
    return BundleFact(id=fact_id, label=fact_id, value=value, source=_src())


def _state(
    *,
    methods: list[ValuationMethod] | None = None,
    extra_facts: dict[str, BundleFact] | None = None,
) -> ReportState:
    facts = {"rev_ttm": _scalar("rev_ttm", 100.0)}
    if extra_facts:
        facts.update(extra_facts)
    s = ReportState(
        run_id="r",
        user_id="u",
        raw_prompt="initiate on NVDA",
        language=Language.EN,
        report_type=ReportType.INITIATION,
        tickers=["NVDA"],
        template=get_builtin(ReportType.INITIATION),
    )
    s.bundle = ResearchBundle(tickers=["NVDA"], facts=facts)
    s.outline = Outline(
        tickers=["NVDA"],
        report_type=ReportType.INITIATION,
        sections=[OutlineSection(id="overview", title="Overview")],
        valuation_plan=ValuationPlan(methods=methods or []),
    )
    return s


def _ctx() -> StageContext:
    return StageContext(clients={}, tools={}, extras={})


def _dcf_inputs() -> DCFInputs:
    return DCFInputs(
        revenue_base_fact_id="rev_ttm",
        revenue_growth_path=[0.10, 0.10],
        margin_path=[0.30, 0.30],
        wacc=0.10,
        terminal_growth=0.02,
        tax_rate=0.20,
    )


# ---------------------------------------------------------------------------
# Graceful no-op
# ---------------------------------------------------------------------------


def test_empty_valuation_plan_is_noop() -> None:
    fake = FakeComputeClient(inputs_by_method={})
    state = ComputeStage(fake).run(_state(methods=[]), _ctx())
    # Bundle unchanged.
    assert set(state.bundle.facts.keys()) == {"rev_ttm"}
    assert fake.calls == []


# ---------------------------------------------------------------------------
# DCF method
# ---------------------------------------------------------------------------


def test_dcf_method_adds_facts_to_bundle() -> None:
    fake = FakeComputeClient(inputs_by_method={ValuationMethod.DCF: _dcf_inputs()})
    state = ComputeStage(fake).run(_state(methods=[ValuationMethod.DCF]), _ctx())

    assert "dcf_enterprise_value" in state.bundle.facts
    assert "dcf_fair_value" in state.bundle.facts
    assert isinstance(state.bundle.facts["dcf_fair_value"].source, ComputedSource)
    assert len(fake.calls) == 1
    request = fake.calls[0]
    assert isinstance(request, ComputeRequest)
    assert request.method == ValuationMethod.DCF


# ---------------------------------------------------------------------------
# Comps method
# ---------------------------------------------------------------------------


def test_comps_method_adds_per_multiple_facts() -> None:
    extra = {
        "amd_pe": _scalar("amd_pe", 30.0),
        "intc_pe": _scalar("intc_pe", 26.0),
        "subj_eps": _scalar("subj_eps", 5.0),
    }
    state = _state(methods=[ValuationMethod.COMPS], extra_facts=extra)
    inputs = CompsInputs(
        subject_ticker="NVDA",
        peers=[
            CompPeer(ticker="AMD", metric_fact_ids={"pe": "amd_pe"}),
            CompPeer(ticker="INTC", metric_fact_ids={"pe": "intc_pe"}),
        ],
        multiples=["pe"],
        subject_metric_fact_ids={"pe": "subj_eps"},
    )
    fake = FakeComputeClient(inputs_by_method={ValuationMethod.COMPS: inputs})
    state = ComputeStage(fake).run(state, _ctx())
    assert "comps_implied_pe" in state.bundle.facts


# ---------------------------------------------------------------------------
# Multiple methods in one run
# ---------------------------------------------------------------------------


def test_multiple_methods_dispatch_in_plan_order() -> None:
    extra = {
        "amd_pe": _scalar("amd_pe", 30.0),
        "subj_eps": _scalar("subj_eps", 5.0),
    }
    state = _state(
        methods=[ValuationMethod.DCF, ValuationMethod.COMPS],
        extra_facts=extra,
    )
    fake = FakeComputeClient(
        inputs_by_method={
            ValuationMethod.DCF: _dcf_inputs(),
            ValuationMethod.COMPS: CompsInputs(
                subject_ticker="NVDA",
                peers=[CompPeer(ticker="AMD", metric_fact_ids={"pe": "amd_pe"})],
                multiples=["pe"],
                subject_metric_fact_ids={"pe": "subj_eps"},
            ),
        }
    )
    state = ComputeStage(fake).run(state, _ctx())
    assert "dcf_fair_value" in state.bundle.facts
    assert "comps_implied_pe" in state.bundle.facts
    methods_called = [c.method for c in fake.calls]
    assert methods_called == [ValuationMethod.DCF, ValuationMethod.COMPS]


# ---------------------------------------------------------------------------
# Type guard: wrong inputs for method
# ---------------------------------------------------------------------------


def test_dcf_method_rejects_non_dcf_inputs(caplog) -> None:
    # The per-method tolerance added for graceful-degradation now catches
    # the type-mismatch RuntimeError, logs a warning, and continues. The
    # bundle should be untouched (no facts from a malformed run).
    bad = CompsInputs(
        subject_ticker="NVDA",
        peers=[CompPeer(ticker="AMD", metric_fact_ids={"pe": "amd_pe"})],
        multiples=["pe"],
    )
    fake = FakeComputeClient(inputs_by_method={ValuationMethod.DCF: bad})
    state = _state(methods=[ValuationMethod.DCF])
    bundle_before = state.bundle
    with caplog.at_level("WARNING"):
        result = ComputeStage(fake).run(state, _ctx())
    assert "COMPUTE/dcf skipped" in caplog.text
    assert "DCFInputs" in caplog.text
    # Bundle is rebuilt each run for validation, but the fact set is
    # unchanged because the skipped method produced no new facts.
    assert result.bundle is not None and bundle_before is not None
    assert result.bundle.facts == bundle_before.facts


# ---------------------------------------------------------------------------
# Preconditions
# ---------------------------------------------------------------------------


def test_missing_outline_raises() -> None:
    state = _state(methods=[ValuationMethod.DCF])
    state.outline = None
    fake = FakeComputeClient(inputs_by_method={ValuationMethod.DCF: _dcf_inputs()})
    with pytest.raises(RuntimeError, match=r"state\.outline"):
        ComputeStage(fake).run(state, _ctx())


def test_missing_bundle_raises() -> None:
    state = _state(methods=[ValuationMethod.DCF])
    state.bundle = None
    fake = FakeComputeClient(inputs_by_method={ValuationMethod.DCF: _dcf_inputs()})
    with pytest.raises(RuntimeError, match=r"state\.bundle"):
        ComputeStage(fake).run(state, _ctx())
