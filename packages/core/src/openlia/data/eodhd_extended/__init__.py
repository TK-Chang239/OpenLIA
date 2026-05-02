"""Extends EODHD's APIClient with derived series for needs that aren't
covered by the macro-indicators-data endpoint.

EODHD's macro-indicators catalog (debt_percent_gdp, gdp_growth_annual,
inflation_consumer_prices_annual, …) doesn't include core CPI or ISM
PMI. Both series do appear in the economic-events feed, but as one
event-type among hundreds. This wrapper filters the feed and reduces
each to a single latest-non-null float.

ExtendedAPIClient inherits from `eodhd.APIClient` so every existing
method (get_live_stock_prices, get_sentiment, get_macro_indicators_data
…) keeps working. The connector subsystem hands this class to its
python_lib transport instead of the bare APIClient.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, cast

from eodhd import APIClient


def _latest_actual(events: list[dict[str, Any]], event_type: str) -> float:
    """Pick the most recent event with a non-null `actual` field for `event_type`."""
    matching = [
        e
        for e in events
        if (e.get("type") or "") == event_type and e.get("actual") is not None
    ]
    if not matching:
        raise RuntimeError(
            f"EODHD economic-events: no {event_type!r} record with non-null actual",
        )
    matching.sort(key=lambda e: e.get("date") or "", reverse=True)
    return float(cast(Any, matching[0]["actual"]))


class ExtendedAPIClient(APIClient):
    """`eodhd.APIClient` plus derived macro series.

    Country codes follow EODHD's economic-events convention (alpha-2,
    e.g. 'US') — different from the macro-indicators endpoint, which
    expects alpha-3.
    """

    def _events_window(self, country: str, lookback_days: int) -> list[dict[str, Any]]:
        """Fetch a backward-looking event window. We bound `date_to` to today
        so the page-1000 budget isn't burned on upcoming releases.
        """
        now = datetime.now(timezone.utc)
        date_from = (now - timedelta(days=lookback_days)).strftime("%Y-%m-%d")
        date_to = now.strftime("%Y-%m-%d")
        return cast(
            list[dict[str, Any]],
            self.get_economic_events_data(
                country=country, limit=1000, date_from=date_from, date_to=date_to,
            ),
        )

    def core_inflation_rate(self, country: str = "US", lookback_days: int = 180) -> float:
        """Latest YoY core CPI as published by the BLS.

        EODHD lists this in the economic-events feed under
        `type='Core Inflation Rate'`; the `actual` field is the YoY %.
        """
        return _latest_actual(self._events_window(country, lookback_days), "Core Inflation Rate")

    def ism_manufacturing_pmi(self, country: str = "US", lookback_days: int = 180) -> float:
        """Latest ISM Manufacturing PMI value.

        EODHD lists this in the economic-events feed under
        `type='ISM Manufacturing PMI'`; the `actual` field is the
        diffusion index level (>50 = expansion).
        """
        return _latest_actual(self._events_window(country, lookback_days), "ISM Manufacturing PMI")


__all__ = ["ExtendedAPIClient"]
