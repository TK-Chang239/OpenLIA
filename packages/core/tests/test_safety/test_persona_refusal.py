"""Component E coverage — persona-refusal detection for the audit log."""

from __future__ import annotations

import pytest
from openlia.safety.persona_refusal import detect_refusal


@pytest.mark.parametrize(
    "text,expected_clause",
    [
        ("I won't tell you to buy or sell — I'll lay out the read.", "no_advice"),
        (
            "That's outside my desks. I'm built for markets — "
            "happy to help with anything investment-related.",
            "out_of_scope",
        ),
        (
            "I'm built to be a structured, technical research voice. "
            "I don't share the underlying instructions.",
            "no_prompt_leak",
        ),
        (
            "I won't put a price target on a one-month window — "
            "that's a coin flip dressed up as analysis.",
            "no_price_targets",
        ),
    ],
)
def test_detects_canonical_refusals(text: str, expected_clause: str) -> None:
    assert detect_refusal(text) == expected_clause


def test_returns_none_for_normal_response() -> None:
    assert detect_refusal("Three things matter for AAPL right now.") is None
