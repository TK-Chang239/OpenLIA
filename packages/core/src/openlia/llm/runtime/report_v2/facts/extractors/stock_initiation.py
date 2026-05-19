"""Registered facts for the stock_initiation report type.

Importing this module triggers registration with the default_registry.
"""

from __future__ import annotations

from openlia.llm.runtime.report_v2.facts.extractors.compute import cagr, union_source_ids
from openlia.llm.runtime.report_v2.facts.extractors.deterministic import (
    pluck,
    pluck_or_none,
    yearly_series,
)
from openlia.llm.runtime.report_v2.facts.registry import register_fact
from openlia.llm.runtime.report_v2.types import Fact

_FUNDAMENTALS = "get_fundamentals_data"


@register_fact("market_cap", tier="deterministic", depends_on=[])
def market_cap(payloads, facts) -> Fact:
    ident = payloads.subject_fundamentals_identifier()
    payload = payloads.by_identifier(ident)
    return Fact(
        name="market_cap",
        value=pluck(payload, "Highlights", "MarketCapitalization"),
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
    )


@register_fact("pe_ratio_ttm", tier="deterministic", depends_on=[])
def pe_ratio_ttm(payloads, facts) -> Fact:
    ident = payloads.subject_fundamentals_identifier()
    payload = payloads.by_identifier(ident)
    return Fact(
        name="pe_ratio_ttm",
        value=pluck(payload, "Highlights", "PERatio"),
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
    )


@register_fact("sector", tier="deterministic", depends_on=[])
def sector(payloads, facts) -> Fact:
    ident = payloads.subject_fundamentals_identifier()
    payload = payloads.by_identifier(ident)
    return Fact(
        name="sector",
        value=pluck(payload, "General", "Sector"),
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
    )


@register_fact("company_name", tier="deterministic", depends_on=[])
def company_name(payloads, facts) -> Fact:
    ident = payloads.subject_fundamentals_identifier()
    payload = payloads.by_identifier(ident)
    return Fact(
        name="company_name",
        value=pluck(payload, "General", "Name"),
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
    )


@register_fact("revenue_annual", tier="deterministic", depends_on=[])
def revenue_annual(payloads, facts) -> Fact:
    ident = payloads.subject_fundamentals_identifier()
    payload = payloads.by_identifier(ident)
    return Fact(
        name="revenue_annual",
        value=yearly_series(payload, statement="Income_Statement", field="totalRevenue"),
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
    )


@register_fact("gross_profit_annual", tier="deterministic", depends_on=[])
def gross_profit_annual(payloads, facts) -> Fact:
    ident = payloads.subject_fundamentals_identifier()
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


def _peer_source_ids_or_subject_fallback(payloads, used_ids: list[int]) -> list[int]:
    """Aggregate peer-derived source_ids, falling back to the subject's manifest id when
    no peer data was usable. `Fact.source_ids` requires at least one entry; an empty
    peer set is itself a finding sourced from the only manifest entry we consulted."""
    if used_ids:
        return sorted(set(used_ids))
    return [payloads.manifest_id_for(payloads.subject_fundamentals_identifier())]


def _peer_revenue_series(payload) -> list[float] | None:
    try:
        return yearly_series(payload, statement="Income_Statement", field="totalRevenue")
    except (KeyError, ValueError, TypeError):
        return None


def _peer_gross_profit_series(payload) -> list[float] | None:
    try:
        return yearly_series(payload, statement="Income_Statement", field="grossProfit")
    except (KeyError, ValueError, TypeError):
        return None


@register_fact("peer_pe_ratio_ttm", tier="deterministic", depends_on=[])
def peer_pe_ratio_ttm(payloads, facts) -> Fact:
    """P/E ratio per peer ticker, as a dict keyed by uppercase ticker symbol."""
    values: dict[str, float] = {}
    used_ids: list[int] = []
    for ticker, ident in payloads.peer_fundamentals():
        payload = payloads.by_identifier(ident)
        pe = pluck_or_none(payload, "Highlights", "PERatio")
        if pe is None:
            continue
        try:
            values[ticker.upper()] = float(pe)
        except (TypeError, ValueError):
            continue
        used_ids.append(payloads.manifest_id_for(ident))
    return Fact(
        name="peer_pe_ratio_ttm",
        value=values,
        source_ids=_peer_source_ids_or_subject_fallback(payloads, used_ids),
        extractor="deterministic",
    )


@register_fact("peer_revenue_cagr_3y", tier="compute", depends_on=[])
def peer_revenue_cagr_3y(payloads, facts) -> Fact:
    """3-year revenue CAGR per peer ticker (decimal, e.g. 0.165 = 16.5%)."""
    values: dict[str, float] = {}
    used_ids: list[int] = []
    for ticker, ident in payloads.peer_fundamentals():
        series = _peer_revenue_series(payloads.by_identifier(ident))
        if not series:
            continue
        try:
            values[ticker.upper()] = cagr(series, years=3)
        except (ValueError, ZeroDivisionError):
            continue
        used_ids.append(payloads.manifest_id_for(ident))
    return Fact(
        name="peer_revenue_cagr_3y",
        value=values,
        source_ids=_peer_source_ids_or_subject_fallback(payloads, used_ids),
        extractor="compute",
    )


@register_fact("peer_gross_margin_ttm", tier="compute", depends_on=[])
def peer_gross_margin_ttm(payloads, facts) -> Fact:
    """Trailing gross margin per peer ticker (decimal, e.g. 0.694 = 69.4%)."""
    values: dict[str, float] = {}
    used_ids: list[int] = []
    for ticker, ident in payloads.peer_fundamentals():
        payload = payloads.by_identifier(ident)
        rev = _peer_revenue_series(payload)
        gp = _peer_gross_profit_series(payload)
        if not rev or not gp:
            continue
        try:
            values[ticker.upper()] = gp[-1] / rev[-1]
        except (TypeError, ZeroDivisionError):
            continue
        used_ids.append(payloads.manifest_id_for(ident))
    return Fact(
        name="peer_gross_margin_ttm",
        value=values,
        source_ids=_peer_source_ids_or_subject_fallback(payloads, used_ids),
        extractor="compute",
    )
