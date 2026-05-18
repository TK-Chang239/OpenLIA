"""Registered facts for the stock_initiation report type.

Importing this module triggers registration with the default_registry.
"""

from __future__ import annotations

from openlia.llm.runtime.report_v2.facts.extractors.compute import cagr, union_source_ids
from openlia.llm.runtime.report_v2.facts.extractors.deterministic import (
    pluck,
    yearly_series,
)
from openlia.llm.runtime.report_v2.facts.registry import register_fact
from openlia.llm.runtime.report_v2.types import Fact

_FUNDAMENTALS = "get_fundamentals_data"


@register_fact("market_cap", tier="deterministic", depends_on=[])
def market_cap(payloads, facts) -> Fact:
    ident = _find_fundamentals_identifier(payloads)
    payload = payloads.by_identifier(ident)
    return Fact(
        name="market_cap",
        value=pluck(payload, "Highlights", "MarketCapitalization"),
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
    )


@register_fact("pe_ratio_ttm", tier="deterministic", depends_on=[])
def pe_ratio_ttm(payloads, facts) -> Fact:
    ident = _find_fundamentals_identifier(payloads)
    payload = payloads.by_identifier(ident)
    return Fact(
        name="pe_ratio_ttm",
        value=pluck(payload, "Highlights", "PERatio"),
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
    )


@register_fact("sector", tier="deterministic", depends_on=[])
def sector(payloads, facts) -> Fact:
    ident = _find_fundamentals_identifier(payloads)
    payload = payloads.by_identifier(ident)
    return Fact(
        name="sector",
        value=pluck(payload, "General", "Sector"),
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
    )


@register_fact("company_name", tier="deterministic", depends_on=[])
def company_name(payloads, facts) -> Fact:
    ident = _find_fundamentals_identifier(payloads)
    payload = payloads.by_identifier(ident)
    return Fact(
        name="company_name",
        value=pluck(payload, "General", "Name"),
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
    )


@register_fact("revenue_annual", tier="deterministic", depends_on=[])
def revenue_annual(payloads, facts) -> Fact:
    ident = _find_fundamentals_identifier(payloads)
    payload = payloads.by_identifier(ident)
    return Fact(
        name="revenue_annual",
        value=yearly_series(payload, statement="Income_Statement", field="totalRevenue"),
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
    )


@register_fact("gross_profit_annual", tier="deterministic", depends_on=[])
def gross_profit_annual(payloads, facts) -> Fact:
    ident = _find_fundamentals_identifier(payloads)
    payload = payloads.by_identifier(ident)
    return Fact(
        name="gross_profit_annual",
        value=yearly_series(payload, statement="Income_Statement", field="grossProfit"),
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
    )


@register_fact("revenue_cagr_3y", tier="compute", depends_on=["revenue_annual"])
def revenue_cagr_3y(payloads, facts) -> Fact:
    series = facts["revenue_annual"].value
    return Fact(
        name="revenue_cagr_3y",
        value=cagr(series, years=3),
        source_ids=union_source_ids(facts["revenue_annual"]),
        extractor="compute",
        depends_on=["revenue_annual"],
    )


@register_fact(
    "gross_margin_ttm", tier="compute", depends_on=["revenue_annual", "gross_profit_annual"]
)
def gross_margin_ttm(payloads, facts) -> Fact:
    rev = facts["revenue_annual"].value[-1]
    gp = facts["gross_profit_annual"].value[-1]
    return Fact(
        name="gross_margin_ttm",
        value=gp / rev,
        source_ids=union_source_ids(facts["revenue_annual"], facts["gross_profit_annual"]),
        extractor="compute",
        depends_on=["revenue_annual", "gross_profit_annual"],
    )


def _find_fundamentals_identifier(payloads) -> str:
    """Find the manifest identifier for a fundamentals fetch (ticker-agnostic)."""
    for candidate in list(payloads._by_identifier.keys()):  # private access intentional
        if candidate.startswith(_FUNDAMENTALS + "/"):
            return candidate
    raise KeyError(f"no manifest entry starting with {_FUNDAMENTALS!r}")
