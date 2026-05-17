"""The report wrapper coroutine:
1. Iterates the runner, fans events out via registry's machinery
2. On ReportComplete: persists complete status + payload, calls presence.fanout(report.complete)
3. On ReportError: persists failed status + failure_reason, fanout report.failed
4. On asyncio.CancelledError: persists cancelled status, fanout report.cancelled
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest
from openlia.llm.runtime.events import ReportComplete, ReportError, ReportStart
from openlia_server.services.background_report_registry import BackgroundReportRegistry
from openlia_server.services.report_wrapper import run_wrapped_report


@dataclass
class _Captured:
    user_id: str
    event: dict


class _StubPresence:
    def __init__(self) -> None:
        self.events: list[_Captured] = []

    def fanout(self, user_id: str, event: dict) -> None:
        self.events.append(_Captured(user_id=user_id, event=event))


class _StubReportRow:
    def __init__(self) -> None:
        self.status: str | None = None
        self.failure_reason: str | None = None
        self.report_schema_json: str | None = None
        self.completed_at = None


class _StubSession:
    def __init__(self, row: _StubReportRow) -> None:
        self._row = row
        self.committed = False

    def get(self, model, _id):
        return self._row

    def commit(self) -> None:
        self.committed = True

    def close(self) -> None:
        pass


def _session_factory(row: _StubReportRow):
    def factory():
        class _CM:
            def __enter__(self_inner):
                return _StubSession(row)

            def __exit__(self_inner, *a):
                return False

        return _CM()

    return factory


@pytest.mark.asyncio
async def test_wrapper_persists_complete_status_on_report_complete() -> None:
    row = _StubReportRow()
    presence = _StubPresence()
    registry = BackgroundReportRegistry()

    async def runner():
        yield ReportStart(
            report_id="r1",
            department="equity_research",
            mode="stock_initiation",
            section_titles=[],
        )
        yield ReportComplete(report_id="r1", schema={"cover": {"title": "MSFT"}})

    await run_wrapped_report(
        runner_coro=runner(),
        report_id="r1",
        user_id="u1",
        db_session_factory=_session_factory(row),
        presence=presence,
        registry=registry,
    )
    assert row.status == "complete"
    assert row.report_schema_json is not None
    assert presence.events[-1].event["type"] == "report.complete"
    assert presence.events[-1].event["report_id"] == "r1"
    assert presence.events[-1].event["title"] == "MSFT"


@pytest.mark.asyncio
async def test_wrapper_persists_failed_status_on_report_error() -> None:
    row = _StubReportRow()
    presence = _StubPresence()
    registry = BackgroundReportRegistry()

    async def runner():
        yield ReportError(report_id="r1", error_class="oops", message="something broke")

    await run_wrapped_report(
        runner_coro=runner(),
        report_id="r1",
        user_id="u1",
        db_session_factory=_session_factory(row),
        presence=presence,
        registry=registry,
    )
    assert row.status == "failed"
    assert row.failure_reason == "something broke"
    assert presence.events[-1].event["type"] == "report.failed"


@pytest.mark.asyncio
async def test_wrapper_persists_cancelled_on_cancellation() -> None:
    row = _StubReportRow()
    presence = _StubPresence()
    registry = BackgroundReportRegistry()

    async def runner():
        await asyncio.sleep(10)
        yield ReportComplete(report_id="r1", schema={"cover": {"title": "never"}})

    task = asyncio.create_task(
        run_wrapped_report(
            runner_coro=runner(),
            report_id="r1",
            user_id="u1",
            db_session_factory=_session_factory(row),
            presence=presence,
            registry=registry,
        )
    )
    await asyncio.sleep(0.05)
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert row.status == "cancelled"
    assert row.failure_reason == "user_cancelled"
    assert presence.events[-1].event["type"] == "report.cancelled"
