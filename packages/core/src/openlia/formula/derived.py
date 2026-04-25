"""Reserved-scalar computation from raw OHLC series."""

from __future__ import annotations

import math

# Names the engine reserves for derived computation. Callers cannot pass
# these in `scalars` or `params` -- it is an error to shadow them.
RESERVED_NAMES: frozenset[str] = frozenset(
    {
        "price",
        "prev_close",
        "change_pct",
        "ma20",
        "ma50",
        "ma100",
        "ma200",
        "atr_14",
        "std_20",
        "high_52w",
        "low_52w",
        "pct_from_high",
        "pct_from_low",
        "price_vs_ma200",
        "ma50_vs_ma200",
    }
)


_MA_WINDOWS: tuple[tuple[str, int], ...] = (
    ("ma20", 20),
    ("ma50", 50),
    ("ma100", 100),
    ("ma200", 200),
)


def compute_derived_scalars(
    raw_series: dict[str, list[float]],
) -> dict[str, float | None]:
    """Compute every reserved scalar; values are None if history is short."""

    out: dict[str, float | None] = {name: None for name in RESERVED_NAMES}

    closes = raw_series.get("price") or []
    highs = raw_series.get("high") or []
    lows = raw_series.get("low") or []

    if not closes:
        return out

    out["price"] = float(closes[-1])
    out["prev_close"] = float(closes[-2]) if len(closes) >= 2 else None
    if out["prev_close"] is not None and out["prev_close"] != 0:
        out["change_pct"] = (out["price"] - out["prev_close"]) / out["prev_close"] * 100.0

    for name, window in _MA_WINDOWS:
        if len(closes) >= window:
            out[name] = sum(closes[-window:]) / float(window)

    if len(closes) >= 14 and len(highs) >= 14 and len(lows) >= 14:
        n = min(len(highs), len(lows), len(closes))
        trs: list[float] = []
        for i in range(n - 14, n):
            if i == 0:
                tr = highs[i] - lows[i]
            else:
                tr = max(
                    highs[i] - lows[i],
                    abs(highs[i] - closes[i - 1]),
                    abs(lows[i] - closes[i - 1]),
                )
            trs.append(float(tr))
        if trs:
            out["atr_14"] = sum(trs) / float(len(trs))

    if len(closes) >= 21:
        returns = [
            math.log(closes[i] / closes[i - 1])
            for i in range(len(closes) - 20, len(closes))
            if closes[i - 1] > 0
        ]
        if len(returns) >= 2:
            mean_r = sum(returns) / len(returns)
            var = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
            out["std_20"] = math.sqrt(var)

    if len(closes) >= 252:
        window = closes[-252:]
        out["high_52w"] = float(max(window))
        out["low_52w"] = float(min(window))
    elif closes:
        out["high_52w"] = float(max(closes))
        out["low_52w"] = float(min(closes))

    if out["high_52w"] not in (None, 0):
        out["pct_from_high"] = (out["price"] - out["high_52w"]) / out["high_52w"] * 100.0
    if out["low_52w"] not in (None, 0):
        out["pct_from_low"] = (out["price"] - out["low_52w"]) / out["low_52w"] * 100.0
    if out["ma200"] not in (None, 0):
        out["price_vs_ma200"] = out["price"] / out["ma200"]
    if out["ma50"] is not None and out["ma200"] not in (None, 0):
        out["ma50_vs_ma200"] = out["ma50"] / out["ma200"]

    return out


def compute_derived_series(
    raw_series: dict[str, list[float]],
) -> dict[str, list[float | None]]:
    """Compute the full bar-by-bar history of each derived scalar.

    Used by streak backtests and by `cross_above`/`cross_below` over derived
    series. Insufficient-history bars are filled with None.
    """

    closes = raw_series.get("price") or []
    highs = raw_series.get("high") or []
    lows = raw_series.get("low") or []

    n = len(closes)
    out: dict[str, list[float | None]] = {name: [None] * n for name in RESERVED_NAMES}

    if n == 0:
        return out

    for i in range(n):
        out["price"][i] = float(closes[i])
        if i >= 1:
            prev = closes[i - 1]
            out["prev_close"][i] = float(prev)
            if prev != 0:
                out["change_pct"][i] = (closes[i] - prev) / prev * 100.0

    for name, window in _MA_WINDOWS:
        if n < window:
            continue
        running = 0.0
        for i in range(n):
            running += closes[i]
            if i >= window:
                running -= closes[i - window]
            if i >= window - 1:
                out[name][i] = running / float(window)

    if n >= 14 and len(highs) >= 14 and len(lows) >= 14:
        trs: list[float] = []
        m = min(n, len(highs), len(lows))
        for i in range(m):
            if i == 0:
                tr = highs[i] - lows[i]
            else:
                tr = max(
                    highs[i] - lows[i],
                    abs(highs[i] - closes[i - 1]),
                    abs(lows[i] - closes[i - 1]),
                )
            trs.append(float(tr))
            if i >= 13:
                out["atr_14"][i] = sum(trs[i - 13 : i + 1]) / 14.0

    if n >= 21:
        for i in range(20, n):
            returns = [
                math.log(closes[k] / closes[k - 1])
                for k in range(i - 19, i + 1)
                if closes[k - 1] > 0
            ]
            if len(returns) >= 2:
                mean_r = sum(returns) / len(returns)
                var = sum((r - mean_r) ** 2 for r in returns) / (len(returns) - 1)
                out["std_20"][i] = math.sqrt(var)

    for i in range(n):
        start = max(0, i - 251)
        window = closes[start : i + 1]
        if not window:
            continue
        out["high_52w"][i] = float(max(window))
        out["low_52w"][i] = float(min(window))

    for i in range(n):
        h = out["high_52w"][i]
        lo = out["low_52w"][i]
        ma50 = out["ma50"][i]
        ma200 = out["ma200"][i]
        if h not in (None, 0):
            out["pct_from_high"][i] = (closes[i] - h) / h * 100.0
        if lo not in (None, 0):
            out["pct_from_low"][i] = (closes[i] - lo) / lo * 100.0
        if ma200 not in (None, 0):
            out["price_vs_ma200"][i] = closes[i] / ma200
        if ma50 is not None and ma200 not in (None, 0):
            out["ma50_vs_ma200"][i] = ma50 / ma200

    return out
