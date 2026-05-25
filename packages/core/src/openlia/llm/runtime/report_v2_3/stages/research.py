"""RESEARCH stage — gathers facts to populate the bundle.

Reads ``state.outline.sections[*].data_needs`` (PLAN's targeted work
queue), hands the request to the ResearcherClient, and writes the
returned ``ResearchBundle`` to ``state.bundle``. The autonomous tool-use
loop — EODHD/FMP/web tools, iterative fact accumulation — lives inside
the client implementation; this stage only owns the dispatch.

Validation: the bundle's tickers must match the run's tickers, so a
researcher cannot silently widen scope. Per spec, RESEARCH is the only
stage with broad tool autonomy; everything else here is structural.
"""

from __future__ import annotations

from ..clients.researcher import ResearcherClient, ResearchRequest
from ..schemas import Outline, ResearchBundle
from ..slots import V23Slot
from ..state import ReportState
from .base import Stage, StageContext


class ResearchStage(Stage):
    slot = V23Slot.RESEARCH

    def __init__(self, client: ResearcherClient) -> None:
        self._client = client

    def run(self, state: ReportState, ctx: StageContext) -> ReportState:
        outline = self._require_outline(state)

        request = ResearchRequest(
            raw_prompt=state.raw_prompt,
            language=state.language,
            report_type=state.report_type,
            tickers=list(state.tickers),
            outline=outline,
            template=state.template,
            clarify_result=state.clarify_result,
        )
        bundle = self._client.research(request)
        self._validate_bundle(bundle, state)
        state.bundle = bundle
        return state

    @staticmethod
    def _require_outline(state: ReportState) -> Outline:
        if state.outline is None:
            raise RuntimeError("RESEARCH requires state.outline from PLAN.")
        return state.outline

    @staticmethod
    def _validate_bundle(bundle: ResearchBundle, state: ReportState) -> None:
        if bundle.tickers != state.tickers:
            raise RuntimeError(
                f"Researcher returned bundle for tickers {bundle.tickers} "
                f"but the run is on {state.tickers}."
            )
