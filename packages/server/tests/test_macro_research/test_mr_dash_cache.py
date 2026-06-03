from datetime import UTC, datetime

from openlia_server.db.models.dashboard import MrDashboardCache


def test_cache_row_roundtrip(db_session, make_user):
    user = make_user()
    row = MrDashboardCache(
        user_id=user.id,
        dashboard="debt_cycle",
        payload_json='{"phaseBox": {"title": "Late plateau"}}',
        provenance="live",
        model_ref="claude-sonnet-4-6",
        generated_at=datetime.now(UTC),
    )
    db_session.add(row)
    db_session.flush()
    fetched = (
        db_session.query(MrDashboardCache).filter_by(user_id=user.id, dashboard="debt_cycle").one()
    )
    assert "Late plateau" in fetched.payload_json
