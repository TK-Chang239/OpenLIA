from openlia.panic_thermometer.panels.inflation import InflationPanel


def test_inflation_panel_id_and_requirements():
    p = InflationPanel()
    assert p.panel_id == "inflation"
    assert set(p.required_requirements) == {
        "historical_prices",
        "stock_quote",
        "economic_events",
    }


def test_inflation_default_ruleset_has_amber_red_darkred_green():
    rs = InflationPanel().default_ruleset
    statuses = [r["status"] for r in rs["rules"]]
    assert statuses[0] == "dark_red"
    assert "green" in statuses
    assert rs["params"]["primary_ticker"] == "TIP.US"
    assert rs["params"]["level_red"] == 3.0


def test_inflation_build_context_picks_michigan_latest():
    p = InflationPanel()
    history = [
        {
            "date": "2026-03-01",
            "open": 100,
            "high": 100,
            "low": 100,
            "close": 99.0,
            "volume": 0,
        },
        {
            "date": "2026-03-02",
            "open": 100,
            "high": 100,
            "low": 100,
            "close": 99.5,
            "volume": 0,
        },
    ]
    quote = {"price": 99.7, "previous_close": 99.5}
    events = [
        {
            "date": "2026-02-15",
            "event_name": "Michigan 5 Year Inflation Expectations",
            "actual": 3.1,
            "country": "US",
        },
        {
            "date": "2026-03-15",
            "event_name": "Michigan 5 Year Inflation Expectations",
            "actual": 3.3,
            "country": "US",
        },
        {
            "date": "2026-03-15",
            "event_name": "Nonfarm Payrolls",
            "actual": 150000,
            "country": "US",
        },
    ]
    r = p.build_context(
        panel_config={
            "params": {
                "primary_ticker": "TIP.US",
                "event_type_filter": "Michigan 5 Year Inflation Expectations",
            }
        },
        payloads={
            "historical_prices": history,
            "stock_quote": quote,
            "economic_events": events,
        },
    )
    assert r.scalars["michigan_5y"] == 3.3
    assert r.scalars["michigan_prev"] == 3.1
    assert r.raw_series["tip_price"][-1] == 99.5


def test_inflation_build_context_without_michigan_release():
    p = InflationPanel()
    r = p.build_context(
        panel_config={
            "params": {
                "primary_ticker": "TIP.US",
                "event_type_filter": "Michigan 5 Year Inflation Expectations",
            }
        },
        payloads={"historical_prices": [], "stock_quote": None, "economic_events": []},
    )
    assert r.scalars["michigan_5y"] is None
    assert r.scalars["michigan_prev"] is None
