# packages/server/tests/test_services/test_eu_v2_calendar_sync.py
from datetime import UTC, datetime

from openlia_server.db.models.report_eu import EuV2EarningsSchedule
from openlia_server.services import eu_v2_watchlist
from openlia_server.services.eu_v2_calendar_sync import (
    sync_all_watchlists,
    sync_user_watchlist,
)


def add_watchlist(db, user_id: str, tickers: list[str]) -> None:
    for ticker in tickers:
        eu_v2_watchlist.add_entry(db, user_id=user_id, ticker=ticker, company_name=None)


def _cal(rows):
    return lambda ticker: rows.get(ticker, [])


def test_sync_inserts_pending_rows(db_session):
    add_watchlist(db_session, "u-1", ["MSFT.US"])
    cal = _cal(
        {
            "MSFT.US": [
                {
                    "report_date": "2026-06-15",
                    "before_after_market": "AfterMarket",
                    "estimate": "2.50",
                }
            ]
        }
    )
    n = sync_user_watchlist(
        db_session,
        user_id="u-1",
        earnings_calendar=cal,
        now=datetime(2026, 6, 1, tzinfo=UTC),
    )
    assert n == 1
    row = db_session.query(EuV2EarningsSchedule).one()
    assert row.ticker == "MSFT.US"
    assert row.fiscal_date == "2026-06-15"
    assert row.status == "pending"
    assert row.release_timing == "post_market"


def test_resync_updates_shifted_date_not_duplicates(db_session):
    add_watchlist(db_session, "u-1", ["MSFT.US"])
    cal1 = _cal({"MSFT.US": [{"report_date": "2026-06-15", "before_after_market": "AfterMarket"}]})
    sync_user_watchlist(
        db_session,
        user_id="u-1",
        earnings_calendar=cal1,
        now=datetime(2026, 6, 1, tzinfo=UTC),
    )
    cal2 = _cal({"MSFT.US": [{"report_date": "2026-06-15", "before_after_market": "AfterMarket"}]})
    # same fiscal_date -> dedup, still one row
    sync_user_watchlist(
        db_session,
        user_id="u-1",
        earnings_calendar=cal2,
        now=datetime(2026, 6, 2, tzinfo=UTC),
    )
    assert db_session.query(EuV2EarningsSchedule).count() == 1


def test_already_reported_row_untouched(db_session):
    add_watchlist(db_session, "u-1", ["MSFT.US"])
    cal = _cal({"MSFT.US": [{"report_date": "2026-06-15", "before_after_market": "BeforeMarket"}]})
    sync_user_watchlist(
        db_session,
        user_id="u-1",
        earnings_calendar=cal,
        now=datetime(2026, 6, 1, tzinfo=UTC),
    )
    row = db_session.query(EuV2EarningsSchedule).one()
    row.status = "reported"
    db_session.commit()
    sync_user_watchlist(
        db_session,
        user_id="u-1",
        earnings_calendar=cal,
        now=datetime(2026, 6, 2, tzinfo=UTC),
    )
    assert db_session.query(EuV2EarningsSchedule).one().status == "reported"


def test_sync_all_watchlists_covers_distinct_users(db_session):
    add_watchlist(db_session, "u-1", ["MSFT.US"])
    add_watchlist(db_session, "u-2", ["AAPL.US"])
    cal = _cal(
        {
            "MSFT.US": [{"report_date": "2026-06-15", "before_after_market": "AfterMarket"}],
            "AAPL.US": [{"report_date": "2026-07-30", "before_after_market": "BeforeMarket"}],
        }
    )
    n = sync_all_watchlists(
        db_session,
        earnings_calendar=cal,
        now=datetime(2026, 6, 1, tzinfo=UTC),
    )
    assert n == 2
    tickers = {r.ticker for r in db_session.query(EuV2EarningsSchedule).all()}
    assert tickers == {"MSFT.US", "AAPL.US"}
