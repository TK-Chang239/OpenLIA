"""SaaS-mode helpers (WS7)."""

from __future__ import annotations


def rule_of_40(revenue_growth_pct: float, fcf_margin_pct: float) -> float:
    """Sum of revenue-growth % and FCF-margin %. Both inputs in percent units."""
    return revenue_growth_pct + fcf_margin_pct


def nrr_trend(
    prior_period_arr: list[float], current_period_arr_from_same_cohort: list[float]
) -> float:
    """Dollar-based net revenue retention: sum(current) / sum(prior)."""
    if len(prior_period_arr) != len(current_period_arr_from_same_cohort):
        raise ValueError("cohort series must be the same length")
    prior_sum = sum(prior_period_arr)
    if prior_sum == 0:
        raise ValueError("prior cohort ARR sum is zero")
    return sum(current_period_arr_from_same_cohort) / prior_sum
