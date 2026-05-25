"""Client protocol for the COMPUTE stage's input proposals.

The model proposes/justifies the INPUTS (growth path, WACC, comp set);
the runner then calls the deterministic ``dcf()``/``comps()``/
``sensitivity()`` math. Splitting it this way keeps the math
reproducible and unit-testable while still letting the LLM bring
analytical judgment about *which* assumptions to use.

One call per method requested in ``outline.valuation_plan.methods`` —
the stage drives the loop. The returned ``*Inputs`` is validated by
Pydantic on the way back; bad shapes surface as a stage-level error.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from ..schemas import (
    ClarifyResult,
    Language,
    Outline,
    ResearchBundle,
    ValuationInputs,
    ValuationMethod,
)
from ..templates import TemplateSpec


@dataclass(slots=True)
class ComputeRequest:
    """One COMPUTE call — propose inputs for a single method."""

    method: ValuationMethod
    raw_prompt: str
    language: Language
    bundle: ResearchBundle
    outline: Outline
    # Phase 1 pass-through: carried for symmetry across all stage Requests.
    # COMPUTE works from outline.valuation_plan, which PLAN derives from the
    # template — so template content already shapes COMPUTE indirectly.
    template: TemplateSpec
    clarify_result: ClarifyResult | None = None


class ComputeClient(Protocol):
    def propose_inputs(self, request: ComputeRequest) -> ValuationInputs: ...


class FakeComputeClient(ComputeClient):
    """Test fake. Provide either fixed `inputs_by_method` (dict keyed by
    `ValuationMethod`) or a `responder` callable for per-call control."""

    def __init__(
        self,
        inputs_by_method: dict[ValuationMethod, ValuationInputs] | None = None,
        responder: Callable[[ComputeRequest], ValuationInputs] | None = None,
    ) -> None:
        if (inputs_by_method is None) == (responder is None):
            raise ValueError("Provide exactly one of `inputs_by_method` or `responder`.")
        self._inputs_by_method = inputs_by_method
        self._responder = responder
        self.calls: list[ComputeRequest] = []

    def propose_inputs(self, request: ComputeRequest) -> ValuationInputs:
        self.calls.append(request)
        if self._responder is not None:
            return self._responder(request)
        assert self._inputs_by_method is not None
        if request.method not in self._inputs_by_method:
            raise KeyError(f"FakeComputeClient has no inputs for {request.method}")
        return self._inputs_by_method[request.method]
