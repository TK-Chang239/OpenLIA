from openlia.panic_thermometer.panels.oil import OilPanel


def _panel():
    return OilPanel()


def test_oil_panel_id_and_requirements():
    p = _panel()
    assert p.panel_id == "oil"
    assert p.required_requirements == ("historical_prices", "stock_quote")
    assert p.optional_requirements == ()


def test_oil_default_ruleset_has_four_rules():
    p = _panel()
    rs = p.default_ruleset
    assert len(rs["rules"]) == 4
    assert {r["status"] for r in rs["rules"]} == {"dark_red", "red", "amber", "green"}
    assert rs["params"]["price_threshold"] == 85
    assert rs["params"]["streak_red"] == 30
    assert rs["params"]["streak_dark_red"] == 90
    assert rs["streak_condition"] == "price > price_threshold"


def test_oil_build_context_from_payloads():
    p = _panel()
    history = [
        {
            "date": f"2026-01-{i:02d}",
            "open": 80.0,
            "high": 82.0,
            "low": 79.0,
            "close": 80.0 + i * 0.5,
            "volume": 0,
        }
        for i in range(1, 11)
    ]
    quote = {"price": 92.4, "previous_close": 91.0, "timestamp": "2026-04-23T20:00:00Z"}
    r = p.build_context(
        panel_config={"params": {"ticker": "BNO.US"}},
        payloads={"historical_prices": history, "stock_quote": quote},
    )
    # Live quote tick is appended to raw_series so reserved `price` derives correctly.
    assert r.raw_series["price"][-1] == 92.4
    assert r.raw_series["price"][-2] == 85.0
    assert r.scalars == {}


def test_oil_build_context_without_live_quote_falls_back_to_last_close():
    p = _panel()
    history = [
        {
            "date": "2026-01-01",
            "open": 80.0,
            "high": 82.0,
            "low": 79.0,
            "close": 80.0,
            "volume": 0,
        },
        {
            "date": "2026-01-02",
            "open": 80.5,
            "high": 83.0,
            "low": 80.0,
            "close": 82.5,
            "volume": 0,
        },
    ]
    r = p.build_context(
        panel_config={"params": {"ticker": "BNO.US"}},
        payloads={"historical_prices": history, "stock_quote": None},
    )
    assert r.raw_series["price"][-1] == 82.5
    assert r.scalars == {}
    assert "quote unavailable" in " ".join(r.warnings)
