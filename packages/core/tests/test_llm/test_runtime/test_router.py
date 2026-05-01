"""Unit tests for openlia.llm.runtime.router.route_tools."""

from __future__ import annotations

from typing import Any

import pytest
from openlia.llm.runtime.router import route_tools

pytestmark = pytest.mark.asyncio


class _StubLlm:
    def __init__(self, response: Any) -> None:
        self._response = response
        self.captured_prompts: list[str] = []

    async def generate_json(self, *, prompt: str) -> Any:
        self.captured_prompts.append(prompt)
        return self._response


CANDIDATES = [
    {"name": "eodhd__get_quote", "description": "Latest stock quote.", "input_schema": {}},
    {
        "name": "fmp__get_company_profile",
        "description": "Company profile.",
        "input_schema": {},
    },
    {"name": "newsapi_ai__search", "description": "News search.", "input_schema": {}},
]


async def test_returns_only_valid_names() -> None:
    llm = _StubLlm(["eodhd__get_quote", "made_up_tool", "fmp__get_company_profile"])
    out = await route_tools(
        department_id="equity_research",
        routing_context="ER context",
        user_prompt="What's AAPL trading at?",
        candidate_tools=CANDIDATES,
        llm_client=llm,
    )
    assert out == ["eodhd__get_quote", "fmp__get_company_profile"]


async def test_de_duplicates() -> None:
    llm = _StubLlm(["eodhd__get_quote", "eodhd__get_quote"])
    out = await route_tools(
        department_id="equity_research",
        routing_context="x",
        user_prompt="x",
        candidate_tools=CANDIDATES,
        llm_client=llm,
    )
    assert out == ["eodhd__get_quote"]


async def test_accepts_object_response_with_tools_key() -> None:
    llm = _StubLlm({"tools": ["eodhd__get_quote"]})
    out = await route_tools(
        department_id="equity_research",
        routing_context="x",
        user_prompt="x",
        candidate_tools=CANDIDATES,
        llm_client=llm,
    )
    assert out == ["eodhd__get_quote"]


async def test_handles_llm_error_returns_empty() -> None:
    class _Boom:
        async def generate_json(self, *, prompt: str) -> Any:
            raise RuntimeError("router LLM unreachable")

    out = await route_tools(
        department_id="equity_research",
        routing_context="x",
        user_prompt="x",
        candidate_tools=CANDIDATES,
        llm_client=_Boom(),
    )
    assert out == []


async def test_empty_candidate_pool_short_circuits() -> None:
    class _Sentinel:
        async def generate_json(self, *, prompt: str) -> Any:
            raise AssertionError("router must not be invoked with no candidates")

    out = await route_tools(
        department_id="equity_research",
        routing_context="x",
        user_prompt="x",
        candidate_tools=[],
        llm_client=_Sentinel(),
    )
    assert out == []


async def test_prompt_includes_required_pieces() -> None:
    llm = _StubLlm([])
    await route_tools(
        department_id="macro_research",
        routing_context="MR routes data only",
        user_prompt="Show debt cycle",
        candidate_tools=CANDIDATES,
        llm_client=llm,
    )
    prompt = llm.captured_prompts[0]
    assert "macro_research" in prompt
    assert "MR routes data only" in prompt
    assert "Show debt cycle" in prompt
    assert "eodhd__get_quote" in prompt
