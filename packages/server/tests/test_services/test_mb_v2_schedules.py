"""Tests for the MB v2 schedule service (CRUD + config binding + hot-reload).

Forked from ``test_mb_schedules_service.py``. The v2 schedule binds a full
per-schedule config (template / instructions / connectors / model / language /
length / reasoning_effort / web_search). The fake ``SchedulerControl`` records
add/modify/remove calls; the DB assertions confirm the binding columns persist.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

import pytest
from openlia.llm.runtime.report_mb.default_template import build_default_template
from openlia_server.db.models.auth import User
from openlia_server.db.models.report_mb import ReportMbTemplate
from openlia_server.db.models.scheduler import MbSchedule
from openlia_server.services import mb_v2_schedules as svc
from sqlalchemy.orm import Session


def _mk_user(db: Session, user_id: str = "u_1") -> User:
    u = User(
        id=user_id,
        email=f"{user_id}@x",
        display_name=user_id,
        password_hash="x",
        is_admin=False,
    )
    db.add(u)
    db.commit()
    return u


def _seed_mb_default(db: Session) -> None:
    spec = build_default_template()
    now = datetime.now(UTC)
    db.add(
        ReportMbTemplate(
            id=spec.template_id,
            user_id=None,
            name=spec.name,
            is_builtin=True,
            template_spec_json=json.loads(spec.model_dump_json()),
            source_markdown=None,
            source_doc_blob=None,
            source_doc_mime=None,
            created_at=now,
            updated_at=now,
            deleted_at=None,
        )
    )
    db.commit()


@dataclass
class FakeScheduler:
    added: list[Any] = field(default_factory=list)
    modified: list[Any] = field(default_factory=list)
    removed: list[tuple[str, str, str | None]] = field(default_factory=list)

    async def add_schedule(self, schedule):
        self.added.append(schedule)

    async def modify_schedule(self, schedule):
        self.modified.append(schedule)

    async def remove_schedule(self, *, job_type, user_id, schedule_id=None):
        self.removed.append((job_type.value, user_id, schedule_id))


def _full_binding() -> dict[str, Any]:
    return dict(
        template_id="mb_default",
        instructions_id=None,
        enabled_connectors={"provider_ids": ["eodhd"], "web_search": True},
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        language="en",
        length="normal",
        reasoning_effort="high",
        web_search=True,
    )


@pytest.mark.asyncio
async def test_create_persists_full_binding_and_registers(
    create_tables, db_session: Session
) -> None:
    _mk_user(db_session)
    _seed_mb_default(db_session)
    sched = FakeScheduler()
    dto = await svc.create_schedule(
        db_session,
        user_id="u_1",
        time="07:00",
        timezone="America/New_York",
        days_of_week=["mon", "tue", "wed", "thu", "fri"],
        label="Pre-Market",
        scheduler=sched,
        **_full_binding(),
    )
    assert dto.template_id == "mb_default"
    assert dto.enabled_connectors == {"provider_ids": ["eodhd"], "web_search": True}
    assert dto.provider_kind == "anthropic"
    assert dto.model == "claude-sonnet-4-6"
    assert dto.language == "en"
    assert dto.length == "normal"
    assert dto.reasoning_effort == "high"
    assert dto.web_search is True

    row = db_session.query(MbSchedule).filter_by(user_id="u_1").one()
    assert row.template_id == "mb_default"
    assert row.enabled_connectors == {"provider_ids": ["eodhd"], "web_search": True}
    assert row.provider_kind == "anthropic"
    assert row.model == "claude-sonnet-4-6"
    assert row.reasoning_effort == "high"
    assert row.web_search is True
    assert len(sched.added) == 1
    assert len(sched.modified) == 0


@pytest.mark.asyncio
async def test_create_allows_freeform_template_id(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    sched = FakeScheduler()
    binding = _full_binding()
    binding["template_id"] = "freeform"
    binding["instructions_id"] = None
    dto = await svc.create_schedule(
        db_session,
        user_id="u_1",
        time="07:00",
        timezone="America/New_York",
        days_of_week=["mon"],
        label="Freeform",
        scheduler=sched,
        **binding,
    )
    assert dto.template_id == "freeform"


@pytest.mark.asyncio
async def test_update_rebinds_and_registers(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    _seed_mb_default(db_session)
    sched = FakeScheduler()
    a = await svc.create_schedule(
        db_session,
        user_id="u_1",
        time="07:00",
        timezone="America/New_York",
        days_of_week=["mon"],
        label="a",
        scheduler=sched,
        **_full_binding(),
    )
    updated = await svc.update_schedule(
        db_session,
        user_id="u_1",
        schedule_id=a.id,
        time="08:30",
        timezone="America/New_York",
        days_of_week=["mon", "tue"],
        label="b",
        scheduler=sched,
        template_id="mb_default",
        instructions_id=None,
        enabled_connectors={"provider_ids": [], "web_search": False},
        provider_kind="openai",
        model="gpt-5",
        language="zh-Hant",
        length="concise",
        reasoning_effort=None,
        web_search=False,
    )
    assert updated is not None
    assert updated.time == "08:30"
    assert updated.provider_kind == "openai"
    assert updated.model == "gpt-5"
    assert updated.language == "zh-Hant"
    assert updated.length == "concise"
    assert updated.reasoning_effort is None
    assert updated.web_search is False
    assert updated.enabled_connectors == {"provider_ids": [], "web_search": False}

    row = db_session.query(MbSchedule).filter_by(id=a.id).one()
    assert row.provider_kind == "openai"
    assert row.model == "gpt-5"
    assert len(sched.modified) == 1


@pytest.mark.asyncio
async def test_list_returns_binding_fields(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    _seed_mb_default(db_session)
    sched = FakeScheduler()
    await svc.create_schedule(
        db_session,
        user_id="u_1",
        time="07:00",
        timezone="America/New_York",
        days_of_week=["mon"],
        label="a",
        scheduler=sched,
        **_full_binding(),
    )
    dtos = svc.list_schedules(db_session, user_id="u_1")
    assert len(dtos) == 1
    dto = dtos[0]
    assert dto.template_id == "mb_default"
    assert dto.enabled_connectors == {"provider_ids": ["eodhd"], "web_search": True}
    assert dto.provider_kind == "anthropic"
    assert dto.model == "claude-sonnet-4-6"
    assert dto.web_search is True


@pytest.mark.asyncio
async def test_delete_removes_row_and_unregisters(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    _seed_mb_default(db_session)
    sched = FakeScheduler()
    a = await svc.create_schedule(
        db_session,
        user_id="u_1",
        time="07:00",
        timezone="America/New_York",
        days_of_week=["mon"],
        label="a",
        scheduler=sched,
        **_full_binding(),
    )
    deleted = await svc.delete_schedule(
        db_session, user_id="u_1", schedule_id=a.id, scheduler=sched
    )
    assert deleted is True
    assert db_session.query(MbSchedule).count() == 0
    assert sched.removed[-1] == ("mb_briefing", "u_1", a.id)


@pytest.mark.asyncio
async def test_create_rejects_unknown_template_id(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    sched = FakeScheduler()
    binding = _full_binding()
    binding["template_id"] = "no-such-template"
    with pytest.raises(ValueError, match="template"):
        await svc.create_schedule(
            db_session,
            user_id="u_1",
            time="07:00",
            timezone="America/New_York",
            days_of_week=["mon"],
            label="bad",
            scheduler=sched,
            **binding,
        )
    assert sched.added == []


@pytest.mark.asyncio
async def test_create_rejects_unknown_instructions_id(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    _seed_mb_default(db_session)
    sched = FakeScheduler()
    binding = _full_binding()
    binding["instructions_id"] = "no-such-instructions"
    with pytest.raises(ValueError, match="instructions"):
        await svc.create_schedule(
            db_session,
            user_id="u_1",
            time="07:00",
            timezone="America/New_York",
            days_of_week=["mon"],
            label="bad",
            scheduler=sched,
            **binding,
        )
    assert sched.added == []


@pytest.mark.asyncio
async def test_create_rejects_malformed_connectors_shape(
    create_tables, db_session: Session
) -> None:
    _mk_user(db_session)
    _seed_mb_default(db_session)
    sched = FakeScheduler()
    binding = _full_binding()
    binding["enabled_connectors"] = {"provider_ids": "eodhd"}  # not a list
    with pytest.raises(ValueError, match="enabled_connectors"):
        await svc.create_schedule(
            db_session,
            user_id="u_1",
            time="07:00",
            timezone="America/New_York",
            days_of_week=["mon"],
            label="bad",
            scheduler=sched,
            **binding,
        )
    assert sched.added == []


@pytest.mark.asyncio
async def test_create_still_validates_time(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    _seed_mb_default(db_session)
    sched = FakeScheduler()
    binding = _full_binding()
    with pytest.raises(ValueError, match="time"):
        await svc.create_schedule(
            db_session,
            user_id="u_1",
            time="25:00",
            timezone="America/New_York",
            days_of_week=["mon"],
            label="bad",
            scheduler=sched,
            **binding,
        )
