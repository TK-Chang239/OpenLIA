"""Tests for ddm_family helper — Gordon, two-stage, H-model, sustainability check."""

from __future__ import annotations

import pytest
from openlia.llm.runtime.report_v2_2.tools.library_helpers.ddm_family import execute

# ---------------------------------------------------------------------------
# Gordon growth model
# ---------------------------------------------------------------------------


def test_gordon_known_value() -> None:
    """P0 = D1 / (Re - g) = D0 * (1 + g) / (Re - g).

    D0=2.00, Re=0.09, g=0.04
    D1 = 2.00 * 1.04 = 2.08
    P0 = 2.08 / 0.05 = 41.60
    """
    result = execute(
        current_dividend_per_share=2.00,
        cost_of_equity=0.09,
        method="gordon",
        gordon_growth=0.04,
    )
    assert abs(result["price_per_share"] - 41.60) < 0.01
    assert result["method_used"] == "gordon"
    assert result["primary_model"] == "gordon"


def test_gordon_g_equals_re_raises() -> None:
    with pytest.raises(ValueError, match="must be >"):
        execute(
            current_dividend_per_share=1.00,
            cost_of_equity=0.05,
            method="gordon",
            gordon_growth=0.05,
        )


def test_gordon_g_exceeds_re_raises() -> None:
    with pytest.raises(ValueError, match="must be >"):
        execute(
            current_dividend_per_share=1.00,
            cost_of_equity=0.04,
            method="gordon",
            gordon_growth=0.06,
        )


def test_zero_dividend_raises() -> None:
    with pytest.raises(ValueError, match="positive"):
        execute(
            current_dividend_per_share=0.0,
            cost_of_equity=0.09,
            method="gordon",
            gordon_growth=0.03,
        )


# ---------------------------------------------------------------------------
# Two-stage DDM
# ---------------------------------------------------------------------------


def test_two_stage_pv_reconciles() -> None:
    """Stage-1 PV + stage-2 terminal PV must sum to total price.

    D0=4.20, Re=0.085, g_high=0.07, n_high=5, g_stable=0.025
    """
    result = execute(
        current_dividend_per_share=4.20,
        cost_of_equity=0.085,
        method="two_stage",
        stage1_growth=0.07,
        stage1_years=5,
        terminal_growth=0.025,
    )
    pv_breakdown = result["pv_breakdown"]
    s1 = pv_breakdown["stage1_explicit"]
    s2 = pv_breakdown["stage2_terminal"]
    total = result["price_per_share"]
    assert abs(s1 + s2 - total) < 1e-9


def test_two_stage_explicit_dividends_count() -> None:
    """Explicit dividend list must have length == stage1_years."""
    result = execute(
        current_dividend_per_share=2.00,
        cost_of_equity=0.10,
        method="two_stage",
        stage1_growth=0.08,
        stage1_years=7,
        terminal_growth=0.03,
    )
    stage1 = next(s for s in result["stages"] if "stage1" in s["label"])
    assert len(stage1["dividends"]) == 7


def test_two_stage_price_is_positive() -> None:
    result = execute(
        current_dividend_per_share=1.50,
        cost_of_equity=0.09,
        method="two_stage",
        stage1_growth=0.06,
        stage1_years=5,
        terminal_growth=0.025,
    )
    assert result["price_per_share"] > 0


# ---------------------------------------------------------------------------
# H-model
# ---------------------------------------------------------------------------


def test_h_model_algebra() -> None:
    """Verify H-model formula against manual calculation.

    P0 = D0 * (1 + g_L) / (Re - g_L)  +  D0 * H * (g_S - g_L) / (Re - g_L)

    D0=3.00, Re=0.08, g_S=0.12, g_L=0.03, H=5
    denom = 0.08 - 0.03 = 0.05
    stable  = 3.00 * 1.03 / 0.05 = 61.80
    excess  = 3.00 * 5 * (0.12 - 0.03) / 0.05 = 3.00 * 5 * 0.09 / 0.05 = 27.00
    P0 = 88.80
    """
    result = execute(
        current_dividend_per_share=3.00,
        cost_of_equity=0.08,
        method="h_model",
        h_half_life=5,
        h_short_growth=0.12,
        terminal_growth=0.03,
    )
    expected = 61.80 + 27.00  # 88.80
    assert abs(result["price_per_share"] - expected) < 0.01


def test_h_model_pv_breakdown_sums_to_price() -> None:
    result = execute(
        current_dividend_per_share=2.50,
        cost_of_equity=0.09,
        method="h_model",
        h_half_life=4,
        h_short_growth=0.10,
        terminal_growth=0.025,
    )
    bd = result["pv_breakdown"]
    total = bd["stable_component"] + bd["excess_growth_component"]
    assert abs(total - result["price_per_share"]) < 1e-9


def test_h_model_missing_h_raises() -> None:
    with pytest.raises(ValueError, match="h_half_life"):
        execute(
            current_dividend_per_share=2.00,
            cost_of_equity=0.09,
            method="h_model",
            h_short_growth=0.10,
            terminal_growth=0.03,
        )


# ---------------------------------------------------------------------------
# Sustainability check
# ---------------------------------------------------------------------------


def test_sustainability_unsustainable_gap() -> None:
    """growth=0.07 > ROE*(1-payout)=0.10*(1-0.65)=0.035 — flagged unsustainable."""
    result = execute(
        current_dividend_per_share=2.00,
        cost_of_equity=0.09,
        method="two_stage",
        stage1_growth=0.07,
        stage1_years=5,
        terminal_growth=0.025,
        current_payout_ratio=0.65,
        current_roe=0.10,
    )
    sus = result["sustainability"]
    assert sus["sustainable"] is False
    assert sus["gap"] > 0
    assert len(sus["warnings"]) > 0


def test_sustainability_payout_over_100_pct() -> None:
    """Payout > 100% should flag unsustainable and add a warning."""
    result = execute(
        current_dividend_per_share=2.00,
        cost_of_equity=0.09,
        method="gordon",
        gordon_growth=0.025,
        current_payout_ratio=1.20,
        current_roe=0.12,
    )
    sus = result["sustainability"]
    assert sus["sustainable"] is False
    assert any("100%" in w or "exceed" in w.lower() for w in sus["warnings"])


def test_sustainability_sustainable_case() -> None:
    """growth=0.03, ROE=0.15, payout=0.80 → sustainable_growth=0.03=growth, gap=0."""
    result = execute(
        current_dividend_per_share=1.00,
        cost_of_equity=0.08,
        method="gordon",
        gordon_growth=0.03,
        current_payout_ratio=0.80,
        current_roe=0.15,
    )
    sus = result["sustainability"]
    # sustainable_growth = 0.15 * (1 - 0.80) = 0.03; gap = 0
    assert sus["sustainable"] is True
    assert abs(sus["gap"]) < 1e-9


def test_sustainability_no_inputs_returns_none() -> None:
    """When payout and ROE are not provided, sustainable is None."""
    result = execute(
        current_dividend_per_share=1.00,
        cost_of_equity=0.08,
        method="gordon",
        gordon_growth=0.03,
    )
    sus = result["sustainability"]
    assert sus["sustainable"] is None


# ---------------------------------------------------------------------------
# Method "all"
# ---------------------------------------------------------------------------


def test_all_method_returns_alternative_methods() -> None:
    result = execute(
        current_dividend_per_share=2.00,
        cost_of_equity=0.09,
        method="all",
        gordon_growth=0.03,
        stage1_growth=0.07,
        stage1_years=5,
        terminal_growth=0.025,
        h_half_life=5,
        h_short_growth=0.07,
    )
    assert result["alternative_methods"] is not None
    assert "gordon" in result["alternative_methods"]
    assert "two_stage" in result["alternative_methods"]
    assert "h_model" in result["alternative_methods"]


# ---------------------------------------------------------------------------
# Upside computation
# ---------------------------------------------------------------------------


def test_implied_upside_present_with_price() -> None:
    result = execute(
        current_dividend_per_share=2.00,
        cost_of_equity=0.09,
        method="gordon",
        gordon_growth=0.04,
        current_price=40.00,
    )
    # P0 = 41.60 vs price=40.00 => ~4% upside
    assert result["implied_upside_pct"] is not None
    assert result["implied_upside_pct"] > 0


def test_implied_upside_none_without_price() -> None:
    result = execute(
        current_dividend_per_share=2.00,
        cost_of_equity=0.09,
        method="gordon",
        gordon_growth=0.04,
    )
    assert result["implied_upside_pct"] is None
