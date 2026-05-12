"""Phase 1: portfolio_quotes service — upsert + read helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from decimal import Decimal

from sqlalchemy.orm import Session


def test_upsert_quote_writes_new_row(create_tables, db_session: Session) -> None:
    from openlia_server.services import portfolio_quotes as svc

    now = datetime.now(UTC)
    svc.upsert_quote(
        db_session,
        ticker="aapl",
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

    row = svc.get_quote(db_session, ticker="AAPL")
    assert row is not None
    assert row.ticker == "AAPL"  # uppercased on write
    assert row.last_price == Decimal("150.25")
    assert row.source == "eodhd"


def test_upsert_quote_replaces_existing(create_tables, db_session: Session) -> None:
    from openlia_server.services import portfolio_quotes as svc

    t0 = datetime.now(UTC)
    svc.upsert_quote(
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
        fetched_at=t0,
        source="eodhd",
    )
    t1 = t0 + timedelta(hours=1)
    svc.upsert_quote(
        db_session,
        ticker="AAPL",
        last_price=Decimal("200"),
        previous_close=Decimal("100"),
        day_open=Decimal("100"),
        day_high=Decimal("210"),
        day_low=Decimal("95"),
        volume=42,
        currency="USD",
        quote_at=t1,
        fetched_at=t1,
        source="eodhd",
    )

    row = svc.get_quote(db_session, ticker="AAPL")
    assert row is not None
    assert row.last_price == Decimal("200")
    assert row.previous_close == Decimal("100")
    assert row.volume == 42


def test_get_quote_returns_none_when_missing(create_tables, db_session: Session) -> None:
    from openlia_server.services import portfolio_quotes as svc

    assert svc.get_quote(db_session, ticker="ZZZZ") is None


def test_get_quotes_bulk(create_tables, db_session: Session) -> None:
    from openlia_server.services import portfolio_quotes as svc

    now = datetime.now(UTC)
    svc.upsert_quote(
        db_session,
        ticker="AAPL",
        last_price=Decimal("150"),
        previous_close=None,
        day_open=None,
        day_high=None,
        day_low=None,
        volume=None,
        currency="USD",
        quote_at=None,
        fetched_at=now,
        source="eodhd",
    )
    svc.upsert_quote(
        db_session,
        ticker="GOOG",
        last_price=Decimal("2700"),
        previous_close=None,
        day_open=None,
        day_high=None,
        day_low=None,
        volume=None,
        currency="USD",
        quote_at=None,
        fetched_at=now,
        source="eodhd",
    )

    rows = svc.get_quotes_bulk(db_session, tickers=["aapl", "goog", "missing"])
    # Result is keyed by upper-case ticker; missing keys are absent (not None
    # entries) so the caller can distinguish "no row" from "row with null price".
    assert set(rows.keys()) == {"AAPL", "GOOG"}
    assert rows["AAPL"].last_price == Decimal("150")
    assert rows["GOOG"].last_price == Decimal("2700")
