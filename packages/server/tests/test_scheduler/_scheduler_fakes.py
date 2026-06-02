"""Shared test doubles for Plan 6 scheduler tests.

Imported by sibling test files via `from _fakes import FakeFoo`. The
`sys.path.insert(...)` in conftest.py makes this directory importable
as top-level modules under --import-mode=importlib.

Test-only stubs for the scheduler `payloads` Protocols also live here
so production code never depends on a "raises at fire time" payload
builder. Tests that exercise the not-wired failure path import them
from this module."""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from openlia.llm.runtime.events import SseEvent
from openlia.llm.runtime.messages import (
    Attachment,
    BatchItem,
    BatchResult,
    ChatMessage,
    ReportRequest,
)
from openlia_server.scheduler.payloads import (
    DepartmentPayloadBuilderNotWired,
    EUScanTarget,
    MRAssessmentPayload,
)
from sqlalchemy.orm import Session

# ------------------------------------------------------------------
# Test-only stub builders — historically lived in scheduler/payloads.py.
# Moved here once every department shipped a real builder so production
# wiring fails loudly when a real builder is missing.
# ------------------------------------------------------------------


class StubEUScanPlanner:
    def plan(
        self,
        *,
        session: Session | None,
        user_id: str,
        schedule_id: str,
        since: datetime | None,
    ) -> list[EUScanTarget]:
        raise DepartmentPayloadBuilderNotWired("EUScanPlanner not provided")


class StubMRAssessmentBuilder:
    def build(self, *, session: Session | None, user_id: str) -> MRAssessmentPayload:
        raise DepartmentPayloadBuilderNotWired("MRAssessmentBuilder not provided")


class StubReportStore:
    def save(
        self,
        *,
        session: Session | None,
        user_id: str,
        department: str,
        payload: dict[str, Any],
    ) -> str:
        raise DepartmentPayloadBuilderNotWired("ReportStore not provided")


class StubMRCacheStore:
    def save(self, *, session: Session | None, user_id: str, payload: dict[str, Any]) -> str:
        raise DepartmentPayloadBuilderNotWired("MRCacheStore not provided")


# ------------------------------------------------------------------
# FakeSleep — swap for asyncio.sleep in retry-backoff tests.
# ------------------------------------------------------------------


@dataclass
class FakeSleep:
    calls: list[float] = field(default_factory=list)

    async def __call__(self, seconds: float) -> None:
        self.calls.append(seconds)


# ------------------------------------------------------------------
# Payload builder fakes
# ------------------------------------------------------------------


@dataclass
class FakeEUPlanner:
    targets: list[EUScanTarget]
    raise_exc: Exception | None = None
    received: list[dict[str, Any]] = field(default_factory=list)

    def plan(
        self,
        *,
        session: Session | None,
        user_id: str,
        schedule_id: str,
        since: datetime | None,
    ) -> list[EUScanTarget]:
        self.received.append(
            {
                "user_id": user_id,
                "schedule_id": schedule_id,
                "since": since,
            }
        )
        if self.raise_exc is not None:
            raise self.raise_exc
        return list(self.targets)


@dataclass
class FakeMRBuilder:
    items: list[BatchItem]
    synth: ReportRequest
    t4_task: str = "t4"
    t4_schema: type = field(default_factory=lambda: _default_t4_schema())
    received_results: list[list[BatchResult]] = field(default_factory=list)

    def build(self, *, session: Session | None, user_id: str) -> MRAssessmentPayload:
        def _synthesize(results: list[BatchResult]) -> ReportRequest:
            self.received_results.append(list(results))
            return self.synth

        return MRAssessmentPayload(
            items=list(self.items),
            t4_task=self.t4_task,
            t4_schema=self.t4_schema,
            synthesize=_synthesize,
        )


def _default_t4_schema() -> type:
    from pydantic import BaseModel

    class _T4(BaseModel):
        label: str
        score: float

    return _T4


@dataclass
class FakeReportStore:
    next_id: str = "r_stub"
    saves: list[dict[str, Any]] = field(default_factory=list)

    def save(
        self,
        *,
        session: Session | None,
        user_id: str,
        department: str,
        payload: dict[str, Any],
    ) -> str:
        self.saves.append(
            {
                "user_id": user_id,
                "department": department,
                "payload": payload,
            }
        )
        return self.next_id


@dataclass
class FakeMRCacheStore:
    next_id: str = "c_stub"
    saves: list[dict[str, Any]] = field(default_factory=list)

    def save(
        self,
        *,
        session: Session | None,
        user_id: str,
        payload: dict[str, Any],
    ) -> str:
        self.saves.append({"user_id": user_id, "payload": payload})
        return self.next_id


# ------------------------------------------------------------------
# Runner fakes
# ------------------------------------------------------------------


@dataclass
class FakeReportRunner:
    """Scripted ReportRunner. Emits `events` in order, then stops.

    If `raise_exc` is set, raises it mid-iteration after emitting any
    events accumulated before the failure marker.
    """

    events: list[SseEvent]
    raise_exc: Exception | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def run(
        self,
        *,
        department_id: str,
        user_id: str | None,
        request: ReportRequest,
        cancel_token: Any | None = None,
    ) -> AsyncIterator[SseEvent]:
        self.calls.append(
            {
                "department_id": department_id,
                "user_id": user_id,
                "request": request,
            }
        )
        for ev in self.events:
            if cancel_token is not None and getattr(cancel_token, "is_cancelled", False):
                return
            yield ev
        if self.raise_exc is not None:
            raise self.raise_exc


@dataclass
class FakeBatchRunner:
    results: list[BatchResult]
    raise_exc: Exception | None = None
    calls: list[dict[str, Any]] = field(default_factory=list)

    async def run(
        self,
        *,
        department_id: str,
        task: str,
        items: list[BatchItem],
        schema: type,
        concurrency: int = 8,
        user_id: str | None = None,
    ) -> list[BatchResult]:
        self.calls.append(
            {
                "department_id": department_id,
                "task": task,
                "items": list(items),
                "user_id": user_id,
            }
        )
        if self.raise_exc is not None:
            raise self.raise_exc
        return list(self.results)


# ------------------------------------------------------------------
# A trivial chat-message fake in case a test needs one (ChatRunner
# isn't used by the scheduler, but a ChatMessage value may be needed
# to exercise Attachment passthrough in future tasks).
# ------------------------------------------------------------------


def make_chat_message(text: str = "hi") -> ChatMessage:
    return ChatMessage(role="user", content=text, attachments=[])


def make_attachment() -> Attachment:
    return Attachment(kind="image", url="u", mime_type="image/png")


# ------------------------------------------------------------------
# FakeAPScheduler — stand-in for APScheduler AsyncScheduler in tests
# ------------------------------------------------------------------


@dataclass
class _ScheduledJob:
    id: str
    func: Any  # Callable
    trigger: Any
    args: tuple
    kwargs: dict
    misfire_grace_time: float | None
    max_instances: int | None = None
    coalesce: bool | None = None


@dataclass
class FakeAPScheduler:
    started: bool = False
    stopped: bool = False
    jobs: dict[str, _ScheduledJob] = field(default_factory=dict)

    def start_in_background(self) -> None:
        self.started = True

    async def stop(self) -> None:
        self.stopped = True

    async def add_schedule(
        self,
        func,
        trigger,
        *,
        id: str,
        args: tuple = (),
        kwargs: dict | None = None,
        misfire_grace_time: float | None = None,
        max_instances: int | None = None,
        coalesce: bool | None = None,
    ) -> str:
        if id in self.jobs:
            raise ValueError(f"duplicate schedule id: {id}")
        self.jobs[id] = _ScheduledJob(
            id=id,
            func=func,
            trigger=trigger,
            args=args,
            kwargs=kwargs or {},
            misfire_grace_time=misfire_grace_time,
            max_instances=max_instances,
            coalesce=coalesce,
        )
        return id

    async def remove_schedule(self, id: str) -> None:
        self.jobs.pop(id, None)

    async def get_schedules(self) -> list[_ScheduledJob]:
        return list(self.jobs.values())

    async def fire(self, id: str) -> Any:
        """Test helper: run a scheduled job's callback synchronously."""
        job = self.jobs[id]
        return await job.func(*job.args, **job.kwargs)
