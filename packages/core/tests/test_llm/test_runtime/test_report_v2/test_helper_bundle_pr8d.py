"""Tests for the PR 8d helper bundle.

Four small helpers surfaced by gap analysis against the Chinese 28-section
template: three-scenario forecast, consensus-vs-three-scenarios table,
DuPont decomposition, catalyst horizon bucketing.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest
from openlia.llm.runtime.report_v2.facts.helpers.forecast import (
    consensus_vs_three_scenarios_table,
    three_scenario_forecast,
)
from openlia.llm.runtime.report_v2.facts.helpers.returns import dupont_decomposition
from openlia.llm.runtime.report_v2.scanners.catalyst_pack import (
    CatalystEvent,
    catalysts_by_horizon,
)


def test_three_scenario_forecast_returns_three_paths_with_horizon() -> None:
    out = three_scenario_forecast(
        base_revenue=100.0,
        base_op_margin=0.20,
        conservative_revenue_growth=0.05,
        neutral_revenue_growth=0.10,
        optimistic_revenue_growth=0.15,
        horizon_years=3,
    )

    assert set(out.keys()) == {"conservative", "neutral", "optimistic"}
    assert len(out["neutral"]) == 3
    # neutral path: revenue grows 10% per year, margin stays at 20%
    assert out["neutral"][0]["revenue"] == pytest.approx(110.0)
    assert out["neutral"][0]["op_margin"] == pytest.approx(0.20)
    assert out["neutral"][2]["revenue"] == pytest.approx(133.1, rel=1e-3)


def test_three_scenario_forecast_rejects_invalid_horizon() -> None:
    with pytest.raises(ValueError, match="horizon_years"):
        three_scenario_forecast(
            base_revenue=1.0,
            base_op_margin=0.1,
            conservative_revenue_growth=0.0,
            neutral_revenue_growth=0.0,
            optimistic_revenue_growth=0.0,
            horizon_years=0,
        )


def test_consensus_vs_three_scenarios_table_computes_deltas() -> None:
    scenarios = three_scenario_forecast(
        base_revenue=100.0,
        base_op_margin=0.20,
        conservative_revenue_growth=0.05,
        neutral_revenue_growth=0.10,
        optimistic_revenue_growth=0.15,
        horizon_years=2,
    )

    table = consensus_vs_three_scenarios_table(
        scenarios=scenarios,
        consensus_revenue_path=[110.0, 121.0],
    )

    rows = {row["scenario"]: row["deltas_vs_consensus"] for row in table["rows"]}
    # Neutral path matches consensus exactly => deltas are 0
    assert rows["neutral"][0] == pytest.approx(0.0)
    assert rows["neutral"][1] == pytest.approx(0.0)
    # Optimistic > consensus
    assert rows["optimistic"][0] > 0
    # Conservative < consensus
    assert rows["conservative"][0] < 0


def test_dupont_decomposition_reconciles() -> None:
    out = dupont_decomposition(
        net_income=20.0,
        revenue=100.0,
        total_assets=200.0,
        equity=80.0,
    )

    # net_margin = 0.20, asset_turnover = 0.50, equity_multiplier = 2.5
    # product = 0.20 * 0.50 * 2.5 = 0.25; direct ROE = 20/80 = 0.25
    assert out["net_margin"] == pytest.approx(0.20)
    assert out["asset_turnover"] == pytest.approx(0.50)
    assert out["equity_multiplier"] == pytest.approx(2.5)
    assert out["computed_roe"] == pytest.approx(0.25)
    assert out["direct_roe"] == pytest.approx(0.25)
    assert out["reconciles"] is True


def test_dupont_decomposition_rejects_zero_denominators() -> None:
    with pytest.raises(ValueError, match="non-zero"):
        dupont_decomposition(net_income=1.0, revenue=0.0, total_assets=1.0, equity=1.0)


def test_catalysts_by_horizon_buckets_events() -> None:
    today = date(2026, 5, 20)
    near = CatalystEvent(
        catalyst_class="product_announcement",
        event_date=today + timedelta(days=30),
        confidence="high",
        title="Near",
        summary="x",
        evidence=[1],
        source_url=None,
        relevance_score=0.5,
    )
    mid = CatalystEvent(
        catalyst_class="product_announcement",
        event_date=today + timedelta(days=180),
        confidence="high",
        title="Mid",
        summary="x",
        evidence=[2],
        source_url=None,
        relevance_score=0.5,
    )
    far = CatalystEvent(
        catalyst_class="product_announcement",
        event_date=today + timedelta(days=400),
        confidence="high",
        title="Far",
        summary="x",
        evidence=[3],
        source_url=None,
        relevance_score=0.5,
    )

    buckets = catalysts_by_horizon([near, mid, far], as_of=today)

    assert buckets["3m"] == [near]
    assert buckets["3-12m"] == [mid]
    assert buckets["1-3y"] == [far]


def test_catalysts_by_horizon_buckets_serialised_dicts() -> None:
    # Accepts already-serialised dicts (as stored in the `catalysts_recent` Fact).
    today = date(2026, 5, 20)
    items = [
        {"event_date": (today + timedelta(days=10)).isoformat(), "title": "near"},
        {"event_date": None, "title": "undated"},
        {"event_date": (today - timedelta(days=5)).isoformat(), "title": "past"},
    ]

    buckets = catalysts_by_horizon(items, as_of=today)

    titles = {bucket: [e["title"] for e in items] for bucket, items in buckets.items()}
    assert "near" in titles["3m"]
    assert "undated" in titles["3m"]  # undated lands in short-horizon bucket
    assert "past" in titles["past"]
