"""CRUD on mb_schedules. Multiple schedules per user (Plan 6 multi-schedule).

Hot-reloads the running SchedulerService via the shipped
`add_schedule` / `modify_schedule` / `remove_schedule` methods. Each row
is keyed in APScheduler by (user_id, schedule_id) so they don't collide.
"""

from __future__ import annotations

import json
import re
import uuid
import zoneinfo
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.orm import Session

from openlia_server.db.models.scheduler import MbSchedule
from openlia_server.scheduler.registry import JobType

_VALID_DAYS = frozenset({"mon", "tue", "wed", "thu", "fri", "sat", "sun"})
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


@dataclass(frozen=True)
class MbScheduleDTO:
    id: str
    user_id: str
    time: str
    timezone: str
    days_of_week: list[str]
    label: str
    is_enabled: bool


class SchedulerControl(Protocol):
    async def add_schedule(self, schedule: MbSchedule) -> None: ...
    async def modify_schedule(self, schedule: MbSchedule) -> None: ...
    async def remove_schedule(
        self, *, job_type: JobType, user_id: str, schedule_id: str | None = None
    ) -> None: ...


def _validate(time: str, timezone: str, days_of_week: list[str]) -> None:
    if not _TIME_RE.match(time):
        raise ValueError(f"invalid time: {time!r}")
    try:
        zoneinfo.ZoneInfo(timezone)
    except Exception as exc:
        raise ValueError(f"invalid timezone: {timezone!r}") from exc
    if not days_of_week or any(d not in _VALID_DAYS for d in days_of_week):
        raise ValueError(f"invalid days_of_week: {days_of_week!r}")


def _to_dto(row: MbSchedule) -> MbScheduleDTO:
    return MbScheduleDTO(
        id=row.id,
        user_id=row.user_id,
        time=row.time,
        timezone=row.timezone,
        days_of_week=list(json.loads(row.days_of_week or "[]")),
        label=row.label or "",
        is_enabled=bool(row.is_enabled),
    )


def list_schedules(db: Session, *, user_id: str) -> list[MbScheduleDTO]:
    rows = (
        db.query(MbSchedule)
        .filter(MbSchedule.user_id == user_id)
        .order_by(MbSchedule.time, MbSchedule.created_at)
        .all()
    )
    return [_to_dto(r) for r in rows]


def get_schedule_by_id(
    db: Session, *, user_id: str, schedule_id: str
) -> MbScheduleDTO | None:
    row = db.query(MbSchedule).filter_by(id=schedule_id, user_id=user_id).one_or_none()
    if row is None:
        return None
    return _to_dto(row)


async def create_schedule(
    db: Session,
    *,
    user_id: str,
    time: str,
    timezone: str,
    days_of_week: list[str],
    label: str,
    scheduler: SchedulerControl,
) -> MbScheduleDTO:
    _validate(time, timezone, days_of_week)
    row = MbSchedule(
        id=str(uuid.uuid4()),
        user_id=user_id,
        time=time,
        timezone=timezone,
        days_of_week=json.dumps(list(days_of_week)),
        label=label,
        is_enabled=True,
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    await scheduler.add_schedule(row)
    return _to_dto(row)


async def update_schedule(
    db: Session,
    *,
    user_id: str,
    schedule_id: str,
    time: str,
    timezone: str,
    days_of_week: list[str],
    label: str,
    scheduler: SchedulerControl,
) -> MbScheduleDTO | None:
    _validate(time, timezone, days_of_week)
    row = db.query(MbSchedule).filter_by(id=schedule_id, user_id=user_id).one_or_none()
    if row is None:
        return None
    row.time = time
    row.timezone = timezone
    row.days_of_week = json.dumps(list(days_of_week))
    row.label = label
    db.commit()
    db.refresh(row)

    await scheduler.modify_schedule(row)
    return _to_dto(row)


async def delete_schedule(
    db: Session,
    *,
    user_id: str,
    schedule_id: str,
    scheduler: SchedulerControl,
) -> bool:
    row = db.query(MbSchedule).filter_by(id=schedule_id, user_id=user_id).one_or_none()
    if row is None:
        return False
    db.delete(row)
    db.commit()
    await scheduler.remove_schedule(
        job_type=JobType.MB_BRIEFING, user_id=user_id, schedule_id=schedule_id
    )
    return True
