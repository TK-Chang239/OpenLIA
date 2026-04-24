"""T4 — Long-Term World Order (Dalio)."""

from __future__ import annotations

import statistics
from typing import Any

_STAGE_LABELS = {
    1: "early",
    2: "mid",
    3: "late",
}


class WorldOrderDashboard:
    slug = "world_order"
    display_name = "World Order"

    T1_REQUIREMENTS: tuple[str, ...] = (
        "macro_indicator:usd_fx_reserve_share",
        "macro_indicator:cb_gold_purchases",
        "macro_indicator:foreign_treasury_holdings",
        "stock_quote:UUP",
        "company_news:geopolitical",
    )

    T2_FORMULAS: dict[str, str] = {
        "usd_reserve_share": "usd_fx_reserve_share",
        "cb_gold_yoy": "cb_gold_purchases",
        "foreign_treasuries_change": "foreign_treasury_holdings",
        "dxy": "UUP_price * 3.3",
    }

    T4_PROMPT_KEY: str | None = "world_order"

    def T3_compute(
        self,
        *,
        metrics: dict[str, float],
        portfolio: dict[str, float] | None,
    ) -> dict[str, Any]:
        components = [
            int(metrics.get("institutional_shift", 1)),
            int(metrics.get("market_shift", 1)),
            int(metrics.get("geopolitical_shift", 1)),
            int(metrics.get("retail_shift", 1)),
        ]
        median = int(statistics.median(components))
        stage_label = _STAGE_LABELS.get(median, "early")

        severity = "green"
        if stage_label == "mid":
            severity = "amber"
        elif stage_label == "late":
            severity = "red"

        return {
            "wealth_shift_stage": stage_label,
            "wealth_shift_components": {
                "institutional": components[0],
                "market": components[1],
                "geopolitical": components[2],
                "retail": components[3],
            },
            "severity": severity,
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
        if context.get("dollar_weakness") and "stage_5_threshold" in adjusted:
            adjusted["stage_5_threshold"] *= 0.9
        return adjusted
