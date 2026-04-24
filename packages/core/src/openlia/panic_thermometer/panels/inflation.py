"""Inflation expectations panel — TIP ETF + Michigan 5Y survey."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from openlia.panic_thermometer.panels.base import PanelContextBuildResult

_DEFAULT_RULESET: dict[str, Any] = {
    "rules": [
        {
            "status": "dark_red",
            "formula": "michigan_5y >= level_dark_red",
            "label": "Expectations unanchored ({michigan_5y}%)",
        },
        {
            "status": "red",
            "formula": "michigan_5y >= level_red",
            "label": "Expectations drifting ({michigan_5y}%)",
        },
        {
            "status": "red",
            "formula": (
                "michigan_5y_missing and "
                "pct_change(tip_price, slope_lookback_days) > slope_threshold"
            ),
            "label": "TIP rising fast (no survey data)",
        },
        {
            "status": "amber",
            "formula": "michigan_5y >= level_amber",
            "label": "Approaching concern zone",
        },
        {
            "status": "green",
            "formula": "true",
            "label": "Expectations anchored",
        },
    ],
    "params": {
        "primary_ticker": "TIP.US",
        "event_type_filter": "Michigan 5 Year Inflation Expectations",
        "level_amber": 2.5,
        "level_red": 3.0,
        "level_dark_red": 3.5,
        "tip_lookback_months": 6,
        "slope_lookback_days": 30,
        "slope_threshold": 0.02,
    },
    "streak_condition": None,
}


@dataclass(frozen=True)
class InflationPanel:
    panel_id: str = "inflation"
    required_requirements: tuple[str, ...] = (
        "historical_prices",
        "stock_quote",
        "economic_events",
    )
    optional_requirements: tuple[str, ...] = ()
    default_ruleset: dict[str, Any] = field(default_factory=lambda: _DEFAULT_RULESET)

    def build_context(
        self,
        *,
        panel_config: dict[str, Any],
        payloads: dict[str, Any],
    ) -> PanelContextBuildResult:
        params = panel_config.get("params", {})
        event_filter = params.get("event_type_filter", "Michigan 5 Year Inflation Expectations")

        history = payloads.get("historical_prices") or []
        quote = payloads.get("stock_quote")
        events = payloads.get("economic_events") or []

        closes = [float(bar["close"]) for bar in history]
        warnings: list[str] = []

        matching = sorted(
            [e for e in events if e.get("event_name") == event_filter],
            key=lambda e: e.get("date", ""),
        )
        latest = matching[-1]["actual"] if matching else None
        prev = matching[-2]["actual"] if len(matching) >= 2 else None

        if latest is None:
            warnings.append(f"inflation: no recent release matching '{event_filter}'")

        if quote and quote.get("price") is not None:
            price = float(quote["price"])
            prev_close = (
                float(quote["previous_close"]) if quote.get("previous_close") is not None else price
            )
        elif closes:
            price = closes[-1]
            prev_close = closes[-2] if len(closes) >= 2 else price
        else:
            price = 0.0
            prev_close = 0.0
            warnings.append("inflation: no TIP price data available")

        return PanelContextBuildResult(
            scalars={
                "michigan_5y": float(latest) if latest is not None else None,
                "michigan_prev": float(prev) if prev is not None else None,
                "michigan_5y_missing": latest is None,
                "tip_price_latest": price,
                "tip_prev_close": prev_close,
            },
            raw_series={"tip_price": closes, "price": closes},
            warnings=warnings,
        )
