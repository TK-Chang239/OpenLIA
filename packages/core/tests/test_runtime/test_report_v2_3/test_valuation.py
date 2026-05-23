"""Unit tests for the deterministic valuation math (dcf, comps, sensitivity)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from openlia.llm.runtime.report_v2_3.schemas import (
    BundleFact,
    CompPeer,
    CompsInputs,
    DataProviderSource,
    DCFInputs,
    ResearchBundle,
    SensitivityInputs,
)
from openlia.llm.runtime.report_v2_3.valuation import (
    comps,
    comps_result_to_facts,
    dcf,
    sensitivity,
    sensitivity_result_to_fact,
)


def _src() -> DataProviderSource:
    return DataProviderSource(
        provider="EODHD",
        endpoint="fundamentals/income_statement",
        period="TTM",
        retrieved_at=datetime.now(UTC),
    )


def _scalar(fact_id: str, value: float) -> BundleFact:
    return BundleFact(id=fact_id, label=fact_id, value=value, source=_src())


# ---------------------------------------------------------------------------
# DCF
# ---------------------------------------------------------------------------


def test_dcf_matches_hand_computed_value() -> None:
    bundle = ResearchBundle(tickers=["NVDA"], facts={"rev_ttm": _scalar("rev_ttm", 100.0)})
    inputs = DCFInputs(
        revenue_base_fact_id="rev_ttm",
        revenue_growth_path=[0.10, 0.10],
        margin_path=[0.30, 0.30],
        wacc=0.10,
        terminal_growth=0.02,
        tax_rate=0.20,
    )
    # Year 1: rev = 110, FCF = 110*0.3*0.8 = 26.4 -> PV = 26.4/1.1 = 24.0
    # Year 2: rev = 121, FCF = 29.04 -> PV = 29.04/1.21 = 24.0
    # Terminal: FCF2*(1.02)/(0.10-0.02) = 29.04*1.02/0.08 = 370.26
    #   discounted: 370.26/1.21 = 306.00
    # EV = 24.0 + 24.0 + 306.00 = 354.00
    result = dcf(inputs, bundle)
    assert result.enterprise_value == pytest.approx(354.0, abs=0.5)
    # Without net_debt/shares grounding, equity = EV, fair value per share = EV.
    assert result.equity_value == result.enterprise_value
    assert result.fair_value_per_share == result.enterprise_value


def test_dcf_grounds_per_share_with_net_debt_and_shares() -> None:
    bundle = ResearchBundle(
        tickers=["NVDA"],
        facts={
            "rev_ttm": _scalar("rev_ttm", 100.0),
            "net_debt": _scalar("net_debt", 50.0),
            "shares_outstanding": _scalar("shares_outstanding", 10.0),
        },
    )
    inputs = DCFInputs(
        revenue_base_fact_id="rev_ttm",
        revenue_growth_path=[0.10, 0.10],
        margin_path=[0.30, 0.30],
        wacc=0.10,
        terminal_growth=0.02,
        tax_rate=0.20,
        grounding_fact_ids=["net_debt", "shares_outstanding"],
    )
    result = dcf(inputs, bundle)
    assert result.equity_value == pytest.approx(result.enterprise_value - 50.0, abs=0.5)
    assert result.fair_value_per_share == pytest.approx(result.equity_value / 10.0, abs=0.05)


def test_dcf_rejects_terminal_ge_wacc() -> None:
    bundle = ResearchBundle(tickers=["NVDA"], facts={"rev_ttm": _scalar("rev_ttm", 100.0)})
    inputs = DCFInputs(
        revenue_base_fact_id="rev_ttm",
        revenue_growth_path=[0.10],
        margin_path=[0.30],
        wacc=0.05,
        terminal_growth=0.05,
        tax_rate=0.20,
    )
    with pytest.raises(RuntimeError, match="wacc"):
        dcf(inputs, bundle)


def test_dcf_rejects_missing_revenue_base() -> None:
    bundle = ResearchBundle(tickers=["NVDA"], facts={"x": _scalar("x", 1.0)})
    inputs = DCFInputs(
        revenue_base_fact_id="not_in_bundle",
        revenue_growth_path=[0.10],
        margin_path=[0.30],
        wacc=0.10,
        terminal_growth=0.02,
        tax_rate=0.20,
    )
    with pytest.raises(RuntimeError, match="revenue base fact"):
        dcf(inputs, bundle)


# ---------------------------------------------------------------------------
# Comps
# ---------------------------------------------------------------------------


def test_comps_applies_median_peer_multiple() -> None:
    bundle = ResearchBundle(
        tickers=["NVDA"],
        facts={
            "amd_ev_ebitda": _scalar("amd_ev_ebitda", 12.0),
            "intc_ev_ebitda": _scalar("intc_ev_ebitda", 10.0),
            "subj_ebitda": _scalar("subj_ebitda", 50.0),
        },
    )
    inputs = CompsInputs(
        subject_ticker="NVDA",
        peers=[
            CompPeer(ticker="AMD", metric_fact_ids={"ev_ebitda": "amd_ev_ebitda"}),
            CompPeer(ticker="INTC", metric_fact_ids={"ev_ebitda": "intc_ev_ebitda"}),
        ],
        multiples=["ev_ebitda"],
        subject_metric_fact_ids={"ev_ebitda": "subj_ebitda"},
    )
    result = comps(inputs, bundle)
    # Median peer ev_ebitda = (12+10)/2 = 11.0; subject_ebitda = 50.0
    # Implied value = 11.0 * 50.0 = 550.0
    assert result.implied_value_by_multiple == {"ev_ebitda": pytest.approx(550.0)}
    assert result.peer_table == [{"ev_ebitda": 12.0}, {"ev_ebitda": 10.0}]


def test_comps_skips_multiples_with_no_subject_metric() -> None:
    bundle = ResearchBundle(
        tickers=["NVDA"],
        facts={"amd_pe": _scalar("amd_pe", 30.0)},
    )
    inputs = CompsInputs(
        subject_ticker="NVDA",
        peers=[CompPeer(ticker="AMD", metric_fact_ids={"pe": "amd_pe"})],
        multiples=["pe"],
        subject_metric_fact_ids={},  # no subject metric provided
    )
    result = comps(inputs, bundle)
    assert result.implied_value_by_multiple == {}


def test_comps_result_to_facts_carries_derived_chain() -> None:
    bundle = ResearchBundle(
        tickers=["NVDA"],
        facts={
            "amd_pe": _scalar("amd_pe", 30.0),
            "subj_eps": _scalar("subj_eps", 5.0),
        },
    )
    inputs = CompsInputs(
        subject_ticker="NVDA",
        peers=[CompPeer(ticker="AMD", metric_fact_ids={"pe": "amd_pe"})],
        multiples=["pe"],
        subject_metric_fact_ids={"pe": "subj_eps"},
    )
    result = comps(inputs, bundle)
    facts = comps_result_to_facts(result, inputs)
    assert len(facts) == 1
    assert facts[0].id == "comps_implied_pe"
    assert facts[0].value == pytest.approx(150.0)  # 30 * 5
    assert {"amd_pe", "subj_eps"} <= set(facts[0].source.derived_from)


# ---------------------------------------------------------------------------
# Sensitivity
# ---------------------------------------------------------------------------


def test_sensitivity_grid_dimensions_and_monotonicity() -> None:
    bundle = ResearchBundle(tickers=["NVDA"], facts={"rev_ttm": _scalar("rev_ttm", 100.0)})
    base = DCFInputs(
        revenue_base_fact_id="rev_ttm",
        revenue_growth_path=[0.10, 0.10],
        margin_path=[0.30, 0.30],
        wacc=0.10,
        terminal_growth=0.02,
        tax_rate=0.20,
    )
    inputs = SensitivityInputs(
        base=base,
        row_driver="wacc",
        col_driver="terminal_growth",
        row_values=[0.09, 0.10, 0.11],
        col_values=[0.01, 0.02, 0.03],
    )
    result = sensitivity(inputs, bundle)
    assert len(result.grid) == 3
    for row in result.grid:
        assert len(row) == 3

    # Fair value should be monotonically *decreasing* in WACC at fixed
    # terminal growth — higher discount rate, lower PV.
    for col in range(3):
        column_values = [result.grid[r][col] for r in range(3)]
        assert column_values == sorted(column_values, reverse=True), column_values

    # And *increasing* in terminal growth at fixed WACC.
    for row in range(3):
        assert result.grid[row] == sorted(result.grid[row])


def test_sensitivity_result_to_fact_returns_single_unit() -> None:
    """Locked design: ONE fact for the whole grid, not N."""
    bundle = ResearchBundle(tickers=["NVDA"], facts={"rev_ttm": _scalar("rev_ttm", 100.0)})
    base = DCFInputs(
        revenue_base_fact_id="rev_ttm",
        revenue_growth_path=[0.10],
        margin_path=[0.30],
        wacc=0.10,
        terminal_growth=0.02,
        tax_rate=0.20,
    )
    inputs = SensitivityInputs(
        base=base,
        row_driver="wacc",
        col_driver="terminal_growth",
        row_values=[0.09, 0.10],
        col_values=[0.01, 0.02],
    )
    fact = sensitivity_result_to_fact(sensitivity(inputs, bundle), inputs)
    assert fact.id == "sensitivity_grid"
    assert "wacc" in fact.label
    assert "rev_ttm" in fact.source.derived_from
