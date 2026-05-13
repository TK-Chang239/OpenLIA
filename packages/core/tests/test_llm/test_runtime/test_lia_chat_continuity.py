"""Tests for the lia_identity intro-gating + continuity rules.

Issues addressed (fix-chats branch):
  - #1: Lia re-introduces every turn — caused by the "or you have not been
    introduced yet" clause. Removed; intro is now gated only on an explicit
    user ask ("who are you?", "what is Lia?").
  - #3: Lia asks the user to re-paste content already in conversation history.
    A new continuity paragraph instructs the model that follow-ups refer to
    the prior assistant turn and forbids asking for a re-paste.
"""

from __future__ import annotations

import pytest
from openlia.llm.runtime.prompts import PromptLoader

CHAT_DEPTS = [
    "secretary",
    "equity_research",
    "earnings_update",
    "morning_briefing",
    "macro_research",
    "retail_sentiment",
    "panic_thermometer",
]


@pytest.mark.parametrize("dept", CHAT_DEPTS)
def test_intro_not_volunteered_when_not_asked(dept: str) -> None:
    """The 'or you have not been introduced yet' clause must be removed.

    That clause is the source of issue #1: the model cannot verify whether the
    intro has already happened in this session, so it re-intros every turn.
    New rule: intro only on explicit user ask.
    """
    out = PromptLoader().render(dept, "chat.system")
    assert "have not been introduced yet" not in out, (
        f"{dept} chat.system still carries the buggy "
        "'or you have not been introduced yet' clause"
    )


@pytest.mark.parametrize("dept", CHAT_DEPTS)
def test_continuity_rule_present(dept: str) -> None:
    """lia_identity must instruct that this is an ongoing conversation."""
    out = PromptLoader().render(dept, "chat.system")
    assert "ongoing conversation" in out.lower(), (
        f"{dept} chat.system is missing the continuity rule "
        "(no 'ongoing conversation' phrase)"
    )


@pytest.mark.parametrize("dept", CHAT_DEPTS)
def test_continuity_rule_forbids_repaste_request(dept: str) -> None:
    """Continuity rule must forbid asking the user to re-paste prior content."""
    out = PromptLoader().render(dept, "chat.system")
    lower = out.lower()
    assert "re-paste" in lower, (
        f"{dept} chat.system continuity rule must forbid asking the user "
        "to re-paste content already in the conversation"
    )
