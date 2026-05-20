"""Tests for `facts.helpers.forecast`."""

from __future__ import annotations

import pytest
from openlia.llm.runtime.report_v2.facts.helpers.forecast import (
    actual_vs_consensus,
    consensus_vs_assumptions_table,
    forecast_table,
    sensitivity_grid,
)


def test_forecast_table_empty_consensus_returns_empty_rows() -> None:
    out = forecast_table(history=[{"revenue": 100.0, "eps": 1.0}], consensus={})
    assert out["rows"] == []
    assert out["fabricated"] is False


def test_forecast_table_typical() -> None:
    out = forecast_table(
        history=[{"revenue": 100.0, "eps": 1.0}, {"revenue": 120.0, "eps": 1.2}],
        consensus={
            "revenue_fy1": 144.0,
            "revenue_fy2": 173.0,
            "revenue_fy3": 210.0,
            "eps_fy1": 1.5,
            "eps_fy2": 1.8,
            "eps_fy3": 2.2,
        },
        growth_assumptions={"op_margin_fy1": 0.20},
    )
    assert len(out["rows"]) == 3
    assert out["rows"][0]["revenue"] == 144.0
    # FY1 growth: 144 / 120 - 1 = 0.20
    assert out["rows"][0]["revenue_growth"] == pytest.approx(0.20)
    # FY1 op income: 144 * 0.20 = 28.8
    assert out["rows"][0]["operating_income"] == pytest.approx(28.8)
    # FY2 growth: 173 / 144 - 1
    assert out["rows"][1]["revenue_growth"] == pytest.approx(173.0 / 144.0 - 1.0)


def test_forecast_table_partial_consensus_emits_partial_rows() -> None:
    out = forecast_table(
        history=[{"revenue": 100.0, "eps": 1.0}],
        consensus={"revenue_fy1": 110.0},
    )
    assert len(out["rows"]) == 3
    assert out["rows"][0]["revenue"] == 110.0
    assert out["rows"][1]["revenue"] is None


def test_sensitivity_grid_smoke() -> None:
    out = sensitivity_grid(
        base_inputs={"k": 0},
        sweep_dim_a=("a", [1.0]),
        sweep_dim_b=("b", [2.0, 3.0]),
        output_fn=lambda i: i["a"] * i["b"],
    )
    assert len(out["rows"]) == 2
    assert out["rows"][1]["output"] == pytest.approx(3.0)


def test_actual_vs_consensus_typical() -> None:
    out = actual_vs_consensus(consensus_eps_fy_next=2.0, our_eps_assumption=2.2)
    assert out["diff_pct"] == pytest.approx(0.10)


def test_actual_vs_consensus_none_inputs() -> None:
    out = actual_vs_consensus(consensus_eps_fy_next=None, our_eps_assumption=2.0)
    assert out["diff_pct"] is None
    out = actual_vs_consensus(consensus_eps_fy_next=2.0, our_eps_assumption=None)
    assert out["diff_pct"] is None


def test_actual_vs_consensus_zero_consensus_returns_none_diff() -> None:
    out = actual_vs_consensus(consensus_eps_fy_next=0.0, our_eps_assumption=2.0)
    assert out["diff_pct"] is None


def test_consensus_vs_assumptions_table_flags_divergence() -> None:
    out = consensus_vs_assumptions_table(
        consensus_facts={"revenue_fy1": 100.0, "op_margin_fy1": 0.20},
        named_assumptions=[
            {"name": "revenue_fy1", "our_value": 110.0, "source_citation": "c1"},
            {"name": "op_margin_fy1", "our_value": 0.21, "source_citation": "c2"},
        ],
    )
    rows = {r["name"]: r for r in out["rows"]}
    assert rows["revenue_fy1"]["diverges"] is True  # 10% vs default 5% threshold
    assert rows["op_margin_fy1"]["diverges"] is False  # 5% diff at threshold
    assert rows["revenue_fy1"]["source_citation"] == "c1"


def test_consensus_vs_assumptions_table_missing_consensus_is_no_divergence() -> None:
    out = consensus_vs_assumptions_table(
        consensus_facts={},
        named_assumptions=[{"name": "x", "our_value": 1.0}],
    )
    assert out["rows"][0]["diff_pct"] is None
    assert out["rows"][0]["diverges"] is False
