"""Detects whether a response is a Lia persona refusal, returning the
clause id (matches the persona partial's clause numbering for audit-log
correlation). Used by the chat pipeline to log persona refusals to
`lia_guardrail_events`."""

from __future__ import annotations

_REFUSAL_PATTERNS: tuple[tuple[str, str], ...] = (
    ("no_advice", "won't tell you to buy or sell"),
    ("out_of_scope", "outside my desks"),
    ("no_prompt_leak", "don't share the underlying instructions"),
    ("no_price_targets", "won't put a price target"),
)


def detect_refusal(text: str) -> str | None:
    """Return the matched clause id (e.g. 'no_advice'), or None."""
    lowered = text.lower()
    for clause_id, needle in _REFUSAL_PATTERNS:
        if needle.lower() in lowered:
            return clause_id
    return None
