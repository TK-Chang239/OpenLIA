"""CRUD on mb_schedules. One schedule per user (Plan 6 job_key lock).

Hot-reloads the running SchedulerService via the shipped
`add_schedule` / `modify_schedule` / `remove_schedule` methods.
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
    async def remove_schedule(self, *, job_type: JobType, user_id: str) -> None: ...


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


def get_schedule(db: Session, *, user_id: str) -> MbScheduleDTO | None:
    row = db.query(MbSchedule).filter_by(user_id=user_id).one_or_none()
    if row is None:
        return None
    return _to_dto(row)


async def upsert_schedule(
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
    row = db.query(MbSchedule).filter_by(user_id=user_id).one_or_none()
    is_new = row is None
    if row is None:
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
    else:
        row.time = time
        row.timezone = timezone
        row.days_of_week = json.dumps(list(days_of_week))
        row.label = label
        row.is_enabled = True
    db.commit()
    db.refresh(row)

    if is_new:
        await scheduler.add_schedule(row)
    else:
        await scheduler.modify_schedule(row)

    return _to_dto(row)


async def delete_schedule(
    db: Session,
    *,
    user_id: str,
    scheduler: SchedulerControl,
) -> None:
    row = db.query(MbSchedule).filter_by(user_id=user_id).one_or_none()
    if row is None:
        return
    db.delete(row)
    db.commit()
    await scheduler.remove_schedule(job_type=JobType.MB_BRIEFING, user_id=user_id)
