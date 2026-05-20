"""Registered facts for the stock_initiation report type.

Importing this module triggers registration with the default_registry.
"""

from __future__ import annotations

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
