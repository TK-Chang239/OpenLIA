"""Tests for `facts.helpers.saas`."""

from __future__ import annotations

import pytest
from openlia.llm.runtime.report_v2.facts.helpers.saas import nrr_trend, rule_of_40


def test_rule_of_40_typical() -> None:
    # 30% growth + 15% FCF margin = 45 (passing)
    assert rule_of_40(revenue_growth_pct=30.0, fcf_margin_pct=15.0) == pytest.approx(45.0)


def test_rule_of_40_negative_fcf_margin() -> None:
    assert rule_of_40(revenue_growth_pct=50.0, fcf_margin_pct=-10.0) == pytest.approx(40.0)


def test_nrr_trend_typical() -> None:
    # Cohort grew from $100 to $115 total ARR → NRR = 1.15
    out = nrr_trend(
        prior_period_arr=[40.0, 60.0],
        current_period_arr_from_same_cohort=[46.0, 69.0],
    )
    assert out == pytest.approx(1.15)


def test_nrr_trend_mismatched_lengths_raises() -> None:
    with pytest.raises(ValueError):
        nrr_trend(prior_period_arr=[100.0], current_period_arr_from_same_cohort=[110.0, 120.0])


def test_nrr_trend_zero_prior_raises() -> None:
    with pytest.raises(ValueError):
        nrr_trend(prior_period_arr=[0.0], current_period_arr_from_same_cohort=[10.0])
