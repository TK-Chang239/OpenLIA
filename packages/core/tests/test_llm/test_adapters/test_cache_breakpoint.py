"""Tests for the prompt-cache breakpoint helpers + adapter behavior.

The cache breakpoint is a sentinel marker embedded in the rendered system
prompt by the cache_breakpoint.yaml.j2 partial. Adapters that support
prompt caching (Anthropic) split the system at the marker and tag the
static prefix with cache_control. Adapters that don't (OpenAI, Gemini,
Ollama, OpenRouter, openai_compat) strip the marker so it never reaches
the model.
"""

from __future__ import annotations

from openlia.llm.adapters._content import (
    CACHE_BREAKPOINT_MARKER,
    split_at_cache_breakpoint,
    strip_cache_breakpoint,
)

# ---- helpers ---------------------------------------------------------------


def test_split_at_cache_breakpoint_returns_two_parts_when_present() -> None:
    text = f"STATIC PART\n\n{CACHE_BREAKPOINT_MARKER}\n\nDYNAMIC PART"
    static, dynamic = split_at_cache_breakpoint(text)
    assert static.strip() == "STATIC PART"
    assert dynamic is not None
    assert dynamic.strip() == "DYNAMIC PART"


def test_split_at_cache_breakpoint_returns_single_part_when_absent() -> None:
    text = "no marker here"
    static, dynamic = split_at_cache_breakpoint(text)
    assert static == "no marker here"
    assert dynamic is None


def test_split_at_cache_breakpoint_handles_none() -> None:
    static, dynamic = split_at_cache_breakpoint(None)
    assert static == ""
    assert dynamic is None


def test_strip_cache_breakpoint_removes_marker_when_present() -> None:
    text = f"BEFORE\n\n{CACHE_BREAKPOINT_MARKER}\n\nAFTER"
    out = strip_cache_breakpoint(text)
    assert CACHE_BREAKPOINT_MARKER not in out
    assert "BEFORE" in out
    assert "AFTER" in out


def test_strip_cache_breakpoint_passes_through_when_absent() -> None:
    assert strip_cache_breakpoint("no marker") == "no marker"


def test_strip_cache_breakpoint_handles_none() -> None:
    assert strip_cache_breakpoint(None) is None


# ---- Secretary prompt actually renders the marker -------------------------


def test_secretary_chat_system_emits_cache_breakpoint_marker() -> None:
    """End-to-end: shared/cache_breakpoint.yaml.j2 is wired into Secretary."""
    from openlia.llm.runtime.prompts import PromptLoader

    out = PromptLoader().render("secretary", "chat.system")
    assert CACHE_BREAKPOINT_MARKER in out, (
        "Secretary chat.system must embed the cache breakpoint marker"
    )


def test_secretary_static_partials_appear_before_marker() -> None:
    """Reorder check: lia_identity, finance_voice, output_discipline all
    static — must be in the cacheable prefix (before the marker)."""
    from openlia.llm.runtime.prompts import PromptLoader

    out = PromptLoader().render("secretary", "chat.system")
    static, dynamic = split_at_cache_breakpoint(out)
    assert dynamic is not None
    # static-prefix anchors
    assert "Lia — short for Little Investor Assistant" in static
    assert "strategist" in static.lower()  # finance_voice persona
    assert "Market vocabulary" in static or "risk-on" in static.lower()  # market_conventions
