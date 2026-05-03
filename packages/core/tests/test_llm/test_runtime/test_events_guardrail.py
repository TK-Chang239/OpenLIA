"""ChatGuardrail event lives in the SseEvent union and serializes."""

from __future__ import annotations

from openlia.llm.runtime.events import ChatGuardrail, SseEvent, to_wire


def test_chat_guardrail_to_wire() -> None:
    ev = ChatGuardrail(
        message_id="m_abc",
        category="leaked_prompt",
        action="replaced",
        replacement="I don't share my underlying instructions.",
    )
    wire = to_wire(ev)
    assert wire["type"] == "chat.guardrail"
    assert wire["category"] == "leaked_prompt"
    assert wire["action"] == "replaced"
    assert wire["replacement"] == "I don't share my underlying instructions."


def test_chat_guardrail_in_sse_union() -> None:
    ev: SseEvent = ChatGuardrail(
        message_id="m_x",
        category="advice_phrasing",
        action="warned",
        replacement=None,
        chip_text="Flagged: directive advice phrasing",
    )
    assert isinstance(ev, ChatGuardrail)
