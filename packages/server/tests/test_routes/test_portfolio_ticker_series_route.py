"""Phase 4: GET /portfolio/ticker-series."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal


def _seed_holding(uid: str, ticker: str) -> None:
    from openlia_server.db import session as session_mod
    from openlia_server.db.models.content import PortfolioHolding

    with session_mod.SessionLocal() as s:
        s.add(
            PortfolioHolding(
                id=f"h-{ticker}",
                user_id=uid,
                ticker=ticker,
                shares=Decimal("10"),
                currency="USD",
                added_at=datetime(2026, 5, 1, tzinfo=UTC),
            )
        )
        s.commit()


def test_ticker_series_1d_reads_intraday(client, user_factory, login_as) -> None:
    from openlia_server.db import session as session_mod
    from openlia_server.db.models.content import PortfolioQuoteIntraday

    u = user_factory()
    login_as(u)
    _seed_holding(u.id, "AAPL")

    today_start = datetime.combine(datetime.now(UTC).date(), datetime.min.time(), tzinfo=UTC)
    with session_mod.SessionLocal() as s:
        s.add(
            PortfolioQuoteIntraday(
                ticker="AAPL", ts=today_start + timedelta(hours=10), close=Decimal("100")
            )
        )
        s.add(
            PortfolioQuoteIntraday(
                ticker="AAPL", ts=today_start + timedelta(hours=15), close=Decimal("110")
            )
        )
        s.commit()

    r = client.get("/portfolio/ticker-series?timeframe=1d")
    assert r.status_code == 200
    body = r.json()
    assert body["timeframe"] == "1d"
    assert len(body["series"]["AAPL"]) == 2
    assert Decimal(body["series"]["AAPL"][0]["close"]) == Decimal("100")
    assert Decimal(body["period_change_pct"]["AAPL"]) == Decimal("0.1")


def test_ticker_series_1m_reads_daily(client, user_factory, login_as) -> None:
    from openlia_server.db import session as session_mod
    from openlia_server.db.models.content import PortfolioQuoteDaily

    u = user_factory()
    login_as(u)
    _seed_holding(u.id, "AAPL")

    today = datetime.now(UTC).date()
    with session_mod.SessionLocal() as s:
        for offset, close in ((25, "100"), (15, "105"), (1, "110")):
            s.add(
                PortfolioQuoteDaily(
                    ticker="AAPL",
                    trade_date=today - timedelta(days=offset),
                    close=Decimal(close),
                )
            )
        s.commit()

    r = client.get("/portfolio/ticker-series?timeframe=1m")
    body = r.json()
    assert len(body["series"]["AAPL"]) == 3
    assert Decimal(body["period_change_pct"]["AAPL"]) == Decimal("0.1")


def test_ticker_series_empty_portfolio(client, user_factory, login_as) -> None:
    u = user_factory()
    login_as(u)
    r = client.get("/portfolio/ticker-series?timeframe=1d")
    assert r.status_code == 200
    body = r.json()
    assert body["series"] == {}
    assert body["period_change_pct"] == {}


def test_ticker_series_requires_auth(client) -> None:
    r = client.get("/portfolio/ticker-series?timeframe=1d")
    assert r.status_code in (401, 403)


def test_ticker_series_filters_by_market(client, user_factory, login_as) -> None:
    from openlia_server.db import session as session_mod
    from openlia_server.db.models.content import PortfolioQuoteDaily

    u = user_factory()
    login_as(u)
    _seed_holding(u.id, "AAPL")
    _seed_holding(u.id, "2330.TW")

    today = datetime.now(UTC).date()
    with session_mod.SessionLocal() as s:
        for ticker, close in (("AAPL", "100"), ("2330.TW", "600")):
            s.add(
                PortfolioQuoteDaily(
                    ticker=ticker,
                    trade_date=today - timedelta(days=1),
                    close=Decimal(close),
                )
            )
            s.add(
                PortfolioQuoteDaily(
                    ticker=ticker,
                    trade_date=today,
                    close=Decimal(close),
                )
            )
        s.commit()

    r_us = client.get("/portfolio/ticker-series?timeframe=1w&market=us")
    assert r_us.status_code == 200
    assert set(r_us.json()["series"].keys()) == {"AAPL"}

    r_tw = client.get("/portfolio/ticker-series?timeframe=1w&market=tw")
    assert r_tw.status_code == 200
    assert set(r_tw.json()["series"].keys()) == {"2330.TW"}


def test_ticker_series_1d_returns_dense_intraday_points(client, user_factory, login_as) -> None:
    """Per-ticker 1D sparklines must surface every intraday tick collected
    today — one point per row, ordered ascending — so the sparkline reflects
    the same density as the aggregate 1D value-series chart."""
    from openlia_server.db import session as session_mod
    from openlia_server.db.models.content import PortfolioQuoteIntraday

    u = user_factory()
    login_as(u)
    _seed_holding(u.id, "AAPL")

    session_start = datetime.combine(
        datetime.now(UTC).date(), datetime.min.time(), tzinfo=UTC
    ) + timedelta(hours=14)
    closes = [Decimal(c) for c in (100, 101, 102, 103, 104)]
    with session_mod.SessionLocal() as s:
        for i, close in enumerate(closes):
            s.add(
                PortfolioQuoteIntraday(
                    ticker="AAPL",
                    ts=session_start + timedelta(minutes=15 * i),
                    close=close,
                )
            )
        s.commit()

    r = client.get("/portfolio/ticker-series?timeframe=1d")
    assert r.status_code == 200
    body = r.json()
    series = body["series"]["AAPL"]
    assert len(series) == 5
    ts_list = [pt["ts"] for pt in series]
    assert ts_list == sorted(ts_list)
    assert Decimal(series[0]["close"]) == Decimal("100")
    assert Decimal(series[-1]["close"]) == Decimal("104")
    assert Decimal(body["period_change_pct"]["AAPL"]) == Decimal("0.04")
