"""Client protocol for the RESEARCH stage.

A `ResearcherClient` consumes the outline (with its per-section
`data_needs` work queue) plus the tickers, and returns a fully-assembled
`ResearchBundle`. The real implementation runs the autonomous tool-use
loop over EODHD/FMP/web tools and accumulates `BundleFact`s with
provenance attached at fetch time — that's the engine's most important
fabrication-prevention property. Tests inject `FakeResearcherClient`
with a canned bundle.

The protocol intentionally hides the loop: it takes one request and
returns one bundle. Stages don't care whether the bundle was assembled
in 1 turn or 50. That keeps the stage layer mock-friendly and lets the
real client iterate freely on tool-use design.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol

from ..schemas import ClarifyResult, Language, Outline, ReportType, ResearchBundle
from ..templates import TemplateSpec


@dataclass(slots=True)
class ResearchRequest:
    """Input passed to one RESEARCH invocation."""

    raw_prompt: str
    language: Language
    report_type: ReportType
    tickers: list[str]
    outline: Outline
    # Phase 1 pass-through: carried for symmetry across all stage Requests.
    # RESEARCH consumes outline.sections[*].data_needs, which PLAN populates
    # against the template — so template intent already shapes RESEARCH
    # indirectly. A future phase may surface template hints directly.
    template: TemplateSpec
    clarify_result: ClarifyResult | None = None


class ResearcherClient(Protocol):
    def research(self, request: ResearchRequest) -> ResearchBundle: ...


class FakeResearcherClient(ResearcherClient):
    """Test fake. Pass either a fixed `result` (single canned bundle) or a
    `responder` that derives the bundle from the request (useful when a
    test wants the bundle to depend on outline.data_needs)."""

    def __init__(
        self,
        result: ResearchBundle | None = None,
        responder: Callable[[ResearchRequest], ResearchBundle] | None = None,
    ) -> None:
        if (result is None) == (responder is None):
            raise ValueError("Provide exactly one of `result` or `responder`.")
        self._result = result
        self._responder = responder
        self.calls: list[ResearchRequest] = []

    def research(self, request: ResearchRequest) -> ResearchBundle:
        self.calls.append(request)
        if self._responder is not None:
            return self._responder(request)
        assert self._result is not None
        return self._result
