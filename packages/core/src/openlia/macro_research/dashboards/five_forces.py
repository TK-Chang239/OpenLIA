"""T5 — Five Interlocking Forces (Dalio)."""

from __future__ import annotations

from typing import Any, ClassVar


class FiveForcesDashboard:
    slug = "five_forces"
    display_name = "Five Forces"

    T1_REQUIREMENTS: ClassVar[tuple[str, ...]] = ()

    T2_FORMULAS: ClassVar[dict[str, str]] = {
        "force_debt_money": "force_debt_money",
        "force_political": "force_political",
        "force_geopolitical": "force_geopolitical",
        "force_technology": "force_technology",
        "force_natural": "force_natural",
    }

    T4_PROMPT_KEY: str | None = "five_forces"

    def T3_compute(
        self,
        *,
        metrics: dict[str, float],
        portfolio: dict[str, float] | None,
    ) -> dict[str, Any]:
        forces = {
            "debt_money": metrics.get("force_debt_money", 0),
            "political": metrics.get("force_political", 0),
            "geopolitical": metrics.get("force_geopolitical", 0),
            "technology": metrics.get("force_technology", 0),
            "natural": metrics.get("force_natural", 0),
        }
        active = sum(1 for score in forces.values() if score >= 7)

        if active <= 1:
            bucket = "Normal"
            severity = "green"
        elif active <= 3:
            bucket = "Elevated"
            severity = "amber"
        else:
            bucket = "Historical turning point zone"
            severity = "red"

        return {
            "force_scores": forces,
            "active_force_count": active,
            "bucket": bucket,
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
        drift = float(context.get("baseline_drift", 0.0))
        if "anchor_high" in adjusted:
            adjusted["anchor_high"] = max(1.0, adjusted["anchor_high"] - drift)
        if "anchor_critical" in adjusted:
            adjusted["anchor_critical"] = max(
                adjusted.get("anchor_high", 0.0) + 0.5,
                adjusted["anchor_critical"] - drift * 0.5,
            )
        return adjusted
