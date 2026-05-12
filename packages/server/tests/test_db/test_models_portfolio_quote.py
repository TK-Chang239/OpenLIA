"""Phase 1 (portfolio live data): PortfolioQuote model — DB round-trip."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session


@pytest.fixture
def create_tables(engine):
    import openlia_server.db.models.register_all  # noqa: F401
    from openlia_server.db.base import Base

    Base.metadata.create_all(engine)
    yield
    Base.metadata.drop_all(engine)


def test_portfolio_quote_round_trip(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.content import PortfolioQuote

    now = datetime.now(UTC)
    q = PortfolioQuote(
        ticker="AAPL",
        last_price=Decimal("150.25"),
        previous_close=Decimal("148.10"),
        day_open=Decimal("149.00"),
        day_high=Decimal("151.40"),
        day_low=Decimal("148.75"),
        volume=12_345_678,
        currency="USD",
        quote_at=now,
        fetched_at=now,
        source="eodhd",
    )
    db_session.add(q)
    db_session.commit()

    fetched = db_session.execute(
        select(PortfolioQuote).where(PortfolioQuote.ticker == "AAPL")
    ).scalar_one()
    assert fetched.last_price == Decimal("150.25")
    assert fetched.previous_close == Decimal("148.10")
    assert fetched.day_open == Decimal("149.00")
    assert fetched.day_high == Decimal("151.40")
    assert fetched.day_low == Decimal("148.75")
    assert fetched.volume == 12_345_678
    assert fetched.currency == "USD"
    assert fetched.source == "eodhd"
    assert fetched.fetched_at is not None


def test_portfolio_quote_ticker_is_primary_key(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.content import PortfolioQuote

    now = datetime.now(UTC)
    db_session.add(PortfolioQuote(ticker="AAPL", fetched_at=now, source="eodhd"))
    db_session.commit()

    db_session.add(PortfolioQuote(ticker="AAPL", fetched_at=now, source="eodhd"))
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_portfolio_quote_nullable_fields(create_tables, db_session: Session) -> None:
    """All quote fields except ticker + fetched_at + source are nullable
    (so a degraded provider can still write a sentinel row)."""
    from openlia_server.db.models.content import PortfolioQuote

    now = datetime.now(UTC)
    q = PortfolioQuote(ticker="UNKN", fetched_at=now, source="eodhd")
    db_session.add(q)
    db_session.commit()

    fetched = db_session.execute(
        select(PortfolioQuote).where(PortfolioQuote.ticker == "UNKN")
    ).scalar_one()
    assert fetched.last_price is None
    assert fetched.previous_close is None
    assert fetched.volume is None
