"""Profitability and returns helpers (WS7)."""

from __future__ import annotations

from openlia.llm.runtime.report_v2.facts.extractors.compute import union_source_ids
from openlia.llm.runtime.report_v2.facts.helpers._util import (
    last_or_none,
    oldest_data_as_of_of_deps,
)
from openlia.llm.runtime.report_v2.facts.registry import register_fact
from openlia.llm.runtime.report_v2.types import Fact


def roe_ttm_computed(net_income_ttm: float, beginning_equity: float, ending_equity: float) -> float:
    """ROE using average equity (beginning + ending) / 2."""
    avg_equity = (beginning_equity + ending_equity) / 2.0
    if avg_equity == 0:
        raise ValueError("average equity is zero")
    return net_income_ttm / avg_equity


def roic_ttm_computed(
    nopat_ttm: float,
    beginning_invested_capital: float,
    ending_invested_capital: float,
) -> float:
    """ROIC using average invested capital."""
    avg_ic = (beginning_invested_capital + ending_invested_capital) / 2.0
    if avg_ic == 0:
        raise ValueError("average invested capital is zero")
    return nopat_ttm / avg_ic


def fcf_yield_computed(fcf_ttm: float, market_cap: float) -> float:
    if market_cap == 0:
        raise ValueError("market_cap is zero")
    return fcf_ttm / market_cap


def fcf_margin(fcf_ttm: float, revenue_ttm: float) -> float:
    if revenue_ttm == 0:
        raise ValueError("revenue_ttm is zero")
    return fcf_ttm / revenue_ttm


def dupont_decomposition(
    net_income: float,
    revenue: float,
    total_assets: float,
    equity: float,
    tolerance_pct: float = 1.0,
) -> dict:
    """DuPont decomposition: ROE = net_margin * asset_turnover * equity_multiplier.

    Returns the three components plus a reconciliation check that their
    product equals direct ROE (net_income / equity) within `tolerance_pct`.
    """
    if revenue == 0 or total_assets == 0 or equity == 0:
        raise ValueError("revenue, total_assets, and equity must be non-zero")
    net_margin = net_income / revenue
    asset_turnover = revenue / total_assets
    equity_multiplier = total_assets / equity
    computed_roe = net_margin * asset_turnover * equity_multiplier
    direct_roe = net_income / equity
    reconciles = abs(computed_roe - direct_roe) <= abs(direct_roe) * (tolerance_pct / 100.0)
    return {
        "net_margin": net_margin,
        "asset_turnover": asset_turnover,
        "equity_multiplier": equity_multiplier,
        "computed_roe": computed_roe,
        "direct_roe": direct_roe,
        "reconciles": reconciles,
    }


def margin_bridge(
    prior_margins: dict[str, float], current_margins: dict[str, float]
) -> dict[str, dict[str, float]]:
    """Period-over-period spread per margin line, in percentage points."""
    out: dict[str, dict[str, float]] = {}
    for key in current_margins:
        if key not in prior_margins:
            continue
        prior = prior_margins[key]
        current = current_margins[key]
        out[key] = {
            "prior": prior,
            "current": current,
            "spread_pp": (current - prior) * 100.0,
        }
    return out


# -- Registered Facts -------------------------------------------------------


_ROE_DEPS = ["net_income_annual", "equity_annual"]


@register_fact("roe_ttm_computed", tier="compute", depends_on=_ROE_DEPS)
def roe_ttm_computed_fact(payloads, facts) -> Fact:
    ni_f = facts["net_income_annual"]
    eq_f = facts["equity_annual"]
    ni = last_or_none(ni_f)
    eq_series = eq_f.value if isinstance(eq_f.value, list) else None
    value: float | None
    if ni is None or eq_series is None or len(eq_series) < 2:
        value = None
    else:
        try:
            value = roe_ttm_computed(
                net_income_ttm=ni,
                beginning_equity=eq_series[-2],
                ending_equity=eq_series[-1],
            )
        except ValueError:
            value = None
    return Fact(
        name="roe_ttm_computed",
        value=value,
        source_ids=union_source_ids(ni_f, eq_f),
        extractor="compute",
        depends_on=_ROE_DEPS,
        data_as_of=oldest_data_as_of_of_deps([ni_f, eq_f]),
        source_tier="derived",
    )


_ROIC_DEPS = ["operating_income_annual", "total_debt_annual", "equity_annual"]


@register_fact("roic_ttm_computed", tier="compute", depends_on=_ROIC_DEPS)
def roic_ttm_computed_fact(payloads, facts) -> Fact:
    """ROIC = NOPAT / avg invested capital. NOPAT approximated as
    operating_income * (1 - 0.21) flat tax; invested capital = debt + equity."""
    oi_f = facts["operating_income_annual"]
    debt_f = facts["total_debt_annual"]
    eq_f = facts["equity_annual"]
    oi = last_or_none(oi_f)
    debt_series = debt_f.value if isinstance(debt_f.value, list) else None
    eq_series = eq_f.value if isinstance(eq_f.value, list) else None
    value: float | None
    if (
        oi is None
        or debt_series is None
        or eq_series is None
        or len(debt_series) < 2
        or len(eq_series) < 2
    ):
        value = None
    else:
        nopat = oi * (1.0 - 0.21)
        try:
            value = roic_ttm_computed(
                nopat_ttm=nopat,
                beginning_invested_capital=debt_series[-2] + eq_series[-2],
                ending_invested_capital=debt_series[-1] + eq_series[-1],
            )
        except ValueError:
            value = None
    return Fact(
        name="roic_ttm_computed",
        value=value,
        source_ids=union_source_ids(oi_f, debt_f, eq_f),
        extractor="compute",
        depends_on=_ROIC_DEPS,
        data_as_of=oldest_data_as_of_of_deps([oi_f, debt_f, eq_f]),
        source_tier="derived",
    )


_FCF_YIELD_DEPS = ["free_cash_flow_annual", "market_cap"]


@register_fact("fcf_yield_computed", tier="compute", depends_on=_FCF_YIELD_DEPS)
def fcf_yield_computed_fact(payloads, facts) -> Fact:
    fcf_f = facts["free_cash_flow_annual"]
    mcap_f = facts["market_cap"]
    fcf = last_or_none(fcf_f)
    mcap = mcap_f.value if isinstance(mcap_f.value, (int, float)) else None
    value: float | None
    if fcf is None or mcap is None:
        value = None
    else:
        try:
            value = fcf_yield_computed(fcf_ttm=fcf, market_cap=mcap)
        except ValueError:
            value = None
    return Fact(
        name="fcf_yield_computed",
        value=value,
        source_ids=union_source_ids(fcf_f, mcap_f),
        extractor="compute",
        depends_on=_FCF_YIELD_DEPS,
        data_as_of=oldest_data_as_of_of_deps([fcf_f, mcap_f]),
        source_tier="derived",
    )


_FCF_MARGIN_DEPS = ["free_cash_flow_annual", "revenue_annual"]


@register_fact("fcf_margin", tier="compute", depends_on=_FCF_MARGIN_DEPS)
def fcf_margin_fact(payloads, facts) -> Fact:
    fcf_f = facts["free_cash_flow_annual"]
    rev_f = facts["revenue_annual"]
    fcf = last_or_none(fcf_f)
    rev = last_or_none(rev_f)
    value: float | None
    if fcf is None or rev is None:
        value = None
    else:
        try:
            value = fcf_margin(fcf_ttm=fcf, revenue_ttm=rev)
        except ValueError:
            value = None
    return Fact(
        name="fcf_margin",
        value=value,
        source_ids=union_source_ids(fcf_f, rev_f),
        extractor="compute",
        depends_on=_FCF_MARGIN_DEPS,
        data_as_of=oldest_data_as_of_of_deps([fcf_f, rev_f]),
        source_tier="derived",
    )


_MARGIN_BRIDGE_DEPS = ["gross_margin_annual", "operating_margin_annual", "net_margin_annual"]


@register_fact("margin_bridge", tier="compute", depends_on=_MARGIN_BRIDGE_DEPS)
def margin_bridge_fact(payloads, facts) -> Fact:
    gm_f = facts["gross_margin_annual"]
    om_f = facts["operating_margin_annual"]
    nm_f = facts["net_margin_annual"]

    def _last_two(f: Fact) -> tuple[float, float] | None:
        v = f.value
        if isinstance(v, list) and len(v) >= 2 and v[-1] is not None and v[-2] is not None:
            return float(v[-2]), float(v[-1])
        return None

    gm = _last_two(gm_f)
    om = _last_two(om_f)
    nm = _last_two(nm_f)
    prior: dict[str, float] = {}
    current: dict[str, float] = {}
    if gm:
        prior["gross"], current["gross"] = gm
    if om:
        prior["operating"], current["operating"] = om
    if nm:
        prior["net"], current["net"] = nm
    value: dict | None
    value = margin_bridge(prior_margins=prior, current_margins=current) if current else None
    return Fact(
        name="margin_bridge",
        value=value,
        source_ids=union_source_ids(gm_f, om_f, nm_f),
        extractor="compute",
        depends_on=_MARGIN_BRIDGE_DEPS,
        data_as_of=oldest_data_as_of_of_deps([gm_f, om_f, nm_f]),
        source_tier="derived",
    )
