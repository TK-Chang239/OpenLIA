"""Phase 2: refresh_due_quotes honors per-ticker cadence floors."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session


class _RecordingProvider:
    def __init__(self, prices: dict[str, Decimal]) -> None:
        self.prices = prices
        self.called: list[str] = []

    def fetch_quote(self, ticker: str) -> dict | None:
        self.called.append(ticker.upper())
        return {
            "last_price": self.prices.get(ticker.upper()),
            "previous_close": None,
            "day_open": None,
            "day_high": None,
            "day_low": None,
            "volume": None,
            "currency": "USD",
            "quote_at": None,
            "source": "fake",
        } if ticker.upper() in self.prices else None


def _seed_user(db_session, uid: str, cadence: str) -> None:
    from openlia_server.db.models.auth import User
    from openlia_server.db.models.config import UserPrefs

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
    db_session.add(UserPrefs(user_id=uid, portfolio_refresh_cadence=cadence))
    db_session.commit()


def _add_holding(db_session, uid: str, ticker: str) -> None:
    from openlia_server.db.models.content import PortfolioHolding

    db_session.add(
        PortfolioHolding(id=f"h-{uid}-{ticker}", user_id=uid, ticker=ticker)
    )
    db_session.commit()


def test_refresh_skips_ticker_within_its_own_cadence_window(
    create_tables, db_session: Session
) -> None:
    """A user on Weekly cadence's ticker is only due once a week, even if the
    scheduler ticks hourly. The hourly tick should not fetch this ticker until
    >7 days have passed."""
    from openlia_server.services import portfolio_quotes as quotes_svc
    from openlia_server.services.portfolio_quote_refresh import refresh_due_quotes

    _seed_user(db_session, "u1", "weekly")
    _add_holding(db_session, "u1", "AAPL")

    now = datetime(2026, 5, 12, 14, 30, tzinfo=UTC)
    # Fetched 3 days ago — within the weekly window, skip.
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
        fetched_at=now - timedelta(days=3),
        source="fake",
    )

    provider = _RecordingProvider({"AAPL": Decimal("999")})
    result = refresh_due_quotes(db_session, provider=provider, now_utc=now)

    assert provider.called == []
    assert result.skipped_fresh == 1


def test_refresh_uses_min_cadence_when_multiple_holders(
    create_tables, db_session: Session
) -> None:
    """AAPL held by an Hourly user and a Weekly user → effective cadence
    is 1h, so a 90-minute-old fetch triggers a refresh."""
    from openlia_server.services import portfolio_quotes as quotes_svc
    from openlia_server.services.portfolio_quote_refresh import refresh_due_quotes

    _seed_user(db_session, "u1", "weekly")
    _seed_user(db_session, "u2", "hourly")
    _add_holding(db_session, "u1", "AAPL")
    _add_holding(db_session, "u2", "AAPL")

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
        fetched_at=now - timedelta(minutes=90),
        source="fake",
    )

    provider = _RecordingProvider({"AAPL": Decimal("999")})
    result = refresh_due_quotes(db_session, provider=provider, now_utc=now)

    assert provider.called == ["AAPL"]
    assert result.fetched == 1


def test_refresh_excludes_manual_only_ticker(create_tables, db_session: Session) -> None:
    """A ticker held only by manual-cadence users is not in the polling union
    and so is never fetched by refresh_due_quotes."""
    from openlia_server.services.portfolio_quote_refresh import refresh_due_quotes

    _seed_user(db_session, "u1", "manual")
    _add_holding(db_session, "u1", "AAPL")

    now = datetime(2026, 5, 12, 14, 30, tzinfo=UTC)
    provider = _RecordingProvider({"AAPL": Decimal("100")})
    result = refresh_due_quotes(db_session, provider=provider, now_utc=now)

    assert provider.called == []
    assert result.fetched == 0
