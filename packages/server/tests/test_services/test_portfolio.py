"""Portfolio service tests — CRUD + groups + analytics + CSV + reference helper."""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest
from openlia_server.db.models.auth import User
from openlia_server.services import portfolio as svc


@pytest.fixture()
def user(db_session) -> User:
    u = User(
        id="u-portfolio-1",
        email="port@example.com",
        password_hash="x",
        display_name="Port",
        is_admin=False,
        is_disabled=False,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(u)
    db_session.commit()
    return u


def test_create_uppercases_ticker_and_defaults_currency(db_session, user) -> None:
    dto = svc.create_holding(
        db_session,
        user_id=user.id,
        ticker="aapl",
        shares=Decimal("10"),
        cost_basis=Decimal("150"),
        currency=None,
        notes=None,
        groups=None,
    )
    assert dto.ticker == "AAPL"
    assert dto.currency == "USD"
    assert dto.shares == Decimal("10")
    assert dto.groups == []


def test_create_rejects_duplicate(db_session, user) -> None:
    svc.create_holding(
        db_session,
        user_id=user.id,
        ticker="AAPL",
        shares=Decimal("1"),
        cost_basis=None,
        currency="USD",
        notes=None,
        groups=None,
    )
    with pytest.raises(svc.DuplicateTickerError):
        svc.create_holding(
            db_session,
            user_id=user.id,
            ticker="AAPL",
            shares=Decimal("2"),
            cost_basis=None,
            currency="USD",
            notes=None,
            groups=None,
        )


def test_groups_round_trip_through_notes(db_session, user) -> None:
    dto = svc.create_holding(
        db_session,
        user_id=user.id,
        ticker="MSFT",
        shares=Decimal("5"),
        cost_basis=None,
        currency="USD",
        notes="watching",
        groups=["Tech", "Dividends"],
    )
    assert dto.groups == ["Tech", "Dividends"]
    assert dto.notes_text == "watching"
    listed = svc.list_holdings(db_session, user_id=user.id)
    assert listed[0].groups == ["Tech", "Dividends"]


def test_update_patch_semantics(db_session, user) -> None:
    created = svc.create_holding(
        db_session,
        user_id=user.id,
        ticker="NVDA",
        shares=Decimal("5"),
        cost_basis=None,
        currency="USD",
        notes=None,
        groups=["Tech"],
    )
    updated = svc.update_holding(
        db_session,
        user_id=user.id,
        holding_id=created.id,
        shares=Decimal("8"),
        _patch_shares=True,
    )
    assert updated.shares == Decimal("8")
    assert updated.groups == ["Tech"]  # untouched


def test_delete_and_404(db_session, user) -> None:
    created = svc.create_holding(
        db_session,
        user_id=user.id,
        ticker="T",
        shares=None,
        cost_basis=None,
        currency="USD",
        notes=None,
        groups=None,
    )
    svc.delete_holding(db_session, user_id=user.id, holding_id=created.id)
    with pytest.raises(svc.HoldingNotFoundError):
        svc.delete_holding(db_session, user_id=user.id, holding_id=created.id)


def test_reference_holdings_minimal_shape(db_session, user) -> None:
    svc.create_holding(
        db_session,
        user_id=user.id,
        ticker="AAPL",
        shares=Decimal("10"),
        cost_basis=Decimal("150"),
        currency="USD",
        notes=None,
        groups=None,
    )
    ref = svc.get_reference_holdings(db_session, user_id=user.id)
    assert ref == [{"ticker": "AAPL", "name": None, "shares": Decimal("10"), "currency": "USD"}]


def test_analytics_totals_and_weights(db_session, user) -> None:
    svc.create_holding(
        db_session,
        user_id=user.id,
        ticker="AAPL",
        shares=Decimal("10"),
        cost_basis=Decimal("100"),
        currency="USD",
        notes=None,
        groups=None,
    )
    svc.create_holding(
        db_session,
        user_id=user.id,
        ticker="MSFT",
        shares=Decimal("5"),
        cost_basis=Decimal("200"),
        currency="USD",
        notes=None,
        groups=None,
    )
    prices = {"AAPL": Decimal("150"), "MSFT": Decimal("300")}
    summary = svc.compute_analytics(db_session, user_id=user.id, prices=prices)
    # 10*150 + 5*300 = 1500 + 1500 = 3000
    assert summary.total_market_value == Decimal("3000.0000")
    # 10*100 + 5*200 = 1000 + 1000 = 2000
    assert summary.total_cost_basis == Decimal("2000.0000")
    assert summary.total_unrealized_pl == Decimal("1000.0000")
    assert summary.allocations["AAPL"] == Decimal("0.500000")
    assert summary.allocations["MSFT"] == Decimal("0.500000")


def test_analytics_handles_missing_prices(db_session, user) -> None:
    svc.create_holding(
        db_session,
        user_id=user.id,
        ticker="AAPL",
        shares=Decimal("10"),
        cost_basis=Decimal("100"),
        currency="USD",
        notes=None,
        groups=None,
    )
    summary = svc.compute_analytics(db_session, user_id=user.id, prices={"AAPL": None})
    assert summary.total_market_value == Decimal("0.0000")
    assert summary.positions[0].market_value is None


def test_csv_export_and_import(db_session, user) -> None:
    svc.create_holding(
        db_session,
        user_id=user.id,
        ticker="AAPL",
        shares=Decimal("10"),
        cost_basis=Decimal("150"),
        currency="USD",
        notes=None,
        groups=None,
    )
    text = svc.export_csv(db_session, user_id=user.id)
    assert "ticker,shares,cost_basis,currency,notes,added_at" in text
    assert "AAPL" in text
    assert "USD" in text

    # New user imports CSV text
    other = User(
        id="u-portfolio-2",
        email="port2@example.com",
        password_hash="x",
        display_name="P2",
        is_admin=False,
        is_disabled=False,
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    db_session.add(other)
    db_session.commit()
    csv_text = "ticker,shares,cost_basis,currency,notes\nMSFT,3,250,USD,\nAAPL,5,160,USD,\n"
    result = svc.import_csv(db_session, user_id=other.id, text=csv_text)
    assert len(result.created) == 2
    assert result.errors == []


def test_csv_import_reports_duplicates(db_session, user) -> None:
    svc.create_holding(
        db_session,
        user_id=user.id,
        ticker="AAPL",
        shares=Decimal("1"),
        cost_basis=None,
        currency="USD",
        notes=None,
        groups=None,
    )
    csv_text = "ticker,shares,cost_basis,currency,notes\nAAPL,5,160,USD,\n"
    result = svc.import_csv(db_session, user_id=user.id, text=csv_text)
    assert result.created == []
    assert len(result.errors) == 1
    assert result.errors[0]["row"] == "1"
