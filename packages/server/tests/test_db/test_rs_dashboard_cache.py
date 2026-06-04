"""ORM-level contract for rs_dashboard_cache."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from openlia_server.db.models.dashboard import RsDashboardCache
from sqlalchemy.orm import Session


def test_rs_dashboard_cache_roundtrip(create_tables, db_session: Session, make_user) -> None:
    user = make_user(email="rstest@example.com")
    row = RsDashboardCache(
        user_id=user.id,
        ticker="AAPL",
        payload_json="{}",
        provenance="live",
        model_ref="m",
        generated_at=datetime.now(UTC),
    )
    db_session.add(row)
    db_session.commit()
    got = db_session.query(RsDashboardCache).filter_by(user_id=user.id, ticker="AAPL").one()
    assert got.payload_json == "{}"


def test_rs_dashboard_cache_allows_multiple_rows_same_user_ticker(
    create_tables, db_session: Session, make_user
) -> None:
    """No unique constraint on (user_id, ticker) — two runs produce two rows."""
    user = make_user(email="rstest2@example.com")
    now = datetime.now(UTC)
    db_session.add(
        RsDashboardCache(
            user_id=user.id,
            ticker="MSFT",
            payload_json='{"sentiment_score": 0.3}',
            provenance="live",
            model_ref="m",
            generated_at=now - timedelta(hours=1),
        )
    )
    db_session.add(
        RsDashboardCache(
            user_id=user.id,
            ticker="MSFT",
            payload_json='{"sentiment_score": 0.6}',
            provenance="live",
            model_ref="m",
            generated_at=now,
        )
    )
    db_session.commit()

    rows = (
        db_session.query(RsDashboardCache)
        .filter_by(user_id=user.id, ticker="MSFT")
        .order_by(RsDashboardCache.generated_at.desc())
        .all()
    )
    assert len(rows) == 2
    import json

    assert json.loads(rows[0].payload_json)["sentiment_score"] == 0.6
