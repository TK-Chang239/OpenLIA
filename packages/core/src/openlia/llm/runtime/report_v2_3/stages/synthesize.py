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

import logging

from ..clients.synthesizer import SynthesizerClient, SynthesizerRequest
from ..schemas import Outline, ReportThesis, ResearchBundle
from ..slots import V23Slot
from ..state import ReportState
from .base import Stage, StageContext

log = logging.getLogger(__name__)


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

        self._strip_phantom_fact_refs(thesis, bundle)
        self._validate_thesis(thesis, bundle, outline, state)
        state.thesis = thesis
        return state

    # ------------------------------------------------------------------
    # Defensive coercion — strip LLM hallucinations before validation
    # ------------------------------------------------------------------
    @staticmethod
    def _strip_phantom_fact_refs(thesis: ReportThesis, bundle: ResearchBundle) -> None:
        """Drop thesis references to fact_ids that don't exist in the bundle.

        SYNTHESIZE LLMs routinely invent plausible-sounding fact ids
        (``geo_mix``, ``rev_mix_segments``) when the bundle doesn't carry
        them. Failing the whole run for one stray reference is overkill —
        the writer can render the section with the facts that DO exist.
        We surface each strip as a warning so the divergence is visible
        in logs without nuking the report.

        - canonical_figures with bad fact_ids → drop the entry (cover
          shows fewer metrics).
        - charts that reference any unknown fact → drop the whole chart
          (a half-resolved chart would mis-plot).
        - mandate.relevant_fact_ids → filter the list (writer just has
          access to a smaller slice).
        - mandate.chart_ids → restripped after charts are dropped, so
          mandates can't point at a chart we just removed.
        """
        bundle_fact_ids = set(bundle.facts.keys())

        before_cf = len(thesis.canonical_figures)
        thesis.canonical_figures = [
            cf for cf in thesis.canonical_figures if cf.fact_id in bundle_fact_ids
        ]
        if len(thesis.canonical_figures) != before_cf:
            log.warning(
                "SYNTHESIZE: dropped %d canonical_figures with unknown fact_ids.",
                before_cf - len(thesis.canonical_figures),
            )

        surviving_charts = []
        for chart in thesis.charts:
            missing = chart.referenced_fact_ids() - bundle_fact_ids
            if missing:
                log.warning(
                    "SYNTHESIZE: dropping chart %r — references unknown facts %s.",
                    chart.id,
                    sorted(missing),
                )
                continue
            surviving_charts.append(chart)
        thesis.charts = surviving_charts
        chart_ids = {c.id for c in thesis.charts}

        for mandate in thesis.mandates:
            kept_facts = [fid for fid in mandate.relevant_fact_ids if fid in bundle_fact_ids]
            phantom_facts = set(mandate.relevant_fact_ids) - set(kept_facts)
            if phantom_facts:
                log.warning(
                    "SYNTHESIZE: stripping unknown fact_ids %s from mandate %r.",
                    sorted(phantom_facts),
                    mandate.section_id,
                )
                mandate.relevant_fact_ids = kept_facts

            kept_charts = [cid for cid in mandate.chart_ids if cid in chart_ids]
            phantom_charts = set(mandate.chart_ids) - set(kept_charts)
            if phantom_charts:
                log.warning(
                    "SYNTHESIZE: stripping phantom chart_ids %s from mandate %r.",
                    sorted(phantom_charts),
                    mandate.section_id,
                )
                mandate.chart_ids = kept_charts

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

        # Structural guards — phantom fact/chart refs were stripped in
        # _strip_phantom_fact_refs above, so these checks should never
        # fire in practice. Kept as fail-fast invariants in case the
        # strip helper ever drifts out of sync with the rules below.
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
        chart_ids = {c.id for c in thesis.charts}
        for mandate in thesis.mandates:
            phantom_charts = set(mandate.chart_ids) - chart_ids
            if phantom_charts:
                raise RuntimeError(
                    f"Mandate for section '{mandate.section_id}' references "
                    f"unknown charts: {sorted(phantom_charts)}"
                )
            missing_mandate_facts = set(mandate.relevant_fact_ids) - bundle_fact_ids
            if missing_mandate_facts:
                raise RuntimeError(
                    f"Mandate for section '{mandate.section_id}' references "
                    f"unknown facts: {sorted(missing_mandate_facts)}"
                )
