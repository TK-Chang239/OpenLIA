"""Registered facts for the stock_initiation report type.

Importing this module triggers registration with the default_registry.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

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
    # Highlights/General lack any filing date; use the ManifestEntry retrieval timestamp.
    return Fact(
        name="market_cap",
        value=pluck(payload, "Highlights", "MarketCapitalization"),
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.retrieved_at_for(ident),
        source_tier="vendor",
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
        data_as_of=payloads.retrieved_at_for(ident),
        source_tier="vendor",
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
        data_as_of=payloads.retrieved_at_for(ident),
        source_tier="vendor",
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
        data_as_of=payloads.retrieved_at_for(ident),
        source_tier="vendor",
    )


@register_fact("revenue_annual", tier="deterministic", depends_on=[])
def revenue_annual(payloads, facts) -> Fact:
    ident = payloads.subject_fundamentals_identifier()
    payload = payloads.by_identifier(ident)
    # Annual facts: latest yearly Income_Statement key is the canonical filing date.
    return Fact(
        name="revenue_annual",
        value=yearly_series(payload, statement="Income_Statement", field="totalRevenue"),
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.latest_annual_filing_date(ident),
        source_tier="vendor",
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
        data_as_of=payloads.latest_annual_filing_date(ident),
        source_tier="vendor",
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
        data_as_of=facts["revenue_annual"].data_as_of,
        source_tier="derived",
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
        data_as_of=facts["revenue_annual"].data_as_of,
        source_tier="derived",
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
    subject_ident = payloads.subject_fundamentals_identifier()
    return Fact(
        name="peer_pe_ratio_ttm",
        value=values,
        source_ids=_peer_source_ids_or_subject_fallback(payloads, used_ids),
        extractor="deterministic",
        data_as_of=payloads.retrieved_at_for(subject_ident),
        source_tier="vendor",
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
    subject_ident = payloads.subject_fundamentals_identifier()
    return Fact(
        name="peer_revenue_cagr_3y",
        value=values,
        source_ids=_peer_source_ids_or_subject_fallback(payloads, used_ids),
        extractor="compute",
        data_as_of=payloads.latest_annual_filing_date(subject_ident),
        source_tier="derived",
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
    subject_ident = payloads.subject_fundamentals_identifier()
    return Fact(
        name="peer_gross_margin_ttm",
        value=values,
        source_ids=_peer_source_ids_or_subject_fallback(payloads, used_ids),
        extractor="compute",
        data_as_of=payloads.latest_annual_filing_date(subject_ident),
        source_tier="derived",
    )


# ---------------------------------------------------------------------------
# Subject identity fields (deterministic, sourced from EODHD `General` block).
# These power the company-identity card and the rail market-data strip.
# ---------------------------------------------------------------------------


def _subject_fundamentals_payload(payloads):
    ident = payloads.subject_fundamentals_identifier()
    return ident, payloads.by_identifier(ident)


@register_fact("ipo_date", tier="deterministic", depends_on=[])
def ipo_date(payloads, facts) -> Fact:
    ident, payload = _subject_fundamentals_payload(payloads)
    return Fact(
        name="ipo_date",
        value=pluck_or_none(payload, "General", "IPODate"),
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.retrieved_at_for(ident),
        source_tier="vendor",
    )


@register_fact("employees", tier="deterministic", depends_on=[])
def employees(payloads, facts) -> Fact:
    ident, payload = _subject_fundamentals_payload(payloads)
    return Fact(
        name="employees",
        value=pluck_or_none(payload, "General", "FullTimeEmployees"),
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.retrieved_at_for(ident),
        source_tier="vendor",
    )


@register_fact("exchange", tier="deterministic", depends_on=[])
def exchange(payloads, facts) -> Fact:
    ident, payload = _subject_fundamentals_payload(payloads)
    return Fact(
        name="exchange",
        value=pluck_or_none(payload, "General", "Exchange"),
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.retrieved_at_for(ident),
        source_tier="vendor",
    )


@register_fact("headquarters", tier="deterministic", depends_on=[])
def headquarters(payloads, facts) -> Fact:
    """Compact HQ string from AddressData ("City, State, Country")."""
    ident, payload = _subject_fundamentals_payload(payloads)
    addr = pluck_or_none(payload, "General", "AddressData") or {}
    parts = [addr.get("City"), addr.get("State"), addr.get("Country")]
    value = ", ".join(p for p in parts if p)
    return Fact(
        name="headquarters",
        value=value if value else None,
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.retrieved_at_for(ident),
        source_tier="vendor",
    )


# ---------------------------------------------------------------------------
# Subject Highlights — extra valuation/profitability fields used by the cover
# hero, rail market-data strip, and margin-progression rows.
# ---------------------------------------------------------------------------


@register_fact("pe_ratio_forward", tier="deterministic", depends_on=[])
def pe_ratio_forward(payloads, facts) -> Fact:
    ident, payload = _subject_fundamentals_payload(payloads)
    return Fact(
        name="pe_ratio_forward",
        value=pluck_or_none(payload, "Highlights", "ForwardPE"),
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.retrieved_at_for(ident),
        source_tier="vendor",
    )


@register_fact("net_margin_ttm", tier="deterministic", depends_on=[])
def net_margin_ttm(payloads, facts) -> Fact:
    ident, payload = _subject_fundamentals_payload(payloads)
    return Fact(
        name="net_margin_ttm",
        value=pluck_or_none(payload, "Highlights", "ProfitMargin"),
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.retrieved_at_for(ident),
        source_tier="vendor",
    )


@register_fact("operating_margin_ttm", tier="deterministic", depends_on=[])
def operating_margin_ttm(payloads, facts) -> Fact:
    ident, payload = _subject_fundamentals_payload(payloads)
    return Fact(
        name="operating_margin_ttm",
        value=pluck_or_none(payload, "Highlights", "OperatingMarginTTM"),
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.retrieved_at_for(ident),
        source_tier="vendor",
    )


@register_fact("ebitda_ttm", tier="deterministic", depends_on=[])
def ebitda_ttm(payloads, facts) -> Fact:
    ident, payload = _subject_fundamentals_payload(payloads)
    return Fact(
        name="ebitda_ttm",
        value=pluck_or_none(payload, "Highlights", "EBITDA"),
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.retrieved_at_for(ident),
        source_tier="vendor",
    )


@register_fact("revenue_ttm", tier="deterministic", depends_on=[])
def revenue_ttm(payloads, facts) -> Fact:
    ident, payload = _subject_fundamentals_payload(payloads)
    return Fact(
        name="revenue_ttm",
        value=pluck_or_none(payload, "Highlights", "RevenueTTM"),
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.retrieved_at_for(ident),
        source_tier="vendor",
    )


@register_fact("eps_ttm", tier="deterministic", depends_on=[])
def eps_ttm(payloads, facts) -> Fact:
    ident, payload = _subject_fundamentals_payload(payloads)
    return Fact(
        name="eps_ttm",
        value=pluck_or_none(payload, "Highlights", "EarningsShare"),
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.retrieved_at_for(ident),
        source_tier="vendor",
    )


# ---------------------------------------------------------------------------
# Current price (live) — from `get_live_stock_prices/<TICKER>`.
# ---------------------------------------------------------------------------


@register_fact("current_price", tier="deterministic", depends_on=[])
def current_price(payloads, facts) -> Fact:
    ident = payloads.subject_identifier_for("get_live_stock_prices")
    if ident is None:
        # Fall back to fundamentals identifier so the Fact has a valid source.
        fid = payloads.subject_fundamentals_identifier()
        return Fact(
            name="current_price",
            value=None,
            source_ids=[payloads.manifest_id_for(fid)],
            extractor="deterministic",
            data_as_of=payloads.retrieved_at_for(fid),
            source_tier="vendor",
        )
    payload = payloads.by_identifier(ident)
    # EODHD live returns a top-level dict with `close` or `last` key.
    value: float | None = None
    for k in ("close", "last", "price"):
        v = payload.get(k) if isinstance(payload, dict) else None
        if v is not None:
            try:
                value = float(v)
                break
            except (TypeError, ValueError):
                continue
    # Use the live payload's own date when present; otherwise the retrieval
    # timestamp. EODHD live exposes a top-level `date` (YYYY-MM-DD) and
    # `timestamp` (epoch seconds); prefer the explicit date string.
    live_date: Any = None
    if isinstance(payload, dict):
        live_date = payload.get("date") or payload.get("timestamp")
    return Fact(
        name="current_price",
        value=value,
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=live_date if live_date is not None else payloads.retrieved_at_for(ident),
        source_tier="vendor",
    )


# ---------------------------------------------------------------------------
# 52-week range and average daily trading volume — from EOD history.
# ---------------------------------------------------------------------------


def _eod_history_rows(payloads) -> tuple[str | None, list[dict]]:
    ident = payloads.subject_identifier_for("get_eod_historical_stock_market_data")
    if ident is None:
        return None, []
    rows = payloads.by_identifier(ident)
    if not isinstance(rows, list):
        return ident, []
    return ident, rows


@register_fact("price_range_52w", tier="deterministic", depends_on=[])
def price_range_52w(payloads, facts) -> Fact:
    ident, rows = _eod_history_rows(payloads)
    last_252 = rows[-252:] if len(rows) > 252 else rows
    highs = [
        float(r["high"]) for r in last_252 if isinstance(r, dict) and r.get("high") is not None
    ]
    lows = [float(r["low"]) for r in last_252 if isinstance(r, dict) and r.get("low") is not None]
    value = {"low": min(lows), "high": max(highs)} if highs and lows else None
    fallback = payloads.subject_fundamentals_identifier()
    chosen = ident or fallback
    # Use the latest EOD row's date when available; otherwise the retrieval timestamp.
    last_date: Any = None
    if last_252 and isinstance(last_252[-1], dict):
        last_date = last_252[-1].get("date")
    return Fact(
        name="price_range_52w",
        value=value,
        source_ids=[payloads.manifest_id_for(chosen)],
        extractor="deterministic",
        data_as_of=last_date if last_date is not None else payloads.retrieved_at_for(chosen),
        source_tier="vendor",
    )


@register_fact("avg_daily_volume_3m", tier="deterministic", depends_on=[])
def avg_daily_volume_3m(payloads, facts) -> Fact:
    ident, rows = _eod_history_rows(payloads)
    last_63 = rows[-63:] if len(rows) > 63 else rows
    vols = [
        float(r["volume"]) for r in last_63 if isinstance(r, dict) and r.get("volume") is not None
    ]
    value = sum(vols) / len(vols) if vols else None
    fallback = payloads.subject_fundamentals_identifier()
    chosen = ident or fallback
    last_date: Any = None
    if last_63 and isinstance(last_63[-1], dict):
        last_date = last_63[-1].get("date")
    return Fact(
        name="avg_daily_volume_3m",
        value=value,
        source_ids=[payloads.manifest_id_for(chosen)],
        extractor="deterministic",
        data_as_of=last_date if last_date is not None else payloads.retrieved_at_for(chosen),
        source_tier="vendor",
    )


# ---------------------------------------------------------------------------
# Analyst consensus (deterministic, sourced from EODHD `AnalystRatings`).
# Powers the cover hero verdict pill, rail verdict card, and analyst_view
# section's rating-distribution and price-target-band blocks. NEVER LLM-AUTHORED.
# ---------------------------------------------------------------------------

_ANALYST_RATING_LABELS = {
    1: "Strong Buy",
    2: "Buy",
    3: "Hold",
    4: "Sell",
    5: "Strong Sell",
}


def _analyst_block(payload) -> dict | None:
    """Return the AnalystRatings sub-dict if present and well-formed."""
    block = pluck_or_none(payload, "AnalystRatings")
    return block if isinstance(block, dict) else None


@register_fact("analyst_consensus_rating", tier="deterministic", depends_on=[])
def analyst_consensus_rating(payloads, facts) -> Fact:
    """Consensus rating label ("Strong Buy" / "Buy" / "Hold" / "Sell" / "Strong Sell")
    derived from `AnalystRatings.Rating` (1.0-5.0 scale, 1 = strongest buy)."""
    ident, payload = _subject_fundamentals_payload(payloads)
    block = _analyst_block(payload)
    label: str | None = None
    if block is not None:
        raw = block.get("Rating")
        if raw is not None:
            try:
                bucket = max(1, min(5, round(float(raw))))
                label = _ANALYST_RATING_LABELS[bucket]
            except (TypeError, ValueError):
                label = None
    return Fact(
        name="analyst_consensus_rating",
        value=label,
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.retrieved_at_for(ident),
        source_tier="vendor",
    )


@register_fact("analyst_target_mean", tier="deterministic", depends_on=[])
def analyst_target_mean(payloads, facts) -> Fact:
    """Mean analyst price target. Prefers `Highlights.WallStreetTargetPrice` (the
    canonical aggregated mean); falls back to `AnalystRatings.TargetPrice`."""
    ident, payload = _subject_fundamentals_payload(payloads)
    value = pluck_or_none(payload, "Highlights", "WallStreetTargetPrice")
    if value is None:
        block = _analyst_block(payload)
        if block is not None:
            value = block.get("TargetPrice")
    try:
        value = float(value) if value is not None else None
    except (TypeError, ValueError):
        value = None
    return Fact(
        name="analyst_target_mean",
        value=value,
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.retrieved_at_for(ident),
        source_tier="vendor",
    )


@register_fact("analyst_count", tier="deterministic", depends_on=[])
def analyst_count(payloads, facts) -> Fact:
    """Total covering analysts: StrongBuy + Buy + Hold + Sell + StrongSell."""
    ident, payload = _subject_fundamentals_payload(payloads)
    block = _analyst_block(payload) or {}
    total = 0
    for k in ("StrongBuy", "Buy", "Hold", "Sell", "StrongSell"):
        v = block.get(k)
        try:
            total += int(v) if v is not None else 0
        except (TypeError, ValueError):
            continue
    return Fact(
        name="analyst_count",
        value=total if total > 0 else None,
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.retrieved_at_for(ident),
        source_tier="vendor",
    )


@register_fact("analyst_rating_distribution", tier="deterministic", depends_on=[])
def analyst_rating_distribution(payloads, facts) -> Fact:
    """Dict of bucket → count for the rating distribution stacked-bar exhibit."""
    ident, payload = _subject_fundamentals_payload(payloads)
    block = _analyst_block(payload) or {}
    out: dict[str, int] = {}
    for k in ("StrongBuy", "Buy", "Hold", "Sell", "StrongSell"):
        v = block.get(k)
        try:
            n = int(v) if v is not None else 0
        except (TypeError, ValueError):
            continue
        if n > 0:
            out[k] = n
    return Fact(
        name="analyst_rating_distribution",
        value=out if out else None,
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.retrieved_at_for(ident),
        source_tier="vendor",
    )


@register_fact(
    "consensus_upside_pct",
    tier="compute",
    depends_on=["analyst_target_mean", "current_price"],
)
def consensus_upside_pct(payloads, facts) -> Fact:
    """Consensus upside vs. current price: (target - price) / price.

    Only meaningful when both inputs are present. Returns None otherwise so the
    cover/rail verdict can suppress the upside display cleanly."""
    target = facts["analyst_target_mean"].value
    price = facts["current_price"].value
    value: float | None = None
    if (
        target is not None
        and price is not None
        and isinstance(target, int | float)
        and isinstance(price, int | float)
        and price > 0
    ):
        value = (float(target) - float(price)) / float(price)
    return Fact(
        name="consensus_upside_pct",
        value=value,
        source_ids=union_source_ids(facts["analyst_target_mean"], facts["current_price"]),
        extractor="compute",
        depends_on=["analyst_target_mean", "current_price"],
        data_as_of=facts["current_price"].data_as_of,
        source_tier="derived",
    )


# ---------------------------------------------------------------------------
# Full income-statement and balance-sheet annual series (5y).
# Power the always-included historical financial tables.
# ---------------------------------------------------------------------------


def _series_or_none(payload, *, statement: str, field: str) -> list[float] | None:
    try:
        return yearly_series(payload, statement=statement, field=field)
    except (KeyError, ValueError, TypeError):
        return None


@register_fact("revenue_years", tier="deterministic", depends_on=[])
def revenue_years(payloads, facts) -> Fact:
    """Sorted list of fiscal-year-end dates for the Income_Statement series.
    Used as the row key for the always-included historical tables."""
    ident, payload = _subject_fundamentals_payload(payloads)
    yearly = pluck_or_none(payload, "Financials", "Income_Statement", "yearly") or {}
    dates = sorted(yearly.keys())[-5:]
    return Fact(
        name="revenue_years",
        value=dates if dates else None,
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.latest_annual_filing_date(ident),
        source_tier="vendor",
    )


@register_fact("cogs_annual", tier="deterministic", depends_on=[])
def cogs_annual(payloads, facts) -> Fact:
    ident, payload = _subject_fundamentals_payload(payloads)
    return Fact(
        name="cogs_annual",
        value=_series_or_none(payload, statement="Income_Statement", field="costOfRevenue"),
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.latest_annual_filing_date(ident),
        source_tier="vendor",
    )


@register_fact("operating_income_annual", tier="deterministic", depends_on=[])
def operating_income_annual(payloads, facts) -> Fact:
    ident, payload = _subject_fundamentals_payload(payloads)
    return Fact(
        name="operating_income_annual",
        value=_series_or_none(payload, statement="Income_Statement", field="operatingIncome"),
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.latest_annual_filing_date(ident),
        source_tier="vendor",
    )


@register_fact("net_income_annual", tier="deterministic", depends_on=[])
def net_income_annual(payloads, facts) -> Fact:
    ident, payload = _subject_fundamentals_payload(payloads)
    return Fact(
        name="net_income_annual",
        value=_series_or_none(payload, statement="Income_Statement", field="netIncome"),
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.latest_annual_filing_date(ident),
        source_tier="vendor",
    )


@register_fact("eps_annual", tier="deterministic", depends_on=[])
def eps_annual(payloads, facts) -> Fact:
    ident, payload = _subject_fundamentals_payload(payloads)
    return Fact(
        name="eps_annual",
        value=_series_or_none(payload, statement="Income_Statement", field="eps"),
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.latest_annual_filing_date(ident),
        source_tier="vendor",
    )


@register_fact("total_assets_annual", tier="deterministic", depends_on=[])
def total_assets_annual(payloads, facts) -> Fact:
    ident, payload = _subject_fundamentals_payload(payloads)
    return Fact(
        name="total_assets_annual",
        value=_series_or_none(payload, statement="Balance_Sheet", field="totalAssets"),
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.latest_annual_filing_date(ident),
        source_tier="vendor",
    )


@register_fact("total_liabilities_annual", tier="deterministic", depends_on=[])
def total_liabilities_annual(payloads, facts) -> Fact:
    ident, payload = _subject_fundamentals_payload(payloads)
    return Fact(
        name="total_liabilities_annual",
        value=_series_or_none(payload, statement="Balance_Sheet", field="totalLiab"),
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.latest_annual_filing_date(ident),
        source_tier="vendor",
    )


@register_fact("equity_annual", tier="deterministic", depends_on=[])
def equity_annual(payloads, facts) -> Fact:
    ident, payload = _subject_fundamentals_payload(payloads)
    return Fact(
        name="equity_annual",
        value=_series_or_none(payload, statement="Balance_Sheet", field="totalStockholderEquity"),
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.latest_annual_filing_date(ident),
        source_tier="vendor",
    )


@register_fact("cash_annual", tier="deterministic", depends_on=[])
def cash_annual(payloads, facts) -> Fact:
    ident, payload = _subject_fundamentals_payload(payloads)
    return Fact(
        name="cash_annual",
        value=_series_or_none(payload, statement="Balance_Sheet", field="cash"),
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.latest_annual_filing_date(ident),
        source_tier="vendor",
    )


@register_fact("total_debt_annual", tier="deterministic", depends_on=[])
def total_debt_annual(payloads, facts) -> Fact:
    ident, payload = _subject_fundamentals_payload(payloads)
    # EODHD has a few naming variations; prefer the explicit total-debt field.
    series = _series_or_none(payload, statement="Balance_Sheet", field="shortLongTermDebtTotal")
    if series is None:
        series = _series_or_none(payload, statement="Balance_Sheet", field="totalDebt")
    return Fact(
        name="total_debt_annual",
        value=series,
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.latest_annual_filing_date(ident),
        source_tier="vendor",
    )


# ---------------------------------------------------------------------------
# Computed multi-year margin progression — for the Financial Analysis
# always-included margin table.
# ---------------------------------------------------------------------------


def _zip_div(
    numerators: list[float] | None, denominators: list[float] | None
) -> list[float] | None:
    if not numerators or not denominators:
        return None
    n = min(len(numerators), len(denominators))
    out: list[float] = []
    for i in range(n):
        d = denominators[i]
        if d == 0 or d is None:
            return None  # Bail rather than emit a partially-aligned series.
        out.append(float(numerators[i]) / float(d))
    return out


@register_fact(
    "gross_margin_annual",
    tier="compute",
    depends_on=["revenue_annual", "gross_profit_annual"],
)
def gross_margin_annual(payloads, facts) -> Fact:
    return Fact(
        name="gross_margin_annual",
        value=_zip_div(facts["gross_profit_annual"].value, facts["revenue_annual"].value),
        source_ids=union_source_ids(facts["revenue_annual"], facts["gross_profit_annual"]),
        extractor="compute",
        depends_on=["revenue_annual", "gross_profit_annual"],
        data_as_of=facts["revenue_annual"].data_as_of,
        source_tier="derived",
    )


@register_fact(
    "operating_margin_annual",
    tier="compute",
    depends_on=["revenue_annual", "operating_income_annual"],
)
def operating_margin_annual(payloads, facts) -> Fact:
    return Fact(
        name="operating_margin_annual",
        value=_zip_div(facts["operating_income_annual"].value, facts["revenue_annual"].value),
        source_ids=union_source_ids(facts["revenue_annual"], facts["operating_income_annual"]),
        extractor="compute",
        depends_on=["revenue_annual", "operating_income_annual"],
        data_as_of=facts["revenue_annual"].data_as_of,
        source_tier="derived",
    )


@register_fact(
    "net_margin_annual",
    tier="compute",
    depends_on=["revenue_annual", "net_income_annual"],
)
def net_margin_annual(payloads, facts) -> Fact:
    return Fact(
        name="net_margin_annual",
        value=_zip_div(facts["net_income_annual"].value, facts["revenue_annual"].value),
        source_ids=union_source_ids(facts["revenue_annual"], facts["net_income_annual"]),
        extractor="compute",
        depends_on=["revenue_annual", "net_income_annual"],
        data_as_of=facts["revenue_annual"].data_as_of,
        source_tier="derived",
    )


# ---------------------------------------------------------------------------
# Broader peer multiples (P/B, EV/EBITDA, PEG) — extends the existing
# peer_pe_ratio_ttm so the always-included peer multiples table can ship
# with the four-column shape the May 16 reports had.
# ---------------------------------------------------------------------------


@register_fact("peer_price_to_book", tier="deterministic", depends_on=[])
def peer_price_to_book(payloads, facts) -> Fact:
    values: dict[str, float] = {}
    used_ids: list[int] = []
    for ticker, ident in payloads.peer_fundamentals():
        payload = payloads.by_identifier(ident)
        v = pluck_or_none(payload, "Highlights", "PriceToBookMRQ")
        if v is None:
            continue
        try:
            values[ticker.upper()] = float(v)
        except (TypeError, ValueError):
            continue
        used_ids.append(payloads.manifest_id_for(ident))
    subject_ident = payloads.subject_fundamentals_identifier()
    return Fact(
        name="peer_price_to_book",
        value=values,
        source_ids=_peer_source_ids_or_subject_fallback(payloads, used_ids),
        extractor="deterministic",
        data_as_of=payloads.retrieved_at_for(subject_ident),
        source_tier="vendor",
    )


@register_fact("peer_ev_to_ebitda", tier="deterministic", depends_on=[])
def peer_ev_to_ebitda(payloads, facts) -> Fact:
    values: dict[str, float] = {}
    used_ids: list[int] = []
    for ticker, ident in payloads.peer_fundamentals():
        payload = payloads.by_identifier(ident)
        v = pluck_or_none(payload, "Highlights", "EVToEBITDA")
        if v is None:
            continue
        try:
            values[ticker.upper()] = float(v)
        except (TypeError, ValueError):
            continue
        used_ids.append(payloads.manifest_id_for(ident))
    subject_ident = payloads.subject_fundamentals_identifier()
    return Fact(
        name="peer_ev_to_ebitda",
        value=values,
        source_ids=_peer_source_ids_or_subject_fallback(payloads, used_ids),
        extractor="deterministic",
        data_as_of=payloads.retrieved_at_for(subject_ident),
        source_tier="vendor",
    )


@register_fact("peer_peg_ratio", tier="deterministic", depends_on=[])
def peer_peg_ratio(payloads, facts) -> Fact:
    values: dict[str, float] = {}
    used_ids: list[int] = []
    for ticker, ident in payloads.peer_fundamentals():
        payload = payloads.by_identifier(ident)
        v = pluck_or_none(payload, "Highlights", "PEGRatio")
        if v is None:
            continue
        try:
            values[ticker.upper()] = float(v)
        except (TypeError, ValueError):
            continue
        used_ids.append(payloads.manifest_id_for(ident))
    subject_ident = payloads.subject_fundamentals_identifier()
    return Fact(
        name="peer_peg_ratio",
        value=values,
        source_ids=_peer_source_ids_or_subject_fallback(payloads, used_ids),
        extractor="deterministic",
        data_as_of=payloads.retrieved_at_for(subject_ident),
        source_tier="vendor",
    )


# ---------------------------------------------------------------------------
# P3/WS2: facts expansion. Segment, capital-structure, FCF, returns, SBC,
# dividend, share-count, forward-consensus, and peer-absolute facts.
# Each extractor returns Fact(value=None ...) cleanly when the EODHD payload
# lacks the source field — never fabricates. data_as_of and source_tier
# follow the P1 conventions: annual/quarterly facts use the latest filing
# date; live/highlights facts use retrieved_at; derived facts inherit from
# the oldest dependency.
# ---------------------------------------------------------------------------


def _oldest_dep_as_of(*facts: Fact) -> datetime | str | None:
    """Return the oldest `data_as_of` across a set of dependency facts.

    Mirrors `freshness.oldest_data_as_of` but operates on positional Fact
    arguments rather than a dict, for use inside compute-tier extractors.
    Returns the original value (str or datetime) for display."""
    oldest: tuple[datetime, datetime | str] | None = None
    for f in facts:
        v = f.data_as_of
        if v is None:
            continue
        parsed: datetime | None
        if isinstance(v, datetime):
            parsed = v if v.tzinfo is not None else v.replace(tzinfo=UTC)
        elif isinstance(v, str):
            s = v.strip()
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            try:
                parsed = datetime.fromisoformat(s)
            except ValueError:
                try:
                    parsed = datetime.strptime(s, "%Y-%m-%d")
                except ValueError:
                    parsed = None
            if parsed is not None and parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
        else:
            parsed = None
        if parsed is None:
            continue
        if oldest is None or parsed < oldest[0]:
            oldest = (parsed, v)
    return oldest[1] if oldest is not None else None


def _newest_dep_as_of(*facts: Fact) -> datetime | str | None:
    """Return the newest `data_as_of` across a set of dependency facts.

    Use this for derived facts whose freshness is gated by the most recently
    updated input — typically forward-looking estimates anchored on stable
    historical data (e.g. `consensus_eps_growth_fy_next` = consensus / prior
    annual EPS). The historical anchor is by definition non-recent; the
    growth value is "as fresh as the consensus that produced it."
    """
    newest: tuple[datetime, datetime | str] | None = None
    for f in facts:
        v = f.data_as_of
        if v is None:
            continue
        parsed: datetime | None
        if isinstance(v, datetime):
            parsed = v if v.tzinfo is not None else v.replace(tzinfo=UTC)
        elif isinstance(v, str):
            s = v.strip()
            if s.endswith("Z"):
                s = s[:-1] + "+00:00"
            try:
                parsed = datetime.fromisoformat(s)
            except ValueError:
                try:
                    parsed = datetime.strptime(s, "%Y-%m-%d")
                except ValueError:
                    parsed = None
            if parsed is not None and parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=UTC)
        else:
            parsed = None
        if parsed is None:
            continue
        if newest is None or parsed > newest[0]:
            newest = (parsed, v)
    return newest[1] if newest is not None else None


# --- Group 1: Segment / business-model facts -------------------------------


def _segment_breakdown_block(payload: Any) -> Any:
    """Return the EODHD SegmentBreakdown sub-block when present.

    EODHD's `SegmentBreakdown` shape is inconsistent across tickers — many
    fundamentals payloads omit the field entirely. Callers must handle the
    None case cleanly."""
    return pluck_or_none(payload, "SegmentBreakdown")


def _latest_segment_revenue(block: Any) -> tuple[dict[str, float] | None, str | None]:
    """From a SegmentBreakdown dict (date -> {segment: dollars}), return the
    most recent year's segment-revenue dict plus the date string.

    Returns (None, None) when the block is missing, malformed, or empty."""
    if not isinstance(block, dict) or not block:
        return None, None
    # Each top-level key is a date string mapping to a dict of segment names.
    valid_dates = [k for k in block if isinstance(block.get(k), dict)]
    if not valid_dates:
        return None, None
    latest = max(valid_dates)
    raw = block[latest]
    out: dict[str, float] = {}
    for segment_name, dollars in raw.items():
        try:
            out[str(segment_name)] = float(dollars)
        except (TypeError, ValueError):
            continue
    return (out if out else None), latest


@register_fact("segment_revenue_latest", tier="deterministic", depends_on=[])
def segment_revenue_latest(payloads, facts) -> Fact:
    """Most recent fiscal-year segment revenue as a {segment -> dollars} dict.

    Source: EODHD `SegmentBreakdown` when present. Many EODHD payloads do not
    expose this field; in that case the fact returns value=None and the
    business_model / products_and_services prompts are expected to omit the
    segment pie rather than fabricate one."""
    ident, payload = _subject_fundamentals_payload(payloads)
    block = _segment_breakdown_block(payload)
    value, _ = _latest_segment_revenue(block)
    return Fact(
        name="segment_revenue_latest",
        value=value,
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.latest_annual_filing_date(ident),
        source_tier="vendor",
    )


@register_fact("segment_revenue_yoy", tier="deterministic", depends_on=[])
def segment_revenue_yoy(payloads, facts) -> Fact:
    """Multi-year segment-revenue series as a {segment -> [year_dollars]} dict.

    Source: EODHD `SegmentBreakdown`. Years are sorted ascending; segments
    missing in a given year are filled with None. Returns value=None when the
    SegmentBreakdown block is absent or malformed."""
    ident, payload = _subject_fundamentals_payload(payloads)
    block = _segment_breakdown_block(payload)
    if not isinstance(block, dict) or not block:
        return Fact(
            name="segment_revenue_yoy",
            value=None,
            source_ids=[payloads.manifest_id_for(ident)],
            extractor="deterministic",
            data_as_of=payloads.latest_annual_filing_date(ident),
            source_tier="vendor",
        )
    dates = sorted(k for k in block if isinstance(block.get(k), dict))
    if not dates:
        return Fact(
            name="segment_revenue_yoy",
            value=None,
            source_ids=[payloads.manifest_id_for(ident)],
            extractor="deterministic",
            data_as_of=payloads.latest_annual_filing_date(ident),
            source_tier="vendor",
        )
    segment_names: set[str] = set()
    for d in dates:
        for seg in block[d]:
            segment_names.add(str(seg))
    series: dict[str, list[float | None]] = {seg: [] for seg in segment_names}
    for d in dates:
        row = block[d]
        for seg in segment_names:
            raw = row.get(seg)
            try:
                series[seg].append(float(raw) if raw is not None else None)
            except (TypeError, ValueError):
                series[seg].append(None)
    return Fact(
        name="segment_revenue_yoy",
        value=series if series else None,
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.latest_annual_filing_date(ident),
        source_tier="vendor",
    )


@register_fact("fiscal_year_end_latest", tier="deterministic", depends_on=[])
def fiscal_year_end_latest(payloads, facts) -> Fact:
    """Date string of the most recent annual fiscal year-end (e.g. "2024-12-31").

    Pulled from the latest key in `Financials.Income_Statement.yearly`. Used
    by WS4 year-label consistency validation to keep every section's "FY20XX"
    reference aligned with the company's actual fiscal calendar."""
    ident, payload = _subject_fundamentals_payload(payloads)
    yearly = pluck_or_none(payload, "Financials", "Income_Statement", "yearly")
    value: str | None = None
    if isinstance(yearly, dict) and yearly:
        value = max(yearly.keys())
    return Fact(
        name="fiscal_year_end_latest",
        value=value,
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.latest_annual_filing_date(ident),
        source_tier="vendor",
    )


@register_fact(
    "segment_share_latest",
    tier="compute",
    depends_on=["segment_revenue_latest"],
)
def segment_share_latest(payloads, facts) -> Fact:
    """Derived: {segment -> share-of-total} percentages from segment_revenue_latest.

    Returns value=None when the upstream segment dict is missing or sums to 0.
    Shares sum to 1.0 within rounding."""
    seg = facts["segment_revenue_latest"]
    value: dict[str, float] | None = None
    if isinstance(seg.value, dict) and seg.value:
        total = 0.0
        for v in seg.value.values():
            try:
                total += float(v)
            except (TypeError, ValueError):
                continue
        if total > 0:
            value = {k: float(v) / total for k, v in seg.value.items()}
    return Fact(
        name="segment_share_latest",
        value=value,
        source_ids=union_source_ids(seg),
        extractor="compute",
        depends_on=["segment_revenue_latest"],
        data_as_of=seg.data_as_of,
        source_tier="derived",
    )


# --- Group 2: Capital structure and returns --------------------------------


@register_fact("cash_and_short_term_investments_annual", tier="deterministic", depends_on=[])
def cash_and_short_term_investments_annual(payloads, facts) -> Fact:
    """Annual series of cash + shortTermInvestments combined.

    The reviewer's "$10.6B cash" understatement traced to reading only the
    `cash` line; combining with `shortTermInvestments` matches how the 10-K
    reports total liquidity."""
    ident, payload = _subject_fundamentals_payload(payloads)
    cash = _series_or_none(payload, statement="Balance_Sheet", field="cash")
    sti = _series_or_none(payload, statement="Balance_Sheet", field="shortTermInvestments")
    value: list[float] | None
    if cash is None and sti is None:
        value = None
    elif cash is None:
        value = sti
    elif sti is None:
        value = cash
    else:
        n = min(len(cash), len(sti))
        value = [float(cash[i]) + float(sti[i]) for i in range(n)]
    return Fact(
        name="cash_and_short_term_investments_annual",
        value=value,
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.latest_annual_filing_date(ident),
        source_tier="vendor",
    )


@register_fact(
    "net_cash_annual",
    tier="compute",
    depends_on=["cash_and_short_term_investments_annual", "total_debt_annual"],
)
def net_cash_annual(payloads, facts) -> Fact:
    """Derived: cash + ST investments minus total debt, per year.

    Returns value=None when either input is missing. Series length matches
    the shorter of the two inputs."""
    cash = facts["cash_and_short_term_investments_annual"]
    debt = facts["total_debt_annual"]
    value: list[float] | None = None
    if isinstance(cash.value, list) and isinstance(debt.value, list):
        n = min(len(cash.value), len(debt.value))
        value = [float(cash.value[i]) - float(debt.value[i]) for i in range(n)]
    return Fact(
        name="net_cash_annual",
        value=value,
        source_ids=union_source_ids(cash, debt),
        extractor="compute",
        depends_on=["cash_and_short_term_investments_annual", "total_debt_annual"],
        data_as_of=_oldest_dep_as_of(cash, debt),
        source_tier="derived",
    )


@register_fact("operating_cash_flow_annual", tier="deterministic", depends_on=[])
def operating_cash_flow_annual(payloads, facts) -> Fact:
    """Annual operating cash flow series from the cash flow statement."""
    ident, payload = _subject_fundamentals_payload(payloads)
    series = _series_or_none(
        payload, statement="Cash_Flow", field="totalCashFromOperatingActivities"
    )
    return Fact(
        name="operating_cash_flow_annual",
        value=series,
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.latest_annual_filing_date(ident),
        source_tier="vendor",
    )


@register_fact("capex_annual", tier="deterministic", depends_on=[])
def capex_annual(payloads, facts) -> Fact:
    """Annual capital expenditures from the cash flow statement.

    EODHD reports capex as a negative number (cash outflow); sign is preserved
    so downstream callers can add directly to OCF for FCF."""
    ident, payload = _subject_fundamentals_payload(payloads)
    series = _series_or_none(payload, statement="Cash_Flow", field="capitalExpenditures")
    return Fact(
        name="capex_annual",
        value=series,
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.latest_annual_filing_date(ident),
        source_tier="vendor",
    )


@register_fact("free_cash_flow_annual", tier="deterministic", depends_on=[])
def free_cash_flow_annual(payloads, facts) -> Fact:
    """Annual free cash flow series.

    Prefers EODHD's `freeCashFlow` line. Falls back to
    `totalCashFromOperatingActivities + capitalExpenditures` (capex is
    typically negative in EODHD so addition yields FCF)."""
    ident, payload = _subject_fundamentals_payload(payloads)
    fcf = _series_or_none(payload, statement="Cash_Flow", field="freeCashFlow")
    if fcf is None:
        ocf = _series_or_none(
            payload, statement="Cash_Flow", field="totalCashFromOperatingActivities"
        )
        capex = _series_or_none(payload, statement="Cash_Flow", field="capitalExpenditures")
        if ocf is not None and capex is not None:
            n = min(len(ocf), len(capex))
            fcf = [float(ocf[i]) + float(capex[i]) for i in range(n)]
    return Fact(
        name="free_cash_flow_annual",
        value=fcf,
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.latest_annual_filing_date(ident),
        source_tier="vendor",
    )


@register_fact("roe_ttm", tier="deterministic", depends_on=[])
def roe_ttm(payloads, facts) -> Fact:
    """Trailing return on equity, from `Highlights.ReturnOnEquityTTM`."""
    ident, payload = _subject_fundamentals_payload(payloads)
    return Fact(
        name="roe_ttm",
        value=pluck_or_none(payload, "Highlights", "ReturnOnEquityTTM"),
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.retrieved_at_for(ident),
        source_tier="vendor",
    )


@register_fact("roa_ttm", tier="deterministic", depends_on=[])
def roa_ttm(payloads, facts) -> Fact:
    """Trailing return on assets, from `Highlights.ReturnOnAssetsTTM`."""
    ident, payload = _subject_fundamentals_payload(payloads)
    return Fact(
        name="roa_ttm",
        value=pluck_or_none(payload, "Highlights", "ReturnOnAssetsTTM"),
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.retrieved_at_for(ident),
        source_tier="vendor",
    )


@register_fact("roic_ttm", tier="deterministic", depends_on=[])
def roic_ttm(payloads, facts) -> Fact:
    """Trailing return on invested capital.

    EODHD does not expose ROIC directly. We substitute `ReturnOnAssetsTTM`
    when present and document the substitution here. A future helper-tier
    extractor (WS7) can compute true ROIC = NOPAT / avg invested capital."""
    ident, payload = _subject_fundamentals_payload(payloads)
    return Fact(
        name="roic_ttm",
        value=pluck_or_none(payload, "Highlights", "ReturnOnAssetsTTM"),
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.retrieved_at_for(ident),
        source_tier="vendor",
    )


@register_fact("sbc_annual", tier="deterministic", depends_on=[])
def sbc_annual(payloads, facts) -> Fact:
    """Stock-based compensation per year from the cash flow statement.

    EODHD's `stockBasedCompensation` is the standard non-cash add-back line."""
    ident, payload = _subject_fundamentals_payload(payloads)
    series = _series_or_none(payload, statement="Cash_Flow", field="stockBasedCompensation")
    return Fact(
        name="sbc_annual",
        value=series,
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.latest_annual_filing_date(ident),
        source_tier="vendor",
    )


@register_fact("buyback_authorization", tier="deterministic", depends_on=[])
def buyback_authorization(payloads, facts) -> Fact:
    """Outstanding share-repurchase authorization in dollars.

    EODHD does not expose a buyback-authorization field on its fundamentals
    payload. This extractor is registered as None for now so the section
    briefs can reference the name; a future LLM-tier extractor (WS3-A
    catalyst pack) can fill it from press-release scrapes."""
    ident, _payload = _subject_fundamentals_payload(payloads)
    return Fact(
        name="buyback_authorization",
        value=None,
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.retrieved_at_for(ident),
        source_tier="vendor",
    )


@register_fact("dividend_per_share_annual", tier="deterministic", depends_on=[])
def dividend_per_share_annual(payloads, facts) -> Fact:
    """Trailing dividend per share. Prefers `Highlights.DividendShare`; falls
    back to `SplitsDividends.ForwardAnnualDividendRate` when present.

    Returns a scalar (TTM rate), not a multi-year series — EODHD's fundamental
    payload exposes the headline rate but not a year-by-year history."""
    ident, payload = _subject_fundamentals_payload(payloads)
    value = pluck_or_none(payload, "Highlights", "DividendShare")
    if value is None:
        value = pluck_or_none(payload, "SplitsDividends", "ForwardAnnualDividendRate")
    try:
        value = float(value) if value is not None else None
    except (TypeError, ValueError):
        value = None
    return Fact(
        name="dividend_per_share_annual",
        value=value,
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.retrieved_at_for(ident),
        source_tier="vendor",
    )


@register_fact("dividend_yield", tier="deterministic", depends_on=[])
def dividend_yield(payloads, facts) -> Fact:
    """Trailing dividend yield as a decimal (e.g. 0.025 = 2.5%)."""
    ident, payload = _subject_fundamentals_payload(payloads)
    value = pluck_or_none(payload, "Highlights", "DividendYield")
    try:
        value = float(value) if value is not None else None
    except (TypeError, ValueError):
        value = None
    return Fact(
        name="dividend_yield",
        value=value,
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.retrieved_at_for(ident),
        source_tier="vendor",
    )


@register_fact("beta", tier="deterministic", depends_on=[])
def beta(payloads, facts) -> Fact:
    """Equity beta. Prefers `Technicals.Beta`; falls back to `Highlights.Beta`."""
    ident, payload = _subject_fundamentals_payload(payloads)
    value = pluck_or_none(payload, "Technicals", "Beta")
    if value is None:
        value = pluck_or_none(payload, "Highlights", "Beta")
    try:
        value = float(value) if value is not None else None
    except (TypeError, ValueError):
        value = None
    return Fact(
        name="beta",
        value=value,
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.retrieved_at_for(ident),
        source_tier="vendor",
    )


@register_fact("shares_outstanding", tier="deterministic", depends_on=[])
def shares_outstanding(payloads, facts) -> Fact:
    """Total shares outstanding, from `SharesStats.SharesOutstanding`."""
    ident, payload = _subject_fundamentals_payload(payloads)
    value = pluck_or_none(payload, "SharesStats", "SharesOutstanding")
    try:
        value = float(value) if value is not None else None
    except (TypeError, ValueError):
        value = None
    return Fact(
        name="shares_outstanding",
        value=value,
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.retrieved_at_for(ident),
        source_tier="vendor",
    )


@register_fact("float_shares", tier="deterministic", depends_on=[])
def float_shares(payloads, facts) -> Fact:
    """Public float, from `SharesStats.SharesFloat`."""
    ident, payload = _subject_fundamentals_payload(payloads)
    value = pluck_or_none(payload, "SharesStats", "SharesFloat")
    try:
        value = float(value) if value is not None else None
    except (TypeError, ValueError):
        value = None
    return Fact(
        name="float_shares",
        value=value,
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.retrieved_at_for(ident),
        source_tier="vendor",
    )


@register_fact("short_interest_pct", tier="deterministic", depends_on=[])
def short_interest_pct(payloads, facts) -> Fact:
    """Short interest as a percentage of float.

    Prefers `SharesStats.ShortPercent`; falls back to `SharesStats.ShortRatio`
    when present. EODHD's coverage of short-interest fields is patchy across
    tickers; returns None cleanly when neither is present."""
    ident, payload = _subject_fundamentals_payload(payloads)
    value = pluck_or_none(payload, "SharesStats", "ShortPercent")
    if value is None:
        value = pluck_or_none(payload, "SharesStats", "ShortRatio")
    try:
        value = float(value) if value is not None else None
    except (TypeError, ValueError):
        value = None
    return Fact(
        name="short_interest_pct",
        value=value,
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.retrieved_at_for(ident),
        source_tier="vendor",
    )


# --- Group 3: Forward consensus -------------------------------------------


def _annual_estimates_block(payload: Any) -> Any:
    """Return the EODHD `Earnings.Annual` sub-block (mapping date -> dict of
    epsActual/epsEstimate/revenueEstimate fields)."""
    return pluck_or_none(payload, "Earnings", "Annual")


def _next_three_annual_fiscal_dates(payload: Any) -> list[str]:
    """Return up to three future fiscal-year dates from `Earnings.Annual`,
    where "future" means dates that are strictly greater than the latest
    `Financials.Income_Statement.yearly` key (i.e. consensus periods, not
    historical actuals)."""
    annual = _annual_estimates_block(payload)
    if not isinstance(annual, dict) or not annual:
        return []
    historical_yearly = pluck_or_none(payload, "Financials", "Income_Statement", "yearly")
    cutoff: str | None = None
    if isinstance(historical_yearly, dict) and historical_yearly:
        cutoff = max(historical_yearly.keys())
    candidates = sorted(annual.keys())
    if cutoff is not None:
        candidates = [d for d in candidates if d > cutoff]
    return candidates[:3]


def _annual_estimate_value(payload: Any, date: str, field: str) -> float | None:
    annual = _annual_estimates_block(payload)
    if not isinstance(annual, dict):
        return None
    row = annual.get(date)
    if not isinstance(row, dict):
        return None
    raw = row.get(field)
    try:
        return float(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


def _consensus_fy_extractor(
    name: str,
    *,
    horizon_index: int,
    estimate_field: str,
) -> Any:
    """Build a consensus FY-N extractor that pulls
    `Earnings.Annual[future_dates[horizon_index]][estimate_field]` from the
    EODHD payload."""

    def fn(payloads, facts) -> Fact:
        ident, payload = _subject_fundamentals_payload(payloads)
        dates = _next_three_annual_fiscal_dates(payload)
        value: float | None = None
        if horizon_index < len(dates):
            value = _annual_estimate_value(payload, dates[horizon_index], estimate_field)
        return Fact(
            name=name,
            value=value,
            source_ids=[payloads.manifest_id_for(ident)],
            extractor="deterministic",
            data_as_of=payloads.retrieved_at_for(ident),
            source_tier="vendor",
        )

    fn.__name__ = name
    return fn


register_fact("consensus_revenue_fy_next", tier="deterministic", depends_on=[])(
    _consensus_fy_extractor(
        "consensus_revenue_fy_next", horizon_index=0, estimate_field="revenueEstimate"
    )
)
register_fact("consensus_revenue_fy_next_plus_one", tier="deterministic", depends_on=[])(
    _consensus_fy_extractor(
        "consensus_revenue_fy_next_plus_one", horizon_index=1, estimate_field="revenueEstimate"
    )
)
register_fact("consensus_revenue_fy_next_plus_two", tier="deterministic", depends_on=[])(
    _consensus_fy_extractor(
        "consensus_revenue_fy_next_plus_two", horizon_index=2, estimate_field="revenueEstimate"
    )
)
register_fact("consensus_eps_fy_next", tier="deterministic", depends_on=[])(
    _consensus_fy_extractor("consensus_eps_fy_next", horizon_index=0, estimate_field="epsEstimate")
)
register_fact("consensus_eps_fy_next_plus_one", tier="deterministic", depends_on=[])(
    _consensus_fy_extractor(
        "consensus_eps_fy_next_plus_one", horizon_index=1, estimate_field="epsEstimate"
    )
)
register_fact("consensus_eps_fy_next_plus_two", tier="deterministic", depends_on=[])(
    _consensus_fy_extractor(
        "consensus_eps_fy_next_plus_two", horizon_index=2, estimate_field="epsEstimate"
    )
)


@register_fact(
    "consensus_revenue_growth_fy_next",
    tier="compute",
    depends_on=["consensus_revenue_fy_next", "revenue_annual"],
)
def consensus_revenue_growth_fy_next(payloads, facts) -> Fact:
    """Derived: (next-FY consensus revenue / latest-FY actual) - 1.

    Returns value=None when either input is missing or the divisor is 0."""
    nxt = facts["consensus_revenue_fy_next"]
    hist = facts["revenue_annual"]
    value: float | None = None
    if (
        nxt.value is not None
        and isinstance(hist.value, list)
        and hist.value
        and hist.value[-1] not in (None, 0)
    ):
        try:
            value = float(nxt.value) / float(hist.value[-1]) - 1.0
        except (TypeError, ValueError, ZeroDivisionError):
            value = None
    return Fact(
        name="consensus_revenue_growth_fy_next",
        value=value,
        source_ids=union_source_ids(nxt, hist),
        extractor="compute",
        depends_on=["consensus_revenue_fy_next", "revenue_annual"],
        # Freshness is gated by the consensus side: the prior-year actual is
        # by definition non-recent (annual filing), but the growth rate is
        # "as fresh as the consensus that produced it." Using the older of
        # the two pinned this fact to the annual filing date and tripped
        # the consensus_ 14-day budget month after month.
        data_as_of=_newest_dep_as_of(nxt, hist),
        source_tier="derived",
    )


@register_fact(
    "consensus_eps_growth_fy_next",
    tier="compute",
    depends_on=["consensus_eps_fy_next", "eps_annual"],
)
def consensus_eps_growth_fy_next(payloads, facts) -> Fact:
    """Derived: (next-FY consensus EPS / latest-FY actual EPS) - 1."""
    nxt = facts["consensus_eps_fy_next"]
    hist = facts["eps_annual"]
    value: float | None = None
    if (
        nxt.value is not None
        and isinstance(hist.value, list)
        and hist.value
        and hist.value[-1] not in (None, 0)
    ):
        try:
            value = float(nxt.value) / float(hist.value[-1]) - 1.0
        except (TypeError, ValueError, ZeroDivisionError):
            value = None
    return Fact(
        name="consensus_eps_growth_fy_next",
        value=value,
        source_ids=union_source_ids(nxt, hist),
        extractor="compute",
        depends_on=["consensus_eps_fy_next", "eps_annual"],
        # See consensus_revenue_growth_fy_next: forward-looking growth tracks
        # consensus freshness, not the stable historical anchor.
        data_as_of=_newest_dep_as_of(nxt, hist),
        source_tier="derived",
    )


def _trend_block(payload: Any) -> list[dict] | None:
    """Return EODHD `Earnings.Trend` as a list of per-period dicts."""
    block = pluck_or_none(payload, "Earnings", "Trend")
    if isinstance(block, list):
        return block
    if isinstance(block, dict):
        # Some EODHD shapes nest the list under a sub-key; flatten cleanly.
        for v in block.values():
            if isinstance(v, list):
                return v
    return None


def _next_quarter_trend_row(payload: Any) -> dict | None:
    """Return the row from `Earnings.Trend` whose `period` is "+1q" (the next
    quarter forecast). Returns None if absent."""
    rows = _trend_block(payload)
    if not rows:
        return None
    for row in rows:
        if isinstance(row, dict) and row.get("period") in ("+1q", "0q"):
            if row.get("period") == "+1q":
                return row
    # Some shapes lack the "+1q" key; fall back to the first row.
    first = rows[0]
    return first if isinstance(first, dict) else None


def _trend_field(row: dict | None, field: str) -> float | None:
    if not isinstance(row, dict):
        return None
    raw = row.get(field)
    try:
        return float(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


@register_fact("next_quarter_revenue_guide_midpoint", tier="deterministic", depends_on=[])
def next_quarter_revenue_guide_midpoint(payloads, facts) -> Fact:
    """Next-quarter revenue estimate midpoint from `Earnings.Trend[+1q]`.

    EODHD's `Earnings.Trend` exposes `revenueEstimateAvg` (consensus mean) as
    a reasonable proxy for the guide midpoint when explicit management
    guidance isn't on the payload."""
    ident, payload = _subject_fundamentals_payload(payloads)
    row = _next_quarter_trend_row(payload)
    value = _trend_field(row, "revenueEstimateAvg")
    return Fact(
        name="next_quarter_revenue_guide_midpoint",
        value=value,
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.retrieved_at_for(ident),
        source_tier="vendor",
    )


@register_fact("next_quarter_revenue_guide_low", tier="deterministic", depends_on=[])
def next_quarter_revenue_guide_low(payloads, facts) -> Fact:
    """Next-quarter revenue estimate low end from `Earnings.Trend[+1q]`."""
    ident, payload = _subject_fundamentals_payload(payloads)
    row = _next_quarter_trend_row(payload)
    value = _trend_field(row, "revenueEstimateLow")
    return Fact(
        name="next_quarter_revenue_guide_low",
        value=value,
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.retrieved_at_for(ident),
        source_tier="vendor",
    )


@register_fact("next_quarter_revenue_guide_high", tier="deterministic", depends_on=[])
def next_quarter_revenue_guide_high(payloads, facts) -> Fact:
    """Next-quarter revenue estimate high end from `Earnings.Trend[+1q]`."""
    ident, payload = _subject_fundamentals_payload(payloads)
    row = _next_quarter_trend_row(payload)
    value = _trend_field(row, "revenueEstimateHigh")
    return Fact(
        name="next_quarter_revenue_guide_high",
        value=value,
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.retrieved_at_for(ident),
        source_tier="vendor",
    )


# --- Group 4: Peer absolute sizes -----------------------------------------


def _peer_highlights_dict_fact(
    *,
    name: str,
    field: str,
) -> Any:
    """Build a peer-dict extractor that pulls a single `Highlights.<field>`
    per peer ticker, returning a {ticker -> value} dict."""

    def fn(payloads, facts) -> Fact:
        values: dict[str, float] = {}
        used_ids: list[int] = []
        for ticker, ident in payloads.peer_fundamentals():
            payload = payloads.by_identifier(ident)
            v = pluck_or_none(payload, "Highlights", field)
            if v is None:
                continue
            try:
                values[ticker.upper()] = float(v)
            except (TypeError, ValueError):
                continue
            used_ids.append(payloads.manifest_id_for(ident))
        subject_ident = payloads.subject_fundamentals_identifier()
        return Fact(
            name=name,
            value=values,
            source_ids=_peer_source_ids_or_subject_fallback(payloads, used_ids),
            extractor="deterministic",
            data_as_of=payloads.retrieved_at_for(subject_ident),
            source_tier="vendor",
        )

    fn.__name__ = name
    return fn


register_fact("peer_market_cap", tier="deterministic", depends_on=[])(
    _peer_highlights_dict_fact(name="peer_market_cap", field="MarketCapitalization")
)
register_fact("peer_revenue_ttm", tier="deterministic", depends_on=[])(
    _peer_highlights_dict_fact(name="peer_revenue_ttm", field="RevenueTTM")
)
register_fact("peer_net_margin_ttm", tier="deterministic", depends_on=[])(
    _peer_highlights_dict_fact(name="peer_net_margin_ttm", field="ProfitMargin")
)
register_fact("peer_operating_margin_ttm", tier="deterministic", depends_on=[])(
    _peer_highlights_dict_fact(name="peer_operating_margin_ttm", field="OperatingMarginTTM")
)


@register_fact("peer_fcf_yield", tier="deterministic", depends_on=[])
def peer_fcf_yield(payloads, facts) -> Fact:
    """Peer FCF yield = peer free cash flow / peer market cap, per ticker.

    Computed per-peer from `Cash_Flow.yearly.freeCashFlow` (or OCF + capex)
    and `Highlights.MarketCapitalization`. Returns an empty dict when no peer
    payload carries both inputs (the most common case in fixture data).
    Documented gap: EODHD peer payloads frequently lack cash flow detail."""
    values: dict[str, float] = {}
    used_ids: list[int] = []
    for ticker, ident in payloads.peer_fundamentals():
        payload = payloads.by_identifier(ident)
        mcap = pluck_or_none(payload, "Highlights", "MarketCapitalization")
        if mcap is None:
            continue
        fcf_series = _series_or_none(payload, statement="Cash_Flow", field="freeCashFlow")
        if fcf_series is None:
            ocf = _series_or_none(
                payload, statement="Cash_Flow", field="totalCashFromOperatingActivities"
            )
            capex = _series_or_none(payload, statement="Cash_Flow", field="capitalExpenditures")
            if ocf is None or capex is None:
                continue
            n = min(len(ocf), len(capex))
            if n == 0:
                continue
            fcf_value = float(ocf[n - 1]) + float(capex[n - 1])
        else:
            if not fcf_series:
                continue
            fcf_value = float(fcf_series[-1])
        try:
            mcap_value = float(mcap)
        except (TypeError, ValueError):
            continue
        if mcap_value <= 0:
            continue
        values[ticker.upper()] = fcf_value / mcap_value
        used_ids.append(payloads.manifest_id_for(ident))
    subject_ident = payloads.subject_fundamentals_identifier()
    return Fact(
        name="peer_fcf_yield",
        value=values,
        source_ids=_peer_source_ids_or_subject_fallback(payloads, used_ids),
        extractor="deterministic",
        data_as_of=payloads.retrieved_at_for(subject_ident),
        source_tier="vendor",
    )


# --- Group 5: Forward valuation -------------------------------------------


@register_fact("ev_to_ebitda_forward", tier="deterministic", depends_on=[])
def ev_to_ebitda_forward(payloads, facts) -> Fact:
    """Forward EV/EBITDA.

    EODHD does not expose a forward EV/EBITDA field directly. Returns None
    until a helper-tier extractor (WS7) computes EV / forward EBITDA from
    the consensus-EBITDA estimate and the enterprise-value components."""
    ident, _ = _subject_fundamentals_payload(payloads)
    return Fact(
        name="ev_to_ebitda_forward",
        value=None,
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.retrieved_at_for(ident),
        source_tier="vendor",
    )


@register_fact("ev_to_sales_forward", tier="deterministic", depends_on=[])
def ev_to_sales_forward(payloads, facts) -> Fact:
    """Forward EV/Sales.

    EODHD does not expose forward EV/Sales directly. Returns None until a
    helper-tier extractor (WS7) divides enterprise value by the
    `consensus_revenue_fy_next` fact."""
    ident, _ = _subject_fundamentals_payload(payloads)
    return Fact(
        name="ev_to_sales_forward",
        value=None,
        source_ids=[payloads.manifest_id_for(ident)],
        extractor="deterministic",
        data_as_of=payloads.retrieved_at_for(ident),
        source_tier="vendor",
    )


@register_fact(
    "fcf_yield",
    tier="compute",
    depends_on=["free_cash_flow_annual", "market_cap"],
)
def fcf_yield(payloads, facts) -> Fact:
    """Derived: latest-FY free cash flow / market cap.

    Returns value=None when either input is missing or the FCF series is
    empty."""
    fcf = facts["free_cash_flow_annual"]
    mcap = facts["market_cap"]
    value: float | None = None
    if isinstance(fcf.value, list) and fcf.value and mcap.value is not None:
        try:
            mcap_value = float(mcap.value)
            if mcap_value > 0:
                value = float(fcf.value[-1]) / mcap_value
        except (TypeError, ValueError):
            value = None
    return Fact(
        name="fcf_yield",
        value=value,
        source_ids=union_source_ids(fcf, mcap),
        extractor="compute",
        depends_on=["free_cash_flow_annual", "market_cap"],
        data_as_of=_oldest_dep_as_of(fcf, mcap),
        source_tier="derived",
    )
