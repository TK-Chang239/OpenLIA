"""PLAN stage — produces the Outline that drives RESEARCH.

Each `OutlineSection.data_needs` becomes RESEARCH's targeted work queue,
so the value of this stage is in the *specificity* of those needs:
"gross margin trend, last 8 quarters" beats "financial detail."

Outline *structure* (section list, ids, titles, order) belongs to the
user template, not the LLM. `_coerce_outline_to_template` rebuilds the
section list from `state.template` after the planner returns, so even
if the LLM drops, reorders, or invents a section, the template's
structure is restored.

Outline *run scope* (tickers, report_type) belongs to the run, not the
LLM either. PlanStage.run overwrites both fields from `state` after the
planner returns — the LLM cannot widen the ticker list or change the
report type, and PLAN's correctness does not depend on the planner
copying those fields verbatim from the prompt's worked-example (a
model under load will lift the example's literal `"initiation"` even
when the run is for an `update`).

The LLM's authoring role shrinks to data_needs, fact_ids, and the
valuation plan.
"""

from __future__ import annotations

from ..clients.planner import PlannerClient, PlannerRequest
from ..schemas import Outline, OutlineSection
from ..slots import V23Slot
from ..state import ReportState
from ..templates import TemplateSpec
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
            template=state.template,
            clarify_result=state.clarify_result,
        )
        outline = self._client.plan(request)
        outline = _coerce_outline_to_template(outline, state.template)
        # Engine owns run scope — the LLM's value for these fields is
        # ignored. The prompt's worked-example includes literal values
        # for shape clarity, which a model under load happily lifts
        # verbatim (e.g. emitting report_type="initiation" on an
        # `update` run because the example shows it). Coercing here
        # decouples PLAN's correctness from prompt compliance.
        outline = outline.model_copy(
            update={
                "tickers": list(state.tickers),
                "report_type": state.report_type,
            }
        )
        self._validate_outline(outline)
        state.outline = outline
        return state

    @staticmethod
    def _validate_outline(outline: Outline) -> None:
        if not outline.sections:
            raise RuntimeError("Outline has no sections — PLAN must emit at least one.")

        section_ids = [s.id for s in outline.sections]
        if len(section_ids) != len(set(section_ids)):
            duplicates = sorted({sid for sid in section_ids if section_ids.count(sid) > 1})
            raise RuntimeError(f"Outline has duplicate section ids: {duplicates}")


def _coerce_outline_to_template(outline: Outline, template: TemplateSpec) -> Outline:
    """Rebuild outline.sections from template.sections, preserving the
    LLM's per-section data_needs where the section ids match.

    The engine owns structure; the LLM owns content. If the LLM drops,
    reorders, or invents a section, the coercer restores the template's
    structure and carries the LLM's data_needs (and the fact_ids inside
    them) forward for the sections whose ids the LLM honored. Sections
    the LLM dropped come back with an empty data_needs list — RESEARCH
    still fires but with no targeted hint.
    """
    llm_section_by_id: dict[str, OutlineSection] = {s.id: s for s in outline.sections}
    coerced_sections = [
        OutlineSection(
            id=spec.id,
            title=spec.title,
            section_type=(
                llm_section_by_id[spec.id].section_type if spec.id in llm_section_by_id else None
            ),
            data_needs=list(llm_section_by_id[spec.id].data_needs)
            if spec.id in llm_section_by_id
            else [],
        )
        for spec in template.sections
    ]
    return outline.model_copy(update={"sections": coerced_sections})
