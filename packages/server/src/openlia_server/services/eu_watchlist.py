"""Per-user Earnings Update watchlist: add/remove/list + cache refresh."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import date
from typing import Protocol

from sqlalchemy import nulls_last
from sqlalchemy.orm import Session

from openlia_server.db.models.departments import EuWatchlistEntry


class AlreadyOnWatchlistError(ValueError):
    pass


class TickerNotFoundError(LookupError):
    pass


class WatchlistEntryNotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class WatchlistEntryDTO:
    id: str
    user_id: str
    ticker: str
    company_name: str
    next_earnings_date: date | None
    release_timing: str | None


class EarningsAdapter(Protocol):
    def next_earnings(self, ticker: str) -> dict | None:
        """Return a lookup dict with keys `ticker`, `company_name`, `date`
        (date|None), `release_timing` ('pre_market'|'post_market'|None),
        or None if the ticker isn't known."""
        ...


def _to_dto(row: EuWatchlistEntry) -> WatchlistEntryDTO:
    return WatchlistEntryDTO(
        id=row.id,
        user_id=row.user_id,
        ticker=row.ticker,
        company_name=row.company_name,
        next_earnings_date=row.next_earnings_date,
        release_timing=row.release_timing,
    )


def add_entry(
    db: Session,
    *,
    user_id: str,
    ticker: str,
    adapter: EarningsAdapter,
) -> WatchlistEntryDTO:
    ticker_up = ticker.strip().upper()
    if not ticker_up:
        raise ValueError("ticker required")

    existing = db.query(EuWatchlistEntry).filter_by(user_id=user_id, ticker=ticker_up).one_or_none()
    if existing is not None:
        raise AlreadyOnWatchlistError(ticker_up)

    lookup = adapter.next_earnings(ticker_up)
    if lookup is None:
        raise TickerNotFoundError(ticker_up)

    row = EuWatchlistEntry(
        id=str(uuid.uuid4()),
        user_id=user_id,
        ticker=ticker_up,
        company_name=lookup.get("company_name") or ticker_up,
        next_earnings_date=lookup.get("date"),
        release_timing=lookup.get("release_timing"),
    )
    db.add(row)
    db.commit()
    return _to_dto(row)


def remove_entry(db: Session, *, user_id: str, entry_id: str) -> None:
    row = db.query(EuWatchlistEntry).filter_by(id=entry_id, user_id=user_id).one_or_none()
    if row is None:
        raise WatchlistEntryNotFoundError(entry_id)
    db.delete(row)
    db.commit()


def list_entries(db: Session, *, user_id: str) -> list[WatchlistEntryDTO]:
    rows = (
        db.query(EuWatchlistEntry)
        .filter_by(user_id=user_id)
        .order_by(
            nulls_last(EuWatchlistEntry.next_earnings_date.asc()),
            EuWatchlistEntry.ticker.asc(),
        )
        .all()
    )
    return [_to_dto(r) for r in rows]


def refresh_for_user(
    db: Session,
    *,
    user_id: str,
    adapter: EarningsAdapter,
) -> int:
    """Re-fetch next-earnings dates for all of a user's watchlist entries.

    Called by the nightly maintenance sweep (Plan 6) and by /refresh endpoints.
    Returns the number of rows updated.
    """
    rows = db.query(EuWatchlistEntry).filter_by(user_id=user_id).all()
    updated = 0
    for row in rows:
        lookup = adapter.next_earnings(row.ticker)
        if lookup is None:
            continue
        new_date = lookup.get("date")
        new_timing = lookup.get("release_timing")
        if new_date != row.next_earnings_date or new_timing != row.release_timing:
            row.next_earnings_date = new_date
            row.release_timing = new_timing
            updated += 1
    if updated:
        db.commit()
    return updated
