"""Diplomatic progress panel — keyword scanner + user-marked milestone."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from openlia.panic_thermometer.panels._scanning import matching_articles
from openlia.panic_thermometer.panels.base import PanelContextBuildResult

_DEFAULT_RULESET: dict[str, Any] = {
    "rules": [
        {
            "status": "red",
            "formula": "days_elapsed >= window_days and escalation_detected",
            "label": "Window lapsed + escalation",
        },
        {
            "status": "red",
            "formula": "days_elapsed >= window_days",
            "label": "Window lapsed, no progress",
        },
        {
            "status": "amber",
            "formula": "days_elapsed >= window_days * (window_amber_pct / 100)",
            "label": "{days_remaining} days remaining",
        },
        {
            "status": "green",
            "formula": "true",
            "label": "Within window",
        },
    ],
    "params": {
        "window_days": 30,
        "window_amber_pct": 50,
        "news_keywords": [
            "ceasefire",
            "Hormuz",
            "strait",
            "Iran",
            "diplomatic",
            "negotiations",
            "peace talks",
            "de-escalation",
        ],
        "escalation_keywords": [
            "military escalation",
            "strike",
            "blockade",
            "retaliation",
            "mobilization",
        ],
        "news_lookback_days": 30,
        # Require this many matching articles before progress/escalation is
        # treated as real, so a single stray "strike" headline does not trip it.
        "min_signal_articles": 2,
    },
    "streak_condition": None,
}


@dataclass(frozen=True)
class DiplomacyPanel:
    panel_id: str = "diplomacy"
    required_requirements: tuple[str, ...] = ("company_news",)
    optional_requirements: tuple[str, ...] = ()
    default_ruleset: dict[str, Any] = field(default_factory=lambda: _DEFAULT_RULESET)

    def known_identifiers(self) -> set[str]:
        from openlia.formula import RESERVED_NAMES

        names: set[str] = set(RESERVED_NAMES) | {
            "days_elapsed",
            "days_remaining",
            "progress_detected",
            "escalation_detected",
            "matched_progress_headlines",
            "matched_escalation_headlines",
            "manual_override",
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
        window_days = int(params.get("window_days", 30))
        news_keywords = params.get("news_keywords", [])
        escalation_keywords = params.get("escalation_keywords", [])

        milestone_raw = panel_config.get("milestone_date")
        if milestone_raw:
            try:
                milestone_date = datetime.fromisoformat(milestone_raw).date()
            except Exception:
                milestone_date = date.today()
        else:
            milestone_date = date.today()

        days_elapsed = (date.today() - milestone_date).days
        days_remaining = max(0, window_days - days_elapsed)

        news = payloads.get("company_news") or []
        min_articles = int(params.get("min_signal_articles", 2))
        progress = matching_articles(news, news_keywords)
        escalation = matching_articles(news, escalation_keywords)

        return PanelContextBuildResult(
            scalars={
                "days_elapsed": days_elapsed,
                "days_remaining": days_remaining,
                "progress_detected": len(progress) >= min_articles,
                "escalation_detected": len(escalation) >= min_articles,
                "matched_progress_headlines": [a.get("headline", "") for _, a in progress[:10]],
                "matched_escalation_headlines": [a.get("headline", "") for _, a in escalation[:10]],
                "manual_override": panel_config.get("manual_override"),
            },
            raw_series={},
            warnings=[],
        )
