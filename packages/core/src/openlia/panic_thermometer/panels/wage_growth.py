"""Wage growth panel — Average Hourly Earnings MoM."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from openlia.panic_thermometer.panels.base import PanelContextBuildResult

_DEFAULT_RULESET: dict[str, Any] = {
    "rules": [
        {
            "status": "dark_red",
            "formula": "consecutive_count >= consecutive_required",
            "label": "Wage-price spiral risk - {consecutive_count} consecutive months",
        },
        {
            "status": "red",
            "formula": "value > wage_threshold_red",
            "label": "Single hot print ({value}%)",
        },
        {
            "status": "amber",
            "formula": "value > wage_threshold_amber",
            "label": "Elevated but not critical ({value}%)",
        },
        {
            "status": "green",
            "formula": "true",
            "label": "Normal ({value}%)",
        },
    ],
    "params": {
        "event_type_filter": "Average Hourly Earnings",
        "wage_threshold_amber": 0.4,
        "wage_threshold_red": 0.5,
        "consecutive_required": 2,
        "history_lookback_months": 12,
    },
    "streak_condition": None,
}


@dataclass(frozen=True)
class WageGrowthPanel:
    panel_id: str = "wage_growth"
    required_requirements: tuple[str, ...] = ("economic_events",)
    optional_requirements: tuple[str, ...] = ()
    default_ruleset: dict[str, Any] = field(default_factory=lambda: _DEFAULT_RULESET)

    def known_identifiers(self) -> set[str]:
        from openlia.formula import RESERVED_NAMES

        names: set[str] = set(RESERVED_NAMES) | {
            "value",
            "prev_value",
            "consecutive_count",
            "avg_12m",
            "cpi_mom",
        }
        names |= set(self.default_ruleset.get("params", {}).keys())
        names.add("streak_days")
        return names

    def build_context(
        self,
        *,
        panel_config: dict[str, Any],
        payloads: dict[str, Any],
    ) -> PanelContextBuildResult:
        params = panel_config.get("params", {})
        event_filter = params.get("event_type_filter", "Average Hourly Earnings")
        red_threshold = float(params.get("wage_threshold_red", 0.5))

        events = payloads.get("economic_events") or []
        warnings: list[str] = []

        wage_events = sorted(
            [
                e
                for e in events
                if e.get("event_name") == event_filter and e.get("actual") is not None
            ],
            key=lambda e: e.get("date", ""),
        )
        values = [float(e["actual"]) for e in wage_events]
        value = values[-1] if values else None
        prev_value = values[-2] if len(values) >= 2 else None

        consecutive_count = 0
        for v in reversed(values):
            if v > red_threshold:
                consecutive_count += 1
            else:
                break

        avg_12m = sum(values[-12:]) / len(values[-12:]) if values else None

        cpi_events = [
            e
            for e in events
            if "CPI" in (e.get("event_name", "") or "") and e.get("actual") is not None
        ]
        cpi_mom = (
            float(sorted(cpi_events, key=lambda e: e.get("date", ""))[-1]["actual"])
            if cpi_events
            else None
        )

        if not values:
            warnings.append("wage_growth: no AHE events in lookback window")

        return PanelContextBuildResult(
            scalars={
                "value": value,
                "prev_value": prev_value,
                "consecutive_count": consecutive_count,
                "avg_12m": avg_12m,
                "cpi_mom": cpi_mom,
            },
            raw_series={"value": values},
            warnings=warnings,
        )
