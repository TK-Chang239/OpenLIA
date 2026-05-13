"""Tests for the always-on general exemplar + recalibrated default length.

Two coupled changes (fix-chats):
  - exemplars/general.yaml.j2 — one worked Q&A (dollar this week) wired
    always-on into Secretary's static prompt as the baseline tone anchor.
  - finance_voice.yaml.j2 default answer shape recalibrated: "normal" mode
    is 4-8 sentences with real analytical depth, not 3-sentence terse.
    Concise + detailed still gated by response_length.yaml.j2.
"""

from __future__ import annotations

from openlia.llm.runtime.prompts import PromptLoader


def _render_secretary() -> str:
    return PromptLoader().render("secretary", "chat.system")


def test_general_exemplar_includes_dollar_worked_example() -> None:
    """general.yaml.j2 carries the locked dollar exemplar (analyst-style density)."""
    out = _render_secretary()
    # Anchor on phrases unique to the dollar exemplar so the test fails if
    # the file is missing or accidentally replaced with placeholder content.
    assert "DXY" in out
    assert "rate differential" in out
    assert "fresh leg" in out
    assert "divergence to fade" in out


def test_general_exemplar_includes_user_assistant_framing() -> None:
    """The exemplar is rendered as a User/You worked example, not as bare prose."""
    out = _render_secretary()
    assert "**User:**" in out, "general exemplar must use **User:** framing"
    assert "**You:**" in out, "general exemplar must use **You:** framing"


def test_default_length_anchor_for_normal_mode() -> None:
    """finance_voice default shape names 'normal' length range explicitly."""
    out = _render_secretary().lower()
    # Anchor phrase that distinguishes the recalibrated default
    assert "4-8 sentences" in out or "4 to 8 sentences" in out, (
        "finance_voice must anchor 'normal' default at 4-8 sentences"
    )


def test_default_length_scales_with_response_length_modes() -> None:
    """finance_voice default shape references all three response-length modes."""
    out = _render_secretary().lower()
    assert "concise" in out
    assert "detailed" in out
    # 'normal' anchor in the response-length scaling section
    assert "normal" in out


def test_default_length_section_anchors_to_three_beat_framework() -> None:
    """The framework (the read / the why / what to watch) is preserved."""
    out = _render_secretary().lower()
    for beat in ("the read", "the why", "what to watch"):
        assert beat in out
