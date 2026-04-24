"""Fed language tracker panel — keyword scanner over recent Fed news."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from openlia.panic_thermometer.panels.base import PanelContextBuildResult

_DEFAULT_RULESET: dict[str, Any] = {
    "rules": [
        {
            "status": "dark_red",
            "formula": "crisis_keyword_detected",
            "label": "Emergency posture - '{matched_phrase}'",
        },
        {
            "status": "red",
            "formula": "hawkish_keyword_detected",
            "label": "Hawkish pivot - '{matched_phrase}'",
        },
        {
            "status": "amber",
            "formula": "neutral_keyword_detected and not dovish_keyword_detected",
            "label": "Neutral pivot",
        },
        {
            "status": "green",
            "formula": "true",
            "label": "Dovish / wait-and-see",
        },
    ],
    "params": {
        "dovish_keywords": ["look through", "transitory", "patient", "well anchored"],
        "neutral_keywords": [
            "monitoring closely",
            "data dependent",
            "will act as appropriate",
        ],
        "hawkish_keywords": [
            "broadly-based price pressures",
            "concerned about inflation",
            "persistent inflation",
        ],
        "crisis_keywords": [
            "inflation expectations becoming unanchored",
            "emergency",
            "expedited",
        ],
        "news_lookback_days": 30,
        "news_search_tags": "Fed,FOMC,Powell,Federal Reserve",
    },
    "streak_condition": None,
}


def _scan(text: str, keywords: list[str]) -> str | None:
    haystack = text.lower()
    for kw in keywords:
        if kw.lower() in haystack:
            return kw
    return None


@dataclass(frozen=True)
class FedLanguagePanel:
    panel_id: str = "fed_language"
    required_requirements: tuple[str, ...] = ("company_news", "economic_events")
    optional_requirements: tuple[str, ...] = ()
    default_ruleset: dict[str, Any] = field(default_factory=lambda: _DEFAULT_RULESET)

    def build_context(
        self,
        *,
        panel_config: dict[str, Any],
        payloads: dict[str, Any],
    ) -> PanelContextBuildResult:
        params = panel_config.get("params", {})
        news = payloads.get("company_news") or []
        events = payloads.get("economic_events") or []
        warnings: list[str] = []

        dovish = params.get("dovish_keywords", [])
        neutral = params.get("neutral_keywords", [])
        hawkish = params.get("hawkish_keywords", [])
        crisis = params.get("crisis_keywords", [])

        sorted_news = sorted(news, key=lambda a: a.get("date", ""), reverse=True)

        matched_phrase = ""
        matched_headline = ""
        matched_date = ""
        flags = {
            "dovish_keyword_detected": False,
            "neutral_keyword_detected": False,
            "hawkish_keyword_detected": False,
            "crisis_keyword_detected": False,
        }
        category_order = [
            ("crisis_keyword_detected", crisis),
            ("hawkish_keyword_detected", hawkish),
            ("neutral_keyword_detected", neutral),
            ("dovish_keyword_detected", dovish),
        ]
        for article in sorted_news:
            text = f"{article.get('headline', '')} {article.get('summary', '')}"
            for flag_name, kw_list in category_order:
                hit = _scan(text, kw_list)
                if hit:
                    flags[flag_name] = True
                    if not matched_phrase:
                        matched_phrase = hit
                        matched_headline = article.get("headline", "")
                        matched_date = article.get("date", "")

        fomc_events = [e for e in events if "FOMC" in (e.get("event_name", "") or "")]
        days_since_fomc: float | None = None
        if fomc_events:
            latest_fomc = max(fomc_events, key=lambda e: e.get("date", ""))
            try:
                fomc_date = datetime.fromisoformat(latest_fomc["date"]).date()
                days_since_fomc = float((date.today() - fomc_date).days)
            except Exception:
                warnings.append("fed_language: could not parse FOMC event date")
        else:
            warnings.append("fed_language: no FOMC event in lookback window")

        scalars: dict[str, Any] = {
            **flags,
            "matched_phrase": matched_phrase,
            "matched_headline": matched_headline,
            "matched_date": matched_date,
            "days_since_fomc": days_since_fomc,
            "manual_override": panel_config.get("manual_override"),
        }
        return PanelContextBuildResult(scalars=scalars, raw_series={}, warnings=warnings)
