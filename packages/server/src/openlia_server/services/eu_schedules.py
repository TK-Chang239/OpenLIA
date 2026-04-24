"""CRUD on eu_schedules with hot-reload into the running SchedulerService."""

from __future__ import annotations

import json
import re
import uuid
import zoneinfo
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.orm import Session

from openlia_server.db.models.scheduler import EuSchedule
from openlia_server.scheduler.registry import JobType

_VALID_DAYS = frozenset({"mon", "tue", "wed", "thu", "fri", "sat", "sun"})
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")


class ScheduleNotFoundError(LookupError):
    pass


@dataclass(frozen=True)
class EuScheduleDTO:
    id: str
    user_id: str
    time: str
    timezone: str
    days_of_week: list[str]
    label: str
    is_enabled: bool


class SchedulerControl(Protocol):
    def add_schedule(self, *, job_type, user_id: str, schedule_id: str,
                     time: str, timezone: str, days_of_week: list[str]) -> None: ...
    def remove_schedule(self, *, job_type, user_id: str, schedule_id: str) -> None: ...


def _validate(time: str, timezone: str, days_of_week: list[str]) -> None:
    if not _TIME_RE.match(time):
        raise ValueError(f"invalid time: {time!r}")
    try:
        zoneinfo.ZoneInfo(timezone)
    except Exception as e:
        raise ValueError(f"invalid timezone: {timezone!r}") from e
    if not days_of_week or any(d not in _VALID_DAYS for d in days_of_week):
        raise ValueError(f"invalid days_of_week: {days_of_week!r}")


def _decode_days(raw: str | list | None) -> list[str]:
    if raw is None:
        return []
    if isinstance(raw, list):
        return list(raw)
    try:
        value = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return list(value) if isinstance(value, list) else []


def _to_dto(row: EuSchedule) -> EuScheduleDTO:
    return EuScheduleDTO(
        id=row.id, user_id=row.user_id, time=row.time,
        timezone=row.timezone, days_of_week=_decode_days(row.days_of_week),
        label=row.label or "", is_enabled=bool(row.is_enabled),
    )


def create_schedule(
    db: Session, *, user_id: str, time: str, timezone: str,
    days_of_week: list[str], label: str, scheduler: SchedulerControl,
) -> EuScheduleDTO:
    _validate(time, timezone, days_of_week)
    row = EuSchedule(
        id=f"eus_{uuid.uuid4().hex[:12]}",
        user_id=user_id, time=time, timezone=timezone,
        days_of_week=json.dumps(list(days_of_week)), label=label, is_enabled=True,
    )
    db.add(row)
    db.commit()
    scheduler.add_schedule(
        job_type=JobType.EU_SCAN, user_id=user_id, schedule_id=row.id,
        time=time, timezone=timezone, days_of_week=list(days_of_week),
    )
    return _to_dto(row)


def list_schedules(db: Session, *, user_id: str) -> list[EuScheduleDTO]:
    rows = db.query(EuSchedule).filter_by(user_id=user_id).order_by(EuSchedule.time).all()
    return [_to_dto(r) for r in rows]


def update_schedule(
    db: Session, *, user_id: str, schedule_id: str,
    time: str, timezone: str, days_of_week: list[str],
    label: str, is_enabled: bool, scheduler: SchedulerControl,
) -> EuScheduleDTO:
    _validate(time, timezone, days_of_week)
    row = (
        db.query(EuSchedule).filter_by(id=schedule_id, user_id=user_id).one_or_none()
    )
    if row is None:
        raise ScheduleNotFoundError(schedule_id)
    row.time = time
    row.timezone = timezone
    row.days_of_week = json.dumps(list(days_of_week))
    row.label = label
    row.is_enabled = is_enabled
    db.commit()
    scheduler.remove_schedule(
        job_type=JobType.EU_SCAN, user_id=user_id, schedule_id=schedule_id,
    )
    if is_enabled:
        scheduler.add_schedule(
            job_type=JobType.EU_SCAN, user_id=user_id, schedule_id=schedule_id,
            time=time, timezone=timezone, days_of_week=list(days_of_week),
        )
    return _to_dto(row)


def delete_schedule(
    db: Session, *, user_id: str, schedule_id: str, scheduler: SchedulerControl,
) -> None:
    row = (
        db.query(EuSchedule).filter_by(id=schedule_id, user_id=user_id).one_or_none()
    )
    if row is None:
        raise ScheduleNotFoundError(schedule_id)
    db.delete(row)
    db.commit()
    scheduler.remove_schedule(
        job_type=JobType.EU_SCAN, user_id=user_id, schedule_id=schedule_id,
    )
