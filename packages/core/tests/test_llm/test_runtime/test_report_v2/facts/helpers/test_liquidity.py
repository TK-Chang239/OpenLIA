"""Tests for `facts.helpers.liquidity`."""

from __future__ import annotations

import pytest
from openlia.llm.runtime.report_v2.facts.helpers.liquidity import (
    cash_runway_quarters,
    current_ratio,
    debt_to_equity,
    interest_coverage,
    net_cash,
    quick_ratio,
)


def test_net_cash_typical() -> None:
    out = net_cash(cash=10.0, short_term_investments=5.0, long_term_investments=2.0, total_debt=8.0)
    assert out == {
        "net_cash": (10.0 + 5.0 + 2.0) - 8.0,
        "cash_and_st": 15.0,
        "total_liquid": 17.0,
        "total_debt": 8.0,
    }


def test_net_cash_negative_when_debt_exceeds_liquid() -> None:
    out = net_cash(cash=1.0, short_term_investments=0.0, long_term_investments=0.0, total_debt=5.0)
    assert out["net_cash"] == -4.0


def test_current_ratio_typical() -> None:
    assert current_ratio(100.0, 40.0) == pytest.approx(2.5)


def test_current_ratio_zero_liabilities_raises() -> None:
    with pytest.raises(ValueError):
        current_ratio(100.0, 0.0)


def test_quick_ratio_typical() -> None:
    assert quick_ratio(100.0, 30.0, 40.0) == pytest.approx(1.75)


def test_quick_ratio_zero_liabilities_raises() -> None:
    with pytest.raises(ValueError):
        quick_ratio(100.0, 30.0, 0.0)


def test_debt_to_equity_typical() -> None:
    assert debt_to_equity(60.0, 120.0) == pytest.approx(0.5)


def test_debt_to_equity_zero_equity_raises() -> None:
    with pytest.raises(ValueError):
        debt_to_equity(60.0, 0.0)


def test_interest_coverage_typical() -> None:
    assert interest_coverage(50.0, 5.0) == pytest.approx(10.0)


def test_interest_coverage_zero_interest_raises() -> None:
    with pytest.raises(ValueError):
        interest_coverage(50.0, 0.0)


def test_cash_runway_none_when_ocf_positive() -> None:
    assert cash_runway_quarters(cash_and_st_investments=100.0, ttm_operating_cash_burn=20.0) is None


def test_cash_runway_quarters_typical() -> None:
    # $100 cash, $40/yr burn → $10/q burn → 10 quarters
    out = cash_runway_quarters(cash_and_st_investments=100.0, ttm_operating_cash_burn=-40.0)
    assert out == pytest.approx(10.0)
