from openlia_server.db.models.scheduler import MbSchedule


def test_mb_schedule_has_config_binding_columns():
    cols = {c.name for c in MbSchedule.__table__.columns}
    assert {
        "template_id",
        "instructions_id",
        "enabled_connectors",
        "provider_kind",
        "model",
        "language",
        "length",
        "reasoning_effort",
        "web_search",
    } <= cols


def test_mb_schedule_keeps_scheduling_columns():
    cols = {c.name for c in MbSchedule.__table__.columns}
    assert {
        "id",
        "user_id",
        "time",
        "timezone",
        "days_of_week",
        "label",
        "is_enabled",
        "last_run_at",
        "created_at",
    } <= cols
