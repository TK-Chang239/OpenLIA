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


_PANEL_SCALAR_KEYS: frozenset[str] = frozenset()


@dataclass(frozen=True)
class OilPanel:
    panel_id: str = "oil"
    required_requirements: tuple[str, ...] = ("historical_prices", "stock_quote")
    optional_requirements: tuple[str, ...] = ()
    default_ruleset: dict[str, Any] = field(default_factory=lambda: _DEFAULT_RULESET)

    def known_identifiers(self) -> set[str]:
        from openlia.formula import RESERVED_NAMES

        names: set[str] = set(RESERVED_NAMES) | set(_PANEL_SCALAR_KEYS)
        names |= {"price", "high", "low"}  # raw_series keys
        names |= set(self.default_ruleset.get("params", {}).keys())
        names.add("streak_days")
        return names

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
            live_price = float(quote["price"])
            # Append the live quote to the series so reserved derived `price`
            # reflects the live tick rather than yesterday's close.
            closes = [*closes, live_price]
            if highs:
                highs = [*highs, max(highs[-1], live_price)]
            if lows:
                lows = [*lows, min(lows[-1], live_price)]
        else:
            warnings.append("oil: live quote unavailable - using last historical close")

        return PanelContextBuildResult(
            scalars={},
            raw_series={"price": closes, "high": highs, "low": lows},
            warnings=warnings,
        )
