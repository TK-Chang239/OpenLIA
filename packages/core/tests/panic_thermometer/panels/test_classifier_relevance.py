"""Audit C5 regressions — corpus relevance for the keyword panels.

(a) The Fed panel flipped RED on "persistent inflation" matched inside an
    ordinary equity article ("Can Intercontinental Exchange (ICE) Defend
    Its Data Moat?"). Signal keywords must only be scanned in articles
    whose HEADLINE anchors them to Fed communications.

(b) The diplomacy panel labeled every topic-matching headline a progress
    signal, including "Hormuz Attacks Push Oil Toward $100". Topic
    relevance (Hormuz/Iran/strait) must be separated from progress
    sentiment (ceasefire/peace talks/...), with escalation taking
    precedence when both match, and full counts exposed.
"""

from __future__ import annotations

from openlia.panic_thermometer.panels.diplomacy import DiplomacyPanel
from openlia.panic_thermometer.panels.fed_language import FedLanguagePanel


def _fed_context(news: list[dict]) -> dict:
    panel = FedLanguagePanel()
    built = panel.build_context(
        panel_config={
            "params": {
                **panel.default_ruleset["params"],
                "min_signal_articles": 1,
            }
        },
        payloads={"company_news": news, "economic_events": []},
    )
    return built.scalars


def test_fed_panel_ignores_equity_article_mentioning_hawkish_phrase() -> None:
    scalars = _fed_context(
        [
            {
                "date": "2026-08-17",
                "headline": "Can Intercontinental Exchange (ICE) Defend Its Data Moat?",
                "summary": "The exchange operator thrives amid persistent inflation worries.",
            }
        ]
    )
    assert scalars["hawkish_keyword_detected"] is False
    assert scalars["matched_headline"] == ""


def test_fed_panel_still_fires_on_fed_anchored_headline() -> None:
    scalars = _fed_context(
        [
            {
                "date": "2026-08-17",
                "headline": "Powell flags persistent inflation in Jackson Hole remarks",
                "summary": "The Fed chair warned of persistent inflation.",
            }
        ]
    )
    assert scalars["hawkish_keyword_detected"] is True
    assert "Powell" in scalars["matched_headline"]


def _diplomacy_scalars(news: list[dict]) -> dict:
    panel = DiplomacyPanel()
    built = panel.build_context(
        panel_config={"params": {**panel.default_ruleset["params"], "min_signal_articles": 1}},
        payloads={"company_news": news},
    )
    return built.scalars


def test_diplomacy_escalatory_topic_headline_is_not_progress() -> None:
    scalars = _diplomacy_scalars(
        [
            {
                "date": "2026-08-17",
                "headline": "Hormuz Attacks Push Oil Toward $100 Despite US Crude Build",
                "summary": "Strikes on tankers continue in the strait.",
            },
            {
                "date": "2026-08-16",
                "headline": "Iran uses diplomatic pause to prepare for wider regional war",
                "summary": "Mobilization continues despite talks.",
            },
        ]
    )
    assert scalars["matched_progress_headlines"] == []
    assert len(scalars["matched_escalation_headlines"]) == 2
    assert scalars["escalation_detected"] is True
    assert scalars["progress_detected"] is False


def test_diplomacy_progress_requires_progress_keyword() -> None:
    scalars = _diplomacy_scalars(
        [
            {
                "date": "2026-08-17",
                "headline": "Iran and US agree ceasefire framework in Hormuz talks",
                "summary": "Peace talks progressed toward a truce.",
            }
        ]
    )
    assert scalars["progress_detected"] is True
    assert len(scalars["matched_progress_headlines"]) == 1


def test_diplomacy_irrelevant_headline_excluded_entirely() -> None:
    scalars = _diplomacy_scalars(
        [
            {
                "date": "2026-08-17",
                "headline": "Micron Watches As A Major Customer Weighs Chinese Memory Chips",
                "summary": "Semiconductor supply chains shift.",
            }
        ]
    )
    assert scalars["matched_progress_headlines"] == []
    assert scalars["matched_escalation_headlines"] == []


def test_diplomacy_exposes_full_counts() -> None:
    news = [
        {
            "date": f"2026-08-{d:02d}",
            "headline": f"Strike number {d} reported near the Strait of Hormuz",
            "summary": "Retaliation continues.",
        }
        for d in range(1, 13)
    ]
    scalars = _diplomacy_scalars(news)
    assert scalars["escalation_count"] == 12
    assert scalars["progress_count"] == 0
    # Headline lists stay capped for display.
    assert len(scalars["matched_escalation_headlines"]) == 10


def test_fed_panel_exposes_fomc_meeting_dates() -> None:
    panel = FedLanguagePanel()
    built = panel.build_context(
        panel_config={"params": panel.default_ruleset["params"]},
        payloads={
            "company_news": [],
            "economic_events": [
                {"event_name": "FOMC Statement", "date": "2026-07-29"},
                {"event_name": "Fed Interest Rate Decision", "date": "2026-06-17"},
                {"event_name": "FOMC Minutes", "date": "2026-05-06"},
                {"event_name": "FOMC Statement", "date": "2026-03-18"},
                {"event_name": "CPI", "date": "2026-08-12"},
            ],
        },
    )
    assert built.scalars["fomc_dates"] == ["2026-07-29", "2026-06-17", "2026-05-06"]


def test_wage_panel_exposes_dates_series() -> None:
    from openlia.panic_thermometer.panels.wage_growth import WageGrowthPanel

    panel = WageGrowthPanel()
    built = panel.build_context(
        panel_config={"params": panel.default_ruleset["params"]},
        payloads={
            "economic_events": [
                {
                    "event_name": "Average Hourly Earnings",
                    "date": f"2026-{m:02d}-05",
                    "actual": 0.2 + (m % 3) / 10,
                    "comparison": "mom",
                }
                for m in range(1, 9)
            ]
        },
    )
    assert len(built.raw_series["value"]) == 8
    assert built.raw_series["date"][0] == "2026-01-05"
    assert built.raw_series["date"][-1] == "2026-08-05"
