from __future__ import annotations

import pytest
from _fakes import FakeProvider, FakeProviderScript
from openlia.llm.runtime.plan_schema import SectionPlan
from openlia.llm.runtime.section_draft import SectionDraft
from openlia.llm.runtime.subagent_client import (
    SECTION_DRAFT_TOOL_NAME,
    SubagentClient,
    SubagentRequest,
)
from openlia.llm.types import ToolCall


def _valid_section_plan() -> SectionPlan:
    return SectionPlan.model_validate(
        {
            "section_id": "company_overview",
            "title": "Company Overview",
            "narrative_goal": "Frame the business.",
            "key_questions": ["q1", "q2", "q3"],
            "target_depth": "standard",
            "word_budget": 200,
            "data_paths": [],
            "cross_refs": [],
        }
    )


def _ok_draft_args(section_id: str, *, content: str, citations: list[str]) -> dict:
    return {
        "section_id": section_id,
        "blocks": [{"type": "text", "content": content}],
        "citations_used": citations,
        "word_count": len(content.split()),
        "open_questions": [],
    }


def _request() -> SubagentRequest:
    return SubagentRequest(
        role_prompt="ROLE",
        style_guide="STYLE",
        schema_strictness="STRICT",
        company_thesis="MSFT is a mature franchise.",
        cross_section_themes=["cloud growth", "AI capex"],
        this_section=_valid_section_plan(),
        fetched_data={},
        prior_section_summaries=[],
    )


@pytest.mark.asyncio
async def test_subagent_calls_model_with_no_tools_other_than_submit_section() -> None:
    ok = _ok_draft_args("company_overview", content=" ".join(["w"] * 200), citations=["c1"])
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[("tool_calls", [ToolCall(id="c1", name=SECTION_DRAFT_TOOL_NAME, arguments=ok)])]
        )
    )
    client = SubagentClient(provider=provider, reprompt_budget=1)
    draft = await client.draft(_request())
    assert isinstance(draft, SectionDraft)
    assert draft.section_id == "company_overview"

    # No tools other than submit_section.
    req = provider.captured_requests[0]
    tool_names = {t.name for t in (req.tools or [])}
    assert tool_names == {SECTION_DRAFT_TOOL_NAME}
    # Force tool_choice == submit_section
    assert isinstance(req.tool_choice, dict) and "submit_section" in str(req.tool_choice)


@pytest.mark.asyncio
async def test_subagent_reprompts_on_underweight_word_count() -> None:
    sp = _valid_section_plan()  # word_budget=200
    # Turn 0: half the budget (rejected). Turn 1: in range.
    underweight = _ok_draft_args(sp.section_id, content=" ".join(["w"] * 80), citations=["c1"])
    inrange = _ok_draft_args(sp.section_id, content=" ".join(["w"] * 200), citations=["c1"])
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                (
                    "tool_calls",
                    [ToolCall(id="t0", name=SECTION_DRAFT_TOOL_NAME, arguments=underweight)],
                ),
                (
                    "tool_calls",
                    [ToolCall(id="t1", name=SECTION_DRAFT_TOOL_NAME, arguments=inrange)],
                ),
            ]
        )
    )
    client = SubagentClient(provider=provider, reprompt_budget=1)
    draft = await client.draft(_request())
    assert draft.word_count == 200
    assert len(provider.captured_requests) == 2
    # The reprompt turn must contain a tool result message naming the issue.
    second = provider.captured_requests[1].messages
    repair_msg = [m for m in second if m.role == "tool"]
    assert repair_msg and "word_count" in repair_msg[-1].content


@pytest.mark.asyncio
async def test_subagent_accepts_after_budget_exhausted() -> None:
    sp = _valid_section_plan()
    bad = _ok_draft_args(sp.section_id, content=" ".join(["w"] * 50), citations=["c1"])
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                (
                    "tool_calls",
                    [ToolCall(id="t0", name=SECTION_DRAFT_TOOL_NAME, arguments=bad)],
                ),
                (
                    "tool_calls",
                    [ToolCall(id="t1", name=SECTION_DRAFT_TOOL_NAME, arguments=bad)],
                ),
            ]
        )
    )
    client = SubagentClient(provider=provider, reprompt_budget=1)
    draft = await client.draft(_request())
    # Accept the last attempt with an open_question flag.
    assert any("word_count" in q for q in draft.open_questions)


@pytest.mark.asyncio
async def test_subagent_reprompts_on_uncited_numeric_claim() -> None:
    sp = _valid_section_plan()
    uncited = _ok_draft_args(
        sp.section_id,
        content="Revenue grew 12.5% YoY to $245B in FY25 " + " ".join(["w"] * 190),
        citations=[],
    )
    cited = _ok_draft_args(
        sp.section_id,
        content="Revenue grew 12.5% YoY to $245B in FY25 " + " ".join(["w"] * 190),
        citations=["c1"],
    )
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                (
                    "tool_calls",
                    [ToolCall(id="t0", name=SECTION_DRAFT_TOOL_NAME, arguments=uncited)],
                ),
                (
                    "tool_calls",
                    [ToolCall(id="t1", name=SECTION_DRAFT_TOOL_NAME, arguments=cited)],
                ),
            ]
        )
    )
    client = SubagentClient(provider=provider, reprompt_budget=1)
    draft = await client.draft(_request())
    assert draft.citations_used == ["c1"]
    assert len(provider.captured_requests) == 2


@pytest.mark.asyncio
async def test_subagent_reprompts_on_invalid_block_shape() -> None:
    sp = _valid_section_plan()
    bad_blocks = {
        "section_id": sp.section_id,
        "blocks": [
            {"type": "text", "content": " ".join(["w"] * 200)},
            {"type": "line_chart", "title": "X"},
        ],  # missing required `series`
        "citations_used": ["c1"],
        "word_count": 200,
        "open_questions": [],
    }
    fixed = _ok_draft_args(sp.section_id, content=" ".join(["w"] * 200), citations=["c1"])
    provider = FakeProvider(
        script=FakeProviderScript(
            turns=[
                (
                    "tool_calls",
                    [ToolCall(id="t0", name=SECTION_DRAFT_TOOL_NAME, arguments=bad_blocks)],
                ),
                ("tool_calls", [ToolCall(id="t1", name=SECTION_DRAFT_TOOL_NAME, arguments=fixed)]),
            ]
        )
    )
    client = SubagentClient(provider=provider, reprompt_budget=1)
    draft = await client.draft(_request())
    assert all(b["type"] == "text" for b in draft.blocks)
    assert len(provider.captured_requests) == 2
