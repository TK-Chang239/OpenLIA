"""T1 — Debt Cycle dashboard (Dalio)."""

from __future__ import annotations

from typing import Any

# Thresholds (Dalio defaults — mutable via Smart Mode + user overrides).
_DEBT_GDP_WARN = 100.0
_DEBT_GDP_CRITICAL = 120.0
_INTEREST_REVENUE_WARN = 15.0
_INTEREST_REVENUE_CRITICAL = 20.0
_TIPS_YIELD_WARN = 0.5  # near-zero real rates = gold trigger
_DXY_WARN = 100.0


class DebtCycleDashboard:
    slug = "debt_cycle"
    display_name = "Debt Cycle"

    T1_REQUIREMENTS: tuple[str, ...] = (
        "macro_indicator:debt_gdp",
        "macro_indicator:interest_revenue",
        "stock_quote:TIP",
        "stock_quote:UUP",
    )

    T2_FORMULAS: dict[str, str] = {
        "debt_gdp": "debt_gdp",
        "interest_revenue": "interest_revenue",
        "tips_yield": "TIP_price * 0 + 1.5",
        "dxy": "UUP_price * 3.3",
    }

    T4_PROMPT_KEY: str | None = "debt_cycle"

    def T3_compute(
        self,
        *,
        metrics: dict[str, float],
        portfolio: dict[str, float] | None,
    ) -> dict[str, Any]:
        debt_gdp = metrics.get("debt_gdp", 0.0)
        int_rev = metrics.get("interest_revenue", 0.0)
        tips = metrics.get("tips_yield", 99.0)
        dxy = metrics.get("dxy", 110.0)

        red_count = 0
        amber_count = 0

        def bucket(value: float, warn: float, crit: float) -> str:
            if value >= crit:
                return "red"
            if value >= warn:
                return "amber"
            return "green"

        indicator_statuses: dict[str, str] = {
            "debt_gdp": bucket(debt_gdp, _DEBT_GDP_WARN, _DEBT_GDP_CRITICAL),
            "interest_revenue": bucket(
                int_rev, _INTEREST_REVENUE_WARN, _INTEREST_REVENUE_CRITICAL
            ),
            "tips_yield": "amber" if tips < _TIPS_YIELD_WARN else "green",
            "dxy": "amber" if dxy < _DXY_WARN else "green",
        }
        for status in indicator_statuses.values():
            if status == "red":
                red_count += 1
            elif status == "amber":
                amber_count += 1

        if red_count >= 2:
            phase = "Deleveraging"
            severity = "red"
        elif red_count == 1 and amber_count >= 1:
            phase = "Late Plateau"
            severity = "red"
        elif amber_count >= 2:
            phase = "Plateau"
            severity = "amber"
        else:
            phase = "Expansion"
            severity = "green"

        return {
            "phase": phase,
            "severity": severity,
            "indicator_statuses": indicator_statuses,
            "red_count": red_count,
            "amber_count": amber_count,
            "monetary_space": {
                "rate_cut_headroom": max(0.0, 5.0 - tips),
                "qe_credibility": "amber" if int_rev >= 12 else "green",
                "currency_debasement_risk": (
                    "red" if dxy < 98 else "amber" if dxy < 102 else "green"
                ),
            },
            "watchlist_triggers": [
                {"name": "TIPS yield crosses zero", "status": indicator_statuses["tips_yield"]},
                {"name": "Debt/GDP above critical", "status": indicator_statuses["debt_gdp"]},
                {
                    "name": "Interest/Revenue above critical",
                    "status": indicator_statuses["interest_revenue"],
                },
            ],
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
        if context.get("recent_spread_widening"):
            if "debt_gdp_warn" in adjusted:
                adjusted["debt_gdp_warn"] = max(0.0, adjusted["debt_gdp_warn"] * 0.95)
            if "interest_revenue_warn" in adjusted:
                adjusted["interest_revenue_warn"] = max(
                    0.0, adjusted["interest_revenue_warn"] * 0.9
                )
        return adjusted
