"""Tests for sotp_builder helper."""

from __future__ import annotations

import pytest
from openlia.llm.runtime.report_v2_2.tools.library_helpers.sotp_builder import execute

# ---------------------------------------------------------------------------
# Helper: minimal 3-segment example
# ---------------------------------------------------------------------------

_THREE_SEGMENTS = [
    {
        "name": "Segment A",
        "valuation_method": "ebitda_multiple",
        "metric_value": 100.0,
        "method_inputs": {"multiple": 8.0},
    },
    {
        "name": "Segment B",
        "valuation_method": "peer_ps",
        "metric_value": 50.0,
        "method_inputs": {"multiple": 3.0},
    },
    {
        "name": "Segment C",
        "valuation_method": "book_value",
        "metric_value": 30.0,
        "method_inputs": {"multiple": 1.0},
    },
]


# ---------------------------------------------------------------------------
# 3-segment reconciliation
# ---------------------------------------------------------------------------


def test_three_segment_equity_value_reconciles() -> None:
    """A=800, B=150, C=30 → gross_ev=980; equity=980-50=930; per_share=93.0."""
    result = execute(
        segments=_THREE_SEGMENTS,
        shares_outstanding=10.0,
        net_debt=50.0,
    )
    assert abs(result["sum_segment_ev"] - 980.0) < 1e-9
    assert abs(result["implied_equity_value"] - 930.0) < 1e-9
    assert abs(result["implied_value_per_share"] - 93.0) < 1e-9


def test_segment_ev_sum_matches_total() -> None:
    result = execute(
        segments=_THREE_SEGMENTS,
        shares_outstanding=10.0,
        net_debt=0.0,
    )
    total_from_segments = sum(s["segment_ev"] for s in result["segment_values"])
    assert abs(total_from_segments - result["sum_segment_ev"]) < 1e-9


def test_equity_bridge_formula() -> None:
    """post_discount_ev + non_op_assets - net_debt - minority = equity_value."""
    result = execute(
        segments=_THREE_SEGMENTS,
        shares_outstanding=10.0,
        net_debt=80.0,
        non_operating_assets=20.0,
        minority_interest=10.0,
        conglomerate_discount_pct=0.05,
    )
    reconstructed = (
        result["post_discount_ev"]
        + result["non_operating_assets"]
        - result["net_debt"]
        - result["minority_interest"]
    )
    assert abs(reconstructed - result["implied_equity_value"]) < 1e-9


# ---------------------------------------------------------------------------
# Conglomerate discount
# ---------------------------------------------------------------------------


def test_conglomerate_discount_applied() -> None:
    result_no_discount = execute(
        segments=_THREE_SEGMENTS,
        shares_outstanding=10.0,
        net_debt=0.0,
    )
    result_with_discount = execute(
        segments=_THREE_SEGMENTS,
        shares_outstanding=10.0,
        net_debt=0.0,
        conglomerate_discount_pct=0.10,
    )
    assert result_with_discount["implied_equity_value"] < result_no_discount["implied_equity_value"]
    expected_discount = result_no_discount["adjusted_sum_ev"] * 0.10
    assert abs(result_with_discount["conglomerate_discount_amount"] - expected_discount) < 1e-6


# ---------------------------------------------------------------------------
# Concentration warning — top segment > 70%
# ---------------------------------------------------------------------------


def test_concentration_warning_fires_above_70_pct() -> None:
    """Single dominant segment at 95% triggers concentration warning."""
    result = execute(
        segments=[
            {
                "name": "Dominant",
                "valuation_method": "ebitda_multiple",
                "metric_value": 950.0,
                "method_inputs": {"multiple": 1.0},
            },
            {
                "name": "Tiny",
                "valuation_method": "ebitda_multiple",
                "metric_value": 50.0,
                "method_inputs": {"multiple": 1.0},
            },
        ],
        shares_outstanding=1.0,
        net_debt=0.0,
    )
    assert result["concentration_ratio"] > 0.70
    assert any(
        "concentration" in w.lower() or "dominant" in w.lower() or "70%" in w
        for w in result["warnings"]
    )


def test_concentration_no_warning_below_70_pct() -> None:
    """Balanced two segments: no concentration warning expected."""
    result = execute(
        segments=[
            {
                "name": "A",
                "valuation_method": "ebitda_multiple",
                "metric_value": 100.0,
                "method_inputs": {"multiple": 1.0},
            },
            {
                "name": "B",
                "valuation_method": "ebitda_multiple",
                "metric_value": 90.0,
                "method_inputs": {"multiple": 1.0},
            },
        ],
        shares_outstanding=1.0,
        net_debt=0.0,
    )
    concentration_warns = [
        w for w in result["warnings"] if "70%" in w or "concentration" in w.lower()
    ]
    assert len(concentration_warns) == 0


# ---------------------------------------------------------------------------
# Negative EBITDA guard
# ---------------------------------------------------------------------------


def test_negative_ebitda_with_multiple_raises() -> None:
    with pytest.raises(ValueError, match="negative EBITDA"):
        execute(
            segments=[
                {
                    "name": "Loss-maker",
                    "valuation_method": "ebitda_multiple",
                    "metric_value": -50.0,
                    "method_inputs": {"multiple": 8.0},
                }
            ],
            shares_outstanding=10.0,
            net_debt=0.0,
        )


# ---------------------------------------------------------------------------
# Single-segment warning
# ---------------------------------------------------------------------------


def test_single_segment_warning() -> None:
    result = execute(
        segments=[
            {
                "name": "Only Segment",
                "valuation_method": "ebitda_multiple",
                "metric_value": 200.0,
                "method_inputs": {"multiple": 5.0},
            }
        ],
        shares_outstanding=10.0,
        net_debt=0.0,
    )
    assert result["single_segment"] is True
    assert any("single" in w.lower() for w in result["warnings"])


# ---------------------------------------------------------------------------
# Corporate overhead deduction
# ---------------------------------------------------------------------------


def test_overhead_deduction() -> None:
    result = execute(
        segments=_THREE_SEGMENTS,
        shares_outstanding=10.0,
        net_debt=0.0,
        corporate_overhead=10.0,
        corporate_overhead_capitalization_multiple=8.0,
    )
    # overhead_capitalized = 10 * 8 = 80
    assert abs(result["corporate_overhead_deduction"] - 80.0) < 1e-9
    assert abs(result["adjusted_sum_ev"] - (result["sum_segment_ev"] - 80.0)) < 1e-9


# ---------------------------------------------------------------------------
# Ownership and user_supplied
# ---------------------------------------------------------------------------


def test_ownership_pct_adjusts_segment_ev() -> None:
    result = execute(
        segments=[
            {
                "name": "Partial Sub",
                "valuation_method": "ebitda_multiple",
                "metric_value": 100.0,
                "method_inputs": {"multiple": 10.0},
                "ownership_pct": 0.70,
            }
        ],
        shares_outstanding=1.0,
        net_debt=0.0,
    )
    # 100 * 10 * 0.70 = 700
    assert abs(result["segment_values"][0]["segment_ev"] - 700.0) < 1e-9


def test_user_supplied_method() -> None:
    result = execute(
        segments=[
            {
                "name": "Custom",
                "valuation_method": "user_supplied",
                "metric_value": 0.0,
                "method_inputs": {"value": 500.0},
            }
        ],
        shares_outstanding=10.0,
        net_debt=0.0,
    )
    assert abs(result["segment_values"][0]["segment_ev"] - 500.0) < 1e-9
    assert any(
        "analyst-supplied" in w.lower() or "user_supplied" in w.lower() for w in result["warnings"]
    )


# ---------------------------------------------------------------------------
# Implied upside
# ---------------------------------------------------------------------------


def test_implied_upside_with_price() -> None:
    result = execute(
        segments=_THREE_SEGMENTS,
        shares_outstanding=10.0,
        net_debt=50.0,
        current_price=80.0,
    )
    # per_share = 93.0, price = 80.0 → upside ~16.25%
    assert result["implied_upside_pct"] is not None
    assert result["implied_upside_pct"] > 0


def test_implied_upside_none_without_price() -> None:
    result = execute(
        segments=_THREE_SEGMENTS,
        shares_outstanding=10.0,
        net_debt=50.0,
    )
    assert result["implied_upside_pct"] is None
