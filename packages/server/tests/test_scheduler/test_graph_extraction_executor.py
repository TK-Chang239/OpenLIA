"""Slice 6 (runtime spec) — nightly graph-extraction executor tests."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from _scheduler_fakes import FakeSleep
from openlia.llm.embeddings import FakeEmbeddingProvider
from openlia_server.db.models.auth import User
from openlia_server.db.models.content import ChatMessage, ChatSession, Report
from openlia_server.db.models.graph import (
    GraphArtifactSummary,
    GraphExtractionProposal,
    GraphExtractionRun,
)
from openlia_server.db.models.scheduler import JobRun
from openlia_server.scheduler.executors.graph_extraction import GraphExtractionExecutor
from openlia_server.scheduler.registry import JobStatus
from openlia_server.services.adapter_llm_client import AdapterLlmNotConfigured
from sqlalchemy import select

# ----------------------------------------------------------------------
# Helpers
# ----------------------------------------------------------------------


class _FakeProvider:
    model = "fake-quick"

    async def generate(self, request):  # pragma: no cover - not used directly
        raise AssertionError("FakeProvider.generate should not be called; tests stub extract/summarize fns")


def _resolve_fake_provider(_db) -> Any:
    return _FakeProvider()


def _raise_not_configured(_db) -> Any:
    raise AdapterLlmNotConfigured("no model configured")


def _embedding_factory() -> tuple[Any, str]:
    return FakeEmbeddingProvider(), "fake-embedding"


def _seed_user(session, user_id: str = "u_1") -> None:
    session.add(
        User(
            id=user_id,
            email=f"{user_id}@e.com",
            display_name=user_id,
            password_hash="h",
            is_admin=False,
            is_disabled=False,
        )
    )


def _seed_chat_session(
    session,
    *,
    sid: str,
    user_id: str,
    updated_at: datetime | None = None,
) -> None:
    cs = ChatSession(
        id=sid,
        user_id=user_id,
        department="secretary",
        title="t",
    )
    session.add(cs)
    session.flush()
    # ChatMessage so extract_proposals_from_session has something to work on.
    session.add(
        ChatMessage(
            id=f"{sid}_m1",
            session_id=sid,
            role="user",
            content="GPU shortages will lift NVDA margins",
            created_at=datetime.now(UTC),
        )
    )
    if updated_at is not None:
        cs.updated_at = updated_at
    session.flush()


def _seed_report(
    session,
    *,
    rid: str,
    user_id: str,
    updated_at: datetime | None = None,
) -> None:
    rep = Report(
        id=rid,
        user_id=user_id,
        department="morning_briefing",
        report_type="briefing",
        title="t",
        subject="NVDA",
        content_markdown="body",
        content_structured={"sections": []},
        model_ref="x",
    )
    session.add(rep)
    session.flush()
    if updated_at is not None:
        rep.updated_at = updated_at
    session.flush()


def _build_executor(
    *,
    session_factory,
    provider_factory=None,
    summary_provider_factory=None,
    extract_results: list[list[dict]] | None = None,
    summarize_result: dict | None = None,
) -> tuple[GraphExtractionExecutor, dict]:
    """Build an executor wired with fake extract / summarize fns.

    Returns (executor, call_log) where call_log is a dict tracking how
    many times each fn was invoked so tests can assert per-session and
    per-report progression.
    """
    extract_queue: list[list[dict]] = list(extract_results or [])
    log: dict[str, list] = {"extract_calls": [], "summarize_calls": []}

    def _extract_builder(_client):
        def _extract(messages):
            log["extract_calls"].append([m.id for m in messages])
            if extract_queue:
                return extract_queue.pop(0)
            return []

        return _extract

    def _summarize_builder(_client):
        def _summarize(report):
            log["summarize_calls"].append(report.id)
            return summarize_result or {
                "subject": "NVDA",
                "tagline": "Long",
                "findings": ["margins up"],
                "entities_mentioned": ["ticker:NVDA"],
                "tone": "bullish",
                "horizon": "medium",
            }

        return _summarize

    ex = GraphExtractionExecutor(
        session_factory=session_factory,
        sleep=FakeSleep(),
        provider_factory=provider_factory or _resolve_fake_provider,
        summary_provider_factory=summary_provider_factory or _resolve_fake_provider,
        embedding_factory=_embedding_factory,
        extract_fn_builder=_extract_builder,
        summarize_fn_builder=_summarize_builder,
    )
    return ex, log


# ----------------------------------------------------------------------
# Happy path
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_extracts_proposals_and_indexes_reports_for_eligible_artifacts(
    session_factory,
) -> None:
    with session_factory() as s:
        _seed_user(s)
        _seed_chat_session(s, sid="cs_1", user_id="u_1")
        _seed_report(s, rid="r_1", user_id="u_1")
        s.commit()

    ex, log = _build_executor(
        session_factory=session_factory,
        extract_results=[
            [
                {
                    "kind": "user_construct",
                    "payload": {
                        "construct_kind": "belief",
                        "statement": "AI capex remains durable",
                        "entity_kind": "theme",
                        "entity_value": "ai-capex",
                        "source_excerpt": "GPU shortages",
                    },
                }
            ]
        ],
    )
    run_id = await ex.execute(user_id="u_1", schedule_id=None)

    with session_factory() as s:
        job = s.get(JobRun, run_id)
        assert job.status == JobStatus.COMPLETED.value
        # Audit row recorded the work.
        audit_rows = list(s.execute(select(GraphExtractionRun)).scalars())
        assert len(audit_rows) == 1
        audit = audit_rows[0]
        assert audit.error is None
        assert audit.finished_at is not None
        assert audit.proposals_inserted == 1
        assert audit.sessions_processed == 1
        # Proposal persisted.
        assert s.query(GraphExtractionProposal).count() == 1
        # Report summary persisted.
        summaries = list(s.execute(select(GraphArtifactSummary)).scalars())
        assert len(summaries) == 1
        assert summaries[0].subject == "NVDA"

    assert len(log["extract_calls"]) == 1
    assert len(log["summarize_calls"]) == 1


# ----------------------------------------------------------------------
# Watermark filtering
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_watermark_skips_artifacts_older_than_last_success(
    session_factory,
) -> None:
    # Prior successful run advances the watermark. Seed an audit row,
    # then a session updated BEFORE it (must be skipped) + a session
    # updated AFTER it (must be processed).
    earlier = datetime.now(UTC) - timedelta(hours=2)
    watermark = datetime.now(UTC) - timedelta(hours=1)
    later = datetime.now(UTC)

    with session_factory() as s:
        _seed_user(s)
        prev = GraphExtractionRun(
            id="prev_run",
            user_id="u_1",
            started_at=watermark,
            model_id="m",
        )
        prev.finished_at = watermark
        prev.error = None
        s.add(prev)
        _seed_chat_session(s, sid="cs_old", user_id="u_1", updated_at=earlier)
        _seed_chat_session(s, sid="cs_new", user_id="u_1", updated_at=later)
        _seed_report(s, rid="r_old", user_id="u_1", updated_at=earlier)
        _seed_report(s, rid="r_new", user_id="u_1", updated_at=later)
        s.commit()

    ex, log = _build_executor(
        session_factory=session_factory,
        extract_results=[[]],
    )
    await ex.execute(user_id="u_1", schedule_id=None)

    # Extract should have been called once (cs_new only).
    assert len(log["extract_calls"]) == 1
    assert len(log["summarize_calls"]) == 1


# ----------------------------------------------------------------------
# AdapterLlmNotConfigured records an audit row + fails the job
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_llm_config_records_audit_and_fails_job(
    session_factory,
) -> None:
    with session_factory() as s:
        _seed_user(s)
        s.commit()

    ex, _ = _build_executor(
        session_factory=session_factory,
        provider_factory=_raise_not_configured,
    )
    run_id = await ex.execute(user_id="u_1", schedule_id=None)

    with session_factory() as s:
        job = s.get(JobRun, run_id)
        assert job.status == JobStatus.FAILED.value
        audit_rows = list(s.execute(select(GraphExtractionRun)).scalars())
        assert len(audit_rows) == 1
        assert audit_rows[0].error is not None
        assert "no model configured" in audit_rows[0].error


# ----------------------------------------------------------------------
# Exception in extraction loop preserves the audit row
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_exception_in_loop_writes_audit_finish_with_error(
    session_factory,
) -> None:
    with session_factory() as s:
        _seed_user(s)
        _seed_chat_session(s, sid="cs_1", user_id="u_1")
        s.commit()

    def _bad_extract_builder(_client):
        def _extract(_messages):
            raise RuntimeError("kaboom")

        return _extract

    ex = GraphExtractionExecutor(
        session_factory=session_factory,
        sleep=FakeSleep(),
        provider_factory=_resolve_fake_provider,
        summary_provider_factory=_resolve_fake_provider,
        embedding_factory=_embedding_factory,
        extract_fn_builder=_bad_extract_builder,
    )
    run_id = await ex.execute(user_id="u_1", schedule_id=None)

    with session_factory() as s:
        job = s.get(JobRun, run_id)
        assert job.status == JobStatus.FAILED.value
        assert "kaboom" in (job.error_message or "")
        audit_rows = list(s.execute(select(GraphExtractionRun)).scalars())
        # Audit row survived the exception.
        assert len(audit_rows) == 1
        assert audit_rows[0].error is not None
        assert "kaboom" in audit_rows[0].error
        assert audit_rows[0].finished_at is not None


# ----------------------------------------------------------------------
# Cancellation between sessions
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancel_between_sessions_stops_processing(session_factory) -> None:
    with session_factory() as s:
        _seed_user(s)
        for i in range(3):
            _seed_chat_session(s, sid=f"cs_{i}", user_id="u_1")
        s.commit()

    from openlia.llm.runtime.cancellation import CancellationToken

    token = CancellationToken()

    call_count = {"n": 0}

    def _extract_builder(_client):
        def _extract(_messages):
            call_count["n"] += 1
            if call_count["n"] >= 1:
                token.cancel()
            return []

        return _extract

    ex = GraphExtractionExecutor(
        session_factory=session_factory,
        sleep=FakeSleep(),
        provider_factory=_resolve_fake_provider,
        summary_provider_factory=_resolve_fake_provider,
        embedding_factory=_embedding_factory,
        extract_fn_builder=_extract_builder,
    )
    await ex.execute(user_id="u_1", schedule_id=None, cancel_token=token)

    # First call ran; cancel triggered between sessions; remaining 2 skipped.
    assert call_count["n"] == 1


# ----------------------------------------------------------------------
# Extraction and summarization resolve via distinct system_role slots
# ----------------------------------------------------------------------


@pytest.mark.asyncio
async def test_summary_phase_resolves_graph_summarization_role(
    session_factory,
) -> None:
    """Summary phase must call its own provider factory, not reuse the
    extraction provider. Default factories route to ``graph_extraction``
    and ``graph_summarization`` system roles respectively.
    """
    with session_factory() as s:
        _seed_user(s)
        _seed_chat_session(s, sid="cs_1", user_id="u_1")
        _seed_report(s, rid="r_1", user_id="u_1")
        s.commit()

    calls: list[str] = []

    class _ExtractProvider:
        model = "extract-model"

        async def generate(self, request):  # pragma: no cover
            raise AssertionError("not used")

    class _SummaryProvider:
        model = "summary-model"

        async def generate(self, request):  # pragma: no cover
            raise AssertionError("not used")

    def _extract_factory(_db) -> Any:
        calls.append("extract")
        return _ExtractProvider()

    def _summary_factory(_db) -> Any:
        calls.append("summary")
        return _SummaryProvider()

    log: dict[str, list] = {"extract_clients": [], "summarize_clients": []}

    def _extract_builder(client):
        log["extract_clients"].append(client)

        def _extract(_messages):
            return []

        return _extract

    def _summarize_builder(client):
        log["summarize_clients"].append(client)

        def _summarize(_report):
            return {
                "subject": "NVDA",
                "tagline": "Long",
                "findings": ["margins up"],
                "entities_mentioned": ["ticker:NVDA"],
                "tone": "bullish",
                "horizon": "medium",
            }

        return _summarize

    ex = GraphExtractionExecutor(
        session_factory=session_factory,
        sleep=FakeSleep(),
        provider_factory=_extract_factory,
        summary_provider_factory=_summary_factory,
        embedding_factory=_embedding_factory,
        extract_fn_builder=_extract_builder,
        summarize_fn_builder=_summarize_builder,
    )
    await ex.execute(user_id="u_1", schedule_id=None)

    assert "extract" in calls
    assert "summary" in calls
    # Distinct clients wrap distinct providers.
    assert len(log["extract_clients"]) == 1
    assert len(log["summarize_clients"]) == 1
    assert log["extract_clients"][0] is not log["summarize_clients"][0]


def test_default_summary_provider_factory_targets_graph_summarization_role() -> None:
    """The default factory must route summarization through the
    ``graph_summarization`` system role slot (not ``graph_extraction``)."""
    from openlia_server.scheduler.executors import graph_extraction as mod

    captured: dict[str, str] = {}

    def _fake_resolver(_db, role_id: str):
        captured["role_id"] = role_id
        return object()

    import openlia_server.scheduler.executors.graph_extraction as gx_mod

    original = gx_mod._resolve_provider_for_role
    gx_mod._resolve_provider_for_role = _fake_resolver
    try:
        mod._default_summary_provider_factory(object())
    finally:
        gx_mod._resolve_provider_for_role = original

    assert captured["role_id"] == "graph_summarization"
