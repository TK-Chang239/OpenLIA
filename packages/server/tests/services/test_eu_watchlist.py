from datetime import date

import pytest
from openlia_server.db.models.auth import User
from openlia_server.db.models.departments import EuWatchlistEntry
from openlia_server.services import eu_watchlist as svc
from sqlalchemy.orm import Session


def _mk_user(db: Session, user_id: str = "u_1") -> User:
    u = User(
        id=user_id, email=f"{user_id}@x", display_name=user_id,
        password_hash="x", is_admin=False,
    )
    db.add(u)
    db.commit()
    return u


class FakeEarningsAdapter:
    def __init__(self, by_ticker: dict[str, dict]) -> None:
        self.by_ticker = by_ticker
        self.calls: list[str] = []

    def next_earnings(self, ticker: str) -> dict | None:
        self.calls.append(ticker)
        return self.by_ticker.get(ticker)


def _apple_blank() -> dict:
    return {
        "ticker": "AAPL", "company_name": "Apple",
        "date": None, "release_timing": None,
    }


def test_add_calls_adapter_and_caches_date(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    adapter = FakeEarningsAdapter({
        "AAPL": {
            "ticker": "AAPL",
            "company_name": "Apple Inc.",
            "date": date(2026, 4, 25),
            "release_timing": "post_market",
        },
    })
    entry = svc.add_entry(db_session, user_id="u_1", ticker="AAPL", adapter=adapter)
    assert entry.ticker == "AAPL"
    assert entry.company_name == "Apple Inc."
    assert entry.next_earnings_date == date(2026, 4, 25)
    assert entry.release_timing == "post_market"
    assert adapter.calls == ["AAPL"]


def test_add_duplicate_raises(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    adapter = FakeEarningsAdapter({"AAPL": _apple_blank()})
    svc.add_entry(db_session, user_id="u_1", ticker="AAPL", adapter=adapter)
    with pytest.raises(svc.AlreadyOnWatchlistError):
        svc.add_entry(db_session, user_id="u_1", ticker="AAPL", adapter=adapter)


def test_add_uppercases_ticker(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    adapter = FakeEarningsAdapter({"AAPL": _apple_blank()})
    entry = svc.add_entry(db_session, user_id="u_1", ticker="aapl", adapter=adapter)
    assert entry.ticker == "AAPL"


def test_add_unknown_ticker_raises(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    adapter = FakeEarningsAdapter({})  # empty
    with pytest.raises(svc.TickerNotFoundError):
        svc.add_entry(db_session, user_id="u_1", ticker="ZZZZ", adapter=adapter)


def test_list_returns_entries_sorted_by_date(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    adapter = FakeEarningsAdapter({
        "AAPL": {
            "ticker": "AAPL", "company_name": "Apple",
            "date": date(2026, 4, 25), "release_timing": "post_market",
        },
        "TSLA": {
            "ticker": "TSLA", "company_name": "Tesla",
            "date": date(2026, 4, 22), "release_timing": "pre_market",
        },
        "NVDA": {
            "ticker": "NVDA", "company_name": "NVIDIA",
            "date": None, "release_timing": None,
        },
    })
    for t in ["AAPL", "TSLA", "NVDA"]:
        svc.add_entry(db_session, user_id="u_1", ticker=t, adapter=adapter)
    entries = svc.list_entries(db_session, user_id="u_1")
    # TSLA (earliest) first, AAPL next, NVDA (NULL) last
    assert [e.ticker for e in entries] == ["TSLA", "AAPL", "NVDA"]


def test_list_is_user_scoped(create_tables, db_session: Session) -> None:
    _mk_user(db_session, "u_1")
    _mk_user(db_session, "u_2")
    adapter = FakeEarningsAdapter({"AAPL": _apple_blank()})
    svc.add_entry(db_session, user_id="u_1", ticker="AAPL", adapter=adapter)
    assert svc.list_entries(db_session, user_id="u_2") == []


def test_remove_deletes_entry(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    adapter = FakeEarningsAdapter({"AAPL": _apple_blank()})
    e = svc.add_entry(db_session, user_id="u_1", ticker="AAPL", adapter=adapter)
    svc.remove_entry(db_session, user_id="u_1", entry_id=e.id)
    assert db_session.query(EuWatchlistEntry).count() == 0


def test_remove_missing_raises(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    with pytest.raises(svc.WatchlistEntryNotFoundError):
        svc.remove_entry(db_session, user_id="u_1", entry_id="nope")


def test_remove_is_user_scoped(create_tables, db_session: Session) -> None:
    _mk_user(db_session, "u_1")
    _mk_user(db_session, "u_2")
    adapter = FakeEarningsAdapter({"AAPL": _apple_blank()})
    e = svc.add_entry(db_session, user_id="u_1", ticker="AAPL", adapter=adapter)
    # u_2 must not be able to delete u_1's row
    with pytest.raises(svc.WatchlistEntryNotFoundError):
        svc.remove_entry(db_session, user_id="u_2", entry_id=e.id)


def test_refresh_updates_stale_dates(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    adapter = FakeEarningsAdapter({
        "AAPL": {
            "ticker": "AAPL", "company_name": "Apple",
            "date": date(2026, 4, 25), "release_timing": "post_market",
        },
    })
    svc.add_entry(db_session, user_id="u_1", ticker="AAPL", adapter=adapter)
    # New quarter date published
    adapter.by_ticker["AAPL"]["date"] = date(2026, 7, 28)
    svc.refresh_for_user(db_session, user_id="u_1", adapter=adapter)
    entry = db_session.query(EuWatchlistEntry).filter_by(user_id="u_1").one()
    assert entry.next_earnings_date == date(2026, 7, 28)
