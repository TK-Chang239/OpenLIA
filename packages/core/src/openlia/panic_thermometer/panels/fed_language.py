"""Fed language tracker panel — keyword scanner over recent Fed news."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from openlia.panic_thermometer.panels._scanning import headline_anchored, matching_articles
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
        # A category counts as a real signal only once this many distinct
        # articles match it, so a single stray keyword mention in a loosely
        # related feed does not flip the panel (e.g. a false "emergency").
        "min_signal_articles": 2,
    },
    "streak_condition": None,
}


def _is_fomc_event(event_name: str | None) -> bool:
    """Match the FOMC family across data-provider naming.

    EODHD's economic calendar splits the meeting into "FOMC Minutes" and
    "FOMC Economic Projections" and names the rate move "Fed Interest Rate
    Decision" (no "FOMC" substring), so match the decision by name too.
    """
    name = event_name or ""
    return "FOMC" in name or "Fed Interest Rate Decision" in name


@dataclass(frozen=True)
class FedLanguagePanel:
    panel_id: str = "fed_language"
    required_requirements: tuple[str, ...] = ("company_news", "economic_events")
    optional_requirements: tuple[str, ...] = ()
    default_ruleset: dict[str, Any] = field(default_factory=lambda: _DEFAULT_RULESET)

    def known_identifiers(self) -> set[str]:
        from openlia.formula import RESERVED_NAMES

        names: set[str] = set(RESERVED_NAMES) | {
            "dovish_keyword_detected",
            "neutral_keyword_detected",
            "hawkish_keyword_detected",
            "crisis_keyword_detected",
            "matched_phrase",
            "matched_headline",
            "matched_date",
            "days_since_fomc",
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
        news = payloads.get("company_news") or []
        events = payloads.get("economic_events") or []
        warnings: list[str] = []
        min_articles = int(params.get("min_signal_articles", 2))

        # The news feed returns anything the provider's auto-tagger loosely
        # associates with the search tags. Signal keywords are only
        # meaningful inside articles actually about Fed communications, so
        # require a tag anchor in the headline before scanning.
        anchors = [
            t.strip() for t in str(params.get("news_search_tags", "")).split(",") if t.strip()
        ]
        relevant = headline_anchored(news, anchors)
        sorted_news = sorted(relevant, key=lambda a: a.get("date", ""), reverse=True)

        # Highest-severity first, so the winning category also supplies the
        # phrase/headline shown in the label.
        category_order = [
            ("crisis_keyword_detected", params.get("crisis_keywords", [])),
            ("hawkish_keyword_detected", params.get("hawkish_keywords", [])),
            ("neutral_keyword_detected", params.get("neutral_keywords", [])),
            ("dovish_keyword_detected", params.get("dovish_keywords", [])),
        ]
        matches = {name: matching_articles(sorted_news, kws) for name, kws in category_order}
        # A category fires only with enough corroborating articles.
        flags = {name: len(matches[name]) >= min_articles for name, _ in category_order}

        matched_phrase = ""
        matched_headline = ""
        matched_date = ""
        for flag_name, _ in category_order:
            if flags[flag_name] and matches[flag_name]:
                hit, article = matches[flag_name][0]  # newest article of that category
                matched_phrase = hit
                matched_headline = article.get("headline", "")
                matched_date = article.get("date", "")
                break

        fomc_events = [e for e in events if _is_fomc_event(e.get("event_name", ""))]
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
