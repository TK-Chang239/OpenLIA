"""Tests that finance_voice partial is wired into every chat department.

The persona / audience model / vocabulary anchors / framework priming in
finance_voice are universal desk-knowledge, not Secretary-specific. The
specialist-output partials (snapshot_format, autonomous_defaults,
market_conventions, exemplars) remain Secretary-only — those describe
freeform conversational defaults the specialist desks intentionally
don't follow.
"""

from __future__ import annotations

import pytest
from openlia.llm.runtime.prompts import PromptLoader

OTHER_CHAT_DEPTS = [
    "equity_research",
    "earnings_update",
    "morning_briefing",
    "macro_research",
    "retail_sentiment",
    "panic_thermometer",
]


@pytest.mark.parametrize("dept", OTHER_CHAT_DEPTS)
def test_other_dept_includes_finance_voice_persona(dept: str) -> None:
    out = PromptLoader().render(dept, "chat.system").lower()
    assert "strategist" in out, f"{dept} chat.system missing finance_voice persona"


@pytest.mark.parametrize("dept", OTHER_CHAT_DEPTS)
def test_other_dept_includes_audience_model(dept: str) -> None:
    out = PromptLoader().render(dept, "chat.system").lower()
    assert "experienced retail investor" in out, (
        f"{dept} chat.system missing finance_voice audience model"
    )


@pytest.mark.parametrize("dept", OTHER_CHAT_DEPTS)
def test_other_dept_includes_vocab_avoid_list(dept: str) -> None:
    out = PromptLoader().render(dept, "chat.system").lower()
    assert "great question" in out, f"{dept} chat.system missing finance_voice vocab avoid list"


@pytest.mark.parametrize("dept", OTHER_CHAT_DEPTS)
def test_other_dept_includes_three_beat_framework(dept: str) -> None:
    out = PromptLoader().render(dept, "chat.system").lower()
    for beat in ("the read", "the why", "what to watch"):
        assert beat in out, f"{dept} chat.system missing framework beat: {beat}"


# ---- Negative assertions: Secretary-specific partials must NOT leak ----


@pytest.mark.parametrize("dept", OTHER_CHAT_DEPTS)
def test_other_dept_does_not_include_snapshot_format(dept: str) -> None:
    """Specialist desks render structured reports/dashboards, not freeform
    market snapshots. snapshot_format stays Secretary-only."""
    out = PromptLoader().render(dept, "chat.system")
    # Anchor on the "decide, do not ask" autonomy line specific to the
    # freeform Secretary surface — specialist desks should not import it.
    assert "decide, do not ask" not in out.lower(), (
        f"{dept} chat.system unexpectedly imports autonomous_defaults"
    )


@pytest.mark.parametrize("dept", OTHER_CHAT_DEPTS)
def test_other_dept_does_not_include_general_exemplar(dept: str) -> None:
    """The always-on general exemplar is a Secretary tone baseline; specialist
    desks have their own output schemas and would over-fit if it leaked in."""
    out = PromptLoader().render(dept, "chat.system").lower()
    # Anchor on the unique dollar-exemplar phrase
    assert "what's the dollar doing this week" not in out, (
        f"{dept} chat.system unexpectedly imports the general exemplar"
    )
