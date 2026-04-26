"""Adapter LLM scoping.

Schema validation is enforced; one retry on malformed output; raises on second failure.
Only eligible departments (those that declare the connector's category) are passed to the LLM.
"""

from __future__ import annotations

import json

import pytest
from openlia.connectors.scope import (
    DepartmentRequirements,
    ScopeLLMClient,
    ScopeRequest,
    scope_connector,
)
from openlia.connectors.types import Category, ToolDefinition

_REQS = {
    "equity_research": DepartmentRequirements(
        department_id="equity_research",
        per_category={
            Category.FINANCIAL.value: {"required": True, "description": "fundamentals etc."},
        },
    ),
    "earnings_update": DepartmentRequirements(
        department_id="earnings_update",
        per_category={
            Category.FINANCIAL.value: {"required": True, "description": "fundamentals etc."},
        },
    ),
}


class _FakeLLM(ScopeLLMClient):
    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls: list[ScopeRequest] = []

    async def call(self, req: ScopeRequest) -> str:
        self.calls.append(req)
        return self.responses.pop(0)


async def test_happy_path_assigns_tools_to_departments():
    tools = [
        ToolDefinition(name="get_fundamentals", description="financial data", input_schema={}),
        ToolDefinition(name="get_options_eod", description="options EOD", input_schema={}),
    ]
    payload = json.dumps(
        {
            "assignments": [
                {
                    "tool_name": "get_fundamentals",
                    "department_ids": ["equity_research", "earnings_update"],
                },
                {"tool_name": "get_options_eod", "department_ids": []},
            ]
        }
    )
    llm = _FakeLLM([payload])

    result = await scope_connector(
        connector_id="c1",
        provider_id="eodhd",
        category=Category.FINANCIAL,
        tools=tools,
        requirements=_REQS,
        llm=llm,
    )

    names = sorted((s.department_id, s.tool_name) for s in result)
    assert names == [
        ("earnings_update", "get_fundamentals"),
        ("equity_research", "get_fundamentals"),
    ]
    assert all(s.connector_id == "c1" for s in result)


async def test_retries_once_on_invalid_json():
    tools = [ToolDefinition(name="t", description="", input_schema={})]
    valid = json.dumps({"assignments": [{"tool_name": "t", "department_ids": ["equity_research"]}]})
    llm = _FakeLLM(["NOT JSON", valid])

    result = await scope_connector(
        connector_id="c",
        provider_id="x",
        category=Category.FINANCIAL,
        tools=tools,
        requirements=_REQS,
        llm=llm,
    )
    assert len(result) == 1
    assert len(llm.calls) == 2  # one retry


async def test_raises_after_second_invalid_json():
    tools = [ToolDefinition(name="t", description="", input_schema={})]
    llm = _FakeLLM(["NOT JSON", "still not"])
    with pytest.raises(ValueError, match="adapter LLM"):
        await scope_connector(
            connector_id="c",
            provider_id="x",
            category=Category.FINANCIAL,
            tools=tools,
            requirements=_REQS,
            llm=llm,
        )


async def test_drops_assignments_to_unknown_departments():
    tools = [ToolDefinition(name="t", description="", input_schema={})]
    payload = json.dumps(
        {"assignments": [{"tool_name": "t", "department_ids": ["bogus_dept", "equity_research"]}]}
    )
    llm = _FakeLLM([payload])
    result = await scope_connector(
        connector_id="c",
        provider_id="x",
        category=Category.FINANCIAL,
        tools=tools,
        requirements=_REQS,
        llm=llm,
    )
    assert [s.department_id for s in result] == ["equity_research"]


async def test_drops_assignments_to_unknown_tools():
    tools = [ToolDefinition(name="real_tool", description="", input_schema={})]
    payload = json.dumps(
        {
            "assignments": [
                {"tool_name": "real_tool", "department_ids": ["equity_research"]},
                {"tool_name": "fabricated_tool", "department_ids": ["equity_research"]},
            ]
        }
    )
    llm = _FakeLLM([payload])
    result = await scope_connector(
        connector_id="c",
        provider_id="x",
        category=Category.FINANCIAL,
        tools=tools,
        requirements=_REQS,
        llm=llm,
    )
    assert [s.tool_name for s in result] == ["real_tool"]


async def test_only_eligible_departments_passed_to_llm():
    """Only departments declaring this category are eligible."""

    reqs = {
        **_REQS,
        "macro_research": DepartmentRequirements(
            department_id="macro_research",
            per_category={
                Category.NEWS.value: {"required": True, "description": "..."},
            },
        ),
    }
    tools = [ToolDefinition(name="t", description="", input_schema={})]
    payload = json.dumps({"assignments": [{"tool_name": "t", "department_ids": []}]})
    llm = _FakeLLM([payload])
    await scope_connector(
        connector_id="c",
        provider_id="x",
        category=Category.FINANCIAL,
        tools=tools,
        requirements=reqs,
        llm=llm,
    )
    eligible = llm.calls[0].eligible_department_ids
    assert "macro_research" not in eligible
    assert "equity_research" in eligible
