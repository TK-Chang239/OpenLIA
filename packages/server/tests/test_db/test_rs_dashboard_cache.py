"""ORM-level contract for rs_dashboard_cache."""

from __future__ import annotations

from datetime import UTC, datetime

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
