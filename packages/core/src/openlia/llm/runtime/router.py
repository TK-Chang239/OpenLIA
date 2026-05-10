"""Runtime router — picks a tool subset for a chat conversation.

Spec: docs/superpowers/specsv2/2026-04-27-connector-dataflow-design.md §8.

The router is a small (Haiku-tier) LLM call. It runs once at conversation
start and again on every escalation. Inputs:

  - `routing_context`: the dept's `<dept>.routing_context.md` body.
  - `user_prompt`: the user's first message (or an escalation reason
    appended for re-routes).
  - `candidate_tools`: full validated tool inventory across the dept's
    configured connectors (already prefixed by `provider_id`).

Output: a list of tool names. Names not present in the candidate pool
are dropped with a warning — never raise. Tolerance is intentional:
hallucinated names must not crash a live conversation.
"""

from __future__ import annotations

import json
import logging
from typing import Any, Protocol, runtime_checkable

logger = logging.getLogger(__name__)


@runtime_checkable
class LlmClient(Protocol):
    """Minimal contract for the runtime-router LLM call.

    Mirrors the wizard-time adapter's `LlmClient` so the same fakes can
    be reused in tests. The router asks the LLM to return a strict JSON
    array of strings.
    """

    async def generate_json(self, *, prompt: str) -> Any: ...


_PROMPT_TEMPLATE = """\
You are routing tools for the {department_id} department.

{routing_context}

User prompt:
{user_prompt}

Available tools (the dept's full validated tool inventory):
{candidate_tools_json}

Pick the smallest subset of tools that lets the main LLM answer this
prompt well.

Be liberal: if a tool might plausibly be useful during the conversation,
include it.

Be conservative: do not include tools that are clearly off-topic for
the dept.

Return the chosen tools as a JSON array of tool names.
"""


def _format_candidate_tools(candidate_tools: list[dict[str, Any]]) -> str:
    """Compact JSON serialization. Each entry: name + description.

    Schemas are omitted to keep the router prompt small; the router only
    needs to pick names, not invoke tools.
    """
    trimmed = [
        {"name": t["name"], "description": t.get("description", "")} for t in candidate_tools
    ]
    return json.dumps(trimmed, indent=2)


def _coerce_to_name_list(raw: Any) -> list[str]:
    """Accept either a JSON array of strings or {"tools": [...]}."""
    if isinstance(raw, list):
        return [str(item) for item in raw if isinstance(item, str)]
    if isinstance(raw, dict):
        for key in ("tools", "names", "selected"):
            value = raw.get(key)
            if isinstance(value, list):
                return [str(item) for item in value if isinstance(item, str)]
    return []


async def route_tools(
    *,
    department_id: str,
    routing_context: str,
    user_prompt: str,
    candidate_tools: list[dict[str, Any]],
    llm_client: LlmClient,
) -> list[str]:
    """Run the router and return tool names from the candidate pool.

    Spec §8.4. Names not present in `candidate_tools` are dropped with
    a logger warning — never raises on bad output.
    """
    if not candidate_tools:
        return []

    prompt = _PROMPT_TEMPLATE.format(
        department_id=department_id,
        routing_context=routing_context,
        user_prompt=user_prompt,
        candidate_tools_json=_format_candidate_tools(candidate_tools),
    )

    candidate_names = [t["name"] for t in candidate_tools]

    try:
        raw = await llm_client.generate_json(prompt=prompt)
    except Exception as exc:
        # Issue #99: an empty fallback forces the model into escalation,
        # which leads it to pull in irrelevant tools (e.g. firecrawl__parse)
        # when something simpler — like reading inline attachment content —
        # is already viable. Fall back to the full validated candidate pool
        # instead so the main model has the same surface routing would have
        # exposed on its best day.
        logger.warning(
            "runtime router failed for dept %s; falling back to full candidate pool (%d tools): %s",
            department_id,
            len(candidate_names),
            exc,
        )
        return list(candidate_names)

    proposed = _coerce_to_name_list(raw)
    valid_names = {t["name"] for t in candidate_tools}

    selected: list[str] = []
    seen: set[str] = set()
    for name in proposed:
        if name in valid_names and name not in seen:
            selected.append(name)
            seen.add(name)
        elif name not in valid_names:
            logger.warning(
                "runtime router for dept %s returned unknown tool %r; dropping",
                department_id,
                name,
            )
    if not selected:
        # Same reasoning as the exception branch: a malformed router output
        # that produces zero valid names should fall back to the full pool.
        logger.warning(
            "runtime router for dept %s returned no valid names; falling back "
            "to full candidate pool (%d tools)",
            department_id,
            len(candidate_names),
        )
        return list(candidate_names)
    return selected


__all__ = ["LlmClient", "route_tools"]
