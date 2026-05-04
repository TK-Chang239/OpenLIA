from openlia_server.db.base import Base
from openlia_server.db.models import register_all  # noqa: F401


def test_skills_tables_registered():
    names = {t.name for t in Base.metadata.tables.values()}
    assert "skills" in names
    assert "skill_user_overrides" in names


def test_guardrail_event_has_payload_json():
    table = Base.metadata.tables["lia_guardrail_events"]
    assert "payload_json" in table.columns


def test_guardrail_event_session_id_nullable():
    table = Base.metadata.tables["lia_guardrail_events"]
    assert table.columns["session_id"].nullable is True
