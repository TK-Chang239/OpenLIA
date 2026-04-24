from openlia.panic_thermometer.panels.wage_growth import WageGrowthPanel


def test_wage_panel_id_and_requirements():
    p = WageGrowthPanel()
    assert p.panel_id == "wage_growth"
    assert p.required_requirements == ("economic_events",)


def test_wage_default_ruleset():
    rs = WageGrowthPanel().default_ruleset
    assert rs["params"]["wage_threshold_red"] == 0.5
    assert rs["params"]["consecutive_required"] == 2


def test_wage_build_context_consecutive_count():
    p = WageGrowthPanel()
    events = [
        {
            "date": "2026-01-05",
            "event_name": "Average Hourly Earnings",
            "actual": 0.35,
            "country": "US",
        },
        {
            "date": "2026-02-05",
            "event_name": "Average Hourly Earnings",
            "actual": 0.55,
            "country": "US",
        },
        {
            "date": "2026-03-05",
            "event_name": "Average Hourly Earnings",
            "actual": 0.60,
            "country": "US",
        },
        {
            "date": "2026-03-10",
            "event_name": "CPI MoM",
            "actual": 0.30,
            "country": "US",
        },
    ]
    r = p.build_context(
        panel_config={"params": WageGrowthPanel().default_ruleset["params"]},
        payloads={"economic_events": events},
    )
    assert r.scalars["value"] == 0.60
    assert r.scalars["prev_value"] == 0.55
    assert r.scalars["consecutive_count"] == 2
    assert r.scalars["cpi_mom"] == 0.30
    assert r.raw_series["value"] == [0.35, 0.55, 0.60]


def test_wage_build_context_no_events():
    p = WageGrowthPanel()
    r = p.build_context(
        panel_config={"params": WageGrowthPanel().default_ruleset["params"]},
        payloads={"economic_events": []},
    )
    assert r.scalars["value"] is None
    assert r.scalars["consecutive_count"] == 0
