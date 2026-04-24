"""Oil price duration panel."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from openlia.panic_thermometer.panels.base import PanelContextBuildResult

_DEFAULT_RULESET: dict[str, Any] = {
    "rules": [
        {
            "status": "dark_red",
            "formula": "streak_days >= streak_dark_red",
            "label": "{streak_days} days elevated - 2022 scenario",
        },
        {
            "status": "red",
            "formula": "streak_days >= streak_red",
            "label": "{streak_days} days elevated - scenario upgrade risk",
        },
        {
            "status": "amber",
            "formula": "price > price_threshold",
            "label": "Above threshold, monitoring",
        },
        {
            "status": "green",
            "formula": "true",
            "label": "Below threshold",
        },
    ],
    "params": {
        "ticker": "BNO.US",
        "price_threshold": 85,
        "streak_amber": 1,
        "streak_red": 30,
        "streak_dark_red": 90,
        "history_lookback_months": 6,
    },
    "streak_condition": "price > price_threshold",
}


@dataclass(frozen=True)
class OilPanel:
    panel_id: str = "oil"
    required_requirements: tuple[str, ...] = ("historical_prices", "stock_quote")
    optional_requirements: tuple[str, ...] = ()
    default_ruleset: dict[str, Any] = field(default_factory=lambda: _DEFAULT_RULESET)

    def build_context(
        self,
        *,
        panel_config: dict[str, Any],
        payloads: dict[str, Any],
    ) -> PanelContextBuildResult:
        history = payloads.get("historical_prices") or []
        quote = payloads.get("stock_quote")
        warnings: list[str] = []

        closes = [float(bar["close"]) for bar in history]
        highs = [float(bar.get("high", bar["close"])) for bar in history]
        lows = [float(bar.get("low", bar["close"])) for bar in history]

        if not closes:
            warnings.append("oil: no historical price data available")

        if quote and quote.get("price") is not None:
            price = float(quote["price"])
            prev_close = (
                float(quote["previous_close"])
                if quote.get("previous_close") is not None
                else (closes[-2] if len(closes) >= 2 else price)
            )
        else:
            warnings.append("oil: live quote unavailable - using last historical close")
            price = closes[-1] if closes else 0.0
            prev_close = closes[-2] if len(closes) >= 2 else price

        return PanelContextBuildResult(
            scalars={"price": price, "prev_close": prev_close},
            raw_series={"price": closes, "high": highs, "low": lows},
            warnings=warnings,
        )
