"""Phase 3: compute_value_series — portfolio value over time.

Sums `shares_current * close(t)` over the user's holdings, only for days
where the holding has been added. The X-axis is clamped to the earliest
holding's added_at.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session


def _seed_user(db_session, uid: str = "u-vs") -> None:
    from openlia_server.db.models.auth import User

    if db_session.get(User, uid) is None:
        db_session.add(
            User(
                id=uid,
                email=f"{uid}@example.com",
                display_name=uid,
                password_hash=None,
                is_admin=False,
                is_disabled=False,
            )
        )
        db_session.commit()


def _add_holding(
    db_session,
    uid: str,
    ticker: str,
    shares: Decimal,
    added_at: datetime,
) -> None:
    from openlia_server.db.models.content import PortfolioHolding

    db_session.add(
        PortfolioHolding(
            id=f"h-{uid}-{ticker}",
            user_id=uid,
            ticker=ticker,
            shares=shares,
            currency="USD",
            added_at=added_at,
        )
    )
    db_session.commit()


def _add_daily(db_session, ticker: str, days_close: list[tuple[date, Decimal]]) -> None:
    from openlia_server.db.models.content import PortfolioQuoteDaily

    for d, c in days_close:
        db_session.add(
            PortfolioQuoteDaily(ticker=ticker, trade_date=d, close=c)
        )
    db_session.commit()


def test_value_series_sums_shares_x_close(create_tables, db_session: Session) -> None:
    from openlia_server.services.portfolio_value_series import compute_value_series

    _seed_user(db_session)
    _add_holding(
        db_session,
        "u-vs",
        "AAPL",
        Decimal("10"),
        added_at=datetime(2026, 5, 1, tzinfo=UTC),
    )
    _add_daily(
        db_session,
        "AAPL",
        [
            (date(2026, 5, 1), Decimal("100")),
            (date(2026, 5, 2), Decimal("105")),
            (date(2026, 5, 3), Decimal("110")),
        ],
    )

    today = date(2026, 5, 3)
    result = compute_value_series(
        db_session, user_id="u-vs", timeframe="1w", today=today
    )

    # 10 shares × close on each day.
    assert [(p.date, p.value) for p in result.points] == [
        (date(2026, 5, 1), Decimal("1000")),
        (date(2026, 5, 2), Decimal("1050")),
        (date(2026, 5, 3), Decimal("1100")),
    ]
    assert result.period_return_abs == Decimal("100")
    assert result.period_return_pct == Decimal("0.1")


def test_value_series_excludes_holdings_before_added_at(
    create_tables, db_session: Session
) -> None:
    """A holding added on day 2 contributes 0 to day 1's value."""
    from openlia_server.services.portfolio_value_series import compute_value_series

    _seed_user(db_session)
    _add_holding(
        db_session,
        "u-vs",
        "AAPL",
        Decimal("10"),
        added_at=datetime(2026, 5, 1, tzinfo=UTC),
    )
    _add_holding(
        db_session,
        "u-vs",
        "GOOG",
        Decimal("2"),
        added_at=datetime(2026, 5, 3, tzinfo=UTC),
    )
    _add_daily(
        db_session,
        "AAPL",
        [
            (date(2026, 5, 1), Decimal("100")),
            (date(2026, 5, 2), Decimal("100")),
            (date(2026, 5, 3), Decimal("100")),
        ],
    )
    _add_daily(
        db_session,
        "GOOG",
        [
            (date(2026, 5, 1), Decimal("500")),  # exists but holding not yet added
            (date(2026, 5, 2), Decimal("500")),
            (date(2026, 5, 3), Decimal("500")),
        ],
    )

    today = date(2026, 5, 3)
    result = compute_value_series(
        db_session, user_id="u-vs", timeframe="1w", today=today
    )

    # Day 1: AAPL only (10 × 100) = 1000. Day 3: AAPL + GOOG (10×100 + 2×500) = 2000.
    values = {p.date: p.value for p in result.points}
    assert values[date(2026, 5, 1)] == Decimal("1000")
    assert values[date(2026, 5, 2)] == Decimal("1000")
    assert values[date(2026, 5, 3)] == Decimal("2000")


def test_value_series_clamps_to_inception(create_tables, db_session: Session) -> None:
    """Pick 5Y but portfolio is 4 days old — actual_span starts at the
    earliest added_at, not 5 years ago."""
    from openlia_server.services.portfolio_value_series import compute_value_series

    _seed_user(db_session)
    _add_holding(
        db_session,
        "u-vs",
        "AAPL",
        Decimal("10"),
        added_at=datetime(2026, 5, 1, tzinfo=UTC),
    )
    _add_daily(
        db_session,
        "AAPL",
        [
            (date(2026, 5, 1), Decimal("100")),
            (date(2026, 5, 4), Decimal("110")),
        ],
    )

    today = date(2026, 5, 4)
    result = compute_value_series(
        db_session, user_id="u-vs", timeframe="5y", today=today
    )

    assert result.actual_span.start == date(2026, 5, 1)
    assert result.actual_span.end == date(2026, 5, 4)


def test_value_series_empty_portfolio_returns_empty(
    create_tables, db_session: Session
) -> None:
    from openlia_server.services.portfolio_value_series import compute_value_series

    _seed_user(db_session)
    today = date(2026, 5, 3)
    result = compute_value_series(
        db_session, user_id="u-vs", timeframe="1m", today=today
    )
    assert result.points == []
    assert result.period_return_abs is None


def test_value_series_filters_by_market(create_tables, db_session: Session) -> None:
    """When market='us' is passed, only US holdings contribute; .TW is ignored."""
    from openlia_server.services.portfolio_value_series import compute_value_series

    _seed_user(db_session)
    _add_holding(
        db_session,
        "u-vs",
        "AAPL",
        Decimal("10"),
        added_at=datetime(2026, 5, 1, tzinfo=UTC),
    )
    _add_holding(
        db_session,
        "u-vs",
        "2330.TW",
        Decimal("5"),
        added_at=datetime(2026, 5, 1, tzinfo=UTC),
    )
    _add_daily(
        db_session,
        "AAPL",
        [(date(2026, 5, 1), Decimal("100")), (date(2026, 5, 2), Decimal("110"))],
    )
    _add_daily(
        db_session,
        "2330.TW",
        [(date(2026, 5, 1), Decimal("500")), (date(2026, 5, 2), Decimal("550"))],
    )

    today = date(2026, 5, 2)
    us = compute_value_series(
        db_session, user_id="u-vs", timeframe="1w", today=today, market="us"
    )
    tw = compute_value_series(
        db_session, user_id="u-vs", timeframe="1w", today=today, market="twse"
    )

    # US only: 10 × AAPL prices
    assert {(p.date, p.value) for p in us.points} == {
        (date(2026, 5, 1), Decimal("1000")),
        (date(2026, 5, 2), Decimal("1100")),
    }
    # TWSE only: 5 × 2330.TW prices
    assert {(p.date, p.value) for p in tw.points} == {
        (date(2026, 5, 1), Decimal("2500")),
        (date(2026, 5, 2), Decimal("2750")),
    }


def _add_intraday(
    db_session, ticker: str, ts_close: list[tuple[datetime, Decimal]]
) -> None:
    from openlia_server.db.models.content import PortfolioQuoteIntraday

    for ts, close in ts_close:
        db_session.add(PortfolioQuoteIntraday(ticker=ticker, ts=ts, close=close))
    db_session.commit()


def test_intraday_value_series_aggregates_per_tick(
    create_tables, db_session: Session
) -> None:
    """Each unique tick timestamp produces one point using last-known price per ticker."""
    from openlia_server.services.portfolio_value_series import (
        compute_value_series_intraday,
    )

    _seed_user(db_session)
    _add_holding(
        db_session,
        "u-vs",
        "AAPL",
        Decimal("10"),
        added_at=datetime(2026, 5, 1, tzinfo=UTC),
    )
    _add_holding(
        db_session,
        "u-vs",
        "NVDA",
        Decimal("5"),
        added_at=datetime(2026, 5, 1, tzinfo=UTC),
    )
    t10 = datetime(2026, 5, 11, 14, 0, tzinfo=UTC)
    t11 = datetime(2026, 5, 11, 15, 0, tzinfo=UTC)
    _add_intraday(
        db_session,
        "AAPL",
        [(t10, Decimal("100")), (t11, Decimal("105"))],
    )
    _add_intraday(
        db_session,
        "NVDA",
        [(t10, Decimal("200")), (t11, Decimal("210"))],
    )

    today = date(2026, 5, 11)
    result = compute_value_series_intraday(
        db_session, user_id="u-vs", today=today
    )

    assert result.timeframe == "1d"
    assert [p.ts for p in result.points] == [t10, t11]
    # t10: 10*100 + 5*200 = 2000; t11: 10*105 + 5*210 = 2100
    assert [p.value for p in result.points] == [Decimal("2000"), Decimal("2100")]
    assert result.period_return_abs == Decimal("100")


def test_intraday_value_series_falls_back_to_prior_trading_day(
    create_tables, db_session: Session
) -> None:
    """When today has no intraday rows (weekend/holiday), fall back to most
    recent UTC date with rows."""
    from openlia_server.services.portfolio_value_series import (
        compute_value_series_intraday,
    )

    _seed_user(db_session)
    _add_holding(
        db_session,
        "u-vs",
        "AAPL",
        Decimal("10"),
        added_at=datetime(2026, 5, 1, tzinfo=UTC),
    )
    friday = datetime(2026, 5, 8, 20, 0, tzinfo=UTC)
    _add_intraday(db_session, "AAPL", [(friday, Decimal("100"))])

    sunday = date(2026, 5, 10)
    result = compute_value_series_intraday(
        db_session, user_id="u-vs", today=sunday
    )

    assert len(result.points) == 1
    assert result.points[0].ts == friday
    assert result.points[0].value == Decimal("1000")


def test_intraday_value_series_market_filter(
    create_tables, db_session: Session
) -> None:
    """market='us' only aggregates US tickers; .TW intraday rows ignored."""
    from openlia_server.services.portfolio_value_series import (
        compute_value_series_intraday,
    )

    _seed_user(db_session)
    _add_holding(
        db_session,
        "u-vs",
        "AAPL",
        Decimal("10"),
        added_at=datetime(2026, 5, 1, tzinfo=UTC),
    )
    _add_holding(
        db_session,
        "u-vs",
        "2330.TW",
        Decimal("5"),
        added_at=datetime(2026, 5, 1, tzinfo=UTC),
    )
    t = datetime(2026, 5, 11, 14, 0, tzinfo=UTC)
    _add_intraday(db_session, "AAPL", [(t, Decimal("100"))])
    _add_intraday(db_session, "2330.TW", [(t, Decimal("500"))])

    today = date(2026, 5, 11)
    us = compute_value_series_intraday(
        db_session, user_id="u-vs", today=today, market="us"
    )
    tw = compute_value_series_intraday(
        db_session, user_id="u-vs", today=today, market="twse"
    )

    assert [p.value for p in us.points] == [Decimal("1000")]
    assert [p.value for p in tw.points] == [Decimal("2500")]


def test_timeframe_decoding() -> None:
    from openlia_server.services.portfolio_value_series import resolve_window

    today = date(2026, 5, 11)
    assert resolve_window("1d", today) == today - timedelta(days=1)
    assert resolve_window("1w", today) == today - timedelta(days=7)
    assert resolve_window("1m", today) == today - timedelta(days=30)
    assert resolve_window("3m", today) == today - timedelta(days=90)
    assert resolve_window("6m", today) == today - timedelta(days=180)
    assert resolve_window("1y", today) == today - timedelta(days=365)
    assert resolve_window("5y", today) == today - timedelta(days=365 * 5)
    assert resolve_window("ytd", today) == date(2026, 1, 1)
