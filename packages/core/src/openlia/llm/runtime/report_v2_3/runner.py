"""ReportRunner — the v2.3 deterministic state-machine pipeline.

Orchestration lives here, not in any model's head. The runner:
  - walks `PIPELINE_ORDER` slot by slot
  - propagates WAITING_ON_USER / FAILED status as early-exit signals
  - applies a bounded verify -> write retry (max once)
  - hands off to ASSEMBLE after VERIFY accepts the draft

Suspend/resume contract:
  - On `WAITING_ON_USER`, current_stage stays pinned to the suspending stage.
    The runner returns; the caller persists `state` to its StateStore.
  - `resume(state, answers)` reapplies the answers to ReportState and
    re-enters the suspending stage so it can finalize.
"""

from __future__ import annotations

from collections.abc import Mapping

from .schemas import ClarifyAnswers, RunStatus
from .slots import V23Slot
from .stages.base import (
    PIPELINE_ORDER,
    AssembleStage,
    Stage,
    StageContext,
)
from .state import ReportState


class ReportRunner:
    """Owns the v2.3 pipeline. Stateless across runs — feed it ReportState."""

    MAX_VERIFY_RETRIES = 1

    def __init__(
        self,
        stages: Mapping[V23Slot, Stage],
        assemble: AssembleStage,
        ctx: StageContext,
    ) -> None:
        missing = set(PIPELINE_ORDER) - set(stages.keys())
        if missing:
            raise ValueError(f"ReportRunner missing stages for slots: {sorted(missing)}")
        for slot, stage in stages.items():
            if stage.slot != slot:
                raise ValueError(f"Stage at slot key '{slot}' reports slot '{stage.slot}'")
        self._stages: dict[V23Slot, Stage] = dict(stages)
        self._assemble = assemble
        self._ctx = ctx

    # ------------------------------------------------------------------
    # Entry points
    # ------------------------------------------------------------------
    def start(self, state: ReportState) -> ReportState:
        if state.status != RunStatus.RUNNING:
            raise ValueError(f"start() requires status=RUNNING; got {state.status}")
        return self._execute_from(state, PIPELINE_ORDER[0])

    def resume(self, state: ReportState, answers: ClarifyAnswers) -> ReportState:
        if state.status != RunStatus.WAITING_ON_USER:
            raise ValueError(f"resume() requires status=WAITING_ON_USER; got {state.status}")
        if state.current_stage is None:
            raise ValueError("resume() requires current_stage to be set.")
        state.resume_with_answers(answers)
        return self._execute_from(state, state.current_stage)

    # ------------------------------------------------------------------
    # Internal execution
    # ------------------------------------------------------------------
    def _execute_from(self, state: ReportState, start_slot: V23Slot) -> ReportState:
        for slot in self._slots_starting_at(start_slot):
            state.current_stage = slot
            try:
                state = self._stages[slot].run(state, self._ctx)
            except Exception as exc:
                state.fail(f"Stage {slot.value} raised: {exc}")
                return state
            state.touch()

            if state.status == RunStatus.WAITING_ON_USER:
                return state
            if state.status == RunStatus.FAILED:
                return state

            if slot == V23Slot.VERIFY and self._needs_rewrite(state):
                state.retry_count += 1
                return self._execute_from(state, V23Slot.WRITE)

        try:
            state = self._assemble.run(state, self._ctx)
        except Exception as exc:
            state.fail(f"Assemble raised: {exc}")
            return state

        state.complete()
        return state

    def _needs_rewrite(self, state: ReportState) -> bool:
        if state.verify_result is None:
            return False
        if not state.verify_result.must_rewrite:
            return False
        return state.retry_count < self.MAX_VERIFY_RETRIES

    @staticmethod
    def _slots_starting_at(start_slot: V23Slot) -> list[V23Slot]:
        try:
            idx = PIPELINE_ORDER.index(start_slot)
        except ValueError as exc:
            raise ValueError(f"Unknown start_slot '{start_slot}'; not in PIPELINE_ORDER.") from exc
        return list(PIPELINE_ORDER[idx:])
