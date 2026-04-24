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
    removed: list[tuple[str, str]] = field(default_factory=list)

    async def add_schedule(self, schedule):
        self.added.append(schedule)

    async def modify_schedule(self, schedule):
        self.modified.append(schedule)

    async def remove_schedule(self, *, job_type, user_id):
        self.removed.append((job_type.value, user_id))


@pytest.mark.asyncio
async def test_get_returns_none_when_no_schedule(
    create_tables, db_session: Session
) -> None:
    _mk_user(db_session)
    dto = svc.get_schedule(db_session, user_id="u_1")
    assert dto is None


@pytest.mark.asyncio
async def test_upsert_creates_row_and_registers(
    create_tables, db_session: Session
) -> None:
    _mk_user(db_session)
    sched = FakeScheduler()
    dto = await svc.upsert_schedule(
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
async def test_upsert_modifies_existing_row(
    create_tables, db_session: Session
) -> None:
    _mk_user(db_session)
    sched = FakeScheduler()
    await svc.upsert_schedule(
        db_session,
        user_id="u_1",
        time="07:00",
        timezone="America/New_York",
        days_of_week=["mon"],
        label="a",
        scheduler=sched,
    )
    await svc.upsert_schedule(
        db_session,
        user_id="u_1",
        time="08:00",
        timezone="America/New_York",
        days_of_week=["mon", "tue"],
        label="b",
        scheduler=sched,
    )
    rows = db_session.query(MbSchedule).filter_by(user_id="u_1").all()
    assert len(rows) == 1
    assert rows[0].time == "08:00"
    assert rows[0].label == "b"
    assert len(sched.added) == 1
    assert len(sched.modified) == 1


@pytest.mark.asyncio
async def test_upsert_validates_time(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    sched = FakeScheduler()
    with pytest.raises(ValueError, match="time"):
        await svc.upsert_schedule(
            db_session,
            user_id="u_1",
            time="25:00",
            timezone="America/New_York",
            days_of_week=["mon"],
            label="bad",
            scheduler=sched,
        )


@pytest.mark.asyncio
async def test_upsert_validates_timezone(
    create_tables, db_session: Session
) -> None:
    _mk_user(db_session)
    sched = FakeScheduler()
    with pytest.raises(ValueError, match="timezone"):
        await svc.upsert_schedule(
            db_session,
            user_id="u_1",
            time="07:00",
            timezone="Not/Real",
            days_of_week=["mon"],
            label="bad",
            scheduler=sched,
        )


@pytest.mark.asyncio
async def test_upsert_validates_days_of_week(
    create_tables, db_session: Session
) -> None:
    _mk_user(db_session)
    sched = FakeScheduler()
    with pytest.raises(ValueError, match="days_of_week"):
        await svc.upsert_schedule(
            db_session,
            user_id="u_1",
            time="07:00",
            timezone="America/New_York",
            days_of_week=["funday"],
            label="bad",
            scheduler=sched,
        )


@pytest.mark.asyncio
async def test_delete_removes_row_and_unregisters(
    create_tables, db_session: Session
) -> None:
    _mk_user(db_session)
    sched = FakeScheduler()
    await svc.upsert_schedule(
        db_session,
        user_id="u_1",
        time="07:00",
        timezone="America/New_York",
        days_of_week=["mon"],
        label="a",
        scheduler=sched,
    )
    await svc.delete_schedule(db_session, user_id="u_1", scheduler=sched)
    assert db_session.query(MbSchedule).count() == 0
    assert sched.removed[-1][1] == "u_1"


@pytest.mark.asyncio
async def test_delete_is_noop_when_missing(
    create_tables, db_session: Session
) -> None:
    _mk_user(db_session)
    sched = FakeScheduler()
    await svc.delete_schedule(db_session, user_id="u_1", scheduler=sched)
    assert sched.removed == []


@pytest.mark.asyncio
async def test_get_is_user_scoped(create_tables, db_session: Session) -> None:
    _mk_user(db_session, "u_1")
    _mk_user(db_session, "u_2")
    sched = FakeScheduler()
    await svc.upsert_schedule(
        db_session,
        user_id="u_1",
        time="07:00",
        timezone="America/New_York",
        days_of_week=["mon"],
        label="a",
        scheduler=sched,
    )
    assert svc.get_schedule(db_session, user_id="u_1") is not None
    assert svc.get_schedule(db_session, user_id="u_2") is None
