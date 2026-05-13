"""Phase 2: scheduler_union — per-ticker min cadence across polling users.

Floor semantics:
  - A ticker held by user A (hourly) and user B (weekly) → min cadence = 1h.
  - A ticker held by user A (manual) only → excluded from the polling union
    (manual users free-ride on others' fetches; if no one else holds it, the
    only way to fetch is the user's manual refresh button).
"""

from __future__ import annotations

from sqlalchemy.orm import Session


def _seed_user(db_session, uid: str, cadence: str) -> None:
    from openlia_server.db.models.auth import User
    from openlia_server.db.models.config import UserPrefs

    if db_session.get(User, uid) is None:
        db_session.add(
            User(
                id=uid,
                email=f"{uid}@example.com",
                display_name=uid,
                password_hash=None,
                is_admin=False,
                is_disabled=False,
            )
        )
    db_session.add(UserPrefs(user_id=uid, portfolio_refresh_cadence=cadence))
    db_session.commit()


def _add_holding(db_session, uid: str, ticker: str) -> None:
    from openlia_server.db.models.content import PortfolioHolding

    db_session.add(PortfolioHolding(id=f"h-{uid}-{ticker}", user_id=uid, ticker=ticker))
    db_session.commit()


def test_single_user_hourly_holds_one_ticker(create_tables, db_session: Session) -> None:
    from openlia_server.services.portfolio_quote_refresh import scheduler_union

    _seed_user(db_session, "u1", "hourly")
    _add_holding(db_session, "u1", "AAPL")

    union = scheduler_union(db_session)
    assert union == [("AAPL", 3600)]


def test_floor_takes_minimum_cadence_across_holders(create_tables, db_session: Session) -> None:
    from openlia_server.services.portfolio_quote_refresh import scheduler_union

    _seed_user(db_session, "u1", "weekly")
    _seed_user(db_session, "u2", "hourly")
    _add_holding(db_session, "u1", "AAPL")
    _add_holding(db_session, "u2", "AAPL")

    union = scheduler_union(db_session)
    assert union == [("AAPL", 3600)]


def test_manual_only_ticker_excluded(create_tables, db_session: Session) -> None:
    from openlia_server.services.portfolio_quote_refresh import scheduler_union

    _seed_user(db_session, "u1", "manual")
    _add_holding(db_session, "u1", "AAPL")

    union = scheduler_union(db_session)
    assert union == []


def test_manual_user_free_rides_on_polling_user(create_tables, db_session: Session) -> None:
    from openlia_server.services.portfolio_quote_refresh import scheduler_union

    _seed_user(db_session, "u1", "manual")
    _seed_user(db_session, "u2", "daily")
    _add_holding(db_session, "u1", "AAPL")
    _add_holding(db_session, "u2", "AAPL")

    union = scheduler_union(db_session)
    assert union == [("AAPL", 86_400)]


def test_skips_groups_meta_pseudo_holding(create_tables, db_session: Session) -> None:
    from openlia_server.db.models.content import PortfolioHolding
    from openlia_server.services.portfolio_quote_refresh import scheduler_union

    _seed_user(db_session, "u1", "hourly")
    db_session.add(PortfolioHolding(id="meta-1", user_id="u1", ticker="__GROUPS__"))
    db_session.commit()

    assert scheduler_union(db_session) == []
