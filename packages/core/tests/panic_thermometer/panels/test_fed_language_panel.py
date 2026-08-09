"""Per-panel core tests for FedLanguagePanel."""

from __future__ import annotations

from openlia.formula import evaluate_ruleset
from openlia.panic_thermometer.panels.fed_language import FedLanguagePanel


def test_fed_panel_detects_hawkish_keyword() -> None:
    panel = FedLanguagePanel()
    built = panel.build_context(
        panel_config={
            "params": {
                "dovish_keywords": ["transitory"],
                "neutral_keywords": ["data dependent"],
                "hawkish_keywords": ["persistent inflation"],
                "crisis_keywords": ["unanchored"],
                "min_signal_articles": 1,  # focus: matching logic, not corroboration
            }
        },
        payloads={
            "company_news": [
                {
                    "date": "2026-04-22",
                    "headline": "Fed warns of persistent inflation",
                    "summary": "Officials cite persistent inflation pressures.",
                }
            ],
            "economic_events": [],
        },
    )
    assert built.scalars["hawkish_keyword_detected"] is True
    assert built.scalars["matched_phrase"] == "persistent inflation"


def test_fed_panel_default_ruleset_evaluates_red() -> None:
    panel = FedLanguagePanel()
    cfg = {"params": panel.default_ruleset["params"]}
    built = panel.build_context(
        panel_config=cfg,
        payloads={
            "company_news": [
                {
                    "date": "2026-04-22",
                    "headline": "Persistent inflation persists",
                    "summary": "concerns about persistent inflation",
                },
                {
                    "date": "2026-04-21",
                    "headline": "Officials flag persistent inflation risk",
                    "summary": "more persistent inflation commentary",
                },
            ],
            "economic_events": [],
        },
    )
    # filter scalars to engine-friendly subset
    engine_scalars = {
        k: v
        for k, v in built.scalars.items()
        if v is None or isinstance(v, (bool, int, float, str))
    }
    result = evaluate_ruleset(
        {
            "rules": panel.default_ruleset["rules"],
            "streak_condition": panel.default_ruleset["streak_condition"],
        },
        built.raw_series,
        scalars=engine_scalars,
        params=panel.default_ruleset["params"],
    )
    assert result.status in ("red", "dark_red")


def test_fed_panel_no_news_falls_through_green() -> None:
    panel = FedLanguagePanel()
    built = panel.build_context(
        panel_config={"params": panel.default_ruleset["params"]},
        payloads={"company_news": [], "economic_events": []},
    )
    assert built.scalars["hawkish_keyword_detected"] is False
    assert built.scalars["crisis_keyword_detected"] is False


def test_fed_panel_recognizes_rate_decision_as_fomc() -> None:
    # EODHD's calendar names the decision "Fed Interest Rate Decision" (no
    # "FOMC" substring); the panel must still resolve days_since_fomc from it.
    from datetime import date, timedelta

    panel = FedLanguagePanel()
    recent = (date.today() - timedelta(days=3)).isoformat()
    built = panel.build_context(
        panel_config={"params": panel.default_ruleset["params"]},
        payloads={
            "company_news": [],
            "economic_events": [{"event_name": "Fed Interest Rate Decision", "date": recent}],
        },
    )
    assert built.scalars["days_since_fomc"] == 3.0
    assert not any("no FOMC event" in w for w in built.warnings)


def test_fed_panel_single_crisis_article_does_not_fire() -> None:
    # A lone "emergency" mention in a loosely-related feed must not trip the
    # dark-red crisis (the false-positive observed against real data).
    panel = FedLanguagePanel()
    built = panel.build_context(
        panel_config={"params": panel.default_ruleset["params"]},
        payloads={
            "company_news": [
                {
                    "date": "2026-04-22",
                    "headline": "Fed rules out emergency action",
                    "summary": "no emergency seen",
                }
            ],
            "economic_events": [],
        },
    )
    assert built.scalars["crisis_keyword_detected"] is False


def test_fed_panel_matched_phrase_reflects_winning_category() -> None:
    # Two corroborating crisis articles fire crisis; the label phrase must come
    # from the crisis category even though a dovish keyword also appears.
    panel = FedLanguagePanel()
    built = panel.build_context(
        panel_config={"params": panel.default_ruleset["params"]},
        payloads={
            "company_news": [
                {
                    "date": "2026-04-22",
                    "headline": "Fed flags emergency",
                    "summary": "emergency measures weighed",
                },
                {
                    "date": "2026-04-21",
                    "headline": "Second emergency warning",
                    "summary": "expedited action possible",
                },
                {
                    "date": "2026-04-20",
                    "headline": "Chair stays patient",
                    "summary": "patient and transitory",
                },
            ],
            "economic_events": [],
        },
    )
    assert built.scalars["crisis_keyword_detected"] is True
    assert built.scalars["matched_phrase"] in ("emergency", "expedited")
