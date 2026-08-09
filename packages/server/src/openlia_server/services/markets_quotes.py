"""Live market-index quotes for the Home TickerStrip.

A small, self-contained reader over EODHD's real-time endpoint for a fixed
basket of market indices (equity indices, VIX, a 10Y yield proxy, the dollar
index and BTC). It is intentionally decoupled from the portfolio quote path,
which is scoped to a user's holdings.

Symbols were chosen from a live EODHD probe: the equity indices and VIX return
real-time ``close`` values; ``US10Y.GBOND`` and ``DXY.INDX`` currently only
carry ``previousClose`` on this plan, so we fall back to that (no intraday
delta) rather than dropping the cell.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

# (EODHD symbol, display label). Order drives the strip left-to-right.
INDEX_BASKET: list[tuple[str, str]] = [
    ("GSPC.INDX", "S&P 500"),
    ("IXIC.INDX", "NASDAQ"),
    ("VIX.INDX", "VIX"),
    ("US10Y.GBOND", "10Y"),
    ("DXY.INDX", "DXY"),
    ("BTC-USD.CC", "BTC"),
]

_EODHD_REALTIME_URL = "https://eodhd.com/api/real-time"
_TIMEOUT_SECONDS = 15.0


def _to_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        # EODHD returns the literal string "NA" when a field is unavailable.
        return None


def _default_fetcher(api_key: str, symbols: list[str]) -> list[dict[str, Any]]:
    """Fetch all symbols in one real-time call (path symbol + ``s`` list)."""
    import requests

    first, rest = symbols[0], symbols[1:]
    resp = requests.get(
        f"{_EODHD_REALTIME_URL}/{first}",
        params={"api_token": api_key, "fmt": "json", "s": ",".join(rest)},
        timeout=_TIMEOUT_SECONDS,
    )
    resp.raise_for_status()
    data = resp.json()
    return list(data) if isinstance(data, list) else [data]


def build_index_quotes(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Normalize EODHD rows into the strip's cell shape, in basket order."""
    by_code = {r.get("code"): r for r in rows if isinstance(r, dict)}
    out: list[dict[str, Any]] = []
    for symbol, label in INDEX_BASKET:
        row = by_code.get(symbol)
        if row is None:
            continue
        close = _to_float(row.get("close"))
        prev = _to_float(row.get("previousClose"))
        value = close if close is not None else prev
        if value is None:
            continue
        change_abs = close - prev if (close is not None and prev is not None) else None
        change_pct = (change_abs / prev * 100.0) if (change_abs is not None and prev) else None
        out.append(
            {
                "symbol": symbol,
                "label": label,
                "value": value,
                "previous_close": prev,
                "change_abs": change_abs,
                "change_pct": change_pct,
            }
        )
    return out


def fetch_indices(
    api_key: str,
    *,
    fetcher: Callable[[str, list[str]], list[dict[str, Any]]] = _default_fetcher,
) -> list[dict[str, Any]]:
    """Fetch and normalize the whole basket. Raises on transport failure."""
    symbols = [s for s, _ in INDEX_BASKET]
    return build_index_quotes(fetcher(api_key, symbols))


__all__ = ["INDEX_BASKET", "build_index_quotes", "fetch_indices"]
