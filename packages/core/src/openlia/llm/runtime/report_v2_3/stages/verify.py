"""VERIFY stage — last gate before ASSEMBLE.

Two layers of checks, cheap-to-expensive:

1. **Deterministic** (in Python, no LLM call):
   - `dangling_cite` — a `{{CITE:fact_id}}` whose fact_id is absent
     from the bundle. Should not happen in normal flow (PR5 WriteStage
     and PR4 SynthesizeStage both validate against this), but worth
     a defense-in-depth pass.
   - `broken_fig_ref` — a `{{FIG:chart_id}}` whose chart_id is absent
     from thesis.charts.

2. **LLM-driven**: pass thesis + bundle + sections to the verifier
   client for coherence-level checks (`value_mismatch`,
   `cross_section_contradiction`, `redundancy`, `chart_text_mismatch`,
   `uncited_number`). The client returns a `VerifyResult`; we merge
   it with the deterministic findings into the final result on state.

The runner reads `state.verify_result.must_rewrite` and routes the
offending sections back to WRITE for one bounded retry.
"""

from __future__ import annotations

from ..clients.verifier import VerifierClient, VerifierRequest
from ..schemas import (
    IssueKind,
    IssueSeverity,
    ReportThesis,
    ResearchBundle,
    VerifyIssue,
    VerifyResult,
    WrittenSection,
)
from ..slots import V23Slot
from ..state import ReportState
from .base import Stage, StageContext


class VerifyStage(Stage):
    slot = V23Slot.VERIFY

    def __init__(self, client: VerifierClient) -> None:
        self._client = client

    def run(self, state: ReportState, ctx: StageContext) -> ReportState:
        thesis = self._require_thesis(state)
        bundle = self._require_bundle(state)
        if not state.sections:
            raise RuntimeError("VERIFY requires state.sections from WRITE.")

        deterministic = _deterministic_checks(state.sections, thesis, bundle)

        request = VerifierRequest(
            raw_prompt=state.raw_prompt,
            language=state.language,
            thesis=thesis,
            bundle=bundle,
            sections=list(state.sections),
        )
        from_llm = self._client.verify(request)

        state.verify_result = VerifyResult(issues=[*deterministic, *from_llm.issues])
        return state

    @staticmethod
    def _require_thesis(state: ReportState) -> ReportThesis:
        if state.thesis is None:
            raise RuntimeError("VERIFY requires state.thesis from SYNTHESIZE.")
        return state.thesis

    @staticmethod
    def _require_bundle(state: ReportState) -> ResearchBundle:
        if state.bundle is None:
            raise RuntimeError("VERIFY requires state.bundle.")
        return state.bundle


def _deterministic_checks(
    sections: list[WrittenSection],
    thesis: ReportThesis,
    bundle: ResearchBundle,
) -> list[VerifyIssue]:
    """Walk every cite/fig placeholder; report missing referents as HIGH."""
    bundle_fact_ids = set(bundle.facts.keys())
    chart_ids = {c.id for c in thesis.charts}

    issues: list[VerifyIssue] = []
    for section in sections:
        for fact_id in section.cited_fact_ids():
            if fact_id not in bundle_fact_ids:
                issues.append(
                    VerifyIssue(
                        section_id=section.section_id,
                        kind=IssueKind.DANGLING_CITE,
                        severity=IssueSeverity.HIGH,
                        detail=f"{{CITE:{fact_id}}} does not resolve in the bundle.",
                    )
                )
        for chart_id in section.figure_ids():
            if chart_id not in chart_ids:
                issues.append(
                    VerifyIssue(
                        section_id=section.section_id,
                        kind=IssueKind.BROKEN_FIG_REF,
                        severity=IssueSeverity.HIGH,
                        detail=f"{{FIG:{chart_id}}} does not match any chart spec.",
                    )
                )
    return issues
