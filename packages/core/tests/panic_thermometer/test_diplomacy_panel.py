from datetime import date, timedelta

from openlia.panic_thermometer.panels.diplomacy import DiplomacyPanel


def test_diplomacy_panel_id_and_requirements():
    p = DiplomacyPanel()
    assert p.panel_id == "diplomacy"
    assert p.required_requirements == ("company_news",)


def test_diplomacy_default_ruleset():
    rs = DiplomacyPanel().default_ruleset
    assert rs["params"]["window_days"] == 30
    assert rs["params"]["window_amber_pct"] == 50


def test_diplomacy_build_context_computes_days_elapsed():
    p = DiplomacyPanel()
    milestone = (date.today() - timedelta(days=10)).isoformat()
    news = [
        {
            "date": "2026-04-20",
            "headline": "Iran strait ceasefire reached",
            "summary": "Diplomatic progress",
        },
        {
            "date": "2026-04-22",
            "headline": "Second ceasefire holds",
            "summary": "negotiations continue",
        },
        {
            "date": "2026-04-21",
            "headline": "Iran mobilization announced",
            "summary": "Retaliation threatened",
        },
        {
            "date": "2026-04-23",
            "headline": "Hormuz blockade tightens",
            "summary": "further military escalation",
        },
    ]
    r = p.build_context(
        panel_config={
            "params": DiplomacyPanel().default_ruleset["params"],
            "milestone_date": milestone,
        },
        payloads={"company_news": news},
    )
    assert r.scalars["days_elapsed"] == 10
    assert r.scalars["days_remaining"] == 20
    assert r.scalars["escalation_detected"] is True
    assert r.scalars["progress_detected"] is True


def test_diplomacy_build_context_no_milestone_defaults_today():
    p = DiplomacyPanel()
    r = p.build_context(
        panel_config={
            "params": DiplomacyPanel().default_ruleset["params"],
            "milestone_date": None,
        },
        payloads={"company_news": []},
    )
    assert r.scalars["days_elapsed"] == 0
    assert r.scalars["escalation_detected"] is False
