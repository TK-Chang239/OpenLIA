from __future__ import annotations

import json

import pytest
from _scheduler_fakes import (
    FakeBatchRunner,
    FakeMRBuilder,
    FakeMRCacheStore,
    FakeReportRunner,
    FakeSleep,
)
from openlia.llm.runtime.events import (
    ReportComplete,
    ReportError,
    ReportStart,
)
from openlia.llm.runtime.messages import (
    BatchItem,
    BatchResult,
    ReportRequest,
)
from openlia_server.db.models.auth import User
from openlia_server.db.models.scheduler import JobRun, UserNotification
from openlia_server.scheduler.executors.mr import MRAssessmentExecutor
from openlia_server.scheduler.registry import JobStatus
from sqlalchemy.orm import Session


def _seed(session: Session) -> None:
    session.add(
        User(
            id="u_1",
            email="u@e.com",
            display_name="u",
            password_hash="h",
            is_admin=False,
            is_disabled=False,
        )
    )
    session.commit()


def _t5_ok_events(report_id: str = "r_t5") -> list:
    return [
        ReportStart(
            report_id=report_id,
            department="macro_research",
            mode="mr_synthesis",
            section_titles=["Assessment"],
        ),
        ReportComplete(
            report_id=report_id,
            schema={
                "title": "Debt Cycle — debt burden rising",
                "sections": [{"id": "assessment", "body": "..."}],
            },
        ),
    ]


@pytest.mark.asyncio
async def test_mr_happy_path_runs_t4_then_t5_and_caches_result(
    session_factory,
) -> None:
    with session_factory() as s:
        _seed(s)

    builder = FakeMRBuilder(
        items=[
            BatchItem(id="debt_burden", context={"metric": "debt_burden"}),
            BatchItem(id="credit_growth", context={"metric": "credit_growth"}),
        ],
        synth=ReportRequest(mode="mr_synthesis", user_input="synthesize"),
    )
    batch_runner = FakeBatchRunner(
        results=[
            BatchResult(id="debt_burden", ok=True, data={"score": 0.8}, error=None),
            BatchResult(id="credit_growth", ok=True, data={"score": 0.6}, error=None),
        ]
    )
    report_runner = FakeReportRunner(events=_t5_ok_events())
    cache = FakeMRCacheStore(next_id="cache_abc")

    ex = MRAssessmentExecutor(
        session_factory=session_factory,
        sleep=FakeSleep(),
        mr_builder=builder,
        batch_runner=batch_runner,
        report_runner=report_runner,
        mr_cache_store=cache,
    )
    run_id = await ex.execute(user_id="u_1", schedule_id="debt_cycle")

    with session_factory() as s:
        row = s.get(JobRun, run_id)
        assert row.status == JobStatus.COMPLETED.value
        summary = json.loads(row.result_summary)
        assert summary == {"cache_id": "cache_abc", "dashboard": "debt_cycle"}

        notifs = s.query(UserNotification).all()
        assert len(notifs) == 1
        assert notifs[0].type == "assessment_ready"
        assert notifs[0].department == "macro_research"
        assert "debt_cycle" in notifs[0].message.lower()

    assert len(batch_runner.calls) == 1
    call = batch_runner.calls[0]
    assert call["department_id"] == "macro_research"
    assert call["task"] == builder.t4_task
    assert [item.id for item in call["items"]] == ["debt_burden", "credit_growth"]

    assert len(builder.received_results) == 1
    assert [r.id for r in builder.received_results[0]] == [
        "debt_burden",
        "credit_growth",
    ]

    assert len(report_runner.calls) == 1
    assert report_runner.calls[0]["department_id"] == "macro_research"
    assert report_runner.calls[0]["request"].mode == "mr_synthesis"

    assert len(cache.saves) == 1
    saved_payload = cache.saves[0]["payload"]
    assert saved_payload["dashboard"] == "debt_cycle"
    assert saved_payload["t5"]["title"].startswith("Debt Cycle")
    assert saved_payload["t4"] == [
        {"id": "debt_burden", "ok": True, "data": {"score": 0.8}, "error": None},
        {"id": "credit_growth", "ok": True, "data": {"score": 0.6}, "error": None},
    ]


@pytest.mark.asyncio
async def test_mr_batch_returns_partial_failures_still_feeds_synthesis(
    session_factory,
) -> None:
    """Per spec: T4 items are independent. A per-item error does NOT fail
    the job — it gets passed to synthesize() so T5 can narrate around the
    gap. Only a BatchRunner-level exception (LLMProviderError) aborts."""
    with session_factory() as s:
        _seed(s)

    builder = FakeMRBuilder(
        items=[BatchItem(id="a", context={}), BatchItem(id="b", context={})],
        synth=ReportRequest(mode="mr_synthesis", user_input="s"),
    )
    batch_runner = FakeBatchRunner(
        results=[
            BatchResult(id="a", ok=True, data={"x": 1}, error=None),
            BatchResult(id="b", ok=False, data=None, error="timeout"),
        ]
    )
    report_runner = FakeReportRunner(events=_t5_ok_events())
    cache = FakeMRCacheStore(next_id="cache_xy")

    ex = MRAssessmentExecutor(
        session_factory=session_factory,
        sleep=FakeSleep(),
        mr_builder=builder,
        batch_runner=batch_runner,
        report_runner=report_runner,
        mr_cache_store=cache,
    )
    run_id = await ex.execute(user_id="u_1", schedule_id="debt_cycle")

    with session_factory() as s:
        assert s.get(JobRun, run_id).status == JobStatus.COMPLETED.value
        assert s.query(UserNotification).count() == 1

    passed = builder.received_results[0]
    assert len(passed) == 2
    assert passed[1].ok is False
    assert passed[1].error == "timeout"

    saved = cache.saves[0]["payload"]
    assert saved["t4"][1] == {"id": "b", "ok": False, "data": None, "error": "timeout"}


@pytest.mark.asyncio
async def test_mr_t5_report_error_transient_triggers_retry(
    session_factory,
) -> None:
    with session_factory() as s:
        _seed(s)

    builder = FakeMRBuilder(
        items=[BatchItem(id="a", context={})],
        synth=ReportRequest(mode="mr_synthesis", user_input="s"),
    )
    batch_runner = FakeBatchRunner(
        results=[BatchResult(id="a", ok=True, data={"x": 1}, error=None)]
    )

    class _TwoPhaseReport:
        def __init__(self) -> None:
            self.phase = 0

        async def run(self, **_):
            self.phase += 1
            if self.phase == 1:
                yield ReportStart(
                    report_id="r_1",
                    department="macro_research",
                    mode="mr_synthesis",
                    section_titles=[],
                )
                yield ReportError(
                    report_id="r_1",
                    error_class="RateLimitError",
                    message="429",
                )
                return
            for ev in _t5_ok_events("r_2"):
                yield ev

    sleep = FakeSleep()
    ex = MRAssessmentExecutor(
        session_factory=session_factory,
        sleep=sleep,
        mr_builder=builder,
        batch_runner=batch_runner,
        report_runner=_TwoPhaseReport(),
        mr_cache_store=FakeMRCacheStore(next_id="cache_ok"),
    )
    run_id = await ex.execute(user_id="u_1", schedule_id="debt_cycle")

    with session_factory() as s:
        row = s.get(JobRun, run_id)
        assert row.status == JobStatus.COMPLETED.value
        assert row.attempt == 2
    assert sleep.calls == [30]

    assert len(batch_runner.calls) == 1


@pytest.mark.asyncio
async def test_mr_batch_runner_transient_failure_retries_both_stages(
    session_factory,
) -> None:
    """If BatchRunner itself raises a transient LLMProviderError on attempt 1,
    the executor re-runs _do_work from the top on attempt 2 — including
    re-calling mr_builder.build() and BatchRunner."""
    with session_factory() as s:
        _seed(s)

    from openlia.llm.exceptions import RateLimitError

    builder = FakeMRBuilder(
        items=[BatchItem(id="a", context={})],
        synth=ReportRequest(mode="mr_synthesis", user_input="s"),
    )

    class _FlakyBatch:
        def __init__(self) -> None:
            self.calls: list = []

        async def run(self, *, department_id, task, items, schema, concurrency=8, user_id=None):
            self.calls.append({"department_id": department_id})
            if len(self.calls) == 1:
                raise RateLimitError("429")
            return [BatchResult(id="a", ok=True, data={"x": 1}, error=None)]

    batch = _FlakyBatch()
    ex = MRAssessmentExecutor(
        session_factory=session_factory,
        sleep=FakeSleep(),
        mr_builder=builder,
        batch_runner=batch,
        report_runner=FakeReportRunner(events=_t5_ok_events()),
        mr_cache_store=FakeMRCacheStore(next_id="cache_ok"),
    )
    run_id = await ex.execute(user_id="u_1", schedule_id="debt_cycle")

    with session_factory() as s:
        assert s.get(JobRun, run_id).status == JobStatus.COMPLETED.value
        assert s.get(JobRun, run_id).attempt == 2
    assert len(batch.calls) == 2


@pytest.mark.asyncio
async def test_mr_executor_reuses_pre_allocated_run_id(session_factory) -> None:
    """Phase 19 P1-05: an HTTP route that pre-allocates a job_runs row
    must see the same id used by the executor (instead of a fresh row),
    so the route's synchronously-returned id is the live row."""
    from datetime import UTC, datetime

    with session_factory() as s:
        _seed(s)
        s.add(
            JobRun(
                id="pre-allocated-id",
                user_id="u_1",
                job_type="mr_assessment",
                schedule_id="debt_cycle",
                status=JobStatus.RUNNING.value,
                started_at=datetime.now(UTC),
            )
        )
        s.commit()

    builder = FakeMRBuilder(
        items=[BatchItem(id="a", context={})],
        synth=ReportRequest(mode="mr_synthesis", user_input="s"),
    )
    batch_runner = FakeBatchRunner(
        results=[BatchResult(id="a", ok=True, data={"x": 1}, error=None)]
    )
    report_runner = FakeReportRunner(events=_t5_ok_events())
    cache = FakeMRCacheStore(next_id="cache_yy")

    ex = MRAssessmentExecutor(
        session_factory=session_factory,
        sleep=FakeSleep(),
        mr_builder=builder,
        batch_runner=batch_runner,
        report_runner=report_runner,
        mr_cache_store=cache,
    )
    returned = await ex.execute(user_id="u_1", schedule_id="debt_cycle", run_id="pre-allocated-id")
    assert returned == "pre-allocated-id"

    with session_factory() as s:
        # Only one row was touched — the pre-allocated one transitioned to
        # COMPLETED rather than a duplicate row being created.
        rows = s.query(JobRun).all()
        assert len(rows) == 1
        assert rows[0].id == "pre-allocated-id"
        assert rows[0].status == JobStatus.COMPLETED.value
