"""Phase 3: GET /portfolio/value-series route."""

from __future__ import annotations

from datetime import UTC, date, datetime
from decimal import Decimal


def _add_aapl_daily(uid: str) -> None:
    from openlia_server.db import session as session_mod
    from openlia_server.db.models.content import (
        PortfolioHolding,
        PortfolioQuoteDaily,
    )

    with session_mod.SessionLocal() as s:
        s.add(
            PortfolioHolding(
                id="h-1",
                user_id=uid,
                ticker="AAPL",
                shares=Decimal("10"),
                currency="USD",
                added_at=datetime(2026, 5, 1, tzinfo=UTC),
            )
        )
        for d, c in (
            (date(2026, 5, 1), Decimal("100")),
            (date(2026, 5, 8), Decimal("110")),
        ):
            s.add(PortfolioQuoteDaily(ticker="AAPL", trade_date=d, close=c))
        s.commit()


def test_value_series_returns_points(client, user_factory, login_as) -> None:
    u = user_factory()
    login_as(u)
    _add_aapl_daily(u.id)

    r = client.get("/portfolio/value-series?timeframe=1m")
    assert r.status_code == 200
    body = r.json()
    assert body["timeframe"] == "1m"
    assert isinstance(body["points"], list)
    assert len(body["points"]) >= 1
    # Period return is positive (100 → 110 = +10%).
    assert body["period_return_abs"] is not None
    assert Decimal(body["period_return_abs"]) == Decimal("100")  # 10 shares × 10 increase
    assert Decimal(body["period_return_pct"]) == Decimal("0.1")


def test_value_series_empty_portfolio_returns_empty(
    client, user_factory, login_as
) -> None:
    u = user_factory()
    login_as(u)
    r = client.get("/portfolio/value-series?timeframe=1m")
    assert r.status_code == 200
    body = r.json()
    assert body["points"] == []
    assert body["actual_span"] is None


def test_value_series_requires_auth(client) -> None:
    r = client.get("/portfolio/value-series?timeframe=1m")
    assert r.status_code in (401, 403)
