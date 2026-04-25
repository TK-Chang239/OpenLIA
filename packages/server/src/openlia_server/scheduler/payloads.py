"""Cross-department payload surface. The scheduler knows *how* to run a
job, not *what* inputs a given department needs — that knowledge lives
in the plan that owns the department. Each Protocol below is implemented
(for production) by the owning department's service layer and (for tests)
by `_scheduler_fakes.py` in this plan's test tree."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from openlia.llm.runtime.messages import BatchItem, BatchResult, ReportRequest
from sqlalchemy.orm import Session


class DepartmentPayloadBuilderNotWired(RuntimeError):
    """Raised when a department builder is missing at fire time. Now that
    every shipping department has a real builder this should never occur
    in production; kept for tests that exercise the failure path."""


# ------------------------------------------------------------------
# MB — Morning Briefing
# ------------------------------------------------------------------


class MBRequestBuilder(Protocol):
    """Given a user + schedule_id, build the ReportRequest for the
    morning briefing."""

    def build(self, *, session: Session, user_id: str, schedule_id: str) -> ReportRequest: ...


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
# MR — Macro Research
# ------------------------------------------------------------------


@dataclass(frozen=True)
class MRAssessmentPayload:
    """Output of MRAssessmentBuilder.

    `synthesize` is a callable the builder owns: it takes the list of
    T4 BatchResults produced by BatchRunner and returns the finished
    ReportRequest for T5 (synthesis). The builder is responsible for
    formatting T4 results into T5's user_input / custom_sections; the
    executor only orchestrates the two runner calls.
    """

    items: list[BatchItem]
    t4_task: str
    t4_schema: type
    synthesize: Callable[[list[BatchResult]], ReportRequest]


class MRAssessmentBuilder(Protocol):
    """Given a user, build the batch items for T4 (plus the pydantic
    schema and task slot name BatchRunner needs) and a `synthesize`
    callable that converts T4 BatchResults into the T5 ReportRequest."""

    def build(self, *, session: Session, user_id: str) -> MRAssessmentPayload: ...


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
# MRCacheStore — where T4/T5 output lands
# ------------------------------------------------------------------


class MRCacheStore(Protocol):
    """Persist T4/T5 output into mr_assessment_cache."""

    def save(
        self, *, session: Session, user_id: str, payload: dict[str, Any]
    ) -> str: ...  # returns cache_id


# ------------------------------------------------------------------
# RS — Retail Sentiment snapshot runner
# ------------------------------------------------------------------


class RSSnapshotRunner(Protocol):
    """Run a RS snapshot for a given user. Owned by the RS service layer."""

    def run_many(self, tickers: Sequence[str]) -> list[Any]: ...
