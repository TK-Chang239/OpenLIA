"""Escalation tool — `request_additional_tools`.

Spec: docs/superpowers/specsv2/2026-04-27-connector-dataflow-design.md §8.5.

Every routed conversation includes a system-provided escalation tool.
When the main LLM emits a `tool_use` for `request_additional_tools` the
orchestrator pauses, re-invokes the runtime router with the escalation
reason, and merges the additional tools into the conversation's tool
set monotonically.

Multiple escalations across a long conversation are allowed; the set
only grows, never shrinks.
"""

from __future__ import annotations

from typing import Any

from openlia.llm.runtime.router import LlmClient, route_tools

ESCALATION_TOOL_NAME = "request_additional_tools"

ESCALATION_TOOL_DEFINITION: dict[str, Any] = {
    "name": ESCALATION_TOOL_NAME,
    "description": (
        "Call this if you realize you need a capability that's not in "
        "your current toolset. Provide a one-sentence reason describing "
        "what you want to do; new tools will be added to your toolset "
        "for the rest of the conversation."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "reason": {
                "type": "string",
                "description": "One-sentence description of the missing capability.",
            },
            "category_hint": {
                "type": "string",
                "description": "Optional connector category hint (financial, news, social, ...).",
            },
        },
        "required": ["reason"],
    },
}


def _format_escalation_prompt(reason: str, category_hint: str | None) -> str:
    """Build the user-prompt analogue for a re-route."""
    base = f"The main LLM has requested additional tools. Reason: {reason}"
    if category_hint:
        base += f"\n(Category hint: {category_hint})"
    base += (
        "\n\nPick any additional tools from the inventory that would help. "
        "Return only the new names — the existing tool set is preserved."
    )
    return base


async def merge_escalation(
    *,
    department_id: str,
    routing_context: str,
    current_tools: list[str],
    escalation_arguments: dict[str, Any],
    candidate_tools: list[dict[str, Any]],
    llm_client: LlmClient,
) -> list[str]:
    """Re-invoke the router on an escalation and return the merged set.

    Spec §8.5: the set grows monotonically (no removals; no duplicates).
    """
    reason = str(escalation_arguments.get("reason", "")).strip()
    category_hint_raw = escalation_arguments.get("category_hint")
    category_hint = (
        str(category_hint_raw).strip()
        if isinstance(category_hint_raw, str) and category_hint_raw.strip()
        else None
    )

    proposed = await route_tools(
        department_id=department_id,
        routing_context=routing_context,
        user_prompt=_format_escalation_prompt(reason, category_hint),
        candidate_tools=candidate_tools,
        llm_client=llm_client,
    )

    merged: list[str] = list(current_tools)
    seen = set(current_tools)
    for name in proposed:
        if name not in seen:
            merged.append(name)
            seen.add(name)
    return merged


def summarize_added(before: list[str], after: list[str]) -> str:
    """One-line summary suitable for the escalation tool_result."""
    added = [name for name in after if name not in set(before)]
    if not added:
        return "No additional tools matched the request."
    return f"Added tools: {', '.join(added)}."


__all__ = [
    "ESCALATION_TOOL_DEFINITION",
    "ESCALATION_TOOL_NAME",
    "merge_escalation",
    "summarize_added",
]
