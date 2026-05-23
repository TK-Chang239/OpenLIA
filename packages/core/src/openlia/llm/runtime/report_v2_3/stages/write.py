"""WRITE stage — section-by-section drafting against the shared thesis.

Iterates `thesis.mandates` and asks the writer client for one
`WrittenSection` per mandate. Every writer call sees the *same* thesis,
which is what makes parallel-shape writing cohere instead of drift; only
the per-section slice of bundle + chart specs is filtered down.

After each call we enforce placeholder discipline:
- ``{{CITE:<fact_id>}}`` ids must be a subset of the mandate's
  `relevant_fact_ids` (the writer cannot pull facts outside its slice).
- ``{{FIG:<chart_id>}}`` ids must be a subset of the mandate's
  `chart_ids` (the writer cannot reference a chart it was not given).

On a VERIFY-driven retry, `state.verify_result` is forwarded to the
client so the rewrite has the critique it must address. Sections that
were not flagged still get re-generated for simplicity — bounded retry
keeps this cheap (one rewrite per run at most).
"""

from __future__ import annotations

from ..clients.writer import WriterClient, WriterRequest
from ..schemas import (
    ChartSpec,
    ReportThesis,
    SectionMandate,
    VerifyIssue,
    WrittenSection,
)
from ..slots import V23Slot
from ..state import ReportState
from .base import Stage, StageContext


class WriteStage(Stage):
    slot = V23Slot.WRITE

    def __init__(self, client: WriterClient) -> None:
        self._client = client

    def run(self, state: ReportState, ctx: StageContext) -> ReportState:
        thesis = self._require_thesis(state)
        if state.bundle is None:
            raise RuntimeError("WRITE requires state.bundle.")

        prior_by_section: dict[str, WrittenSection] = {
            s.section_id: s for s in state.sections
        }
        critique_by_section: dict[str, list[VerifyIssue]] = (
            self._group_critique(state) if state.verify_result is not None else {}
        )
        chart_by_section: dict[str, list[ChartSpec]] = self._group_charts(thesis)

        new_sections: list[WrittenSection] = []
        for mandate in thesis.mandates:
            relevant_facts = {
                fid: state.bundle.facts[fid]
                for fid in mandate.relevant_fact_ids
                if fid in state.bundle.facts
            }
            request = WriterRequest(
                section_mandate=mandate,
                thesis=thesis,
                language=state.language,
                relevant_facts=relevant_facts,
                assigned_charts=chart_by_section.get(mandate.section_id, []),
                prior_attempt=prior_by_section.get(mandate.section_id),
                critique=critique_by_section.get(mandate.section_id),
            )
            section = self._client.write(request)
            self._validate_section(section, mandate)
            new_sections.append(section)

        state.sections = new_sections
        return state

    # ------------------------------------------------------------------
    @staticmethod
    def _require_thesis(state: ReportState) -> ReportThesis:
        if state.thesis is None:
            raise RuntimeError("WRITE requires state.thesis from SYNTHESIZE.")
        return state.thesis

    @staticmethod
    def _group_charts(thesis: ReportThesis) -> dict[str, list[ChartSpec]]:
        out: dict[str, list[ChartSpec]] = {}
        for chart in thesis.charts:
            out.setdefault(chart.section_id, []).append(chart)
        return out

    @staticmethod
    def _group_critique(state: ReportState) -> dict[str, list[VerifyIssue]]:
        assert state.verify_result is not None
        out: dict[str, list[VerifyIssue]] = {}
        for issue in state.verify_result.issues:
            if issue.section_id is not None:
                out.setdefault(issue.section_id, []).append(issue)
        return out

    @staticmethod
    def _validate_section(section: WrittenSection, mandate: SectionMandate) -> None:
        if section.section_id != mandate.section_id:
            raise RuntimeError(
                f"Writer returned section_id '{section.section_id}' "
                f"for mandate '{mandate.section_id}'."
            )

        cited = set(section.cited_fact_ids())
        allowed_facts = set(mandate.relevant_fact_ids)
        bad_cites = cited - allowed_facts
        if bad_cites:
            raise RuntimeError(
                f"Section '{section.section_id}' cites facts outside its mandate: "
                f"{sorted(bad_cites)}"
            )

        figs = set(section.figure_ids())
        allowed_figs = set(mandate.chart_ids)
        bad_figs = figs - allowed_figs
        if bad_figs:
            raise RuntimeError(
                f"Section '{section.section_id}' references charts outside its "
                f"mandate: {sorted(bad_figs)}"
            )
