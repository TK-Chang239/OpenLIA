"""Scenario 5 — mid-conversation escalation flow (spec §8.5).

The chat runtime's mid-conversation router invocation is currently a
core library primitive; it is not wired through a HTTP route as of v2.
This test exercises the same invariant the integration test would
assert via FastAPI: that calling `merge_escalation` with a stubbed
router LLM returns a tool set that is the strict, ordered union of the
two routing rounds (initial subset + escalation pickups).

If/when the chat router is wired into `/chat/stream`, this test should
be expanded into a true HTTP-level scenario walking three turns.
"""

from __future__ import annotations

from typing import Any

import pytest
from openlia.llm.runtime.escalation import (
    ESCALATION_TOOL_DEFINITION,
    ESCALATION_TOOL_NAME,
    merge_escalation,
    summarize_added,
)


class _ScriptedLlm:
    """Returns a pre-baked JSON answer per call. Each call pops the next
    response off `responses`; a missing response raises."""

    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.calls: list[str] = []

    async def generate_json(self, *, prompt: str) -> Any:
        self.calls.append(prompt)
        if not self._responses:
            raise RuntimeError("no scripted response left")
        return self._responses.pop(0)


@pytest.mark.asyncio
async def test_escalation_merges_router_output_monotonically() -> None:
    candidate_tools = [
        {"name": "eodhd.get_quote", "description": "Latest quote."},
        {"name": "eodhd.get_fundamentals", "description": "Fundamentals."},
        {"name": "newsapi.search", "description": "Search news."},
        {"name": "newsapi.headlines", "description": "Top headlines."},
    ]

    # Round 1: initial selection narrowed to two tools.
    initial = ["eodhd.get_quote", "eodhd.get_fundamentals"]

    # Round 2: the main LLM emits `request_additional_tools`. The router
    # answers with one new tool plus one already-present tool (which must
    # be deduped).
    router_round2 = ["newsapi.search", "eodhd.get_quote"]
    llm = _ScriptedLlm(responses=[router_round2])

    merged = await merge_escalation(
        department_id="equity_research",
        routing_context="ER context …",
        current_tools=initial,
        escalation_arguments={
            "reason": "Need recent news on the ticker.",
            "category_hint": "news",
        },
        candidate_tools=candidate_tools,
        llm_client=llm,
    )

    # Strictly grew: every initial name preserved in original order,
    # plus the new name appended once.
    assert merged == [
        "eodhd.get_quote",
        "eodhd.get_fundamentals",
        "newsapi.search",
    ]
    assert llm.calls, "router should have been re-invoked on escalation"

    # Summary helper surfaces the delta.
    summary = summarize_added(initial, merged)
    assert "newsapi.search" in summary


@pytest.mark.asyncio
async def test_escalation_no_new_tools_returns_unchanged_set() -> None:
    """Negative-space: when the router can't find anything new, the tool
    list is unchanged and the helper says so."""
    candidate_tools = [{"name": "eodhd.get_quote", "description": "q"}]
    initial = ["eodhd.get_quote"]
    llm = _ScriptedLlm(responses=[["eodhd.get_quote"]])

    merged = await merge_escalation(
        department_id="equity_research",
        routing_context="ER",
        current_tools=initial,
        escalation_arguments={"reason": "x"},
        candidate_tools=candidate_tools,
        llm_client=llm,
    )
    assert merged == initial
    assert summarize_added(initial, merged) == "No additional tools matched the request."


def test_escalation_tool_definition_shape_is_stable() -> None:
    """Spec §8.5 contract: the escalation tool name and required arg are
    part of the public surface. Lock them so accidental rename surfaces
    here."""
    assert ESCALATION_TOOL_NAME == "request_additional_tools"
    assert ESCALATION_TOOL_DEFINITION["name"] == ESCALATION_TOOL_NAME
    schema = ESCALATION_TOOL_DEFINITION["input_schema"]
    assert "reason" in schema["properties"]
    assert schema["required"] == ["reason"]
