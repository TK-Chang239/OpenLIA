"""Hardcoded market-hours rules for the portfolio price scheduler.

Two market sessions are modelled — NYSE/NASDAQ and TWSE — because those
are the only markets the Portfolio page currently advertises in its spec
(``Real-Time Price Data`` mentions EODHD coverage of US and TWSE). Tickers
that don't match either market default to "always open" so the scheduler
still polls them at the user-selected cadence.

No holiday calendar in v1. The scheduler will burn a handful of wasted
fetches per ticker per year on US/TWSE holidays — accepted trade-off vs.
maintaining (or shipping) a calendar dependency.
"""

from __future__ import annotations

from datetime import datetime, time
from typing import Literal

try:
    from zoneinfo import ZoneInfo
except ImportError:  # pragma: no cover - Python 3.13+ always has zoneinfo
    raise

Market = Literal["us", "twse", "other"]


_NYSE_OPEN = time(9, 30)
_NYSE_CLOSE = time(16, 0)
_NYSE_TZ = ZoneInfo("America/New_York")

_TWSE_OPEN = time(9, 0)
_TWSE_CLOSE = time(13, 30)
_TWSE_TZ = ZoneInfo("Asia/Taipei")


def classify_market(ticker: str) -> Market:
    """Map a ticker symbol to its market.

    EODHD-style suffixes:
      - ``2330.TW`` / ``2330.TWO`` → TWSE
      - ``RDSB.LSE`` / etc. → ``"other"``
      - Bare ``AAPL`` / ``MSFT`` → US (no suffix == US)
    """
    sym = ticker.strip().upper()
    if "." not in sym:
        return "us"
    suffix = sym.rsplit(".", 1)[-1]
    if suffix in ("US", "NYSE", "NASDAQ"):
        return "us"
    if suffix in ("TW", "TWO"):
        return "twse"
    return "other"


def is_market_open(ticker: str, now_utc: datetime) -> bool:
    """Return True if the ticker's home market is currently open.

    ``now_utc`` must be timezone-aware. Open is inclusive (09:30:00 returns
    True); close is exclusive (16:00:00 returns False).
    """
    if now_utc.tzinfo is None:
        raise ValueError("now_utc must be timezone-aware")

    market = classify_market(ticker)
    if market == "other":
        return True

    tz = _NYSE_TZ if market == "us" else _TWSE_TZ
    open_t = _NYSE_OPEN if market == "us" else _TWSE_OPEN
    close_t = _NYSE_CLOSE if market == "us" else _TWSE_CLOSE

    local = now_utc.astimezone(tz)
    # 0=Mon .. 6=Sun; markets closed on Sat (5) and Sun (6).
    if local.weekday() >= 5:
        return False
    local_time = local.time()
    return open_t <= local_time < close_t
