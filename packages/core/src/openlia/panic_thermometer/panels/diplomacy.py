"""Diplomatic progress panel — keyword scanner + user-marked milestone."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from openlia.panic_thermometer.panels._scanning import matching_articles, matching_headlines
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
        # Topic relevance only — an article must match one of these to enter
        # the corpus at all. Sentiment is classified separately below.
        "news_keywords": [
            "Hormuz",
            "strait",
            "Iran",
            "ceasefire",
            "diplomatic",
            "negotiations",
            "peace talks",
            "de-escalation",
        ],
        # Progress sentiment — a corpus article is a progress signal only
        # when one of these matches (and no escalation keyword does).
        "progress_keywords": [
            "ceasefire",
            "peace talks",
            "de-escalation",
            "negotiations",
            "truce",
            "agreement",
            "breakthrough",
        ],
        "escalation_keywords": [
            "military escalation",
            "strike",
            "strikes",
            "attack",
            "attacks",
            "blockade",
            "retaliation",
            "mobilization",
            "war",
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
            "progress_count",
            "escalation_count",
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
        progress_keywords = params.get(
            "progress_keywords",
            _DEFAULT_RULESET["params"]["progress_keywords"],
        )

        # news_keywords define topic relevance only; sentiment is classified
        # inside the relevant corpus. Progress needs a HEADLINE-level match
        # (a passing "negotiations" in an escalation story's body must not
        # tag it as progress), while escalation may match anywhere — the
        # conservative direction. Escalation wins when both match.
        corpus = [a for _, a in matching_articles(news, news_keywords)]
        escalation = matching_articles(corpus, escalation_keywords)
        escalated_ids = {id(a) for _, a in escalation}
        progress = [
            (hit, a)
            for hit, a in matching_headlines(corpus, progress_keywords)
            if id(a) not in escalated_ids
        ]

        return PanelContextBuildResult(
            scalars={
                "days_elapsed": days_elapsed,
                "days_remaining": days_remaining,
                "progress_detected": len(progress) >= min_articles,
                "escalation_detected": len(escalation) >= min_articles,
                "progress_count": len(progress),
                "escalation_count": len(escalation),
                "matched_progress_headlines": [a.get("headline", "") for _, a in progress[:10]],
                "matched_escalation_headlines": [a.get("headline", "") for _, a in escalation[:10]],
                "manual_override": panel_config.get("manual_override"),
            },
            raw_series={},
            warnings=[],
        )
