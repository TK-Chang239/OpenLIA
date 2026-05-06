"""On-demand Morning Briefing report orchestrator.

Wraps `ReportRunner.run()` with MB-specific defaults:
- Builds a `ReportRequest` via `MbRequestBuilderImpl` (config + portfolio).
- Forwards every SSE event to the caller.
- Persists the report on `ReportComplete` via `reports.create_report`
  and yields a synthetic `ReportSavedEvent` per README pattern #3.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from datetime import datetime
from typing import Protocol
from zoneinfo import ZoneInfo

from openlia.llm.runtime.cancellation import CancellationToken
from openlia.llm.runtime.events import ReportComplete, SseEvent
from openlia.llm.runtime.messages import ReportRequest
from openlia.reports.validator import validate_report_payload
from sqlalchemy.orm import Session

from openlia_server.db.models.scheduler import MbSchedule
from openlia_server.services import reports as reports_svc
from openlia_server.services.mb_request_builder import MbRequestBuilderImpl


def _now_local() -> datetime:
    """Return current wall-clock time as a tz-aware datetime in UTC.

    Replaceable in tests; the report-naming helper layers the user's MB
    schedule timezone on top of this so a single seam makes the whole
    auto-titling pipeline deterministic under monkeypatch.
    """
    return datetime.now(ZoneInfo("UTC"))


def _session_label_for_hour(hour: int) -> str:
    """Bucket a 0-23 hour into Morning/Noon/Night.

    Morning 04-11, Noon 12-16, Night 17-03. Tuned so the most common
    on-demand window (pre-market through lunch) reads "Morning"/"Noon",
    and after-hours runs roll into "Night".
    """
    if 4 <= hour <= 11:
        return "Morning"
    if 12 <= hour <= 16:
        return "Noon"
    return "Night"


def _auto_title(local_now: datetime) -> str:
    return f"{local_now:%m/%d/%Y} {_session_label_for_hour(local_now.hour)}"


def _resolve_local_now(session: Session, *, user_id: str) -> datetime:
    """Convert ``_now_local()`` into the user's MB-schedule timezone if set."""
    base = _now_local()
    schedule = (
        session.query(MbSchedule)
        .filter(MbSchedule.user_id == user_id)
        .order_by(MbSchedule.created_at.desc())
        .first()
    )
    if schedule is None:
        return base
    try:
        tz = ZoneInfo(schedule.timezone)
    except Exception:
        return base
    return base.astimezone(tz)


@dataclass(frozen=True)
class ReportSavedEvent:
    """Terminal event emitted after the report is persisted by reports service.

    Mirrors README pattern #3: `report.saved {report_id}`.
    """

    TYPE = "report.saved"
    report_id: str


class ReportRunnerLike(Protocol):
    def run(
        self,
        *,
        department_id: str,
        user_id: str,
        request: ReportRequest,
        cancel_token: CancellationToken | None = ...,
    ) -> AsyncIterator[SseEvent]: ...


async def run_on_demand(
    *,
    session: Session,
    user_id: str,
    report_runner: ReportRunnerLike,
    cancel_token: CancellationToken | None = None,
) -> AsyncIterator[SseEvent | ReportSavedEvent]:
    builder = MbRequestBuilderImpl()
    request = builder.build(session=session, user_id=user_id, schedule_id="on_demand")

    last_complete: ReportComplete | None = None
    async for event in report_runner.run(
        department_id="morning_briefing",
        user_id=user_id,
        request=request,
        cancel_token=cancel_token,
    ):
        if isinstance(event, ReportComplete):
            last_complete = event
        yield event

    if last_complete is None:
        return

    schema_obj = validate_report_payload(last_complete.schema)
    report_id = reports_svc.create_report(
        session,
        user_id=user_id,
        department="morning_briefing",
        mode="morning_briefing",
        schema=schema_obj,
        title=_auto_title(_resolve_local_now(session, user_id=user_id)),
    )
    session.commit()
    yield ReportSavedEvent(report_id=report_id)
