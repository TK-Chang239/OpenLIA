"""Per-user portfolio preferences — refresh cadence (Phase 2),
display currency (Phase 5), etc.

Backed by the row-shaped ``user_prefs`` table; helpers ensure a row
exists for the user before returning/updating.
"""

from __future__ import annotations

from typing import Literal

from sqlalchemy.orm import Session

from openlia_server.db.models.config import UserPrefs

RefreshCadence = Literal["15min", "hourly", "daily", "weekly", "manual"]
_VALID_CADENCES: frozenset[str] = frozenset({"15min", "hourly", "daily", "weekly", "manual"})

# Cadence -> floor seconds. ``manual`` has no floor (returns None) and the
# scheduler excludes those tickers from its union unless some other holder
# picks a polling cadence. ``15min`` matches the intraday */15 cron so every
# fire produces a row for that user's tickers.
_CADENCE_SECONDS: dict[str, int] = {
    "15min": 900,
    "hourly": 3_600,
    "daily": 86_400,
    "weekly": 604_800,
}


class InvalidCadenceError(ValueError):
    pass


def _row(session: Session, user_id: str) -> UserPrefs:
    row = session.get(UserPrefs, user_id)
    if row is None:
        row = UserPrefs(user_id=user_id)
        session.add(row)
        session.flush()
    return row


def get_refresh_cadence(session: Session, *, user_id: str) -> RefreshCadence:
    return _row(session, user_id).portfolio_refresh_cadence  # type: ignore[return-value]


def set_refresh_cadence(session: Session, *, user_id: str, cadence: str) -> RefreshCadence:
    if cadence not in _VALID_CADENCES:
        raise InvalidCadenceError(
            f"cadence must be one of {sorted(_VALID_CADENCES)}; got {cadence!r}"
        )
    row = _row(session, user_id)
    row.portfolio_refresh_cadence = cadence
    session.commit()
    return cadence  # type: ignore[return-value]


def cadence_seconds(cadence: str) -> int | None:
    """Return the floor in seconds for a cadence, or ``None`` for ``manual``."""
    return _CADENCE_SECONDS.get(cadence)


def get_display_currency(session: Session, *, user_id: str) -> str:
    return _row(session, user_id).portfolio_display_currency


def set_display_currency(session: Session, *, user_id: str, currency: str) -> str:
    cleaned = currency.strip().upper()
    if not cleaned or len(cleaned) > 8:
        raise ValueError(f"currency must be 1-8 chars; got {currency!r}")
    row = _row(session, user_id)
    row.portfolio_display_currency = cleaned
    session.commit()
    return cleaned
