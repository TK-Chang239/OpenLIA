"""Canonical list of LLM slots used by the v2.3 equity-research pipeline.

One slot per pipeline stage that calls an LLM. ASSEMBLE is deterministic and
has no slot. The frontend mirrors this enum in
`frontend/src/api/er-v2-models.ts` (or its v2.3 successor); keep both in sync.
"""

from __future__ import annotations

from enum import StrEnum


class V23Slot(StrEnum):
    CLARIFY = "clarify"
    PLAN = "plan"
    RESEARCH = "research"
    COMPUTE = "compute"
    SYNTHESIZE = "synthesize"
    WRITE = "write"
    VISUALIZE = "visualize"
    VERIFY = "verify"


REQUIRED_V23_SLOTS: tuple[V23Slot, ...] = tuple(V23Slot)


# Slots that actually drive an LLM call. VISUALIZE is deterministic
# (chart-renderability check); ASSEMBLE is deterministic (placeholder
# resolution). The per-user model-assignments table stores rows only
# for these — assigning a model to a deterministic slot would be a
# no-op.
LLM_V23_SLOTS: tuple[V23Slot, ...] = (
    V23Slot.CLARIFY,
    V23Slot.PLAN,
    V23Slot.RESEARCH,
    V23Slot.COMPUTE,
    V23Slot.SYNTHESIZE,
    V23Slot.WRITE,
    V23Slot.VERIFY,
)
