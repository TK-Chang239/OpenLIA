"""Tests for `facts.helpers.valuation`."""

from __future__ import annotations

from datetime import date

import pytest
from openlia.llm.runtime.report_v2.facts.helpers.valuation import (
    dcf_intrinsic_value,
    football_field,
    historical_pe_band,
    peer_multiple_implied_range,
    peg_ratio_correct,
    reverse_dcf,
    sensitivity_grid,
    sum_of_parts,
)

# -- peer_multiple_implied_range -------------------------------------------


def test_peer_multiple_implied_range_typical() -> None:
    out = peer_multiple_implied_range(
        subject_eps=5.0,
        subject_ebitda=200.0,
        subject_revenue=1000.0,
        peer_pe_dict={"A": 10.0, "B": 20.0, "C": 30.0},
        peer_ev_ebitda_dict={"A": 8.0, "B": 12.0},
        peer_ev_sales_dict=None,
    )
    assert out["pe_implied"]["low"] == pytest.approx(50.0)
    assert out["pe_implied"]["high"] == pytest.approx(150.0)
    assert out["pe_implied"]["median"] == pytest.approx(100.0)
    assert out["ev_ebitda_implied"]["low"] == pytest.approx(1600.0)
    assert out["ev_sales_implied"] is None


def test_peer_multiple_implied_range_none_inputs() -> None:
    out = peer_multiple_implied_range(
        subject_eps=None,
        subject_ebitda=None,
        subject_revenue=None,
        peer_pe_dict={"A": 10.0},
        peer_ev_ebitda_dict={},
    )
    assert out["pe_implied"] is None
    assert out["ev_ebitda_implied"] is None


# -- historical_pe_band -----------------------------------------------------


def test_historical_pe_band_typical() -> None:
    series = [(date(2025, 1, 1), 20.0), (date(2025, 6, 1), 25.0), (date(2025, 12, 1), 30.0)]
    out = historical_pe_band(series, current_pe=25.0, window_years=5)
    assert out["mean"] == pytest.approx(25.0)
    assert out["std"] > 0
    assert 0.0 <= out["current_percentile"] <= 1.0
    assert out["current_z_score"] == pytest.approx(0.0)


def test_historical_pe_band_empty_raises() -> None:
    with pytest.raises(ValueError):
        historical_pe_band([], current_pe=25.0)


# -- peg_ratio_correct ------------------------------------------------------


def test_peg_ratio_correct_typical() -> None:
    # PE 30, EPS growth 25% → PEG = 30/25 = 1.2
    assert peg_ratio_correct(forward_pe=30.0, forward_eps_growth_pct=25.0) == pytest.approx(1.2)


def test_peg_ratio_correct_none_growth_returns_none() -> None:
    assert peg_ratio_correct(forward_pe=30.0, forward_eps_growth_pct=None) is None


def test_peg_ratio_correct_zero_growth_returns_none() -> None:
    assert peg_ratio_correct(forward_pe=30.0, forward_eps_growth_pct=0.0) is None


def test_peg_ratio_correct_rejects_revenue_cagr_like_input() -> None:
    # A 250% "growth" almost certainly means someone passed a CAGR or wrong unit.
    with pytest.raises(ValueError):
        peg_ratio_correct(forward_pe=30.0, forward_eps_growth_pct=250.0)


# -- dcf_intrinsic_value ----------------------------------------------------


def test_dcf_intrinsic_value_known_inputs() -> None:
    # Hand-computed scenario: 5-year flat $100 revenue, 20% EBIT margin,
    # 0% tax, no capex, no NWC change. EBIT = $20/yr, FCFF = $20/yr.
    # WACC 10%, g 0%. PV explicit = 20 * (1 - 1.1^-5) / 0.1 = 75.8157...
    # Terminal: FCFF6 = 20, TV = 20 / 0.1 = 200, PV = 200 / 1.1^5 = 124.18...
    # EV ≈ 199.99; ÷ 1 share = $199.99
    out = dcf_intrinsic_value(
        forward_revenue_path=[100.0] * 5,
        ebit_margin_path=[0.20] * 5,
        tax_rate=0.0,
        capex_pct_of_revenue=0.0,
        change_in_nwc_pct_of_revenue_change=0.0,
        terminal_growth=0.0,
        wacc=0.10,
        shares_outstanding=1.0,
    )
    pv_explicit_expected = sum(20.0 / (1.10**t) for t in range(1, 6))
    tv_expected = 20.0 / 0.10
    pv_tv_expected = tv_expected / (1.10**5)
    expected = pv_explicit_expected + pv_tv_expected
    assert out["intrinsic_value_per_share"] == pytest.approx(expected, rel=1e-3)
    assert out["pv_explicit"] == pytest.approx(pv_explicit_expected, rel=1e-3)
    assert out["terminal_value"] == pytest.approx(tv_expected, rel=1e-3)
    assert len(out["fcff_path"]) == 5
    assert out["sensitivity_grid"]  # nonempty


def test_dcf_intrinsic_value_wacc_out_of_bounds() -> None:
    with pytest.raises(ValueError):
        dcf_intrinsic_value(
            forward_revenue_path=[100.0] * 5,
            ebit_margin_path=[0.20] * 5,
            tax_rate=0.0,
            capex_pct_of_revenue=0.0,
            change_in_nwc_pct_of_revenue_change=0.0,
            terminal_growth=0.0,
            wacc=0.04,  # below floor
            shares_outstanding=1.0,
        )


def test_dcf_intrinsic_value_terminal_growth_out_of_bounds() -> None:
    with pytest.raises(ValueError):
        dcf_intrinsic_value(
            forward_revenue_path=[100.0] * 5,
            ebit_margin_path=[0.20] * 5,
            tax_rate=0.0,
            capex_pct_of_revenue=0.0,
            change_in_nwc_pct_of_revenue_change=0.0,
            terminal_growth=0.05,  # above ceiling
            wacc=0.10,
            shares_outstanding=1.0,
        )


def test_dcf_intrinsic_value_short_path_raises() -> None:
    with pytest.raises(ValueError):
        dcf_intrinsic_value(
            forward_revenue_path=[100.0] * 3,
            ebit_margin_path=[0.20] * 3,
            tax_rate=0.0,
            capex_pct_of_revenue=0.0,
            change_in_nwc_pct_of_revenue_change=0.0,
            terminal_growth=0.0,
            wacc=0.10,
            shares_outstanding=1.0,
        )


def test_dcf_intrinsic_value_mismatched_paths_raises() -> None:
    with pytest.raises(ValueError):
        dcf_intrinsic_value(
            forward_revenue_path=[100.0] * 5,
            ebit_margin_path=[0.20] * 4,
            tax_rate=0.0,
            capex_pct_of_revenue=0.0,
            change_in_nwc_pct_of_revenue_change=0.0,
            terminal_growth=0.0,
            wacc=0.10,
            shares_outstanding=1.0,
        )


# -- sum_of_parts ----------------------------------------------------------


def test_sum_of_parts_typical() -> None:
    out = sum_of_parts(
        segment_revenue_dict={"A": 100.0, "B": 200.0},
        segment_multiple_dict={"A": 5.0, "B": 3.0},
    )
    assert out["total_ev"] == pytest.approx(500.0 + 600.0)
    assert out["ev_by_segment"]["A"] == 500.0
    assert len(out["breakdown"]) == 2


def test_sum_of_parts_skips_segment_without_multiple() -> None:
    out = sum_of_parts({"A": 100.0, "B": 200.0}, {"A": 5.0})
    assert "B" not in out["ev_by_segment"]
    assert out["total_ev"] == 500.0


# -- reverse_dcf -----------------------------------------------------------


def test_reverse_dcf_solves_for_growth() -> None:
    out = reverse_dcf(
        current_price=100.0,
        shares_outstanding=1.0,
        current_fcf=5.0,
        wacc=0.10,
        terminal_growth=0.02,
        years=10,
    )
    g = out["implied_growth_rate"]
    assert -0.10 < g < 0.50
    # Sanity: at the implied g, our EV computation reproduces the target.
    pv = 0.0
    fcf = 5.0
    for t in range(1, 11):
        fcf *= 1.0 + g
        pv += fcf / (1.10**t)
    tv = fcf * 1.02 / (0.10 - 0.02)
    pv += tv / (1.10**10)
    assert pv == pytest.approx(100.0, rel=1e-2)


def test_reverse_dcf_nonpositive_fcf_raises() -> None:
    with pytest.raises(ValueError):
        reverse_dcf(
            current_price=100.0,
            shares_outstanding=1.0,
            current_fcf=0.0,
            wacc=0.10,
            terminal_growth=0.02,
        )


# -- football_field --------------------------------------------------------


def test_football_field_three_methods() -> None:
    out = football_field(
        {
            "peer_pe": {"low": 100.0, "mid": 120.0, "high": 140.0},
            "dcf_base": {"low": 110.0, "mid": 130.0, "high": 150.0},
            "sell_side": {"low": 105.0, "mid": 125.0, "high": 145.0},
        }
    )
    assert out["method_count"] == 3
    assert out["x_min"] == 100.0
    assert out["x_max"] == 150.0
    assert len(out["rows"]) == 3


def test_football_field_skips_methods_missing_bounds() -> None:
    out = football_field({"a": {"low": 1.0, "mid": 2.0, "high": 3.0}, "b": {"mid": 5.0}})
    assert out["method_count"] == 1


# -- sensitivity_grid ------------------------------------------------------


def test_sensitivity_grid_sweeps_both_dimensions() -> None:
    def add(inputs: dict) -> float:
        return inputs["a"] + inputs["b"]

    out = sensitivity_grid(
        base_inputs={},
        sweep_dim_a=("a", [1.0, 2.0]),
        sweep_dim_b=("b", [10.0, 20.0]),
        output_fn=add,
    )
    assert len(out["rows"]) == 4
    outputs = {(r["a"], r["b"]): r["output"] for r in out["rows"]}
    assert outputs[(1.0, 10.0)] == 11.0
    assert outputs[(2.0, 20.0)] == 22.0
