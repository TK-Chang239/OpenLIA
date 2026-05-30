# packages/server/tests/test_services/test_eu_v2_watchlist.py
import pytest
from openlia_server.services.eu_v2_watchlist import (
    AlreadyOnWatchlistError,
    WatchlistEntryNotFoundError,
    add_entry,
    list_entries,
    remove_entry,
)


def test_add_and_list(db_session):
    e = add_entry(db_session, user_id="u-1", ticker="MSFT.US", company_name="Microsoft")
    rows = list_entries(db_session, user_id="u-1")
    assert [r.ticker for r in rows] == ["MSFT.US"]
    assert e.id


def test_add_duplicate_raises(db_session):
    add_entry(db_session, user_id="u-1", ticker="MSFT.US", company_name=None)
    with pytest.raises(AlreadyOnWatchlistError):
        add_entry(db_session, user_id="u-1", ticker="MSFT.US", company_name=None)


def test_remove(db_session):
    e = add_entry(db_session, user_id="u-1", ticker="AAPL.US", company_name=None)
    remove_entry(db_session, user_id="u-1", entry_id=e.id)
    assert list_entries(db_session, user_id="u-1") == []


def test_remove_missing_raises(db_session):
    with pytest.raises(WatchlistEntryNotFoundError):
        remove_entry(db_session, user_id="u-1", entry_id="nope")
