"""MRAssessmentBuilder implementation — T4 batch items + T5 synthesizer."""

from __future__ import annotations

import hashlib
import json
from typing import Any

from openlia.llm.runtime.messages import BatchItem, BatchResult, ReportRequest
from openlia.macro_research.dashboards import DASHBOARDS
from pydantic import BaseModel
from sqlalchemy.orm import Session

from openlia_server.scheduler.payloads import MRAssessmentPayload


class T4Output(BaseModel):
    stage: str | None = None
    severity: str | None = None
    assessment: str = ""
    notes: list[str] = []


class MRAssessmentBuilderImpl:
    """Builds the batch payload that MRAssessmentExecutor feeds to BatchRunner.

    NOTE: MR runtime data wiring is a follow-up after the connector cutover;
    until then, T4 batch items are emitted with empty `inputs` context.
    """

    def __init__(self) -> None:
        pass

    def build(self, *, session: Session, user_id: str) -> MRAssessmentPayload:
        items: list[BatchItem] = []

        for slug, dashboard in DASHBOARDS.items():
            if dashboard.T4_PROMPT_KEY is None:
                continue
            context_data: dict[str, Any] = {}
            items.append(
                BatchItem(
                    id=slug,
                    context={
                        "dashboard": slug,
                        "user_id": user_id,
                        "prompt_key": f"macro_research/{dashboard.T4_PROMPT_KEY}",
                        "inputs": context_data,
                    },
                )
            )

        def synthesize(results: list[BatchResult]) -> ReportRequest:
            ok = [r for r in results if r.ok]
            summary_lines = [f"{r.id}: {json.dumps(r.data, default=str)[:500]}" for r in ok]
            user_input = "\n".join(summary_lines) or "(no T4 results available)"
            return ReportRequest(
                mode="synthesis",
                user_input=user_input,
                enabled_sections=[],
                custom_sections=[],
                length="long",
            )

        return MRAssessmentPayload(
            items=items,
            t4_task="mr_t4",
            t4_schema=T4Output,
            synthesize=synthesize,
        )

    @staticmethod
    def input_hash(payload: dict[str, Any]) -> str:
        raw = json.dumps(payload, sort_keys=True, default=str).encode()
        return hashlib.sha256(raw).hexdigest()
