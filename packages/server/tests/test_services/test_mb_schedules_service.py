from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

import pytest
from openlia_server.db.models.auth import User
from openlia_server.db.models.scheduler import MbSchedule
from openlia_server.services import mb_schedules as svc
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


@pytest.mark.asyncio
async def test_list_returns_empty_when_no_schedules(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    assert svc.list_schedules(db_session, user_id="u_1") == []


@pytest.mark.asyncio
async def test_create_inserts_row_and_registers(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    sched = FakeScheduler()
    dto = await svc.create_schedule(
        db_session,
        user_id="u_1",
        time="07:00",
        timezone="America/New_York",
        days_of_week=["mon", "tue", "wed", "thu", "fri"],
        label="Pre-Market",
        scheduler=sched,
    )
    assert dto.time == "07:00"
    assert dto.label == "Pre-Market"
    row = db_session.query(MbSchedule).filter_by(user_id="u_1").one()
    assert row.time == "07:00"
    assert json.loads(row.days_of_week) == ["mon", "tue", "wed", "thu", "fri"]
    assert len(sched.added) == 1
    assert len(sched.modified) == 0


@pytest.mark.asyncio
async def test_create_allows_multiple_schedules_per_user(
    create_tables, db_session: Session
) -> None:
    _mk_user(db_session)
    sched = FakeScheduler()
    a = await svc.create_schedule(
        db_session,
        user_id="u_1",
        time="07:00",
        timezone="America/New_York",
        days_of_week=["mon", "tue", "wed", "thu", "fri"],
        label="Pre-Market",
        scheduler=sched,
    )
    b = await svc.create_schedule(
        db_session,
        user_id="u_1",
        time="16:30",
        timezone="America/New_York",
        days_of_week=["mon", "tue", "wed", "thu", "fri"],
        label="Post-Market",
        scheduler=sched,
    )
    assert a.id != b.id
    rows = db_session.query(MbSchedule).filter_by(user_id="u_1").all()
    assert len(rows) == 2
    assert {r.label for r in rows} == {"Pre-Market", "Post-Market"}
    assert len(sched.added) == 2


@pytest.mark.asyncio
async def test_update_modifies_existing_row(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    sched = FakeScheduler()
    a = await svc.create_schedule(
        db_session,
        user_id="u_1",
        time="07:00",
        timezone="America/New_York",
        days_of_week=["mon"],
        label="a",
        scheduler=sched,
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
    )
    assert updated is not None
    assert updated.time == "08:30"
    assert updated.label == "b"
    rows = db_session.query(MbSchedule).filter_by(user_id="u_1").all()
    assert len(rows) == 1
    assert len(sched.modified) == 1


@pytest.mark.asyncio
async def test_update_returns_none_for_unknown_id(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    sched = FakeScheduler()
    out = await svc.update_schedule(
        db_session,
        user_id="u_1",
        schedule_id="missing",
        time="08:00",
        timezone="America/New_York",
        days_of_week=["mon"],
        label="x",
        scheduler=sched,
    )
    assert out is None
    assert sched.modified == []


@pytest.mark.asyncio
async def test_create_validates_time(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    sched = FakeScheduler()
    with pytest.raises(ValueError, match="time"):
        await svc.create_schedule(
            db_session,
            user_id="u_1",
            time="25:00",
            timezone="America/New_York",
            days_of_week=["mon"],
            label="bad",
            scheduler=sched,
        )


@pytest.mark.asyncio
async def test_create_validates_timezone(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    sched = FakeScheduler()
    with pytest.raises(ValueError, match="timezone"):
        await svc.create_schedule(
            db_session,
            user_id="u_1",
            time="07:00",
            timezone="Not/Real",
            days_of_week=["mon"],
            label="bad",
            scheduler=sched,
        )


@pytest.mark.asyncio
async def test_create_validates_days_of_week(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    sched = FakeScheduler()
    with pytest.raises(ValueError, match="days_of_week"):
        await svc.create_schedule(
            db_session,
            user_id="u_1",
            time="07:00",
            timezone="America/New_York",
            days_of_week=["funday"],
            label="bad",
            scheduler=sched,
        )


@pytest.mark.asyncio
async def test_delete_removes_row_and_unregisters(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    sched = FakeScheduler()
    a = await svc.create_schedule(
        db_session,
        user_id="u_1",
        time="07:00",
        timezone="America/New_York",
        days_of_week=["mon"],
        label="a",
        scheduler=sched,
    )
    deleted = await svc.delete_schedule(
        db_session, user_id="u_1", schedule_id=a.id, scheduler=sched
    )
    assert deleted is True
    assert db_session.query(MbSchedule).count() == 0
    assert sched.removed[-1] == ("mb_briefing", "u_1", a.id)


@pytest.mark.asyncio
async def test_delete_returns_false_when_missing(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    sched = FakeScheduler()
    deleted = await svc.delete_schedule(
        db_session, user_id="u_1", schedule_id="missing", scheduler=sched
    )
    assert deleted is False
    assert sched.removed == []


@pytest.mark.asyncio
async def test_list_is_user_scoped(create_tables, db_session: Session) -> None:
    _mk_user(db_session, "u_1")
    _mk_user(db_session, "u_2")
    sched = FakeScheduler()
    await svc.create_schedule(
        db_session,
        user_id="u_1",
        time="07:00",
        timezone="America/New_York",
        days_of_week=["mon"],
        label="a",
        scheduler=sched,
    )
    assert len(svc.list_schedules(db_session, user_id="u_1")) == 1
    assert svc.list_schedules(db_session, user_id="u_2") == []
