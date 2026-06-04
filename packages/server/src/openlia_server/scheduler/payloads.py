"""Cross-department payload surface. The scheduler knows *how* to run a
job, not *what* inputs a given department needs — that knowledge lives
in the plan that owns the department. Each Protocol below is implemented
(for production) by the owning department's service layer and (for tests)
by `_scheduler_fakes.py` in this plan's test tree."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from openlia.llm.runtime.messages import ReportRequest
from sqlalchemy.orm import Session


class DepartmentPayloadBuilderNotWired(RuntimeError):
    """Raised when a department builder is missing at fire time. Now that
    every shipping department has a real builder this should never occur
    in production; kept for tests that exercise the failure path."""


# ------------------------------------------------------------------
# EU — Earnings Update
# ------------------------------------------------------------------


@dataclass(frozen=True)
class EUScanTarget:
    ticker: str
    request: ReportRequest


class EUScanPlanner(Protocol):
    """Given a user + EU schedule + the last time this schedule ran,
    return a list of (ticker, request) tuples for companies that have
    released earnings since."""

    def plan(
        self,
        *,
        session: Session,
        user_id: str,
        schedule_id: str,
        since: datetime | None,
    ) -> list[EUScanTarget]: ...


# ------------------------------------------------------------------
# ReportStore — where finished ReportRunner outputs land
# ------------------------------------------------------------------


class ReportStore(Protocol):
    """Persist a report produced by a background ReportRunner run."""

    def save(
        self,
        *,
        session: Session,
        user_id: str,
        department: str,
        payload: dict[str, Any],
    ) -> str: ...  # returns report_id


# ------------------------------------------------------------------
# EU v2 — Earnings Update v2 calendar sync + dispatch
# ------------------------------------------------------------------


class EuV2CalendarSyncer(Protocol):
    """Run the weekly EODHD calendar sync across all EU v2 watchlists."""

    def sync_all(self, *, session: Session) -> int: ...


class EuV2Dispatcher(Protocol):
    """Fire due scheduled earnings runs from eu_v2_earnings_schedule."""

    def dispatch_due(self, *, session: Session, now: datetime) -> int: ...
