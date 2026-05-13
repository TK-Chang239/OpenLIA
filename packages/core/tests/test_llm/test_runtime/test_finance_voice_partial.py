"""Tests for the finance_voice partial (fix-chats commit 3).

The partial bundles four levers documented in the spec:
  - Persona (20-year multi-asset sell-side strategist, no real-firm name)
  - Audience model (experienced retail investor — not super technical)
  - Vocabulary anchors (use / avoid lists)
  - Framework priming (the read / the why / what to watch)
"""

from __future__ import annotations

from openlia.llm.runtime.prompts import PromptLoader


def _render_secretary() -> str:
    return PromptLoader().render("secretary", "chat.system")


def test_secretary_includes_finance_voice_persona() -> None:
    """Persona anchor — analyst strategist framing, no real-firm name."""
    out = _render_secretary().lower()
    assert "strategist" in out
    # Anti-pattern guard: no real firm names (Morgan Stanley etc.)
    for forbidden in ("morgan stanley", "goldman sachs", "jpmorgan"):
        assert forbidden not in out, f"persona must not name real firm: {forbidden}"


def test_secretary_includes_audience_model() -> None:
    """Audience anchor — experienced retail investor, not CFA-level / not novice."""
    out = _render_secretary().lower()
    assert "experienced retail investor" in out


def test_secretary_includes_vocabulary_use_list() -> None:
    """Vocabulary 'use' list — the desk words Lia reaches for."""
    out = _render_secretary().lower()
    for term in ("tape", "read-through", "bps", "term structure"):
        assert term in out, f"vocabulary 'use' list missing {term}"


def test_secretary_includes_vocabulary_avoid_list() -> None:
    """Vocabulary 'avoid' list — filler phrases that add zero information."""
    out = _render_secretary().lower()
    for term in ("great question", "delve", "as an ai", "i hope this helps"):
        assert term in out, f"vocabulary 'avoid' list missing {term}"


def test_secretary_includes_default_answer_shape() -> None:
    """Framework priming — the three-beat default shape."""
    out = _render_secretary().lower()
    for beat in ("the read", "the why", "what to watch"):
        assert beat in out, f"default answer shape missing beat: {beat}"
