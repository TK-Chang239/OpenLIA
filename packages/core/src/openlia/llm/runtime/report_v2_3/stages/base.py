"""Base contracts for v2.3 pipeline stages.

A stage is a callable that mutates ReportState in place. The runner owns
orchestration — the order, the suspend gate, the retry loop — so stages stay
small and testable: read a slice, write a slice.

CLARIFY is the only stage that may set status=WAITING_ON_USER; the runner
treats that as an early-exit signal. ASSEMBLE is deterministic and has no
LLM slot, so it implements `AssembleStage` (a separate protocol) and is keyed
off `ASSEMBLE_SLOT_KEY` in the runner's stage registry.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

from ..slots import V23Slot
from ..state import ReportState

# Sentinel key for the non-LLM ASSEMBLE stage in the runner's registry. Kept
# outside V23Slot because it has no model assignment.
ASSEMBLE_SLOT_KEY = "assemble"


# Normal-flow execution order. Runner advances through this list. Retry logic
# (verify -> write) is handled by the runner, not by per-stage next pointers.
PIPELINE_ORDER: tuple[V23Slot, ...] = (
    V23Slot.CLARIFY,
    V23Slot.PLAN,
    V23Slot.RESEARCH,
    V23Slot.COMPUTE,
    V23Slot.SYNTHESIZE,
    V23Slot.WRITE,
    V23Slot.VISUALIZE,
    V23Slot.VERIFY,
)


@dataclass(slots=True)
class StageContext:
    """Per-run dependencies passed to every stage call.

    Kept intentionally generic — concrete stages cast `clients` and `tools`
    to whatever they need (LLM client, EODHD client, etc.). PR2 wires only
    the structural shape; PR3+ fill in real dependencies.
    """

    clients: dict[str, Any]
    tools: dict[str, Any]
    extras: dict[str, Any]


class Stage(Protocol):
    """Pipeline stage with an associated LLM slot."""

    slot: V23Slot

    def run(self, state: ReportState, ctx: StageContext) -> ReportState: ...


class AssembleStage(Protocol):
    """ASSEMBLE has no LLM slot; otherwise mirrors Stage."""

    def run(self, state: ReportState, ctx: StageContext) -> ReportState: ...
