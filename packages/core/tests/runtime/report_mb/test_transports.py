import dataclasses

from openlia.llm.runtime.report_mb.transports import MbDataTransports


def _transports() -> MbDataTransports:
    return MbDataTransports(
        quotes=lambda tickers: [{"ticker": t, "price": 100.0} for t in tickers],
        prices=lambda ticker, rng: [{"ticker": ticker, "range": rng, "close": 100.0}],
        news=lambda **kwargs: [{"title": "Markets rally", "symbol": kwargs.get("symbol")}],
        economic_calendar=lambda window: [{"event": "CPI", "window": window}],
        macro_indicators=lambda keys: {k: 1.0 for k in keys},
    )


def test_transports_is_frozen_dataclass():
    t = _transports()
    assert dataclasses.is_dataclass(t)
    field_names = {f.name for f in dataclasses.fields(t)}
    assert field_names == {
        "quotes",
        "prices",
        "news",
        "economic_calendar",
        "macro_indicators",
    }


def test_quotes_callable_returns_canned_data():
    t = _transports()
    rows = t.quotes(["AAPL.US", "MSFT.US"])
    assert [r["ticker"] for r in rows] == ["AAPL.US", "MSFT.US"]


def test_prices_callable_returns_canned_data():
    t = _transports()
    rows = t.prices("AAPL.US", "1mo")
    assert rows[0]["range"] == "1mo"


def test_news_callable_accepts_optional_symbol():
    t = _transports()
    assert t.news()[0]["symbol"] is None
    assert t.news(symbol="AAPL.US")[0]["symbol"] == "AAPL.US"


def test_economic_calendar_callable_returns_canned_data():
    t = _transports()
    assert t.economic_calendar("this_week")[0]["window"] == "this_week"


def test_macro_indicators_callable_returns_canned_data():
    t = _transports()
    assert t.macro_indicators(["us_10y", "vix"]) == {"us_10y": 1.0, "vix": 1.0}
