from dataclasses import dataclass, field

import pytest
from sqlalchemy.orm import Session

from openlia_server.db.models.auth import User
from openlia_server.db.models.scheduler import EuSchedule
from openlia_server.scheduler.registry import JobType
from openlia_server.services import eu_schedules as svc


def _mk_user(db: Session, user_id: str = "u_1") -> User:
    u = User(id=user_id, email=f"{user_id}@x", display_name=user_id, password_hash="x", is_admin=False)
    db.add(u)
    db.commit()
    return u


@dataclass
class FakeScheduler:
    added: list[dict] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)

    def add_schedule(self, *, job_type, user_id, schedule_id, time, timezone, days_of_week):
        self.added.append({
            "job_type": job_type,
            "user_id": user_id,
            "schedule_id": schedule_id,
            "time": time,
            "timezone": timezone,
            "days_of_week": list(days_of_week),
        })

    def remove_schedule(self, *, job_type, user_id, schedule_id):
        self.removed.append(f"{job_type.value}:{user_id}:{schedule_id}")


def test_create_inserts_row_and_schedules_job(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    sched = FakeScheduler()
    dto = svc.create_schedule(
        db_session,
        user_id="u_1",
        time="06:00",
        timezone="America/New_York",
        days_of_week=["mon", "tue", "wed", "thu", "fri"],
        label="Pre-Market Scan",
        scheduler=sched,
    )
    assert dto.time == "06:00"
    assert dto.timezone == "America/New_York"
    assert sched.added[0]["job_type"] == JobType.EU_SCAN
    assert sched.added[0]["user_id"] == "u_1"


def test_create_validates_time_format(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    sched = FakeScheduler()
    with pytest.raises(ValueError, match="time"):
        svc.create_schedule(
            db_session,
            user_id="u_1",
            time="25:00",
            timezone="America/New_York",
            days_of_week=["mon"],
            label="bad",
            scheduler=sched,
        )


def test_create_validates_days_of_week(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    sched = FakeScheduler()
    with pytest.raises(ValueError, match="days_of_week"):
        svc.create_schedule(
            db_session,
            user_id="u_1",
            time="06:00",
            timezone="America/New_York",
            days_of_week=["smthweird"],
            label="bad",
            scheduler=sched,
        )


def test_create_validates_timezone(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    sched = FakeScheduler()
    with pytest.raises(ValueError, match="timezone"):
        svc.create_schedule(
            db_session,
            user_id="u_1",
            time="06:00",
            timezone="Not/AReal/Zone",
            days_of_week=["mon"],
            label="bad",
            scheduler=sched,
        )


def test_list_returns_user_schedules(create_tables, db_session: Session) -> None:
    _mk_user(db_session, "u_1")
    _mk_user(db_session, "u_2")
    sched = FakeScheduler()
    svc.create_schedule(db_session, user_id="u_1", time="06:00", timezone="America/New_York",
                        days_of_week=["mon"], label="a", scheduler=sched)
    svc.create_schedule(db_session, user_id="u_1", time="17:00", timezone="America/New_York",
                        days_of_week=["mon"], label="b", scheduler=sched)
    svc.create_schedule(db_session, user_id="u_2", time="09:00", timezone="America/New_York",
                        days_of_week=["mon"], label="c", scheduler=sched)
    u1 = svc.list_schedules(db_session, user_id="u_1")
    assert {s.label for s in u1} == {"a", "b"}


def test_update_modifies_row_and_reschedules(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    sched = FakeScheduler()
    dto = svc.create_schedule(db_session, user_id="u_1", time="06:00",
                              timezone="America/New_York", days_of_week=["mon"],
                              label="a", scheduler=sched)
    svc.update_schedule(
        db_session, user_id="u_1", schedule_id=dto.id,
        time="07:00", timezone="America/New_York",
        days_of_week=["mon", "tue"], label="a2",
        is_enabled=True, scheduler=sched,
    )
    row = db_session.query(EuSchedule).filter_by(id=dto.id).one()
    assert row.time == "07:00"
    assert row.label == "a2"
    # remove + re-add through scheduler
    assert sched.removed[-1].endswith(dto.id)
    assert sched.added[-1]["schedule_id"] == dto.id
    assert sched.added[-1]["time"] == "07:00"


def test_update_is_user_scoped(create_tables, db_session: Session) -> None:
    _mk_user(db_session, "u_1")
    _mk_user(db_session, "u_2")
    sched = FakeScheduler()
    dto = svc.create_schedule(db_session, user_id="u_1", time="06:00",
                              timezone="America/New_York", days_of_week=["mon"],
                              label="a", scheduler=sched)
    with pytest.raises(svc.ScheduleNotFoundError):
        svc.update_schedule(db_session, user_id="u_2", schedule_id=dto.id,
                            time="07:00", timezone="America/New_York",
                            days_of_week=["mon"], label="x",
                            is_enabled=True, scheduler=sched)


def test_delete_removes_row_and_unschedules(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    sched = FakeScheduler()
    dto = svc.create_schedule(db_session, user_id="u_1", time="06:00",
                              timezone="America/New_York", days_of_week=["mon"],
                              label="a", scheduler=sched)
    svc.delete_schedule(db_session, user_id="u_1", schedule_id=dto.id, scheduler=sched)
    assert db_session.query(EuSchedule).count() == 0
    assert sched.removed[-1].endswith(dto.id)
