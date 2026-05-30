"""Weekly earnings calendar sync — upsert logic.

``sync_user_watchlist`` is a pure, testable function: it accepts an injected
``earnings_calendar`` callable so no network calls occur in tests.

Key upsert rules (keyed on user_id + ticker + fiscal_date):
- No existing row → insert with ``status="pending"``.
- Existing row, status ``"pending"`` → update scheduled_run_at, estimates,
  release_timing, synced_at.
- Existing row, status ``"reported"`` or ``"skipped"`` → leave untouched.

Returns the count of pending rows inserted or updated. Empty calendar → 0,
no error.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import Session

from openlia_server.db.models.report_eu import EuV2EarningsSchedule, EuV2WatchlistEntry

EarningsCalendar = Callable[[str], list[dict]]

_UNTOUCHABLE = {"reported", "skipped"}


def compute_run_at(report_date: str, timing: str | None) -> datetime:
    """Return a timezone-aware UTC datetime for when the run should fire.

    - pre_market  → report_date 14:00 UTC (shortly after US market open)
    - post_market → report_date 23:00 UTC (after US market close)
    - None/other  → report_date 23:00 UTC
    """
    d = date.fromisoformat(report_date)
    base = datetime(d.year, d.month, d.day, tzinfo=UTC)
    if timing == "pre_market":
        return base + timedelta(hours=14)
    return base + timedelta(hours=23)


def _map_timing(before_after_market: str | None) -> str | None:
    if before_after_market == "BeforeMarket":
        return "pre_market"
    if before_after_market == "AfterMarket":
        return "post_market"
    return None


def sync_user_watchlist(
    db: Session,
    *,
    user_id: str,
    earnings_calendar: EarningsCalendar,
    now: datetime,
) -> int:
    """Sync the user's watchlist against the earnings calendar.

    Calls ``earnings_calendar(ticker)`` for each watchlist entry, then
    upserts ``EuV2EarningsSchedule`` rows according to the rules above.
    Returns the count of pending rows inserted or updated.
    """
    entries = db.query(EuV2WatchlistEntry).filter_by(user_id=user_id).all()

    touched = 0
    for entry in entries:
        ticker = entry.ticker
        events: list[dict] = earnings_calendar(ticker)

        for event in events:
            report_date: str | None = event.get("report_date")
            if not report_date:
                continue

            timing = _map_timing(event.get("before_after_market"))
            run_at = compute_run_at(report_date, timing)
            eps_estimate: str | None = (
                str(event["estimate"]) if event.get("estimate") is not None else None
            )
            revenue_estimate: str | None = (
                str(event["revenue_estimate_avg"])
                if event.get("revenue_estimate_avg") is not None
                else None
            )

            existing = (
                db.query(EuV2EarningsSchedule)
                .filter_by(user_id=user_id, ticker=ticker, fiscal_date=report_date)
                .one_or_none()
            )

            if existing is None:
                row = EuV2EarningsSchedule(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    ticker=ticker,
                    fiscal_date=report_date,
                    release_timing=timing,
                    eps_estimate=eps_estimate,
                    revenue_estimate=revenue_estimate,
                    scheduled_run_at=run_at,
                    status="pending",
                    attempts=0,
                    report_id=None,
                    synced_at=now,
                    created_at=now,
                )
                db.add(row)
                db.flush()
                touched += 1

            elif existing.status not in _UNTOUCHABLE:
                # status is "pending" — update mutable fields
                existing.scheduled_run_at = run_at
                existing.release_timing = timing
                existing.eps_estimate = eps_estimate
                existing.revenue_estimate = revenue_estimate
                existing.synced_at = now
                db.flush()
                touched += 1

            # status in {"reported", "skipped"} → leave untouched

    db.commit()
    return touched


def sync_all_watchlists(
    db: Session,
    *,
    earnings_calendar: EarningsCalendar,
    now: datetime,
) -> int:
    """Sync every user that has at least one EU v2 watchlist entry.

    Iterates the distinct ``user_id`` values in ``eu_v2_watchlist`` and
    calls ``sync_user_watchlist`` for each, summing the per-user touched
    counts. Returns the total number of pending rows inserted or updated.
    """
    user_ids = [row[0] for row in db.query(EuV2WatchlistEntry.user_id).distinct().all()]

    total = 0
    for user_id in user_ids:
        total += sync_user_watchlist(
            db,
            user_id=user_id,
            earnings_calendar=earnings_calendar,
            now=now,
        )
    return total
