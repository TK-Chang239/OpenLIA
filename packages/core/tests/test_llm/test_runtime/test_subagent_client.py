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
