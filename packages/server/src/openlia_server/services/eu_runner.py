"""On-demand Earnings Update report orchestrator.

Wraps `ReportRunner.run()` with EU-specific defaults:
- Pulls the user's EU config (sections + length + custom sections).
- Builds a `ReportRequest` with mode="earnings_analysis".
- Forwards every SSE event to the caller.
- Persists the report on `ReportComplete`.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from openlia.llm.runtime.events import ReportComplete, SseEvent
from openlia.llm.runtime.messages import ReportRequest
from sqlalchemy.orm import Session

from openlia_server.services import eu_config as eu_config_svc

_LENGTH_MAP = {"concise": "brief", "normal": "standard", "elaborative": "long"}


class ReportRunnerLike(Protocol):
    async def run(
        self, *, department_id: str, user_id: str, request: ReportRequest,
    ) -> AsyncIterator[SseEvent]: ...


class ReportStoreLike(Protocol):
    def save_from_event(
        self, *, user_id: str, department: str, report_type: str, event: ReportComplete,
    ) -> str: ...


async def run_on_demand(
    *,
    session: Session,
    user_id: str,
    ticker: str,
    report_runner: ReportRunnerLike,
    report_store: ReportStoreLike,
) -> AsyncIterator[SseEvent]:
    t = ticker.strip().upper()
    if not t:
        raise ValueError("ticker required")

    cfg = eu_config_svc.get_config(session, user_id=user_id)
    request = ReportRequest(
        mode="earnings_analysis",
        user_input=(
            f"Generate an earnings analysis report for {t} "
            "on its most recent earnings release."
        ),
        enabled_sections=list(cfg.enabled_section_ids),
        custom_sections=list(cfg.custom_sections),
        length=_LENGTH_MAP.get(cfg.report_length, "standard"),
    )

    async for event in report_runner.run(
        department_id="earnings_update", user_id=user_id, request=request,
    ):
        yield event
        if isinstance(event, ReportComplete):
            report_store.save_from_event(
                user_id=user_id, department="earnings_update",
                report_type="earnings_update", event=event,
            )
