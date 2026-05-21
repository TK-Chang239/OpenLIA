"""Skeleton runner for the v2.2 9-stage pipeline.

See docs/superpowers/specs/2026-05-21-equity-research-v2.2-design.md §2.
The orchestrator that wires every stage together is filled in across Phase P
PRs P1-P7. This skeleton fixes the stage enum, run state machine, and the
minimal coordination types.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class PipelineStage(StrEnum):
    CLARIFY = "clarify"
    READ_TEMPLATE = "read_template"
    RESEARCH_PLAN = "research_plan"
    GATHER = "gather"
    MODEL_PLAN = "model_plan"
    MODEL_BUILD = "model_build"
    DRAFT = "draft"
    VERIFY = "verify"
    ASSEMBLE = "assemble"


class RunState(StrEnum):
    STARTED = "STARTED"
    CLARIFY_AWAITING_USER = "CLARIFY_AWAITING_USER"
    RUNNING = "RUNNING"
    DEGRADED = "DEGRADED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


@dataclass
class RunnerV2:
    state: RunState = RunState.STARTED
    current_stage: PipelineStage | None = None
    outcomes: list = field(default_factory=list)

    def transition(self, new_state: RunState) -> None:
        self.state = new_state

    def enter_stage(self, stage: PipelineStage) -> None:
        self.current_stage = stage
