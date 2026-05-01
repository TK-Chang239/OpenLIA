"""Unit tests for openlia.llm.runtime.escalation."""

from __future__ import annotations

from typing import Any

import pytest
from openlia.llm.runtime.escalation import (
    ESCALATION_TOOL_DEFINITION,
    ESCALATION_TOOL_NAME,
    merge_escalation,
    summarize_added,
)


class _StubLlm:
    def __init__(self, response: Any) -> None:
        self._response = response

    async def generate_json(self, *, prompt: str) -> Any:
        return self._response


CANDIDATES = [
    {"name": "eodhd__get_quote", "description": "quote", "input_schema": {}},
    {"name": "fmp__get_company_profile", "description": "profile", "input_schema": {}},
    {"name": "newsapi_ai__search", "description": "news", "input_schema": {}},
]


def test_escalation_tool_shape() -> None:
    assert ESCALATION_TOOL_DEFINITION["name"] == ESCALATION_TOOL_NAME
    schema = ESCALATION_TOOL_DEFINITION["input_schema"]
    assert "reason" in schema["properties"]
    assert schema["required"] == ["reason"]


@pytest.mark.asyncio
async def test_merge_grows_monotonically() -> None:
    llm = _StubLlm(["fmp__get_company_profile", "newsapi_ai__search"])
    merged = await merge_escalation(
        department_id="equity_research",
        routing_context="ER",
        current_tools=["eodhd__get_quote"],
        escalation_arguments={"reason": "I need company news too"},
        candidate_tools=CANDIDATES,
        llm_client=llm,
    )
    assert merged == [
        "eodhd__get_quote",
        "fmp__get_company_profile",
        "newsapi_ai__search",
    ]


@pytest.mark.asyncio
async def test_merge_dedupes_against_current() -> None:
    llm = _StubLlm(["eodhd__get_quote", "fmp__get_company_profile"])
    merged = await merge_escalation(
        department_id="equity_research",
        routing_context="ER",
        current_tools=["eodhd__get_quote"],
        escalation_arguments={"reason": "more"},
        candidate_tools=CANDIDATES,
        llm_client=llm,
    )
    assert merged == ["eodhd__get_quote", "fmp__get_company_profile"]


@pytest.mark.asyncio
async def test_merge_drops_unknown_router_picks() -> None:
    llm = _StubLlm(["bogus_tool", "fmp__get_company_profile"])
    merged = await merge_escalation(
        department_id="equity_research",
        routing_context="ER",
        current_tools=["eodhd__get_quote"],
        escalation_arguments={"reason": "more"},
        candidate_tools=CANDIDATES,
        llm_client=llm,
    )
    assert merged == ["eodhd__get_quote", "fmp__get_company_profile"]


def test_summarize_added_describes_diff() -> None:
    summary = summarize_added(
        ["eodhd__get_quote"],
        ["eodhd__get_quote", "fmp__get_company_profile", "newsapi_ai__search"],
    )
    assert "fmp__get_company_profile" in summary
    assert "newsapi_ai__search" in summary


def test_summarize_added_empty_diff() -> None:
    summary = summarize_added(["eodhd__get_quote"], ["eodhd__get_quote"])
    assert "No additional tools" in summary
