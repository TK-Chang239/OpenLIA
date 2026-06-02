"""Macro Research assessment executor.

Chains BatchRunner (T4, per-metric analyses) -> mr_builder.synthesize()
-> ReportRunner (T5, synthesis). Persists the combined result into
mr_assessment_cache and emits one `assessment_ready` notification."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, ClassVar

from openlia.llm.runtime.cancellation import CancellationToken
from openlia.llm.runtime.events import ReportComplete, ReportError
from openlia.llm.runtime.messages import BatchResult, ReportRequest

from openlia_server.scheduler.executors.base import (
    AsyncSleep,
    BaseExecutor,
    JobOutcome,
    NotificationSpec,
    SessionFactory,
    raise_from_report_error,
)
from openlia_server.scheduler.payloads import MRAssessmentBuilder, MRCacheStore
from openlia_server.scheduler.registry import JobType, NotificationType

DEPARTMENT = "macro_research"


def _serialize_batch_result(r: BatchResult) -> dict[str, Any]:
    return asdict(r)


class MRAssessmentExecutor(BaseExecutor):
    job_type: ClassVar[JobType] = JobType.MR_ASSESSMENT

    def __init__(
        self,
        *,
        session_factory: SessionFactory,
        mr_builder: MRAssessmentBuilder,
        batch_runner: Any,
        report_runner: Any,
        mr_cache_store: MRCacheStore,
        sleep: AsyncSleep | None = None,
    ) -> None:
        super().__init__(session_factory=session_factory, sleep=sleep)
        self._mr_builder = mr_builder
        self._batch_runner = batch_runner
        self._report_runner = report_runner
        self._mr_cache_store = mr_cache_store
        # Cached T4 results — populated on first successful BatchRunner call so
        # transient T5 retries skip re-running T4.
        self._cached_t4: tuple[list[BatchResult], ReportRequest] | None = None

    async def _do_work(
        self,
        *,
        user_id: str | None,
        schedule_id: str | None,
        run_id: str,
        cancel_token: CancellationToken | None,
    ) -> JobOutcome:
        assert user_id is not None
        assert schedule_id is not None
        dashboard = schedule_id  # MR jobs are keyed by dashboard name, not a schedule row ID

        if self._cached_t4 is not None:
            batch_results, synth_request = self._cached_t4
        else:
            with self._session_factory() as session:
                payload = self._mr_builder.build(session=session, user_id=user_id)

            batch_results = await self._batch_runner.run(
                department_id=DEPARTMENT,
                task=payload.t4_task,
                items=payload.items,
                schema=payload.t4_schema,
                user_id=user_id,
            )

            synth_request = payload.synthesize(batch_results)
            self._cached_t4 = (batch_results, synth_request)

        t5_schema: dict[str, Any] | None = None
        async for event in self._report_runner.run(
            department_id=DEPARTMENT,
            user_id=user_id,
            request=synth_request,
            cancel_token=cancel_token,
        ):
            if isinstance(event, ReportError):
                raise_from_report_error(event)
            if isinstance(event, ReportComplete):
                t5_schema = event.schema

        if t5_schema is None:
            raise RuntimeError(
                f"ReportRunner returned without ReportComplete for "
                f"MR assessment (dashboard={dashboard!r})"
            )

        cache_payload = {
            "dashboard": dashboard,
            "t4": [_serialize_batch_result(r) for r in batch_results],
            "t5": t5_schema,
        }
        with self._session_factory() as session:
            cache_id = self._mr_cache_store.save(
                session=session,
                user_id=user_id,
                payload=cache_payload,
            )
            session.commit()

        return JobOutcome(
            result_summary={"cache_id": cache_id, "dashboard": dashboard},
            notifications=[
                NotificationSpec(
                    type=NotificationType.ASSESSMENT_READY,
                    department=DEPARTMENT,
                    message=f"New {dashboard} assessment ready.",
                )
            ],
        )
