"""T2 — Four Economic Seasons dashboard (Dalio)."""

from __future__ import annotations

from typing import Any, ClassVar


class FourSeasonsDashboard:
    slug = "four_seasons"
    display_name = "Four Seasons"

    T1_REQUIREMENTS: ClassVar[tuple[str, ...]] = (
        "macro_indicator:pmi",
        "macro_indicator:gdp_yoy",
        "macro_indicator:cpi_yoy",
        "macro_indicator:cpi_core_yoy",
        "stock_quote:HYG",
        "stock_quote:LQD",
    )

    T2_FORMULAS: ClassVar[dict[str, str]] = {
        "pmi": "pmi",
        "gdp_yoy": "gdp_yoy",
        "cpi_yoy": "cpi_yoy",
        "credit_spread": "(LQD_price - HYG_price) / 100",
    }

    # T2 formula-only dashboard per spec (MacroResearchPageSpec.md):
    # Four Seasons surfaces T1+T2+T3 derived signals only — no LLM narrative.
    T4_PROMPT_KEY: str | None = None

    def T3_compute(
        self,
        *,
        metrics: dict[str, float],
        portfolio: dict[str, float] | None,
    ) -> dict[str, Any]:
        pmi = metrics.get("pmi", 50.0)
        gdp = metrics.get("gdp_yoy", 0.0)
        cpi = metrics.get("cpi_yoy", 2.0)
        spread = metrics.get("credit_spread", 0.04)

        growth_rising = gdp > 1.0 and pmi >= 50
        growth_falling = gdp < 1.0 and pmi < 50
        inflation_rising = cpi > 3.0
        inflation_falling = cpi <= 2.0

        if growth_rising and inflation_falling:
            season = "Spring"
            severity = "green"
        elif growth_rising and inflation_rising:
            season = "Summer"
            severity = "amber"
        elif growth_falling and inflation_rising:
            season = "Autumn"
            severity = "red"
        elif growth_falling and inflation_falling:
            season = "Winter"
            severity = "amber"
        else:
            season = "Transitioning"
            severity = "amber"

        confidence = "clear"
        if not (growth_rising or growth_falling) or not (inflation_rising or inflation_falling):
            confidence = "mixed"
        if season == "Transitioning":
            confidence = "transitioning"

        return {
            "season": season,
            "severity": severity,
            "confidence": confidence,
            "growth_axis": (
                "rising" if growth_rising else ("falling" if growth_falling else "flat")
            ),
            "inflation_axis": (
                "rising" if inflation_rising else ("falling" if inflation_falling else "steady")
            ),
            "credit_spread": spread,
            "asset_playbook": self._playbook(season),
        }

    @staticmethod
    def _playbook(season: str) -> dict[str, list[str]]:
        mapping = {
            "Spring": {"best": ["equities"], "worst": ["commodities"]},
            "Summer": {"best": ["commodities", "TIPS"], "worst": ["long nominal bonds"]},
            "Autumn": {"best": ["gold", "real assets"], "worst": ["equities", "long bonds"]},
            "Winter": {"best": ["long bonds", "cash"], "worst": ["commodities"]},
        }
        return mapping.get(season, {"best": [], "worst": []})

    def T5_smart_mode_adjustments(
        self,
        *,
        base_thresholds: dict[str, float],
        context: dict[str, Any],
    ) -> dict[str, float]:
        if not context.get("smart_mode"):
            return dict(base_thresholds)
        adjusted = dict(base_thresholds)
        if context.get("vol_regime") == "high" and "credit_spread_warn" in adjusted:
            adjusted["credit_spread_warn"] *= 1.25
        return adjusted
