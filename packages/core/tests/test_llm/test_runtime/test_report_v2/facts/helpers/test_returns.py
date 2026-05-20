"""Tests for `facts.helpers.returns`."""

from __future__ import annotations

import pytest
from openlia.llm.runtime.report_v2.facts.helpers.returns import (
    fcf_margin,
    fcf_yield_computed,
    margin_bridge,
    roe_ttm_computed,
    roic_ttm_computed,
)


def test_roe_ttm_computed_uses_average_equity() -> None:
    # $20 NI on ($100 + $120)/2 = $110 avg equity → 18.18%
    out = roe_ttm_computed(net_income_ttm=20.0, beginning_equity=100.0, ending_equity=120.0)
    assert out == pytest.approx(20.0 / 110.0)


def test_roe_ttm_computed_zero_equity_raises() -> None:
    with pytest.raises(ValueError):
        roe_ttm_computed(net_income_ttm=20.0, beginning_equity=0.0, ending_equity=0.0)


def test_roic_ttm_computed_uses_average_invested_capital() -> None:
    out = roic_ttm_computed(
        nopat_ttm=30.0, beginning_invested_capital=200.0, ending_invested_capital=220.0
    )
    assert out == pytest.approx(30.0 / 210.0)


def test_roic_ttm_computed_zero_ic_raises() -> None:
    with pytest.raises(ValueError):
        roic_ttm_computed(
            nopat_ttm=30.0,
            beginning_invested_capital=0.0,
            ending_invested_capital=0.0,
        )


def test_fcf_yield_computed_typical() -> None:
    assert fcf_yield_computed(fcf_ttm=50.0, market_cap=1000.0) == pytest.approx(0.05)


def test_fcf_yield_computed_zero_mcap_raises() -> None:
    with pytest.raises(ValueError):
        fcf_yield_computed(fcf_ttm=50.0, market_cap=0.0)


def test_fcf_margin_typical() -> None:
    assert fcf_margin(fcf_ttm=30.0, revenue_ttm=300.0) == pytest.approx(0.10)


def test_fcf_margin_zero_revenue_raises() -> None:
    with pytest.raises(ValueError):
        fcf_margin(fcf_ttm=30.0, revenue_ttm=0.0)


def test_margin_bridge_returns_pp_spread() -> None:
    out = margin_bridge(
        prior_margins={"gross": 0.60, "operating": 0.25, "net": 0.18},
        current_margins={"gross": 0.62, "operating": 0.28, "net": 0.20},
    )
    assert out["gross"]["spread_pp"] == pytest.approx(2.0)
    assert out["operating"]["spread_pp"] == pytest.approx(3.0)
    assert out["net"]["spread_pp"] == pytest.approx(2.0)
    assert out["gross"]["prior"] == 0.60
    assert out["gross"]["current"] == 0.62


def test_margin_bridge_skips_missing_prior() -> None:
    out = margin_bridge(prior_margins={"gross": 0.60}, current_margins={"gross": 0.62, "net": 0.18})
    assert "gross" in out
    assert "net" not in out
