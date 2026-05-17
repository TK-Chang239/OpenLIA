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
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from openlia.llm.adapters._content import CACHE_BREAKPOINT_MARKER
from openlia.llm.base import LLMProvider
from openlia.llm.runtime.plan_schema import SectionPlan
from openlia.llm.runtime.section_draft import PriorSection, SectionDraft
from openlia.llm.types import LLMRequest, LLMResponse, Message, ToolSchema
from openlia.reports.validator import validate_report_payload

SECTION_DRAFT_TOOL_NAME = "submit_section"

_NUMERIC_CLAIM_RE = re.compile(r"\b(\d+(?:[.,]\d+)*\s*%?|\$\s*\d+(?:[.,]\d+)*(?:[KMB])?)\b")


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
    def __init__(
        self,
        *,
        provider: LLMProvider,
        reprompt_budget: int = 1,
        on_done: Callable[[LLMResponse], None] | None = None,
    ) -> None:
        self._provider = provider
        self._reprompt_budget = reprompt_budget
        self._on_done = on_done

    async def draft(self, request: SubagentRequest) -> SectionDraft:
        system = _system_prompt(request)
        user = _user_prompt(request)
        messages: list[Message] = [Message(role="user", content=user)]
        tools = [_submit_section_tool()]
        tool_choice = _force_submit_section_choice(self._provider.kind)

        last_draft: SectionDraft | None = None
        last_issues: list[str] = []

        for attempt in range(self._reprompt_budget + 1):
            response = await self._provider.generate(
                LLMRequest(
                    system=system,
                    messages=messages,
                    tools=tools,
                    tool_choice=tool_choice,
                    # Section drafts can be 600-2000 words of prose plus block
                    # JSON. 2048 was too tight; 6144 covers reasoning + output
                    # without bleeding into the editor budget.
                    max_tokens=6144,
                )
            )
            if self._on_done is not None:
                self._on_done(response)
            call = next((c for c in response.tool_calls if c.name == SECTION_DRAFT_TOOL_NAME), None)
            if call is None:
                # No submit_section call at all — treat as a structural
                # issue and re-prompt rather than bubbling. The subagent
                # sometimes calls a non-existent tool or returns prose-only.
                if attempt == self._reprompt_budget:
                    raise ValueError("subagent returned no submit_section call")
                messages.append(
                    Message(
                        role="user",
                        content=(
                            "You did not call submit_section. Call it exactly "
                            "once with a SectionDraft payload: section_id, "
                            "blocks (non-empty), citations_used, word_count, "
                            "open_questions."
                        ),
                    )
                )
                continue
            try:
                draft = SectionDraft.model_validate(call.arguments)
            except Exception as exc:
                # Mini model frequently omits required SectionDraft fields
                # (most often `blocks` itself). Pre-Plan-1-iteration-4 we
                # bubbled this as a hard ReportError; instead treat it as a
                # validation guardrail and let the model try again.
                if attempt == self._reprompt_budget:
                    raise
                issue_msg = f"SectionDraft schema invalid: {exc!s}"
                messages.append(
                    Message(role="assistant", content="", tool_calls=(call,))
                )
                messages.append(
                    Message(
                        role="tool",
                        content=json.dumps(
                            {"issues": [issue_msg], "hint": "Fix and re-submit."}
                        ),
                        tool_call_id=call.id,
                    )
                )
                continue
            issues = self._validate_draft(draft, request.this_section)
            if not issues:
                return draft
            last_draft = draft
            last_issues = issues
            # If this was the last allowed attempt, fall through to flag.
            if attempt == self._reprompt_budget:
                break
            # Otherwise: append assistant + tool repair messages and loop.
            messages.append(Message(role="assistant", content="", tool_calls=(call,)))
            messages.append(
                Message(
                    role="tool",
                    content=json.dumps({"issues": issues, "hint": "Fix and re-submit."}),
                    tool_call_id=call.id,
                )
            )

        # Accepted last attempt; flag the issues.
        assert last_draft is not None
        flagged_open = list(last_draft.open_questions)
        flagged_open.extend(f"[auto-flag] {i}" for i in last_issues)
        return last_draft.model_copy(update={"open_questions": flagged_open})

    def _validate_draft(self, draft: SectionDraft, sp: SectionPlan) -> list[str]:
        issues: list[str] = []
        lo, hi = int(sp.word_budget * 0.8), int(sp.word_budget * 1.2)
        if not (lo <= draft.word_count <= hi):
            issues.append(
                f"word_count={draft.word_count} outside +/-20% of word_budget={sp.word_budget} "
                f"(allowed range {lo}-{hi})."
            )
        if draft.section_id != sp.section_id:
            issues.append(
                f"section_id={draft.section_id!r} does not match expected {sp.section_id!r}."
            )
        has_numeric_claim = False
        for block in draft.blocks:
            if block.get("type") == "text":
                if _NUMERIC_CLAIM_RE.search(str(block.get("content", ""))):
                    has_numeric_claim = True
                    break
        if has_numeric_claim and not draft.citations_used:
            issues.append(
                "TextBlocks contain numeric claims (digits, percentages, "
                "$amounts) but citations_used is empty. Add citation ids."
            )
        # Strict per-block validation by passing a one-section dummy payload
        # through the existing validator. Cheaper than rebuilding block-level
        # discrimination here.
        dummy = {
            "cover": {"title": "x", "subtitle": "x", "tagline": "x"},
            "sections": [{"id": draft.section_id, "title": "x", "blocks": draft.blocks}],
            "schema_version": "2.0",
            "department": "equity_research",
            "generated_at": "2026-05-16T00:00:00+00:00",
        }
        try:
            validate_report_payload(dummy)
        except Exception as exc:
            issues.append(f"block schema invalid: {exc!s}")
        return issues
