"""Per-user EU v2 watchlist: add / list / remove ticker entries."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from openlia_server.db.models.report_eu import EuV2WatchlistEntry


class AlreadyOnWatchlistError(ValueError):
    pass


class WatchlistEntryNotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class WatchlistEntryDTO:
    id: str
    ticker: str
    company_name: str | None
    created_at: datetime


def _to_dto(row: EuV2WatchlistEntry) -> WatchlistEntryDTO:
    return WatchlistEntryDTO(
        id=row.id,
        ticker=row.ticker,
        company_name=row.company_name,
        created_at=row.created_at,
    )


def add_entry(
    db: Session,
    *,
    user_id: str,
    ticker: str,
    company_name: str | None,
) -> WatchlistEntryDTO:
    """Add a ticker to the user's watchlist.

    Ticker is normalized to uppercase. Raises ``AlreadyOnWatchlistError``
    when the (user_id, ticker) pair already exists.
    """
    ticker_up = ticker.strip().upper()
    if not ticker_up:
        raise ValueError("ticker required")

    row = EuV2WatchlistEntry(
        id=str(uuid.uuid4()),
        user_id=user_id,
        ticker=ticker_up,
        company_name=company_name,
        created_at=datetime.now(UTC),
    )
    db.add(row)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise AlreadyOnWatchlistError(ticker_up) from None
    return _to_dto(row)


def list_entries(db: Session, *, user_id: str) -> list[WatchlistEntryDTO]:
    """Return the user's watchlist ordered by ticker."""
    rows = (
        db.query(EuV2WatchlistEntry)
        .filter_by(user_id=user_id)
        .order_by(EuV2WatchlistEntry.ticker.asc())
        .all()
    )
    return [_to_dto(r) for r in rows]


def remove_entry(db: Session, *, user_id: str, entry_id: str) -> None:
    """Delete a watchlist entry by id (scoped to user_id).

    Raises ``WatchlistEntryNotFoundError`` when the entry does not exist
    or belongs to a different user.
    """
    row = db.query(EuV2WatchlistEntry).filter_by(id=entry_id, user_id=user_id).one_or_none()
    if row is None:
        raise WatchlistEntryNotFoundError(entry_id)
    db.delete(row)
    db.commit()
