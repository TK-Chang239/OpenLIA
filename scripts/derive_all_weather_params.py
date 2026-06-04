"""Derive All-Weather second moments (vols + correlations) from real EODHD data.

Offline dev tool -- NOT imported by any runtime module. Fetches daily adjusted
closes for the five proxy ETFs over their maximal common window, computes
annualized volatilities (from daily log returns), the cross-asset correlation
matrix, and the realized annualized return (CAGR) as a sanity reference, then
prints paste-ready constants for macro_research/risk_math.py.

Run:
    set -a && . ./.env && set +a
    uv run python scripts/derive_all_weather_params.py
"""

from __future__ import annotations

import os

import numpy as np
from eodhd import APIClient

PROXIES: dict[str, str] = {
    "equities": "SPY.US",
    "long_bonds": "TLT.US",
    "intermediate_bonds": "IEF.US",
    "gold": "GLD.US",
    "commodities": "DBC.US",
}
ASSET_ORDER = ("equities", "long_bonds", "intermediate_bonds", "gold", "commodities")
FROM_DATE = "2004-01-01"
TO_DATE = "2025-12-31"  # most recent complete year-end
TRADING_DAYS = 252


def _fetch(client: APIClient, symbol: str) -> dict[str, float]:
    rows = client.get_eod_historical_stock_market_data(
        symbol=symbol, period="d", from_date=FROM_DATE, to_date=TO_DATE, order="a"
    )
    return {
        r["date"]: float(r["adjusted_close"]) for r in rows if r.get("adjusted_close") is not None
    }


def main() -> None:
    key = os.environ.get("EODHD_API_KEY") or os.environ.get("EODHD_API_TOKEN")
    if not key:
        raise SystemExit("EODHD_API_KEY (or EODHD_API_TOKEN) must be set")
    client = APIClient(api_key=key)

    series = {asset: _fetch(client, sym) for asset, sym in PROXIES.items()}

    # Maximal common date intersection, ascending.
    common = set.intersection(*(set(s) for s in series.values()))
    dates = sorted(common)
    if len(dates) < TRADING_DAYS:
        raise SystemExit(f"insufficient common history: {len(dates)} days")

    prices = np.array([[series[a][d] for a in ASSET_ORDER] for d in dates], dtype=float)
    log_ret = np.diff(np.log(prices), axis=0)

    vols = log_ret.std(axis=0, ddof=1) * np.sqrt(TRADING_DAYS)
    corr = np.corrcoef(log_ret, rowvar=False)

    years = (np.datetime64(dates[-1]) - np.datetime64(dates[0])) / np.timedelta64(365, "D")
    cagr = (prices[-1] / prices[0]) ** (1.0 / years) - 1.0

    print(f"# Window: {dates[0]} .. {dates[-1]}  ({len(dates)} common trading days)")
    print("# Proxies: " + ", ".join(f"{a}={PROXIES[a]}" for a in ASSET_ORDER))
    print()
    print("DEFAULT_VOLS = {")
    for i, a in enumerate(ASSET_ORDER):
        print(f'    "{a}": {vols[i]:.3f},')
    print("}")
    print()
    print("CORRELATIONS = {")
    for i in range(len(ASSET_ORDER)):
        for j in range(i + 1, len(ASSET_ORDER)):
            print(f'    ("{ASSET_ORDER[i]}", "{ASSET_ORDER[j]}"): {corr[i, j]:.2f},')
    print("}")
    print()
    print("# Realized annualized return (CAGR) over window -- SANITY REFERENCE ONLY,")
    print("# not adopted as EXPECTED_RETURNS (forward CMAs):")
    for i, a in enumerate(ASSET_ORDER):
        print(f"#   {a}: {cagr[i]:.3f}")


if __name__ == "__main__":
    main()
