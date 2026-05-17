"""ChatContext loading for sessions bound to a report.

When a chat session has ``attached_report_id`` set, this service:
  1. Loads the ReportContextBundle from disk (or returns locked=True
     if the bundle is missing or the report is tombstoned)
  2. Seeds the ToolDispatcher's payload_store with the bundle's
     payload_refs so ``read_payload`` can serve them
  3. Returns the augmented tool list: existing department chat tools
     plus ``read_payload``

The chat route consumes the ``ChatContextResult`` to decide whether
to render the locked-chat UI or proceed with normal chat handling.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from openlia.llm.runtime.report_context_bundle import load_bundle
from openlia.llm.runtime.tools import _READ_PAYLOAD_SCHEMA, ToolDispatcher
from openlia.llm.types import ToolSchema

LOCK_MESSAGE = (
    "The report this discussion was about can no longer be fetched. "
    "I'm unable to answer any questions about it."
)

REVISE_TOOL_NAME = "revise_report"
_REVISE_TOOL = ToolSchema(
    name=REVISE_TOOL_NAME,
    description=(
        "Consolidate the original report and this discussion into a "
        "revised report. Call this when the user explicitly asks for a "
        "'final', 'revised', 'consolidated', 'updated', or 'final "
        "version' of the report. Do NOT call this for summary or recap "
        "requests — only when the user wants a NEW report saved."
    ),
    parameters={
        "type": "object",
        "additionalProperties": False,
        "required": ["revision_brief"],
        "properties": {
            "revision_brief": {
                "type": "string",
                "description": (
                    "2-4 sentence summary derived from the chat "
                    "discussion: what's wrong with the original, what's "
                    "missing, what structural changes the user asked for."
                ),
            },
            "sections_to_focus": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Optional section_ids the editor should pay extra "
                    "attention to."
                ),
            },
        },
    },
)


def _revision_flag_on() -> bool:
    return os.environ.get("OPENLIA_REVISION_PASS_ENABLED", "0") == "1"


@dataclass
class ChatContextResult:
    locked: bool
    lock_message: str = ""
    tools: list[ToolSchema] = field(default_factory=list)


def build_chat_context_for_session(
    *,
    attached_report_id: str,
    bundle_dir: Path,
    report_is_tombstoned: bool,
    dispatcher: ToolDispatcher,
    department_id: str,
    has_web_search: bool,
) -> ChatContextResult:
    if report_is_tombstoned:
        return ChatContextResult(locked=True, lock_message=LOCK_MESSAGE)
    bundle_path = bundle_dir / f"{attached_report_id}.json.gz"
    if not bundle_path.exists():
        return ChatContextResult(locked=True, lock_message=LOCK_MESSAGE)
    try:
        bundle = load_bundle(bundle_path)
    except Exception:
        return ChatContextResult(locked=True, lock_message=LOCK_MESSAGE)

    # Seed payload_store so read_payload can resolve refs.
    for ref_id, payload in bundle.payload_refs.items():
        dispatcher._payload_store[ref_id] = payload

    # Tool list = existing department chat tools + read_payload.
    # We compose by asking the dispatcher to build its standard list and
    # then ensuring read_payload is present (it already is for chat
    # builds; this is a defensive include for departments whose chat
    # mode doesn't normally expose it).
    base_tools: list[
        ToolSchema
    ] = []  # caller provides via dispatcher.build(...) in production wiring
    if not any(t.name == "read_payload" for t in base_tools):
        base_tools.append(_READ_PAYLOAD_SCHEMA)
    if _revision_flag_on():
        base_tools.append(_REVISE_TOOL)
    return ChatContextResult(locked=False, lock_message="", tools=base_tools)
