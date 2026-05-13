"""Graph Extraction executor (slice 6 of runtime spec).

Runs nightly per user at their preferred local-clock time. Two phases:

1. **Extraction**: walk every ``ChatSession`` the user has updated since
   the last successful run (the audit-table watermark) and ask the
   ``graph_extraction``-role LLM to produce ``user_construct`` /
   ``mention`` proposals. Each session writes its proposals through
   ``graph_extraction.extract_proposals_from_session``.
2. **Summary indexing**: walk every ``Report`` the user has saved since
   the watermark and embed its structured summary into
   ``graph_artifact_summaries`` via
   ``graph_summarization.index_report_summary``.

Audit guarantees (same two-phase commit shape as
``routes/admin_graph.py``):

- ``record_run_start`` opens a row; its session is committed before
  any work runs so a downstream crash can't roll the audit row back.
- On exception: roll back the work session, write
  ``record_run_finish(error=...)`` on a fresh session, commit, then
  re-raise. The exception still propagates so ``BaseExecutor`` marks
  the ``job_runs`` row failed.

Cancellation: the cancel token is polled between sessions and between
reports. A cancel mid-job lets already-saved proposals stand.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from typing import Any, ClassVar, Protocol

from openlia.llm.base import LLMProvider
from openlia.llm.embeddings import EmbeddingProvider
from openlia.llm.runtime.cancellation import CancellationToken
from openlia.llm.types import LLMRequest, LLMResponse
from sqlalchemy import select
from sqlalchemy.orm import Session as DBSession

from openlia_server.db.models.content import ChatSession, Report
from openlia_server.scheduler.executors.base import (
    AsyncSleep,
    BaseExecutor,
    JobOutcome,
    NotificationSpec,
    SessionFactory,
)
from openlia_server.scheduler.registry import JobType, NotificationType
from openlia_server.services import (
    graph_extraction,
    graph_extraction_llm,
    graph_extraction_runs,
    graph_summarization,
)
from openlia_server.services.adapter_llm_client import (
    AdapterLlmNotConfigured,
    _resolve_provider_for_role,
)

DEPARTMENT = "secretary"


class _SyncProviderAdapter:
    """Bridge async ``LLMProvider.generate`` to the sync ``.generate``
    signature ``make_extract_fn`` / ``make_summarize_fn`` expect.

    The extraction + summarization helpers run inside a thread (see
    ``_do_work``) so a fresh event loop is safe.
    """

    def __init__(self, provider: LLMProvider) -> None:
        self._provider = provider

    def generate(self, request: LLMRequest) -> LLMResponse:
        return asyncio.run(self._provider.generate(request))


class _ProviderFactory(Protocol):
    """Resolve a ``graph_extraction``-role ``LLMProvider`` from the DB session.

    Default factory uses ``_resolve_provider_for_role``; tests pass a fake
    that returns a deterministic provider.
    """

    def __call__(self, db: DBSession) -> LLMProvider: ...


class _EmbeddingProviderFactory(Protocol):
    """Resolve an ``EmbeddingProvider`` + model name.

    Production wiring overrides the default (which returns a
    ``FakeEmbeddingProvider``) once the user's embedding choice is
    persisted. The fake placeholder keeps the nightly job exercisable
    end-to-end without a configured embedding provider.
    """

    def __call__(self) -> tuple[EmbeddingProvider, str]: ...


def _default_provider_factory(db: DBSession) -> LLMProvider:
    return _resolve_provider_for_role(db, "graph_extraction")


def _default_embedding_factory() -> tuple[EmbeddingProvider, str]:
    from openlia.llm.embeddings import FakeEmbeddingProvider

    return FakeEmbeddingProvider(), "fake-embedding"


class GraphExtractionExecutor(BaseExecutor):
    job_type: ClassVar[JobType] = JobType.GRAPH_EXTRACTION

    def __init__(
        self,
        *,
        session_factory: SessionFactory,
        sleep: AsyncSleep | None = None,
        provider_factory: _ProviderFactory | None = None,
        embedding_factory: _EmbeddingProviderFactory | None = None,
        extract_fn_builder: Callable[[Any], graph_extraction.ExtractFn] | None = None,
        summarize_fn_builder: Callable[[Any], graph_summarization.SummarizeFn] | None = None,
    ) -> None:
        super().__init__(session_factory=session_factory, sleep=sleep)
        self._provider_factory = provider_factory or _default_provider_factory
        self._embedding_factory = embedding_factory or _default_embedding_factory
        self._extract_fn_builder = extract_fn_builder or graph_extraction_llm.make_extract_fn
        self._summarize_fn_builder = (
            summarize_fn_builder or graph_summarization.make_summarize_fn
        )

    async def _do_work(
        self,
        *,
        user_id: str | None,
        schedule_id: str | None,
        run_id: str,
        cancel_token: CancellationToken | None,
    ) -> JobOutcome:
        assert user_id is not None

        # 1. Resolve provider. Missing config → clean failure with audit row.
        with self._session_factory() as session:
            try:
                provider = self._provider_factory(session)
            except AdapterLlmNotConfigured as exc:
                # Record an audit row noting the misconfiguration so the
                # admin UI can surface it, then re-raise so the executor
                # marks the JobRun as failed.
                run = graph_extraction_runs.record_run_start(
                    session, user_id=user_id, model_id="(unconfigured)"
                )
                graph_extraction_runs.record_run_finish(
                    session, run_id=run.id, error=str(exc)[:256]
                )
                session.commit()
                raise
            model_id = provider.model

        client = _SyncProviderAdapter(provider)
        extract_fn = self._extract_fn_builder(client)
        summarize_fn = self._summarize_fn_builder(client)
        embed_provider, embed_model_name = self._embedding_factory()

        # 2. Open audit row. Commit before any work so a crash can't
        # roll the row back.
        with self._session_factory() as session:
            audit_run = graph_extraction_runs.record_run_start(
                session, user_id=user_id, model_id=model_id
            )
            audit_run_id = audit_run.id
            watermark = graph_extraction_runs.high_watermark(session, user_id=user_id)
            session.commit()

        proposals_inserted = 0
        sessions_processed = 0
        reports_indexed = 0

        try:
            proposals_inserted, sessions_processed = self._run_extraction_phase(
                user_id=user_id,
                watermark=watermark,
                extract_fn=extract_fn,
                cancel_token=cancel_token,
            )
            reports_indexed = self._run_summary_phase(
                user_id=user_id,
                watermark=watermark,
                summarize_fn=summarize_fn,
                embed_provider=embed_provider,
                embed_model_name=embed_model_name,
                cancel_token=cancel_token,
            )
        except Exception as exc:
            with self._session_factory() as finish_session:
                finish_session.rollback()
                graph_extraction_runs.record_run_finish(
                    finish_session,
                    run_id=audit_run_id,
                    proposals_inserted=proposals_inserted,
                    sessions_processed=sessions_processed,
                    error=str(exc)[:256],
                )
                finish_session.commit()
            raise

        # 3. Success: close the audit row.
        with self._session_factory() as finish_session:
            graph_extraction_runs.record_run_finish(
                finish_session,
                run_id=audit_run_id,
                proposals_inserted=proposals_inserted,
                sessions_processed=sessions_processed,
            )
            finish_session.commit()

        return JobOutcome(
            result_summary={
                "audit_run_id": audit_run_id,
                "proposals_inserted": proposals_inserted,
                "sessions_processed": sessions_processed,
                "reports_indexed": reports_indexed,
            },
            notifications=[
                NotificationSpec(
                    type=NotificationType.REPORT_READY,
                    department=DEPARTMENT,
                    message=(
                        f"Memory updated: {proposals_inserted} proposal(s) "
                        f"from {sessions_processed} session(s), "
                        f"{reports_indexed} report(s) indexed."
                    ),
                )
            ]
            if proposals_inserted or reports_indexed
            else [],
        )

    def _run_extraction_phase(
        self,
        *,
        user_id: str,
        watermark: Any,
        extract_fn: graph_extraction.ExtractFn,
        cancel_token: CancellationToken | None,
    ) -> tuple[int, int]:
        proposals_inserted = 0
        sessions_processed = 0

        # Identify session ids first so the per-session DB session is
        # short-lived (avoids holding a stale cursor across LLM calls).
        with self._session_factory() as ids_session:
            stmt = select(ChatSession.id).where(ChatSession.user_id == user_id)
            if watermark is not None:
                stmt = stmt.where(ChatSession.updated_at > watermark)
            session_ids = [sid for (sid,) in ids_session.execute(stmt).all()]

        for sid in session_ids:
            if cancel_token is not None and cancel_token.is_cancelled:
                break
            with self._session_factory() as work:
                try:
                    rows = graph_extraction.extract_proposals_from_session(
                        work,
                        session_id=sid,
                        user_id=user_id,
                        extract_fn=extract_fn,
                    )
                    work.commit()
                except Exception:
                    work.rollback()
                    raise
            proposals_inserted += len(rows)
            sessions_processed += 1

        return proposals_inserted, sessions_processed

    def _run_summary_phase(
        self,
        *,
        user_id: str,
        watermark: Any,
        summarize_fn: graph_summarization.SummarizeFn,
        embed_provider: EmbeddingProvider,
        embed_model_name: str,
        cancel_token: CancellationToken | None,
    ) -> int:
        with self._session_factory() as ids_session:
            stmt = select(Report.id).where(Report.user_id == user_id)
            if watermark is not None:
                stmt = stmt.where(Report.updated_at > watermark)
            report_ids = [rid for (rid,) in ids_session.execute(stmt).all()]

        indexed = 0
        for rid in report_ids:
            if cancel_token is not None and cancel_token.is_cancelled:
                break
            with self._session_factory() as work:
                report = work.get(Report, rid)
                if report is None:
                    continue
                try:
                    graph_summarization.index_report_summary(
                        work,
                        user_id=user_id,
                        report=report,
                        summarize_fn=summarize_fn,
                        embed_provider=embed_provider,
                        embed_model_name=embed_model_name,
                    )
                    work.commit()
                except Exception:
                    work.rollback()
                    raise
            indexed += 1

        return indexed


__all__ = [
    "GraphExtractionExecutor",
]
