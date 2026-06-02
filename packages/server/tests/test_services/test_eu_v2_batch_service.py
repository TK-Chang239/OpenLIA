"""EU v2 batch service: eligibility + end-to-end group run via a fake transport."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from openlia.llm.batch_transport import BatchResultItem, BatchStatus
from openlia.llm.runtime.report_eu import EuDataTransports
from openlia.llm.runtime.report_eu.run_state import EuRunState
from openlia.llm.runtime.report_eu.schemas import EnabledConnectors, RunRequest
from openlia.llm.runtime.report_v2_3.templates.spec import SectionSpec, TemplateSpec
from openlia.llm.types import LLMResponse, ToolCall
from openlia_server.db.models.report_eu import (
    EuV2BatchJob,
    EuV2BatchRun,
    ReportEu,
    ReportEuSection,
)
from openlia_server.services import eu_v2_batch_service as svc
from openlia_server.services.eu_v2_run_service import insert_report_row
from openlia_server.services.eu_v2_settings import EuSettingsDTO


def _settings(**over) -> EuSettingsDTO:
    base = dict(
        user_id="u-1",
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        template_id="eu_default",
        language="en",
        length="normal",
        reasoning_effort=None,
        enabled_provider_ids=frozenset({"eodhd"}),
        web_search_enabled=False,
        instructions_id=None,
        batch_enabled=True,
    )
    base.update(over)
    return EuSettingsDTO(**base)


def test_is_batch_eligible():
    assert svc.is_batch_eligible(_settings(batch_enabled=True, provider_kind="openai")) is True
    assert svc.is_batch_eligible(_settings(batch_enabled=True, provider_kind="anthropic")) is True
    assert svc.is_batch_eligible(_settings(batch_enabled=False)) is False
    # Opted in but provider has no batch transport -> not eligible.
    assert svc.is_batch_eligible(_settings(batch_enabled=True, provider_kind="ollama")) is False


def _req(subject: str) -> RunRequest:
    return RunRequest(
        subject=subject,
        template=TemplateSpec(
            template_id="eu_default",
            name="EU",
            shape_description="scorecard",
            ticker_anchored=True,
            default_length="normal",
            sections=[SectionSpec(id="quick_take", title="Quick Take", intent="TLDR")],
        ),
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        enabled_connectors=EnabledConnectors(provider_ids=frozenset(), web_search=False),
    )


def _transports() -> EuDataTransports:
    return EuDataTransports(
        fundamentals=lambda t: {},
        prices=lambda t, f, to: [],
        news=lambda t, n: [],
        earnings_calendar=lambda t: [],
    )


def _write() -> LLMResponse:
    return LLMResponse(
        text="",
        finish_reason="tool_calls",
        input_tokens=0,
        output_tokens=0,
        tool_calls=[
            ToolCall(
                id="c1",
                name="write_section",
                arguments={"section_id": "quick_take", "markdown": "Body."},
            )
        ],
    )


def _finalize() -> LLMResponse:
    return LLMResponse(
        text="",
        finish_reason="tool_calls",
        input_tokens=0,
        output_tokens=0,
        tool_calls=[ToolCall(id="c2", name="finalize", arguments={})],
    )


class FakeBatchTransport:
    def __init__(self, scripts):
        self._scripts = {k: iter(v) for k, v in scripts.items()}
        self._pending = {}
        self._n = 0

    async def submit_batch(self, items):
        self._n += 1
        bid = f"batch-{self._n}"
        self._pending[bid] = [it.custom_id for it in items]
        return bid

    async def poll_batch(self, batch_id):
        return BatchStatus.COMPLETED

    async def fetch_results(self, batch_id):
        out = {}
        for cid in self._pending.get(batch_id, []):
            try:
                resp = next(self._scripts[cid])
                out[cid] = BatchResultItem(custom_id=cid, response=resp, error=None)
            except StopIteration:
                out[cid] = BatchResultItem(custom_id=cid, response=None, error="exhausted")
        return out

    async def cancel_batch(self, batch_id):
        return None


@pytest.mark.asyncio
async def test_run_batch_group_completes_and_persists(db_session, db_session_factory, make_user):
    user = make_user(email="batch1@example.com")
    # Two report rows + run states, both finishing in write -> finalize.
    runs = []
    scripts = {}
    for subject in ("AAA.US earnings", "BBB.US earnings"):
        req = _req(subject)
        report_id = insert_report_row(
            db_session, user_id=user.id, request=req, trigger_kind="scheduled"
        )
        state = EuRunState.from_request(req, transports=_transports(), custom_id=report_id)
        runs.append((report_id, state))
        scripts[report_id] = [_write(), _finalize()]
    db_session.commit()

    collected = []
    job_id = svc.run_batch_group(
        session_factory=db_session_factory,
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        runs=runs,
        transport=FakeBatchTransport(scripts),
        spawn=lambda coro: collected.append(coro),
        poll_interval_s=0,
        max_wait_s=10_000,
    )
    await collected[0]  # drive the orchestrator to completion

    # Each report completed with its section persisted.
    for report_id, _ in runs:
        row = db_session.get(ReportEu, report_id)
        db_session.refresh(row)
        assert row.status == "completed"
        sections = (
            db_session.query(ReportEuSection).filter(ReportEuSection.report_id == report_id).all()
        )
        assert any(s.section_id == "quick_take" for s in sections)

    job = db_session.get(EuV2BatchJob, job_id)
    db_session.refresh(job)
    assert job.status == "completed"
    batch_runs = db_session.query(EuV2BatchRun).filter(EuV2BatchRun.batch_job_id == job_id).all()
    assert len(batch_runs) == 2
    assert all(br.status == "completed" for br in batch_runs)


@pytest.mark.asyncio
async def test_run_batch_group_marks_failed_run(db_session, db_session_factory, make_user):
    user = make_user(email="batch2@example.com")
    req = _req("CCC.US earnings")
    report_id = insert_report_row(
        db_session, user_id=user.id, request=req, trigger_kind="scheduled"
    )
    state = EuRunState.from_request(req, transports=_transports(), custom_id=report_id)
    db_session.commit()

    collected = []
    svc.run_batch_group(
        session_factory=db_session_factory,
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        runs=[(report_id, state)],
        transport=FakeBatchTransport({report_id: []}),  # immediate "exhausted" error
        spawn=lambda coro: collected.append(coro),
        poll_interval_s=0,
        max_wait_s=10_000,
    )
    await collected[0]

    row = db_session.get(ReportEu, report_id)
    db_session.refresh(row)
    assert row.status == "failed"
    assert row.error_message == "exhausted"


def test_run_batch_group_empty_raises(db_session_factory):
    with pytest.raises(ValueError, match="no runs"):
        svc.run_batch_group(
            session_factory=db_session_factory,
            provider_kind="anthropic",
            model="claude-sonnet-4-6",
            runs=[],
            transport=FakeBatchTransport({}),
        )


@pytest.mark.asyncio
async def test_recover_inflight_batches_resumes(db_session, db_session_factory, make_user):
    user = make_user(email="resume@example.com")
    req = _req("EEE.US earnings")
    report_id = insert_report_row(
        db_session, user_id=user.id, request=req, trigger_kind="scheduled"
    )
    # Build a mid-run state (quick_take written) and snapshot it, as the
    # checkpoint would have just before the crash.
    state = EuRunState.from_request(req, transports=_transports(), custom_id=report_id)
    state.pending_request()
    await state.apply_response(_write())
    now = datetime.now(UTC)
    db_session.add(
        EuV2BatchJob(
            id="job-r",
            provider_kind="anthropic",
            model="claude-sonnet-4-6",
            status="polling",
            provider_batch_id="batch-resumed",
            turn_index=1,
            created_at=now,
            updated_at=now,
        )
    )
    db_session.add(
        EuV2BatchRun(
            id="run-r",
            batch_job_id="job-r",
            report_id=report_id,
            custom_id=report_id,
            status="active",
            state_json=json.dumps(state.snapshot()),
            updated_at=now,
        )
    )
    db_session.commit()

    transport = FakeBatchTransport(scripts={report_id: [_finalize()]})
    transport._pending["batch-resumed"] = [report_id]  # the in-flight batch
    collected = []
    resumed = svc.recover_inflight_batches(
        session_factory=db_session_factory,
        transport_factory=lambda **kw: transport,
        transports=_transports(),
        spawn=lambda coro: collected.append(coro),
    )
    assert resumed == 1
    await collected[0]

    row = db_session.get(ReportEu, report_id)
    db_session.refresh(row)
    assert row.status == "completed"
    sections = (
        db_session.query(ReportEuSection).filter(ReportEuSection.report_id == report_id).all()
    )
    assert any(s.section_id == "quick_take" for s in sections)


def test_recover_fails_unresumable_job(db_session, db_session_factory, make_user):
    user = make_user(email="unres@example.com")
    req = _req("FFF.US earnings")
    report_id = insert_report_row(
        db_session, user_id=user.id, request=req, trigger_kind="scheduled"
    )
    now = datetime.now(UTC)
    db_session.add(
        EuV2BatchJob(
            id="job-u",
            provider_kind="anthropic",
            model="claude-sonnet-4-6",
            status="polling",
            provider_batch_id=None,  # never checkpointed -> can't resume
            turn_index=0,
            created_at=now,
            updated_at=now,
        )
    )
    db_session.add(
        EuV2BatchRun(
            id="run-u",
            batch_job_id="job-u",
            report_id=report_id,
            custom_id=report_id,
            status="active",
            state_json=None,
            updated_at=now,
        )
    )
    db_session.commit()

    resumed = svc.recover_inflight_batches(
        session_factory=db_session_factory, transports=_transports(), spawn=lambda c: c
    )
    assert resumed == 0
    assert db_session.get(EuV2BatchJob, "job-u").status == "failed"
    row = db_session.get(ReportEu, report_id)
    db_session.refresh(row)
    assert row.status == "failed"


def test_cleanup_skips_resumable_batch_reports(db_session, make_user):
    from openlia_server.services.eu_v2_run_service import cleanup_orphaned_running_rows

    user = make_user(email="cleanup@example.com")
    batch_report = insert_report_row(
        db_session, user_id=user.id, request=_req("GGG.US earnings"), trigger_kind="scheduled"
    )
    plain_report = insert_report_row(
        db_session, user_id=user.id, request=_req("HHH.US earnings"), trigger_kind="on_demand"
    )
    now = datetime.now(UTC)
    db_session.add(
        EuV2BatchJob(
            id="job-c",
            provider_kind="anthropic",
            model="claude-sonnet-4-6",
            status="polling",
            provider_batch_id="b",
            turn_index=1,
            created_at=now,
            updated_at=now,
        )
    )
    db_session.add(
        EuV2BatchRun(
            id="run-c",
            batch_job_id="job-c",
            report_id=batch_report,
            custom_id=batch_report,
            status="active",
            state_json="{}",
            updated_at=now,
        )
    )
    db_session.commit()

    cleanup_orphaned_running_rows(db=db_session)
    db_session.expire_all()
    # Batch-linked report survives (recovery will resume it); plain one fails.
    assert db_session.get(ReportEu, batch_report).status == "running"
    assert db_session.get(ReportEu, plain_report).status == "failed"


def test_mark_orphaned_batch_jobs_failed(db_session, make_user):
    user = make_user(email="orphan@example.com")
    req = _req("DDD.US earnings")
    report_id = insert_report_row(
        db_session, user_id=user.id, request=req, trigger_kind="scheduled"
    )
    now = datetime.now(UTC)
    db_session.add(
        EuV2BatchJob(
            id="job-x",
            provider_kind="anthropic",
            model="claude-sonnet-4-6",
            status="polling",
            provider_batch_id="batch-abc",
            turn_index=2,
            created_at=now,
            updated_at=now,
        )
    )
    db_session.add(
        EuV2BatchRun(
            id="run-x",
            batch_job_id="job-x",
            report_id=report_id,
            custom_id=report_id,
            status="active",
            updated_at=now,
        )
    )
    db_session.commit()

    swept = svc.mark_orphaned_batch_jobs_failed(db=db_session)
    assert swept == 1
    assert db_session.get(EuV2BatchJob, "job-x").status == "failed"
    assert db_session.get(EuV2BatchRun, "run-x").status == "failed"
    report = db_session.get(ReportEu, report_id)
    assert report.status == "failed"
    assert "restart" in report.error_message
