"""Cross-department payload surface. The scheduler knows *how* to run a
job, not *what* inputs a given department needs — that knowledge lives
in the plan that owns the department. Each Protocol below is implemented
(for real) by one of Plans 13/15/16/19 and (for tests) by `_fakes.py`
in this plan's test tree."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

from openlia.llm.runtime.messages import BatchItem, BatchResult, ReportRequest
from sqlalchemy.orm import Session


class DepartmentPayloadBuilderNotWired(RuntimeError):
    """Raised by a stub payload builder to signal that the department-owning
    plan has not provided a real implementation yet."""


# ------------------------------------------------------------------
# MB — Morning Briefing
# ------------------------------------------------------------------


class MBRequestBuilder(Protocol):
    """Given a user + schedule_id, build the ReportRequest for the
    morning briefing. Owned by Plan 16."""

    def build(self, *, session: Session, user_id: str, schedule_id: str) -> ReportRequest: ...


class StubMBRequestBuilder:
    def build(self, *, session: Session | None, user_id: str, schedule_id: str) -> ReportRequest:
        raise DepartmentPayloadBuilderNotWired(
            "MBRequestBuilder not provided — Plan 16 (Morning Briefing) will "
            "supply the real implementation."
        )


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
    released earnings since. Owned by Plan 15."""

    def plan(
        self,
        *,
        session: Session,
        user_id: str,
        schedule_id: str,
        since: datetime | None,
    ) -> list[EUScanTarget]: ...


class StubEUScanPlanner:
    def plan(
        self,
        *,
        session: Session | None,
        user_id: str,
        schedule_id: str,
        since: datetime | None,
    ) -> list[EUScanTarget]:
        raise DepartmentPayloadBuilderNotWired(
            "EUScanPlanner not provided — Plan 15 (Earnings Update) will "
            "supply the real implementation."
        )


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
    executor only orchestrates the two runner calls. This keeps all
    prompt-construction logic inside the department layer (Plan 19)
    and out of the scheduler.
    """

    items: list[BatchItem]
    t4_task: str
    t4_schema: type
    synthesize: Callable[[list[BatchResult]], ReportRequest]


class MRAssessmentBuilder(Protocol):
    """Given a user, build the batch items for T4 (plus the pydantic
    schema and task slot name BatchRunner needs) and a `synthesize`
    callable that converts T4 BatchResults into the T5 ReportRequest.
    Owned by Plan 19."""

    def build(self, *, session: Session, user_id: str) -> MRAssessmentPayload: ...


class StubMRAssessmentBuilder:
    def build(self, *, session: Session | None, user_id: str) -> MRAssessmentPayload:
        raise DepartmentPayloadBuilderNotWired(
            "MRAssessmentBuilder not provided — Plan 19 (Macro Research) will "
            "supply the real implementation."
        )


# ------------------------------------------------------------------
# ReportStore — where finished ReportRunner outputs land
# ------------------------------------------------------------------


class ReportStore(Protocol):
    """Persist a report produced by a background ReportRunner run.
    Owned by Plan 13 (report rendering pipeline)."""

    def save(
        self,
        *,
        session: Session,
        user_id: str,
        department: str,
        payload: dict[str, Any],
    ) -> str: ...  # returns report_id


class StubReportStore:
    def save(
        self,
        *,
        session: Session | None,
        user_id: str,
        department: str,
        payload: dict[str, Any],
    ) -> str:
        raise DepartmentPayloadBuilderNotWired(
            "ReportStore not provided — Plan 13 (report rendering pipeline) "
            "will supply the real implementation."
        )


# ------------------------------------------------------------------
# MRCacheStore — where T4/T5 output lands
# ------------------------------------------------------------------


class MRCacheStore(Protocol):
    """Persist T4/T5 output into mr_assessment_cache. Owned by Plan 19."""

    def save(
        self, *, session: Session, user_id: str, payload: dict[str, Any]
    ) -> str: ...  # returns cache_id


class StubMRCacheStore:
    def save(self, *, session: Session | None, user_id: str, payload: dict[str, Any]) -> str:
        raise DepartmentPayloadBuilderNotWired(
            "MRCacheStore not provided — Plan 19 (Macro Research) will supply "
            "the real implementation."
        )
