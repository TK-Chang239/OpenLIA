"""Per-panel core tests for DiplomacyPanel."""

from __future__ import annotations

from datetime import date, timedelta

from openlia.panic_thermometer.panels.diplomacy import DiplomacyPanel


def test_diplomacy_days_elapsed_uses_milestone_date() -> None:
    panel = DiplomacyPanel()
    fifty_days_ago = (date.today() - timedelta(days=50)).isoformat()
    built = panel.build_context(
        panel_config={
            "milestone_date": fifty_days_ago,
            "params": panel.default_ruleset["params"],
        },
        payloads={"company_news": []},
    )
    assert built.scalars["days_elapsed"] == 50
    assert built.scalars["days_remaining"] == 0  # window is 30


def test_diplomacy_detects_progress_and_escalation() -> None:
    panel = DiplomacyPanel()
    built = panel.build_context(
        panel_config={
            "milestone_date": date.today().isoformat(),
            "params": panel.default_ruleset["params"],
        },
        payloads={
            "company_news": [
                {"headline": "Ceasefire announced", "summary": "talks resumed"},
                {"headline": "Peace talks progress", "summary": "de-escalation hopes"},
                {"headline": "Military escalation reported near Hormuz", "summary": "blockade"},
                {"headline": "Iran retaliation feared", "summary": "further mobilization"},
            ]
        },
    )
    assert built.scalars["progress_detected"] is True
    assert built.scalars["escalation_detected"] is True


def test_diplomacy_no_news_no_milestone_defaults_to_today() -> None:
    panel = DiplomacyPanel()
    built = panel.build_context(
        panel_config={"params": panel.default_ruleset["params"]},
        payloads={"company_news": []},
    )
    assert built.scalars["days_elapsed"] == 0
    assert built.scalars["progress_detected"] is False
    assert built.scalars["escalation_detected"] is False


def test_diplomacy_single_escalation_article_does_not_fire() -> None:
    # A lone "strike" headline (often a labor/price story) must not trip
    # escalation without corroboration.
    panel = DiplomacyPanel()
    built = panel.build_context(
        panel_config={
            "milestone_date": date.today().isoformat(),
            "params": panel.default_ruleset["params"],
        },
        payloads={"company_news": [{"headline": "Workers strike at plant", "summary": ""}]},
    )
    assert built.scalars["escalation_detected"] is False
