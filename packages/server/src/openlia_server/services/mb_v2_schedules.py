"""CRUD on mb_schedules with per-schedule config binding (MB rework Phase 3).

Forked from ``mb_schedules.py``. Each row now binds a full per-schedule run
config (template / instructions / connectors / model / language / length /
reasoning_effort / web_search) so a user can run, e.g., a US-markets briefing
at 07:00 and an Asia briefing at 18:00 with different shapes. The firing
dispatcher (``scheduler/executors/mb.py``) reads these columns and feeds them
straight into ``mb_v2_run_service.build_run_request``.

Hot-reloads the running SchedulerService via the shipped
``add_schedule`` / ``modify_schedule`` / ``remove_schedule`` methods. Each row
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
from openlia_server.services import mb_v2_instructions_service, mb_v2_template_service

_VALID_DAYS = frozenset({"mon", "tue", "wed", "thu", "fri", "sat", "sun"})
_TIME_RE = re.compile(r"^([01]\d|2[0-3]):[0-5]\d$")

# Sentinel template id for a "No template (instructions only)" schedule. Like
# the run service, it is a valid template_id that resolves to a freeform spec
# at run time rather than a DB row, so it skips the resolve-template check.
_FREEFORM_TEMPLATE_ID = "freeform"


@dataclass(frozen=True)
class MbScheduleDTO:
    id: str
    user_id: str
    time: str
    timezone: str
    days_of_week: list[str]
    label: str
    is_enabled: bool
    template_id: str | None
    instructions_id: str | None
    enabled_connectors: dict
    provider_kind: str | None
    model: str | None
    language: str
    length: str
    reasoning_effort: str | None
    web_search: bool


class SchedulerControl(Protocol):
    async def add_schedule(self, schedule: MbSchedule) -> None: ...
    async def modify_schedule(self, schedule: MbSchedule) -> None: ...
    async def remove_schedule(
        self, *, job_type: JobType, user_id: str, schedule_id: str | None = None
    ) -> None: ...


def _validate_cron(time: str, timezone: str, days_of_week: list[str]) -> None:
    if not _TIME_RE.match(time):
        raise ValueError(f"invalid time: {time!r}")
    try:
        zoneinfo.ZoneInfo(timezone)
    except Exception as exc:
        raise ValueError(f"invalid timezone: {timezone!r}") from exc
    if not days_of_week or any(d not in _VALID_DAYS for d in days_of_week):
        raise ValueError(f"invalid days_of_week: {days_of_week!r}")


def _validate_connectors_shape(enabled_connectors: dict) -> None:
    """Require ``{"provider_ids": list, "web_search": bool}`` shape."""
    if not isinstance(enabled_connectors, dict):
        raise ValueError(f"invalid enabled_connectors: {enabled_connectors!r}")
    provider_ids = enabled_connectors.get("provider_ids", [])
    if not isinstance(provider_ids, list):
        raise ValueError(
            f"invalid enabled_connectors.provider_ids (must be a list): {provider_ids!r}"
        )
    web_search = enabled_connectors.get("web_search", False)
    if not isinstance(web_search, bool):
        raise ValueError(f"invalid enabled_connectors.web_search (must be a bool): {web_search!r}")


def _validate_binding(
    db: Session,
    *,
    user_id: str,
    template_id: str | None,
    instructions_id: str | None,
    enabled_connectors: dict,
) -> None:
    """Validate the per-schedule binding resolves against the artifact stores."""
    _validate_connectors_shape(enabled_connectors)
    if template_id is not None and template_id != _FREEFORM_TEMPLATE_ID:
        try:
            mb_v2_template_service.resolve_template(db, user_id=user_id, template_id=template_id)
        except mb_v2_template_service.TemplateNotFoundError as exc:
            raise ValueError(f"invalid template_id: {template_id!r}") from exc
    if instructions_id is not None:
        try:
            mb_v2_instructions_service.resolve_instructions(
                db=db, user_id=user_id, instructions_id=instructions_id
            )
        except mb_v2_instructions_service.InstructionsNotFoundError as exc:
            raise ValueError(f"invalid instructions_id: {instructions_id!r}") from exc


def _to_dto(row: MbSchedule) -> MbScheduleDTO:
    return MbScheduleDTO(
        id=row.id,
        user_id=row.user_id,
        time=row.time,
        timezone=row.timezone,
        days_of_week=list(json.loads(row.days_of_week or "[]")),
        label=row.label or "",
        is_enabled=bool(row.is_enabled),
        template_id=row.template_id,
        instructions_id=row.instructions_id,
        enabled_connectors=dict(row.enabled_connectors or {}),
        provider_kind=row.provider_kind,
        model=row.model,
        language=row.language,
        length=row.length,
        reasoning_effort=row.reasoning_effort,
        web_search=bool(row.web_search),
    )


def list_schedules(db: Session, *, user_id: str) -> list[MbScheduleDTO]:
    rows = (
        db.query(MbSchedule)
        .filter(MbSchedule.user_id == user_id)
        .order_by(MbSchedule.time, MbSchedule.created_at)
        .all()
    )
    return [_to_dto(r) for r in rows]


def get_schedule_by_id(db: Session, *, user_id: str, schedule_id: str) -> MbScheduleDTO | None:
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
    template_id: str | None = None,
    instructions_id: str | None = None,
    enabled_connectors: dict | None = None,
    provider_kind: str | None = None,
    model: str | None = None,
    language: str = "en",
    length: str = "normal",
    reasoning_effort: str | None = None,
    web_search: bool = False,
) -> MbScheduleDTO:
    connectors = enabled_connectors or {}
    _validate_cron(time, timezone, days_of_week)
    _validate_binding(
        db,
        user_id=user_id,
        template_id=template_id,
        instructions_id=instructions_id,
        enabled_connectors=connectors,
    )
    row = MbSchedule(
        id=str(uuid.uuid4()),
        user_id=user_id,
        time=time,
        timezone=timezone,
        days_of_week=json.dumps(list(days_of_week)),
        label=label,
        is_enabled=True,
        template_id=template_id,
        instructions_id=instructions_id,
        enabled_connectors=connectors,
        provider_kind=provider_kind,
        model=model,
        language=language,
        length=length,
        reasoning_effort=reasoning_effort,
        web_search=web_search,
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
    template_id: str | None = None,
    instructions_id: str | None = None,
    enabled_connectors: dict | None = None,
    provider_kind: str | None = None,
    model: str | None = None,
    language: str = "en",
    length: str = "normal",
    reasoning_effort: str | None = None,
    web_search: bool = False,
) -> MbScheduleDTO | None:
    connectors = enabled_connectors or {}
    _validate_cron(time, timezone, days_of_week)
    row = db.query(MbSchedule).filter_by(id=schedule_id, user_id=user_id).one_or_none()
    if row is None:
        return None
    _validate_binding(
        db,
        user_id=user_id,
        template_id=template_id,
        instructions_id=instructions_id,
        enabled_connectors=connectors,
    )
    row.time = time
    row.timezone = timezone
    row.days_of_week = json.dumps(list(days_of_week))
    row.label = label
    row.template_id = template_id
    row.instructions_id = instructions_id
    row.enabled_connectors = connectors
    row.provider_kind = provider_kind
    row.model = model
    row.language = language
    row.length = length
    row.reasoning_effort = reasoning_effort
    row.web_search = web_search
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
