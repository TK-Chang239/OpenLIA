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
            inputs = self._client.propose_inputs(request)
            new_facts.extend(_run_method(method, inputs, bundle))

        # Rebuild the bundle so the derived_from validator runs over the
        # combined facts. Mutating the dict in place would skip validation.
        state.bundle = ResearchBundle(
            tickers=bundle.tickers,
            facts={**bundle.facts, **{f.id: f for f in new_facts}},
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
