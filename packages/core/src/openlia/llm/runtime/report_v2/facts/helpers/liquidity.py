"""Liquidity and leverage helpers (WS7)."""

from __future__ import annotations

from openlia.llm.runtime.report_v2.facts.extractors.compute import union_source_ids
from openlia.llm.runtime.report_v2.facts.helpers._util import (
    last_or_none,
    oldest_data_as_of_of_deps,
)
from openlia.llm.runtime.report_v2.facts.registry import register_fact
from openlia.llm.runtime.report_v2.types import Fact


def net_cash(
    cash: float,
    short_term_investments: float,
    long_term_investments: float,
    total_debt: float,
) -> dict:
    cash_and_st = cash + short_term_investments
    total_liquid = cash_and_st + long_term_investments
    return {
        "net_cash": total_liquid - total_debt,
        "cash_and_st": cash_and_st,
        "total_liquid": total_liquid,
        "total_debt": total_debt,
    }


def current_ratio(current_assets: float, current_liabilities: float) -> float:
    if current_liabilities == 0:
        raise ValueError("current_liabilities is zero")
    return current_assets / current_liabilities


def quick_ratio(current_assets: float, inventory: float, current_liabilities: float) -> float:
    if current_liabilities == 0:
        raise ValueError("current_liabilities is zero")
    return (current_assets - inventory) / current_liabilities


def debt_to_equity(total_debt: float, equity: float) -> float:
    if equity == 0:
        raise ValueError("equity is zero")
    return total_debt / equity


def interest_coverage(operating_income: float, interest_expense: float) -> float:
    if interest_expense == 0:
        raise ValueError("interest_expense is zero")
    return operating_income / interest_expense


def cash_runway_quarters(
    cash_and_st_investments: float, ttm_operating_cash_burn: float
) -> float | None:
    """Quarters of cash runway. Returns None when not burning (OCF >= 0)."""
    if ttm_operating_cash_burn >= 0:
        return None
    quarterly_burn = -ttm_operating_cash_burn / 4.0
    if quarterly_burn == 0:
        return None
    return cash_and_st_investments / quarterly_burn


# -- Registered Facts -------------------------------------------------------


_NET_CASH_DEPS = ["cash_annual", "total_debt_annual", "cash_and_short_term_investments_annual"]


@register_fact("net_cash", tier="compute", depends_on=_NET_CASH_DEPS)
def net_cash_fact(payloads, facts) -> Fact:
    cash_f = facts["cash_annual"]
    debt_f = facts["total_debt_annual"]
    cst_f = facts["cash_and_short_term_investments_annual"]
    cash = last_or_none(cash_f) or 0.0
    debt = last_or_none(debt_f) or 0.0
    cst = last_or_none(cst_f)
    st_investments = max(0.0, (cst if cst is not None else cash) - cash)
    try:
        value = net_cash(
            cash=cash,
            short_term_investments=st_investments,
            long_term_investments=0.0,
            total_debt=debt,
        )
    except ValueError:
        value = None
    return Fact(
        name="net_cash",
        value=value,
        source_ids=union_source_ids(cash_f, debt_f, cst_f),
        extractor="compute",
        depends_on=_NET_CASH_DEPS,
        data_as_of=oldest_data_as_of_of_deps([cash_f, debt_f, cst_f]),
        source_tier="derived",
    )


_CASH_RUNWAY_DEPS = ["cash_and_short_term_investments_annual", "operating_cash_flow_annual"]


@register_fact("cash_runway_quarters", tier="compute", depends_on=_CASH_RUNWAY_DEPS)
def cash_runway_quarters_fact(payloads, facts) -> Fact:
    cst_f = facts["cash_and_short_term_investments_annual"]
    ocf_f = facts["operating_cash_flow_annual"]
    cst = last_or_none(cst_f)
    ocf = last_or_none(ocf_f)
    value: float | None
    if cst is None or ocf is None:
        value = None
    else:
        try:
            value = cash_runway_quarters(cash_and_st_investments=cst, ttm_operating_cash_burn=ocf)
        except ValueError:
            value = None
    return Fact(
        name="cash_runway_quarters",
        value=value,
        source_ids=union_source_ids(cst_f, ocf_f),
        extractor="compute",
        depends_on=_CASH_RUNWAY_DEPS,
        data_as_of=oldest_data_as_of_of_deps([cst_f, ocf_f]),
        source_tier="derived",
    )
