"""Canonical list of LLM slots used by the v2.2 equity-research pipeline.

One slot per distinct stage that calls an LLM. The frontend mirrors this
tuple in `frontend/src/api/er-v2-models.ts`; keep both in sync.
"""

from __future__ import annotations

from enum import StrEnum


class V2Slot(StrEnum):
    CLARIFIER = "clarifier"
    RESEARCH_PLANNER = "research_planner"
    STRAND_SUBAGENT = "strand_subagent"
    MODEL_PLANNER = "model_planner"
    PLANNER_V2_2 = "planner_v2_2"
    MODEL_BUILDER = "model_builder"
    SECTION_DRAFTER = "section_drafter"
    LLM_VERIFIER = "llm_verifier"


REQUIRED_V2_SLOTS: tuple[V2Slot, ...] = tuple(V2Slot)
