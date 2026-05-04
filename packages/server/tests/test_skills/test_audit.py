import pytest
from openlia_server.db.models.safety import LiaGuardrailEvent
from openlia_server.services.skill_audit import (
    record_skill_installed,
    record_skill_loaded,
)
from sqlalchemy import select


@pytest.mark.asyncio
async def test_record_install_writes_event(db_session_factory):
    record_skill_installed(
        db_session_factory,
        skill_id="alpha",
        scope="user",
        user_id="u1",
        source="folder",
        version="1.0.0",
    )
    with db_session_factory() as db:
        rows = db.execute(select(LiaGuardrailEvent)).scalars().all()
        assert len(rows) == 1
        assert rows[0].event_type == "skill_installed"
        assert rows[0].payload_json["skill_id"] == "alpha"


@pytest.mark.asyncio
async def test_record_load_writes_event(db_session_factory):
    record_skill_loaded(
        db_session_factory,
        skill_id="alpha",
        session_id="s1",
        user_id="u1",
        department_id="secretary",
    )
    with db_session_factory() as db:
        rows = db.execute(select(LiaGuardrailEvent)).scalars().all()
        assert rows[0].event_type == "skill_loaded"
        assert rows[0].session_id == "s1"
        assert rows[0].department_id == "secretary"
