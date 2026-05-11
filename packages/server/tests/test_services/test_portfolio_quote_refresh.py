"""Phase 1: refresh_due_quotes — scheduler tick body.

This service is wrapped by the APScheduler-bound executor in Phase 2; for now
we keep it pure and synchronous so it can be invoked from the wake-up sweep
on server start and from the executor's _do_work without async plumbing.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session


class _RecordingProvider:
    """Test double that records the symbols it was asked to price."""

    def __init__(self, prices: dict[str, Decimal | None]) -> None:
        self.prices = prices
        self.called: list[str] = []

    def fetch_quote(self, ticker: str) -> dict | None:
        self.called.append(ticker.upper())
        price = self.prices.get(ticker.upper())
        if price is None:
            return None
        return {
            "last_price": price,
            "previous_close": price - Decimal("1"),
            "day_open": price,
            "day_high": price,
            "day_low": price,
            "volume": 100,
            "currency": "USD",
            "quote_at": datetime.now(UTC),
            "source": "fake",
        }


def _create_holding(session: Session, *, user_id: str, ticker: str) -> None:
    from openlia_server.db.models.auth import User
    from openlia_server.db.models.content import PortfolioHolding

    if session.get(User, user_id) is None:
        session.add(
            User(
                id=user_id,
                email=f"{user_id}@example.com",
                display_name=user_id,
                password_hash=None,
                is_admin=False,
                is_disabled=False,
            )
        )
    session.add(
        PortfolioHolding(id=f"h-{user_id}-{ticker}", user_id=user_id, ticker=ticker)
    )
    session.commit()


def test_refresh_fetches_every_ticker_when_no_quotes_exist(
    create_tables, db_session: Session
) -> None:
    from openlia_server.services.portfolio_quote_refresh import refresh_due_quotes

    _create_holding(db_session, user_id="u1", ticker="AAPL")
    _create_holding(db_session, user_id="u2", ticker="GOOG")

    provider = _RecordingProvider(
        {"AAPL": Decimal("150"), "GOOG": Decimal("2700")}
    )
    # Pick a weekday during US market hours so the market-closed skip doesn't
    # fire.
    now = datetime(2026, 5, 12, 14, 30, tzinfo=UTC)
    result = refresh_due_quotes(
        db_session,
        provider=provider,
        now_utc=now,
        min_cadence_seconds=3600,
    )

    assert set(provider.called) == {"AAPL", "GOOG"}
    assert result.fetched == 2
    assert result.skipped_fresh == 0


def test_refresh_skips_fresh_tickers(create_tables, db_session: Session) -> None:
    from openlia_server.services import portfolio_quotes as quotes_svc
    from openlia_server.services.portfolio_quote_refresh import refresh_due_quotes

    _create_holding(db_session, user_id="u1", ticker="AAPL")
    now = datetime(2026, 5, 12, 14, 30, tzinfo=UTC)
    quotes_svc.upsert_quote(
        db_session,
        ticker="AAPL",
        last_price=Decimal("100"),
        previous_close=None,
        day_open=None,
        day_high=None,
        day_low=None,
        volume=None,
        currency="USD",
        quote_at=None,
        fetched_at=now - timedelta(minutes=30),
        source="fake",
    )

    provider = _RecordingProvider({"AAPL": Decimal("999")})
    result = refresh_due_quotes(
        db_session,
        provider=provider,
        now_utc=now,
        min_cadence_seconds=3600,  # 60 min; 30 min cached row is fresh enough
    )

    assert provider.called == []
    assert result.fetched == 0
    assert result.skipped_fresh == 1
    # Existing row untouched.
    assert quotes_svc.get_quote(db_session, ticker="AAPL").last_price == Decimal("100")


def test_refresh_skips_closed_market_with_recent_quote(
    create_tables, db_session: Session
) -> None:
    """A US ticker fetched < 24h ago when the market is closed is skipped."""
    from openlia_server.services import portfolio_quotes as quotes_svc
    from openlia_server.services.portfolio_quote_refresh import refresh_due_quotes

    _create_holding(db_session, user_id="u1", ticker="AAPL")
    # Sunday — US market closed.
    sunday = datetime(2026, 5, 17, 14, 30, tzinfo=UTC)
    # Quote captured Friday afternoon (a couple of days earlier).
    fetched_friday = datetime(2026, 5, 15, 19, 0, tzinfo=UTC)
    quotes_svc.upsert_quote(
        db_session,
        ticker="AAPL",
        last_price=Decimal("100"),
        previous_close=None,
        day_open=None,
        day_high=None,
        day_low=None,
        volume=None,
        currency="USD",
        quote_at=None,
        fetched_at=fetched_friday,
        source="fake",
    )

    provider = _RecordingProvider({"AAPL": Decimal("999")})
    # Cadence is 1h: the cached row is 19h+ stale, but the market is closed
    # so we don't refetch (no new prints since Friday close).
    result = refresh_due_quotes(
        db_session,
        provider=provider,
        now_utc=sunday,
        min_cadence_seconds=3600,
    )

    assert provider.called == []
    assert result.skipped_market_closed == 1


def test_refresh_fetches_when_market_closed_but_quote_stale(
    create_tables, db_session: Session
) -> None:
    """Even when the market is closed, a >24h stale quote gets a refresh
    so we don't sit on infinitely stale data over long weekends or outages."""
    from openlia_server.services import portfolio_quotes as quotes_svc
    from openlia_server.services.portfolio_quote_refresh import refresh_due_quotes

    _create_holding(db_session, user_id="u1", ticker="AAPL")
    sunday = datetime(2026, 5, 17, 14, 30, tzinfo=UTC)
    # >72h ago -- past the closed-market grace window.
    fetched_long_ago = sunday - timedelta(hours=80)
    quotes_svc.upsert_quote(
        db_session,
        ticker="AAPL",
        last_price=Decimal("100"),
        previous_close=None,
        day_open=None,
        day_high=None,
        day_low=None,
        volume=None,
        currency="USD",
        quote_at=None,
        fetched_at=fetched_long_ago,
        source="fake",
    )
    provider = _RecordingProvider({"AAPL": Decimal("105")})

    result = refresh_due_quotes(
        db_session,
        provider=provider,
        now_utc=sunday,
        min_cadence_seconds=3600,
    )

    assert provider.called == ["AAPL"]
    assert result.fetched == 1


def test_refresh_ignores_groups_meta_row(create_tables, db_session: Session) -> None:
    """The hidden __GROUPS__ pseudo-holding must not become a fetch target."""
    from openlia_server.db.models.auth import User
    from openlia_server.db.models.content import PortfolioHolding
    from openlia_server.services.portfolio_quote_refresh import refresh_due_quotes

    db_session.add(
        User(
            id="u1",
            email="u1@example.com",
            display_name="u1",
            password_hash=None,
            is_admin=False,
            is_disabled=False,
        )
    )
    db_session.add(
        PortfolioHolding(id="meta-1", user_id="u1", ticker="__GROUPS__")
    )
    db_session.commit()

    provider = _RecordingProvider({})
    now = datetime(2026, 5, 12, 14, 30, tzinfo=UTC)
    result = refresh_due_quotes(
        db_session,
        provider=provider,
        now_utc=now,
        min_cadence_seconds=3600,
    )

    assert provider.called == []
    assert result.fetched == 0


def test_refresh_writes_quote_row_with_provider_payload(
    create_tables, db_session: Session
) -> None:
    from openlia_server.services import portfolio_quotes as quotes_svc
    from openlia_server.services.portfolio_quote_refresh import refresh_due_quotes

    _create_holding(db_session, user_id="u1", ticker="MSFT")
    provider = _RecordingProvider({"MSFT": Decimal("420.50")})
    now = datetime(2026, 5, 12, 14, 30, tzinfo=UTC)
    refresh_due_quotes(
        db_session,
        provider=provider,
        now_utc=now,
        min_cadence_seconds=3600,
    )

    row = quotes_svc.get_quote(db_session, ticker="MSFT")
    assert row is not None
    assert row.last_price == Decimal("420.50")
    assert row.previous_close == Decimal("419.50")
    assert row.source == "fake"
    assert row.fetched_at is not None
