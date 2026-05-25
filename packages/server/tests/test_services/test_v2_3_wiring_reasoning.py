"""Tests for the v2.3 reasoning_effort ceiling-growth logic.

The wiring layer's job, when the user enables reasoning:
1. Forward the effort directive to *only* PLAN and SYNTHESIZE clients.
2. Grow ``max_tokens`` on those two stages by the per-effort overhead so
   the truncation guard covers ``visible_output + thinking_budget``.

Other stages stay flat. Off mode is a no-op everywhere.

These tests pin ``_resolve_stage_reasoning`` directly — the helper that
both ``_build_json_client_from_resolved`` and the factory call into.
Plumbing through the SyncJsonLlmClient is verified separately in
``test_v2_stage_factory_usage_logging.py``.
"""

from __future__ import annotations

import pytest
from openlia.llm.types import ReasoningEffort
from openlia_server.services.v2_3_wiring import (
    _REASONING_OVERHEAD,
    _REASONING_STAGES,
    _resolve_stage_reasoning,
)


def test_reasoning_stages_only_contain_plan_and_synthesize() -> None:
    """If the set of reasoning-enabled stages drifts, the ceiling math
    silently misapplies to unintended stages. Pin the contract."""
    assert _REASONING_STAGES == frozenset({"plan", "synthesize"})


@pytest.mark.parametrize(
    "stage",
    ["clarify", "research", "compute", "write", "verify"],
)
def test_off_mode_returns_base_max_for_every_stage(stage: str) -> None:
    """reasoning_effort=None must leave max_tokens and effort untouched
    on every stage so legacy callers behave exactly as before."""
    effective_max, effort = _resolve_stage_reasoning(stage, base_max=4096, reasoning_effort=None)
    assert effective_max == 4096
    assert effort is None


@pytest.mark.parametrize(
    "effort",
    [ReasoningEffort.MEDIUM, ReasoningEffort.HIGH],
)
def test_non_reasoning_stage_drops_effort_and_keeps_base_max(effort: ReasoningEffort) -> None:
    """Even with reasoning ON, stages outside _REASONING_STAGES must
    not get the directive (CLARIFY / COMPUTE / VERIFY are cheap; WRITE
    multiplies latency across N sections)."""
    effective_max, returned_effort = _resolve_stage_reasoning(
        "write", base_max=8192, reasoning_effort=effort
    )
    assert effective_max == 8192
    assert returned_effort is None


def test_plan_with_medium_grows_ceiling_by_8192() -> None:
    effective_max, effort = _resolve_stage_reasoning(
        "plan", base_max=8192, reasoning_effort=ReasoningEffort.MEDIUM
    )
    assert effective_max == 8192 + _REASONING_OVERHEAD[ReasoningEffort.MEDIUM]
    assert effective_max == 16_384
    assert effort is ReasoningEffort.MEDIUM


def test_plan_with_high_grows_ceiling_by_32768() -> None:
    effective_max, effort = _resolve_stage_reasoning(
        "plan", base_max=8192, reasoning_effort=ReasoningEffort.HIGH
    )
    assert effective_max == 8192 + _REASONING_OVERHEAD[ReasoningEffort.HIGH]
    assert effective_max == 40_960
    assert effort is ReasoningEffort.HIGH


def test_synthesize_with_high_grows_ceiling_by_32768() -> None:
    effective_max, effort = _resolve_stage_reasoning(
        "synthesize", base_max=16_384, reasoning_effort=ReasoningEffort.HIGH
    )
    assert effective_max == 16_384 + 32_768
    assert effort is ReasoningEffort.HIGH


def test_reasoning_overhead_table_has_one_entry_per_effort() -> None:
    """If a new ReasoningEffort enum member is added without a matching
    overhead entry, the lookup KeyErrors at request time. Pin the
    invariant — exactly the enum members must be keys."""
    assert set(_REASONING_OVERHEAD.keys()) == set(ReasoningEffort)
