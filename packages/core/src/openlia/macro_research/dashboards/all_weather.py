"""T3 — All-Weather Portfolio Audit."""

from __future__ import annotations

from typing import Any

from openlia.macro_research.risk_math import (
    DEFAULT_VOLS,
    REFERENCE_ALLOCATION,
    SEASON_ASSETS,
    coverage_for_season,
    gold_gap,
    risk_contributions,
)

_FALLBACK_60_40 = {"equities": 0.60, "long_bonds": 0.40}


class AllWeatherDashboard:
    slug = "all_weather"
    display_name = "All-Weather"
    T1_REQUIREMENTS: tuple[str, ...] = ()
    T2_FORMULAS: dict[str, str] = {}
    T4_PROMPT_KEY: str | None = None

    def T3_compute(
        self,
        *,
        metrics: dict[str, float],
        portfolio: dict[str, float] | None,
    ) -> dict[str, Any]:
        source = "user" if portfolio else "fallback_60_40"
        resolved = portfolio or _FALLBACK_60_40

        rc_user = risk_contributions(weights=resolved, vols=DEFAULT_VOLS)
        rc_ref = risk_contributions(weights=REFERENCE_ALLOCATION, vols=DEFAULT_VOLS)

        season_coverage: dict[str, str] = {
            season: coverage_for_season(season=season, weights=resolved)
            for season in SEASON_ASSETS
        }

        user_gold = resolved.get("gold", 0.0)
        gap = gold_gap(user_weight=user_gold)

        max_rc = max(rc_user.values()) if rc_user else 0.0
        if max_rc > 0.6:
            severity = "red"
            label = "Concentrated"
        elif max_rc > 0.4:
            severity = "amber"
            label = "Moderately concentrated"
        else:
            severity = "green"
            label = "Balanced"

        return {
            "portfolio_source": source,
            "portfolio": resolved,
            "reference_allocation": REFERENCE_ALLOCATION,
            "risk_contributions": rc_user,
            "reference_risk_contributions": rc_ref,
            "season_coverage": season_coverage,
            "gold_gap": gap,
            "severity": severity,
            "overall_coverage_label": label,
        }

    def T5_smart_mode_adjustments(
        self,
        *,
        base_thresholds: dict[str, float],
        context: dict[str, Any],
    ) -> dict[str, float]:
        if not context.get("smart_mode"):
            return dict(base_thresholds)
        adjusted = dict(base_thresholds)
        if context.get("vol_regime") == "high" and "strong_threshold" in adjusted:
            adjusted["strong_threshold"] *= 1.1
        return adjusted
