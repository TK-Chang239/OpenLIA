from openlia.panic_thermometer.panels.fed_language import FedLanguagePanel


def test_fed_panel_id_and_requirements():
    p = FedLanguagePanel()
    assert p.panel_id == "fed_language"
    assert set(p.required_requirements) == {"company_news", "economic_events"}


def test_fed_default_ruleset_has_crisis_hawkish_neutral_green():
    rs = FedLanguagePanel().default_ruleset
    statuses = [r["status"] for r in rs["rules"]]
    assert statuses == ["dark_red", "red", "amber", "green"]
    assert "persistent inflation" in rs["params"]["hawkish_keywords"]


def test_fed_build_context_detects_hawkish_keyword():
    p = FedLanguagePanel()
    news = [
        {
            "date": "2026-04-20",
            "headline": "Powell: persistent inflation concerns grow",
            "summary": "The chair warned about persistent inflation.",
            "source": "Reuters",
        },
        {
            "date": "2026-04-18",
            "headline": "Fed stays patient",
            "summary": "Data dependent stance",
            "source": "WSJ",
        },
    ]
    events = [
        {"date": "2026-04-10", "event_name": "FOMC Statement", "country": "US"},
    ]
    r = p.build_context(
        panel_config={"params": FedLanguagePanel().default_ruleset["params"]},
        payloads={"company_news": news, "economic_events": events},
    )
    assert r.scalars["hawkish_keyword_detected"] is True
    assert r.scalars["crisis_keyword_detected"] is False
    assert "persistent inflation" in r.scalars["matched_phrase"].lower()


def test_fed_build_context_no_matches_is_dovish_green():
    p = FedLanguagePanel()
    news = [
        {
            "date": "2026-04-20",
            "headline": "Fed stays patient",
            "summary": "well anchored",
            "source": "Reuters",
        }
    ]
    r = p.build_context(
        panel_config={"params": FedLanguagePanel().default_ruleset["params"]},
        payloads={"company_news": news, "economic_events": []},
    )
    assert r.scalars["hawkish_keyword_detected"] is False
    assert r.scalars["dovish_keyword_detected"] is True
