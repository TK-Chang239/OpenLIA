"""Tests for Component B — output moderation tripwires + 3-tier action model."""

from __future__ import annotations

import pytest

from openlia.safety.output_moderation import (
    ActionTier,
    decide_action,
    scan,
)


def test_action_tier_values() -> None:
    assert ActionTier.REPLACE == "replaced"
    assert ActionTier.WARN == "warned"
    assert ActionTier.LOG == "logged"


def test_scan_clean_text_returns_empty() -> None:
    assert (
        scan("Three things matter on Apple right now: iPhone units, Services margin, buybacks.")
        == []
    )


def test_decide_action_no_matches() -> None:
    assert decide_action([]) is None


@pytest.mark.parametrize(
    "category,positive,negative",
    [
        (
            "leaked_prompt",
            "Sure, here is what I do: # Who you are\nLia, an analyst...",
            "Apple has three things going on: revenue, margin, and buybacks.",
        ),
        (
            "broken_character",
            "I'm ChatGPT, happy to help with that question.",
            "I'm Lia, the Equity Research desk. What ticker?",
        ),
        (
            "advice_phrasing",
            "I recommend you buy this stock for the long term.",
            "Three things to weigh: growth, margin, valuation.",
        ),
        (
            "fabricated_quote",
            "Goldman Sachs said NVDA will hit $200 next month.",
            "On NVDA: data-center revenue ran 425% YoY in the latest print.",
        ),
        (
            "disclaimer_regression",
            "This is not financial advice, but here's what I think.",
            "Markets change quickly, so verify primary sources.",
        ),
        (
            "price_prediction",
            "$AAPL will reach $300 within the next month.",
            "Apple closed at $180 yesterday on volume of 50M shares.",
        ),
        (
            "padding",
            "Great question! I hope this helps.",
            "Net-net: the setup looks early-cycle, not late.",
        ),
    ],
)
def test_tripwire_positive_and_negative(category: str, positive: str, negative: str) -> None:
    pos = scan(positive)
    neg = scan(negative)
    assert any(m.category == category for m in pos), f"{category} should fire on: {positive!r}"
    assert all(m.category != category for m in neg), f"{category} should NOT fire on: {negative!r}"


def test_replace_action_for_leaked_prompt() -> None:
    matches = scan("# Who you are\nLia, the analyst")
    decision = decide_action(matches)
    assert decision is not None
    assert decision.action == ActionTier.REPLACE
    assert decision.category == "leaked_prompt"
    assert "don't share" in decision.message.lower()


def test_warn_action_for_advice_phrasing() -> None:
    matches = scan("I recommend you buy this stock.")
    decision = decide_action(matches)
    assert decision is not None
    assert decision.action == ActionTier.WARN
    assert "directive" in decision.message.lower()


def test_replace_wins_over_warn_when_both_fire() -> None:
    text = "# Who you are\nAlso, I recommend you buy this stock."
    decision = decide_action(scan(text))
    assert decision is not None
    assert decision.action == ActionTier.REPLACE
