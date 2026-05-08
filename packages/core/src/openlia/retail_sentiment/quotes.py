"""Historical price quotes for the Retail Sentiment Overview chart.

Closes dev-backlog Gap 1: the design's "Sentiment vs price (30 days)"
panel needs daily close + cumulative pct vs window start so the
sentiment line can be overlaid against the price line.

Direct EODHD call rather than going through the dispatcher catalog —
the price series is read-only and per-snapshot resolution is overkill
for what amounts to a chart background. The dispatcher route stays
the right shape for sentiment posts (which carry per-source state).
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class QuoteBar:
    date: str
    close: float
    daily_change_pct: float
    cumulative_pct: float


def _normalize_symbol(ticker: str) -> str:
    """EODHD requires SYMBOL.EXCHANGE. Default to .US for bare tickers."""
    return ticker if "." in ticker else f"{ticker}.US"


def _format_date(value: object) -> str | None:
    """EODHD bars come back as either {'date': 'YYYY-MM-DD'} dicts or pandas
    rows. Coerce to a YYYY-MM-DD string; return None on unrecognized shape."""
    if isinstance(value, str):
        return value[:10]
    if hasattr(value, "isoformat"):
        return value.isoformat()[:10]
    return None


def _close_of(row: object) -> float | None:
    candidate = None
    if isinstance(row, dict):
        candidate = row.get("adjusted_close") or row.get("close")
    else:
        candidate = getattr(row, "adjusted_close", None) or getattr(row, "close", None)
    if candidate is None:
        return None
    try:
        return float(candidate)
    except (TypeError, ValueError):
        return None


def _date_of(row: object) -> str | None:
    raw = row.get("date") if isinstance(row, dict) else getattr(row, "date", None)
    return _format_date(raw)


def fetch_quotes(*, ticker: str, days: int = 30) -> list[QuoteBar]:
    """Fetch the last `days` daily closes for `ticker` from EODHD.

    Returns an empty list if `EODHD_API_KEY` is unset or the upstream
    call fails. Callers treat empty as "no overlay available" — the
    Overview chart still renders sentiment on its own.
    """
    api_key = os.environ.get("EODHD_API_KEY")
    if not api_key:
        return []

    try:
        from openlia.data.eodhd_extended import ExtendedAPIClient
    except ImportError:
        return []

    client = ExtendedAPIClient(api_key=api_key)
    try:
        rows = client.get_eod_historical_stock_market_data(
            symbol=_normalize_symbol(ticker),
            period="d",
            order="a",
        )
    except Exception:
        return []

    if not rows:
        return []
    # `days` worth of trading days from the tail (history is ascending).
    tail = list(rows)[-max(days, 1) :]
    parsed: list[tuple[str, float]] = []
    for r in tail:
        d = _date_of(r)
        c = _close_of(r)
        if d is None or c is None:
            continue
        parsed.append((d, c))
    if not parsed:
        return []

    base = parsed[0][1]
    out: list[QuoteBar] = []
    prev = base
    for d, c in parsed:
        daily = ((c - prev) / prev) * 100.0 if prev else 0.0
        cumulative = ((c - base) / base) * 100.0 if base else 0.0
        out.append(
            QuoteBar(
                date=d,
                close=round(c, 4),
                daily_change_pct=round(daily, 4),
                cumulative_pct=round(cumulative, 4),
            )
        )
        prev = c
    return out


__all__ = ["QuoteBar", "fetch_quotes"]
