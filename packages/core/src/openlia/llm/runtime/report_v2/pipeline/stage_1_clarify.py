"""Stage 1 Clarifier — interactive, capability-manifest-driven (Task P1)."""

from __future__ import annotations

from typing import Any

from openlia.llm.runtime.report_v2.capability_manifest import load_manifest
from openlia.llm.runtime.report_v2.schemas.clarifier import (
    CapabilityWarning,
    ClarifierOutput,
    ClarifyingQuestion,
)

__all__ = [
    "CapabilityWarning",
    "Clarifier",
    "ClarifierOutput",
    "ClarifyingQuestion",
    "build_clarifier_system_prompt",
]


def build_clarifier_system_prompt() -> str:
    """Render capability manifest into a structured system prompt for the LLM."""
    m = load_manifest()
    lines: list[str] = [
        f"You are operating on engine version {m.engine_version}.",
        "",
        "Supported capabilities:",
    ]
    for s in m.supported:
        lines.append(f"  - {s.id}: {s.summary}")

    lines += ["", "Unsupported capabilities (with detection cues):"]
    for u in m.unsupported:
        lines.append(f"  - {u.id}: {u.summary}")
        if u.detect_in_prompt:
            lines.append(f"    Watch for these intents: {u.detect_in_prompt}")
        lines.append(f"    User message on detect:\n      {u.user_message.strip()}")

    lines += [
        "",
        "Read composer_inputs and the selected template. Then output a single",
        "JSON object with EXACTLY these top-level keys and shapes:",
        "",
        "{",
        '  "questions": [',
        '    {"id": "q1", "text": "...", "kind": "multiple_choice" | "free_text",',
        '     "options": ["A","B"] | null}',
        "  ],",
        '  "blocking_warnings": [',
        '    {"capability_id": "...", "detected_phrase": "...", "user_message": "...",',
        '     "available_actions": ["proceed_without","cancel_and_edit","clarify"]}',
        "  ],",
        '  "notices": ["plain string", "another string"],',
        '  "detected_intents": ["intent_id"]',
        "}",
        "",
        "Field rules:",
        '  - "questions[].kind" MUST be "multiple_choice" or "free_text"',
        '     (not "type", not anything else).',
        '  - "notices" MUST be a list of plain strings (not objects).',
        "  - Omit a key only by providing an empty list; do not invent extra keys.",
        "",
        "FAIL LOUD: If you see an intent that does not map to a supported",
        "capability AND is not in the unsupported list, ask a clarifying",
        "question rather than silently dropping it.",
    ]
    return "\n".join(lines)


class Clarifier:
    """Interactive clarifier backed by an LLM; enforces a 3-round maximum."""

    MAX_ROUNDS = 3

    def __init__(self, llm: Any) -> None:
        self._llm = llm

    def clarify(
        self,
        composer_inputs: dict[str, Any],
        template_spec: Any,
        clarification_history: list[str] | None = None,
    ) -> ClarifierOutput:
        history = clarification_history or []
        round_num = len(history) + 1
        if round_num > self.MAX_ROUNDS:
            raise ValueError(
                f"Clarifier exceeded maximum of {self.MAX_ROUNDS} rounds "
                f"(attempted round {round_num})."
            )

        system_prompt = build_clarifier_system_prompt()

        try:
            template_dict = template_spec.model_dump()
        except AttributeError:
            template_dict = {"template_id": getattr(template_spec, "template_id", "unknown")}

        user_payload: dict[str, Any] = {
            "composer_inputs": composer_inputs,
            "template": template_dict,
            "clarification_history": history,
            "round": round_num,
        }

        raw = self._llm.call(system=system_prompt, user=user_payload)
        return ClarifierOutput.model_validate(raw)
