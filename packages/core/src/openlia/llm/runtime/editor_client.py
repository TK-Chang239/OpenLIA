"""EditorClient — runs the final assembly pass.

Flagship model. Forced `submit_report` tool call. Strict ReportSchema
validation via the existing validator. One repair attempt on validation
failure; further failures are returned as-is for the caller to apply
its existing coercion fallback.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from openlia.llm.adapters._content import CACHE_BREAKPOINT_MARKER
from openlia.llm.base import LLMProvider
from openlia.llm.runtime.section_draft import OpenQuestion, SectionDraft
from openlia.llm.types import LLMRequest, LLMResponse, Message, ToolSchema
from openlia.reports.schema import ReportSchema
from openlia.reports.validator import validate_report_payload

EDITOR_TOOL_NAME = "submit_report"


@dataclass(frozen=True)
class EditorRequest:
    role_prompt: str
    style_guide: str
    schema_strictness: str
    company_thesis: str
    cross_section_themes: list[str]
    section_drafts: list[SectionDraft]
    open_questions: list[OpenQuestion]
    framework_cover_instructions: str


# Server-controlled fields the editor must not emit; mirrors the
# stripping the classic runner does for its submit_report schema.
_SERVER_CONTROLLED = frozenset(
    {"schema_version", "department", "generated_at", "page_furniture", "meta_stats"}
)


def _submit_report_tool() -> ToolSchema:
    schema = copy.deepcopy(ReportSchema.model_json_schema())
    props = schema.get("properties", {})
    for f in _SERVER_CONTROLLED:
        props.pop(f, None)
    required = schema.get("required") or []
    schema["required"] = [r for r in required if r not in _SERVER_CONTROLLED]
    schema["properties"] = props
    return ToolSchema(
        name=EDITOR_TOOL_NAME,
        description="Submit the final report. Call exactly once with cover + sections.",
        parameters=schema,
    )


def _force_submit_report_choice(provider_kind: str) -> dict[str, Any]:
    if provider_kind == "anthropic":
        return {"type": "tool", "name": EDITOR_TOOL_NAME}
    if provider_kind == "gemini":
        return {
            "function_calling_config": {
                "mode": "ANY",
                "allowed_function_names": [EDITOR_TOOL_NAME],
            }
        }
    return {"type": "function", "function": {"name": EDITOR_TOOL_NAME}}


def _system_prompt(req: EditorRequest) -> str:
    return (
        f"{req.role_prompt}\n\n"
        f"{req.style_guide}\n\n"
        f"{req.schema_strictness}\n\n"
        f"{CACHE_BREAKPOINT_MARKER}\n"
    )


def _user_prompt(req: EditorRequest) -> str:
    drafts_blob = json.dumps([d.model_dump() for d in req.section_drafts], default=str, indent=2)
    open_blob = json.dumps([q.model_dump() for q in req.open_questions], default=str, indent=2)
    themes_list = "\n- ".join(req.cross_section_themes)
    return (
        f"## Company thesis\n{req.company_thesis}\n\n"
        f"## Cross-section themes\n- {themes_list}\n\n"
        f"## Section drafts (verbatim from subagents)\n```json\n{drafts_blob}\n```\n\n"
        f"## Open questions\n```json\n{open_blob}\n```\n\n"
        f"## Cover instructions\n{req.framework_cover_instructions}\n"
    )


class EditorClient:
    def __init__(
        self,
        *,
        provider: LLMProvider,
        repair_budget: int = 1,
        max_output_tokens: int = 8192,
        on_done: Callable[[LLMResponse], None] | None = None,
    ) -> None:
        self._provider = provider
        self._repair_budget = repair_budget
        self._max_output_tokens = max_output_tokens
        self._on_done = on_done

    async def compose(self, request: EditorRequest) -> dict[str, Any]:
        system = _system_prompt(request)
        messages: list[Message] = [Message(role="user", content=_user_prompt(request))]
        tools = [_submit_report_tool()]
        tool_choice = _force_submit_report_choice(self._provider.kind)
        last_payload: dict[str, Any] | None = None
        last_error: str | None = None
        for attempt in range(self._repair_budget + 1):
            response = await self._provider.generate(
                LLMRequest(
                    system=system,
                    messages=messages,
                    tools=tools,
                    tool_choice=tool_choice,
                    max_tokens=self._max_output_tokens,
                )
            )
            if self._on_done is not None:
                self._on_done(response)
            call = next((c for c in response.tool_calls if c.name == EDITOR_TOOL_NAME), None)
            if call is None:
                raise ValueError("editor returned no submit_report call")
            payload = call.arguments if isinstance(call.arguments, dict) else {}
            try:
                validate_report_payload(_stamped(copy.deepcopy(payload)))
                return payload
            except Exception as exc:
                last_payload = payload
                last_error = str(exc)
                if attempt == self._repair_budget:
                    break
                messages.append(Message(role="assistant", content="", tool_calls=(call,)))
                messages.append(
                    Message(
                        role="tool",
                        content=json.dumps({"error": last_error, "hint": "Fix and re-submit."}),
                        tool_call_id=call.id,
                    )
                )
        # Repair exhausted — return the last attempt; caller will coerce.
        assert last_payload is not None
        return last_payload


def _stamped(payload: dict[str, Any]) -> dict[str, Any]:
    """Stamp server-controlled fields so validation does not raise missing-required
    errors for fields the editor is not responsible for."""
    payload.setdefault("schema_version", "2.0")
    payload.setdefault("department", "equity_research")
    payload.setdefault("generated_at", "2026-01-01T00:00:00+00:00")
    return payload
