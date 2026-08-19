"""Behavior tests for the EODHD-backed Panic Thermometer dispatcher.

These exercise the public ``DataDispatcher.fetch`` contract through a fake
EODHD client, asserting the field normalization the core panels rely on.
"""

from __future__ import annotations

from typing import Any

from openlia_server.services.pt_wiring import EodhdPtDispatcher, build_pt_dispatcher


class FakeClient:
    """Records call kwargs and returns EODHD-shaped rows."""

    def __init__(self, api_key: str) -> None:
        self.api_key = api_key
        self.calls: dict[str, Any] = {}

    def get_eod_historical_stock_market_data(
        self, symbol, period="d", from_date=None, to_date=None, **kwargs
    ) -> list[dict[str, Any]]:
        self.calls["prices_symbol"] = symbol
        self.calls["prices_from"] = from_date
        self.calls["prices_to"] = to_date
        return [{"date": "2026-08-01", "open": 46.0, "high": 47.9, "low": 46.8, "close": 46.93}]

    def get_live_stock_prices(self, ticker, s=None, **kwargs) -> dict[str, Any]:
        self.calls["quote_ticker"] = ticker
        return {"code": ticker, "close": 46.93, "previousClose": 47.37, "high": 47.9, "low": 46.8}

    def get_economic_events_data(
        self, date_from=None, date_to=None, country=None, **kwargs
    ) -> list[dict[str, Any]]:
        self.calls["econ_from"] = date_from
        self.calls["econ_to"] = date_to
        self.calls["econ_country"] = country
        return [
            {
                "type": "Average Hourly Earnings",
                "date": "2026-08-01",
                "actual": "0.6",
                "comparison": "mom",
                "country": "US",
            },
            {"type": "Michigan 5 Year Inflation Expectations", "date": "2026-07-15", "actual": 2.9},
        ]


def _dispatcher(
    client: FakeClient,
    key: str | None = "k",
    news_fetcher: Any = None,
) -> EodhdPtDispatcher:
    return EodhdPtDispatcher(
        key_resolver=lambda: key,
        client_factory=lambda _key: client,
        news_fetcher=news_fetcher or (lambda _k, _t, _limit: []),
    )


def test_no_key_returns_none() -> None:
    d = EodhdPtDispatcher(key_resolver=lambda: None, client_factory=lambda _k: FakeClient(_k))
    assert d.fetch(requirement="stock_quote", panel_id="oil", params={"ticker": "BNO.US"}) is None


def test_historical_prices_uses_ticker_param() -> None:
    c = FakeClient("k")
    rows = _dispatcher(c).fetch(
        requirement="historical_prices", panel_id="oil", params={"ticker": "BNO.US"}
    )
    assert c.calls["prices_symbol"] == "BNO.US"
    assert c.calls["prices_from"] <= c.calls["prices_to"]
    assert rows[0]["close"] == 46.93


def test_historical_prices_falls_back_to_primary_ticker() -> None:
    c = FakeClient("k")
    _dispatcher(c).fetch(
        requirement="historical_prices", panel_id="inflation", params={"primary_ticker": "TIP.US"}
    )
    assert c.calls["prices_symbol"] == "TIP.US"


def test_stock_quote_normalizes_field_names() -> None:
    c = FakeClient("k")
    quote = _dispatcher(c).fetch(
        requirement="stock_quote", panel_id="oil", params={"ticker": "BNO.US"}
    )
    # Panels read ``price`` and ``previous_close`` — not EODHD's close/previousClose.
    assert quote == {"price": 46.93, "previous_close": 47.37, "high": 47.9, "low": 46.8}


def test_economic_events_maps_type_to_event_name_and_coerces_actual() -> None:
    c = FakeClient("k")
    events = _dispatcher(c).fetch(requirement="economic_events", panel_id="wage_growth", params={})
    names = {e["event_name"] for e in events}
    assert "Average Hourly Earnings" in names
    ahe = next(e for e in events if e["event_name"] == "Average Hourly Earnings")
    assert ahe["actual"] == 0.6  # string "0.6" coerced to float
    assert ahe["comparison"] == "mom"  # mom/yoy disambiguator preserved
    assert c.calls["econ_country"] == "US"
    assert c.calls["econ_from"] <= c.calls["econ_to"]


def _recording_news_fetcher(seen: list[str]) -> Any:
    def fetch(api_key: str, tag: str, limit: int) -> list[dict[str, Any]]:
        seen.append(tag)
        return [
            {
                "title": f"{tag} hl",
                "content": "body",
                "date": "2026-08-08",
                "link": "https://x.co/a",
            },
            {
                "title": f"{tag} hl",
                "content": "dup",
                "date": "2026-08-08",
                "link": "https://x.co/a",
            },
        ]

    return fetch


def test_company_news_maps_fields_and_dedupes() -> None:
    seen: list[str] = []
    news = _dispatcher(FakeClient("k"), news_fetcher=_recording_news_fetcher(seen)).fetch(
        requirement="company_news",
        panel_id="fed_language",
        params={"news_search_tags": "Fed,FOMC"},
    )
    assert seen == ["Fed", "FOMC"]  # comma-split into per-tag REST calls
    # Panels read ``headline``/``summary``; identical titles are de-duplicated.
    assert all("headline" in n and "summary" in n for n in news)
    assert len(news) == 2  # two distinct tag headlines, dups within each dropped


def test_company_news_defaults_tag_when_none_supplied() -> None:
    seen: list[str] = []
    _dispatcher(FakeClient("k"), news_fetcher=_recording_news_fetcher(seen)).fetch(
        requirement="company_news", panel_id="diplomacy", params={}
    )
    assert seen == ["geopolitics"]


def test_company_news_empty_without_key() -> None:
    # News uses the resolved key directly (not the SDK client); no key -> no news.
    d = EodhdPtDispatcher(
        key_resolver=lambda: None,
        client_factory=lambda _k: FakeClient(_k),
        news_fetcher=_recording_news_fetcher([]),
    )
    assert d.fetch(requirement="company_news", panel_id="diplomacy", params={}) is None


def test_fetch_error_degrades_to_none() -> None:
    class Boom(FakeClient):
        def get_live_stock_prices(self, ticker, s=None, **kwargs):
            raise RuntimeError("network down")

    c = Boom("k")
    assert (
        _dispatcher(c).fetch(requirement="stock_quote", panel_id="oil", params={"ticker": "BNO.US"})
        is None
    )


def test_client_is_cached_across_fetches() -> None:
    built: list[str] = []

    def factory(key: str) -> FakeClient:
        built.append(key)
        return FakeClient(key)

    d = EodhdPtDispatcher(key_resolver=lambda: "k", client_factory=factory)
    d.fetch(requirement="stock_quote", panel_id="oil", params={"ticker": "BNO.US"})
    d.fetch(requirement="economic_events", panel_id="wage_growth", params={})
    assert built == ["k"]  # one client built, reused for the second fetch


def test_unknown_requirement_returns_none() -> None:
    c = FakeClient("k")
    assert _dispatcher(c).fetch(requirement="mystery", panel_id="oil", params={}) is None


def test_build_pt_dispatcher_none_key_yields_none_fetch(monkeypatch) -> None:
    import openlia_server.services.pt_wiring as mod

    monkeypatch.setattr(mod, "resolve_eodhd_api_key", lambda _db: None)

    class _Sess:
        def close(self) -> None:
            pass

    d = build_pt_dispatcher(session_factory=lambda: _Sess())
    assert d.fetch(requirement="stock_quote", panel_id="oil", params={"ticker": "BNO.US"}) is None


class _WindowRecordingClient(FakeClient):
    """Records every economic-events window (the dispatcher chunks long
    lookbacks into <=80-day windows to stay under EODHD's 1000-event cap)."""

    def __init__(self, api_key: str) -> None:
        super().__init__(api_key)
        self.windows: list[tuple[str, str]] = []

    def get_economic_events_data(self, date_from=None, date_to=None, country=None, **kwargs):
        self.windows.append((date_from, date_to))
        return super().get_economic_events_data(
            date_from=date_from, date_to=date_to, country=country, **kwargs
        )


def test_economic_events_honors_history_lookback_months() -> None:
    from datetime import UTC, datetime, timedelta

    client = _WindowRecordingClient("k")
    d = _dispatcher(client)
    d.fetch(
        requirement="economic_events",
        panel_id="wage_growth",
        params={"history_lookback_months": 12},
    )
    first_from = datetime.fromisoformat(client.windows[0][0]).replace(tzinfo=UTC)
    # 12 months * 31 days + 10 slack: comfortably over a year, so twelve
    # monthly AHE prints land in the window (was hard-capped at 70 days).
    assert datetime.now(UTC) - first_from >= timedelta(days=360)
    # Chunked to stay under the per-call event cap, ending at today.
    assert len(client.windows) >= 5
    for date_from, date_to in client.windows:
        span = datetime.fromisoformat(date_to) - datetime.fromisoformat(date_from)
        assert span <= timedelta(days=80)
    assert client.windows[-1][1] == datetime.now(UTC).date().isoformat()


def test_economic_events_honors_events_lookback_days() -> None:
    from datetime import UTC, datetime, timedelta

    client = _WindowRecordingClient("k")
    d = _dispatcher(client)
    d.fetch(
        requirement="economic_events",
        panel_id="fed_language",
        params={"events_lookback_days": 240},
    )
    first_from = datetime.fromisoformat(client.windows[0][0]).replace(tzinfo=UTC)
    delta = datetime.now(UTC) - first_from
    assert timedelta(days=239) <= delta <= timedelta(days=241)


def test_fetch_caches_identical_requests_within_ttl() -> None:
    calls = {"n": 0}

    class CountingClient(FakeClient):
        def get_economic_events_data(self, *args, **kwargs):
            calls["n"] += 1
            return super().get_economic_events_data(*args, **kwargs)

    client = CountingClient("k")
    d = _dispatcher(client)
    first = d.fetch(requirement="economic_events", panel_id="wage_growth", params={})
    second = d.fetch(requirement="economic_events", panel_id="inflation", params={})
    # Default 70-day window = one chunk; the second identical fetch is served
    # from the TTL cache without touching the client.
    assert calls["n"] == 1
    assert first == second
    # Different params -> different cache key -> real upstream calls again
    # (a 240-day window spans 241 days inclusive -> four <=80-day chunks).
    d.fetch(
        requirement="economic_events",
        panel_id="fed_language",
        params={"events_lookback_days": 240},
    )
    assert calls["n"] == 5
