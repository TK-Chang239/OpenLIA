"""Unit tests for the market-index quote normalizer."""

from __future__ import annotations

from openlia_server.services import markets_quotes


def test_build_index_quotes_normalizes_and_computes_change():
    rows = [
        {"code": "GSPC.INDX", "close": 7757.64, "previousClose": 7709.96},
        {"code": "BTC-USD.CC", "close": 64869.6, "previousClose": 64904.7},
    ]
    out = markets_quotes.build_index_quotes(rows)
    by_symbol = {q["symbol"]: q for q in out}

    gspc = by_symbol["GSPC.INDX"]
    assert gspc["label"] == "S&P 500"
    assert gspc["value"] == 7757.64
    assert round(gspc["change_abs"], 2) == 47.68
    assert gspc["change_pct"] > 0

    btc = by_symbol["BTC-USD.CC"]
    assert btc["change_abs"] < 0  # closed below prior close


def test_build_index_quotes_falls_back_to_previous_close_when_close_is_na():
    # EODHD returns the string "NA" for close on some symbols; we should still
    # show the previous close, just without an intraday delta.
    rows = [{"code": "US10Y.GBOND", "close": "NA", "previousClose": 4.651}]
    out = markets_quotes.build_index_quotes(rows)
    assert len(out) == 1
    assert out[0]["value"] == 4.651
    assert out[0]["change_abs"] is None
    assert out[0]["change_pct"] is None


def test_build_index_quotes_drops_symbol_with_no_usable_value():
    rows = [{"code": "DXY.INDX", "close": "NA", "previousClose": "NA"}]
    assert markets_quotes.build_index_quotes(rows) == []


def test_build_index_quotes_preserves_basket_order():
    rows = [
        {"code": "BTC-USD.CC", "close": 1.0, "previousClose": 1.0},
        {"code": "GSPC.INDX", "close": 2.0, "previousClose": 2.0},
        {"code": "VIX.INDX", "close": 3.0, "previousClose": 3.0},
    ]
    symbols = [q["symbol"] for q in markets_quotes.build_index_quotes(rows)]
    # Order follows INDEX_BASKET (GSPC, IXIC, VIX, ..., BTC), not input order.
    assert symbols == ["GSPC.INDX", "VIX.INDX", "BTC-USD.CC"]


def test_fetch_indices_uses_injected_fetcher():
    captured: dict[str, object] = {}

    def fake_fetcher(api_key, symbols):
        captured["api_key"] = api_key
        captured["symbols"] = symbols
        return [{"code": "VIX.INDX", "close": 14.9, "previousClose": 15.15}]

    out = markets_quotes.fetch_indices("k", fetcher=fake_fetcher)
    assert captured["api_key"] == "k"
    assert captured["symbols"][0] == "GSPC.INDX"  # basket drives the request
    assert out[0]["symbol"] == "VIX.INDX"
    assert out[0]["change_abs"] < 0
