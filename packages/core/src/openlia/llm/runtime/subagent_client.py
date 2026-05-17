"""SubagentClient — runs one section through a cheap-model LLM.

Strict contract:
  - The model sees only `submit_section` as a tool. No `read_payload`,
    no `web_search`, no data tools.
  - Forced `tool_choice=submit_section`.
  - Output is parsed as `SectionDraft`.
  - Quality guardrails (word_budget, citation coverage, schema validity)
    enforced with at most ``reprompt_budget`` re-prompts.

Per-section context (request body) lives below a cache breakpoint marker;
the role prompt + style + strictness sit above so the prefix is cached
across all subagents in a single run.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from openlia.llm.adapters._content import CACHE_BREAKPOINT_MARKER
from openlia.llm.base import LLMProvider
from openlia.llm.runtime.plan_schema import SectionPlan
from openlia.llm.runtime.section_draft import PriorSection, SectionDraft
from openlia.llm.types import LLMRequest, Message, ToolSchema

SECTION_DRAFT_TOOL_NAME = "submit_section"


@dataclass(frozen=True)
class SubagentRequest:
    role_prompt: str
    style_guide: str
    schema_strictness: str
    company_thesis: str
    cross_section_themes: list[str]
    this_section: SectionPlan
    fetched_data: dict[str, Any]
    prior_section_summaries: list[PriorSection]


def _submit_section_tool() -> ToolSchema:
    return ToolSchema(
        name=SECTION_DRAFT_TOOL_NAME,
        description=(
            "Submit the section draft. Call exactly once with a SectionDraft "
            "payload: section_id, blocks (non-empty), citations_used, "
            "word_count, open_questions."
        ),
        parameters=SectionDraft.model_json_schema(),
    )


def _force_submit_section_choice(provider_kind: str) -> dict[str, Any]:
    if provider_kind == "anthropic":
        return {"type": "tool", "name": SECTION_DRAFT_TOOL_NAME}
    if provider_kind == "gemini":
        return {
            "function_calling_config": {
                "mode": "ANY",
                "allowed_function_names": [SECTION_DRAFT_TOOL_NAME],
            }
        }
    return {"type": "function", "function": {"name": SECTION_DRAFT_TOOL_NAME}}


def _system_prompt(req: SubagentRequest) -> str:
    return (
        f"{req.role_prompt}\n\n"
        f"{req.style_guide}\n\n"
        f"{req.schema_strictness}\n\n"
        f"{CACHE_BREAKPOINT_MARKER}\n"
    )


def _user_prompt(req: SubagentRequest) -> str:
    sp = req.this_section
    summaries = "\n\n".join(
        f"### Prior section {ps.section_id} — {ps.title}\n"
        f"{ps.summary}\n"
        "Key facts: "
        + (", ".join(ps.key_facts_for_threading) if ps.key_facts_for_threading else "(none)")
        for ps in req.prior_section_summaries
    )
    data_blob = json.dumps(req.fetched_data, default=str, indent=2)
    return (
        f"## Company thesis\n{req.company_thesis}\n\n"
        f"## Cross-section themes\n- " + "\n- ".join(req.cross_section_themes) + "\n\n"
        f"## This section\n"
        f"section_id: {sp.section_id}\n"
        f"title: {sp.title}\n"
        f"narrative_goal: {sp.narrative_goal}\n"
        f"target_depth: {sp.target_depth}\n"
        f"word_budget: {sp.word_budget} (+/-20%)\n"
        f"key_questions:\n- " + "\n- ".join(sp.key_questions) + "\n\n"
        f"## Data available to this section\n```json\n{data_blob}\n```\n\n"
        f"## Prior section summaries\n{summaries or '(none — you are the first section)'}\n"
    )


class SubagentClient:
    def __init__(self, *, provider: LLMProvider, reprompt_budget: int = 1) -> None:
        self._provider = provider
        self._reprompt_budget = reprompt_budget

    async def draft(self, request: SubagentRequest) -> SectionDraft:
        system = _system_prompt(request)
        user = _user_prompt(request)
        messages = [Message(role="user", content=user)]
        tools = [_submit_section_tool()]
        tool_choice = _force_submit_section_choice(self._provider.kind)
        response = await self._provider.generate(
            LLMRequest(
                system=system,
                messages=messages,
                tools=tools,
                tool_choice=tool_choice,
                max_tokens=2048,
            )
        )
        # Pick the submit_section call.
        call = next((c for c in response.tool_calls if c.name == SECTION_DRAFT_TOOL_NAME), None)
        if call is None:
            raise ValueError("subagent returned no submit_section call")
        return SectionDraft.model_validate(call.arguments)
