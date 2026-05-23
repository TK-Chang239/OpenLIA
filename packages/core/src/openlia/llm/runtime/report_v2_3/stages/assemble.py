"""ASSEMBLE stage — deterministic placeholder resolution.

The math here is owned by ``schemas.resolve()`` (PR1):

  - figure numbers are assigned in document order across all sections
  - footnotes are numbered, deduped by ``fact_id``, and rendered from
    each fact's provenance
  - dangling ``{{CITE:}}`` / ``{{FIG:}}`` references raise — better to
    fail loud than ship a broken report

This stage is the only one that has no LLM call: planning, drafting,
and verification have already happened, so the remaining work is purely
arithmetic + string substitution.

Graceful no-op contract: if the run never produced sections (e.g. an
early-suspending CLARIFY that the user abandoned, or a pipeline still
running mostly NoOp stages while the engine is built out), this stage
quietly leaves ``state.resolved`` as ``None`` rather than raising. That
keeps the runner reachable end-to-end during incremental rollouts.
"""

from __future__ import annotations

from ..schemas import resolve
from ..state import ReportState
from .base import StageContext


class AssembleStage:
    """Deterministic ASSEMBLE — no LLM slot, no client.

    Implements the `AssembleStage` Protocol from `base` structurally
    (matches the `run(state, ctx) -> ReportState` shape) without
    inheriting, so the class is concrete and not abstract.
    """

    def run(self, state: ReportState, ctx: StageContext) -> ReportState:
        if not self._ready_to_assemble(state):
            return state

        assert state.thesis is not None
        assert state.bundle is not None
        assert state.outline is not None

        section_order = [s.id for s in state.outline.sections]

        state.resolved = resolve(
            sections=state.sections,
            bundle=state.bundle,
            charts=state.thesis.charts,
            section_order=section_order,
        )
        return state

    @staticmethod
    def _ready_to_assemble(state: ReportState) -> bool:
        return (
            bool(state.sections)
            and state.bundle is not None
            and state.thesis is not None
            and state.outline is not None
        )
