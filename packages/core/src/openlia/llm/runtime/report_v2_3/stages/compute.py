"""COMPUTE stage — runs the planned valuation methods.

Sits between RESEARCH (which fills the bundle with raw facts) and
SYNTHESIZE (which builds the thesis informed by the valuation
results). For each method in ``outline.valuation_plan.methods``, the
stage:

  1. Asks the LLM client to propose inputs (``*Inputs`` schema).
  2. Calls the deterministic math (``dcf``/``comps``/``sensitivity``).
  3. Decomposes the result into ``BundleFact``s with
     ``ComputedSource.derived_from`` chains, and ADDS those facts back
     into ``state.bundle``.

A writer downstream can then cite ``{{CITE:dcf_fair_value}}`` or
``{{CITE:comps_implied_ev_ebitda}}`` and the resolved footnote reads
"Author calculation: DCF" / "Comps median (ev_ebitda)" — same
provenance chain as any other fact.

Graceful no-op contract: if ``outline.valuation_plan.methods`` is empty
(morning briefs, etc.) the stage returns immediately without invoking
the client.
"""

from __future__ import annotations

import logging

from ..clients.compute import ComputeClient, ComputeRequest
from ..schemas import (
    BundleFact,
    CompsInputs,
    DCFInputs,
    Outline,
    ResearchBundle,
    SensitivityInputs,
    ValuationMethod,
    dcf_result_to_facts,
)
from ..slots import V23Slot
from ..state import ReportState
from ..valuation import (
    comps,
    comps_result_to_facts,
    dcf,
    sensitivity,
    sensitivity_result_to_fact,
)
from .base import Stage, StageContext

log = logging.getLogger(__name__)


class ComputeStage(Stage):
    slot = V23Slot.COMPUTE

    def __init__(self, client: ComputeClient) -> None:
        self._client = client

    def run(self, state: ReportState, ctx: StageContext) -> ReportState:
        outline = self._require_outline(state)
        bundle = self._require_bundle(state)

        methods = outline.valuation_plan.methods
        if not methods:
            return state

        new_facts: list[BundleFact] = []
        for method in methods:
            request = ComputeRequest(
                method=method,
                raw_prompt=state.raw_prompt,
                language=state.language,
                bundle=bundle,
                outline=outline,
                clarify_result=state.clarify_result,
            )
            # Per-method tolerance: an LLM that produces malformed inputs
            # (e.g. Comps with peers=[] when the LLM can't find any), or
            # math that can't compute (divide-by-zero, missing facts),
            # should drop that method's contribution rather than abort
            # the whole pipeline. Other methods still produce their
            # facts, and downstream SYNTHESIZE/WRITE work off whatever
            # COMPUTE managed to land. RuntimeError is the umbrella the
            # LLM-validation wrappers + valuation math both raise.
            try:
                inputs = self._client.propose_inputs(request)
                new_facts.extend(_run_method(method, inputs, bundle))
            except RuntimeError as exc:
                log.warning(
                    "COMPUTE/%s skipped: %s",
                    method.value,
                    exc,
                )
                continue

        # Rebuild the bundle so the derived_from validator runs over the
        # combined facts. Mutating the dict in place would skip validation.
        # Explicit duplicate-id check mirrors ResearchBundle.add() — a
        # silent dict-merge overwrite would defeat the schema invariant
        # that fact ids are unique, and the bug only shows up in the docx
        # later. Better to fail loud here.
        new_by_id: dict[str, BundleFact] = {}
        for fact in new_facts:
            if fact.id in new_by_id:
                raise RuntimeError(
                    f"COMPUTE produced duplicate fact id '{fact.id}' within one run."
                )
            if fact.id in bundle.facts:
                raise RuntimeError(
                    f"COMPUTE fact id '{fact.id}' collides with an existing bundle fact."
                )
            new_by_id[fact.id] = fact

        state.bundle = ResearchBundle(
            tickers=bundle.tickers,
            facts={**bundle.facts, **new_by_id},
        )
        return state

    @staticmethod
    def _require_outline(state: ReportState) -> Outline:
        if state.outline is None:
            raise RuntimeError("COMPUTE requires state.outline from PLAN.")
        return state.outline

    @staticmethod
    def _require_bundle(state: ReportState) -> ResearchBundle:
        if state.bundle is None:
            raise RuntimeError("COMPUTE requires state.bundle from RESEARCH.")
        return state.bundle


def _run_method(
    method: ValuationMethod,
    inputs: object,
    bundle: ResearchBundle,
) -> list[BundleFact]:
    if method == ValuationMethod.DCF:
        if not isinstance(inputs, DCFInputs):
            raise RuntimeError(f"DCF requires DCFInputs; got {type(inputs).__name__}.")
        return dcf_result_to_facts(dcf(inputs, bundle), inputs)
    if method == ValuationMethod.COMPS:
        if not isinstance(inputs, CompsInputs):
            raise RuntimeError(f"Comps requires CompsInputs; got {type(inputs).__name__}.")
        return comps_result_to_facts(comps(inputs, bundle), inputs)
    if method == ValuationMethod.SENSITIVITY:
        if not isinstance(inputs, SensitivityInputs):
            raise RuntimeError(
                f"Sensitivity requires SensitivityInputs; got {type(inputs).__name__}."
            )
        return [sensitivity_result_to_fact(sensitivity(inputs, bundle), inputs)]
    raise RuntimeError(f"Unknown ValuationMethod: {method}")
