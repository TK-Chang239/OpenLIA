"""NoOp stages used by tests and PR-by-PR scaffolding.

A `NoOpStage` advances the run without producing real output. Useful for
exercising the runner state machine in isolation before real stages exist.
"""

from __future__ import annotations

from collections.abc import Callable

from ..slots import V23Slot
from ..state import ReportState
from .base import AssembleStage, Stage, StageContext


class NoOpStage(Stage):
    """A stage that simply records that it ran.

    Optional `hook(state, ctx)` lets a test inject behavior (suspend on
    CLARIFY, flip verify_result, etc.) without subclassing.
    """

    def __init__(
        self,
        slot: V23Slot,
        hook: Callable[[ReportState, StageContext], None] | None = None,
    ) -> None:
        self.slot = slot
        self._hook = hook

    def run(self, state: ReportState, ctx: StageContext) -> ReportState:
        if self._hook is not None:
            self._hook(state, ctx)
        return state


class NoOpAssembleStage(AssembleStage):
    def __init__(
        self,
        hook: Callable[[ReportState, StageContext], None] | None = None,
    ) -> None:
        self._hook = hook

    def run(self, state: ReportState, ctx: StageContext) -> ReportState:
        if self._hook is not None:
            self._hook(state, ctx)
        return state
