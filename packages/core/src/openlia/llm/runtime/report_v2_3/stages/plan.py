"""PLAN stage — produces the Outline that drives RESEARCH.

Each `OutlineSection.data_needs` becomes RESEARCH's targeted work queue,
so the value of this stage is in the *specificity* of those needs:
"gross margin trend, last 8 quarters" beats "financial detail."

Validation here keeps cross-stage state aligned: the planner cannot
silently widen the scope (different tickers, different report type) or
return an empty outline that would leave RESEARCH with no work to do.
"""

from __future__ import annotations

from ..clients.planner import PlannerClient, PlannerRequest
from ..schemas import Outline
from ..slots import V23Slot
from ..state import ReportState
from .base import Stage, StageContext


class PlanStage(Stage):
    slot = V23Slot.PLAN

    def __init__(self, client: PlannerClient) -> None:
        self._client = client

    def run(self, state: ReportState, ctx: StageContext) -> ReportState:
        request = PlannerRequest(
            raw_prompt=state.raw_prompt,
            language=state.language,
            report_type=state.report_type,
            tickers=list(state.tickers),
            clarify_result=state.clarify_result,
        )
        outline = self._client.plan(request)
        self._validate_outline(outline, state)
        state.outline = outline
        return state

    @staticmethod
    def _validate_outline(outline: Outline, state: ReportState) -> None:
        if outline.tickers != state.tickers:
            raise RuntimeError(
                f"Outline tickers {outline.tickers} do not match run tickers {state.tickers}."
            )
        if outline.report_type != state.report_type:
            raise RuntimeError(
                f"Outline report_type {outline.report_type} does not match run "
                f"report_type {state.report_type}."
            )
        if not outline.sections:
            raise RuntimeError("Outline has no sections — PLAN must emit at least one.")

        section_ids = [s.id for s in outline.sections]
        if len(section_ids) != len(set(section_ids)):
            duplicates = sorted({sid for sid in section_ids if section_ids.count(sid) > 1})
            raise RuntimeError(f"Outline has duplicate section ids: {duplicates}")
