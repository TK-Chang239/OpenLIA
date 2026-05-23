"""SYNTHESIZE stage — coherence anchor between RESEARCH and WRITE.

Runs once on the full bundle + outline and emits a `ReportThesis`. The
thesis is what makes parallel section writers cohere instead of drift:
a single central argument, one canonical rendering per number, explicit
non-overlap mandates, and chart claims paired with the data they plot.

Why this stage is critical: skipping it (or letting writers improvise the
thesis) is the documented #1 cause of sections drifting or overlapping.
The validators below enforce that the thesis is *structurally* aligned
with both the bundle (every figure resolves) and the outline (every
section has a mandate). Misalignment caught here is cheaper than
mismatch caught at VERIFY.
"""

from __future__ import annotations

from ..clients.synthesizer import SynthesizerClient, SynthesizerRequest
from ..schemas import Outline, ReportThesis, ResearchBundle
from ..slots import V23Slot
from ..state import ReportState
from .base import Stage, StageContext


class SynthesizeStage(Stage):
    slot = V23Slot.SYNTHESIZE

    def __init__(self, client: SynthesizerClient) -> None:
        self._client = client

    def run(self, state: ReportState, ctx: StageContext) -> ReportState:
        bundle = self._require_bundle(state)
        outline = self._require_outline(state)

        request = SynthesizerRequest(
            raw_prompt=state.raw_prompt,
            language=state.language,
            bundle=bundle,
            outline=outline,
            clarify_result=state.clarify_result,
        )
        thesis = self._client.synthesize(request)

        self._validate_thesis(thesis, bundle, outline, state)
        state.thesis = thesis
        return state

    # ------------------------------------------------------------------
    # Preconditions
    # ------------------------------------------------------------------
    @staticmethod
    def _require_bundle(state: ReportState) -> ResearchBundle:
        if state.bundle is None:
            raise RuntimeError("SYNTHESIZE requires state.bundle to be populated by RESEARCH.")
        return state.bundle

    @staticmethod
    def _require_outline(state: ReportState) -> Outline:
        if state.outline is None:
            raise RuntimeError("SYNTHESIZE requires state.outline to be populated by PLAN.")
        return state.outline

    # ------------------------------------------------------------------
    # Cross-validation between thesis, bundle, and outline
    # ------------------------------------------------------------------
    @staticmethod
    def _validate_thesis(
        thesis: ReportThesis,
        bundle: ResearchBundle,
        outline: Outline,
        state: ReportState,
    ) -> None:
        if thesis.language != state.language:
            raise RuntimeError(
                f"Thesis language {thesis.language} != run language {state.language}."
            )

        outline_section_ids = {s.id for s in outline.sections}
        mandate_section_ids = {m.section_id for m in thesis.mandates}

        missing_mandates = outline_section_ids - mandate_section_ids
        if missing_mandates:
            raise RuntimeError(
                f"Thesis missing mandates for outline sections: {sorted(missing_mandates)}"
            )

        stray_mandates = mandate_section_ids - outline_section_ids
        if stray_mandates:
            raise RuntimeError(
                f"Thesis has mandates for sections not in outline: {sorted(stray_mandates)}"
            )

        bundle_fact_ids = set(bundle.facts.keys())

        bad_canonical = [
            cf.fact_id for cf in thesis.canonical_figures if cf.fact_id not in bundle_fact_ids
        ]
        if bad_canonical:
            raise RuntimeError(f"Thesis canonical_figures reference unknown facts: {bad_canonical}")

        for chart in thesis.charts:
            missing_chart_facts = chart.referenced_fact_ids() - bundle_fact_ids
            if missing_chart_facts:
                raise RuntimeError(
                    f"Chart '{chart.id}' references unknown facts: {sorted(missing_chart_facts)}"
                )

        # Each mandate.chart_ids must point at a real ChartSpec. Without
        # this check a phantom id would slip past synthesis, WriteStage
        # would allow {{FIG:phantom}} (writer figs subset of mandate
        # chart_ids), and ASSEMBLE's resolve() would raise late.
        chart_ids = {c.id for c in thesis.charts}
        for mandate in thesis.mandates:
            phantom_charts = set(mandate.chart_ids) - chart_ids
            if phantom_charts:
                raise RuntimeError(
                    f"Mandate for section '{mandate.section_id}' references "
                    f"unknown charts: {sorted(phantom_charts)}"
                )

        # Mandates may only reference bundle facts; the schema does not check
        # this because the bundle is not on the thesis. We check it here so
        # writers cannot be asked to use a fact_id that does not exist.
        for mandate in thesis.mandates:
            missing_mandate_facts = set(mandate.relevant_fact_ids) - bundle_fact_ids
            if missing_mandate_facts:
                raise RuntimeError(
                    f"Mandate for section '{mandate.section_id}' references "
                    f"unknown facts: {sorted(missing_mandate_facts)}"
                )
