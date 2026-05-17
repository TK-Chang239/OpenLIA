"""Unit tests for the exemplar selector (fix-chats).

Deterministic regex/keyword classifier. Returns the names of exemplar
files that should be conditionally injected into the chat system prompt,
based on the user's latest message. Pure function — no DB, no LLM call.
"""

from __future__ import annotations

import pytest

from openlia_server.services.exemplar_selector import select_exemplars


# ---- snapshot triggers -----------------------------------------------------


@pytest.mark.parametrize(
    "message",
    [
        "give me a market snapshot",
        "show me the tape",
        "what's the market doing today?",
        "what's the market doing right now",
        "what are today's main movers?",
        "what's leading and what's lagging?",
        "premarket read please",
        "afterhours snapshot",
        "after-hours read",
    ],
)
def test_snapshot_triggers_select_snapshot(message: str) -> None:
    selected = select_exemplars(message)
    assert "snapshot" in selected


# ---- single_stock triggers -------------------------------------------------


@pytest.mark.parametrize(
    "message",
    [
        "thoughts on NVDA here?",
        "thoughts on $TSLA",
        "read on AAPL please",
        "your view on MSFT",
        "what do you think about $AMZN",
        "$GOOG looking interesting",
    ],
)
def test_single_stock_triggers_select_single_stock(message: str) -> None:
    selected = select_exemplars(message)
    assert "single_stock" in selected


# ---- continuation triggers -------------------------------------------------


@pytest.mark.parametrize(
    "message",
    [
        "reformat this into a clean premarket snapshot",
        "redo that",
        "do that again",
        "expand on this",
        "tighten this up",
        "shorten this",
        "same thing for TLT",
        "make it a snapshot",
        "make it a table",
    ],
)
def test_continuation_triggers_select_continuation(message: str) -> None:
    selected = select_exemplars(message)
    assert "continuation" in selected


# ---- fallback / no match ---------------------------------------------------


@pytest.mark.parametrize(
    "message",
    [
        "hi",
        "what time is it?",
        "tell me a joke",
        "",
    ],
)
def test_no_match_returns_empty(message: str) -> None:
    """No category match returns []; the always-on general exemplar handles baseline tone."""
    assert select_exemplars(message) == []


# ---- multiple matches ------------------------------------------------------


def test_combined_continuation_and_snapshot() -> None:
    """User can trigger multiple categories — selector returns all matches."""
    selected = select_exemplars("redo this snapshot but tighten it")
    assert "continuation" in selected
    assert "snapshot" in selected


def test_combined_continuation_and_single_stock() -> None:
    selected = select_exemplars("redo your read on NVDA")
    assert "continuation" in selected
    assert "single_stock" in selected


# ---- returned order is stable + deduplicated -------------------------------


def test_return_order_is_stable_and_deduplicated() -> None:
    """Selector returns names in a canonical order: snapshot, single_stock, continuation.

    A canonical order keeps prompt-cache prefixes stable across requests
    that match the same set.
    """
    msg = "redo your snapshot read on NVDA"
    selected = select_exemplars(msg)
    # canonical order
    assert selected == sorted(set(selected), key=["snapshot", "single_stock", "continuation"].index)
    # no duplicates
    assert len(selected) == len(set(selected))
