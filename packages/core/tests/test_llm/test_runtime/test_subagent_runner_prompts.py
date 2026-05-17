"""Render the two new shared partials and verify they exist + carry
the required cache-friendly content (no per-turn interpolations)."""
from __future__ import annotations

from pathlib import Path

import openlia.prompts as prompts_pkg


def _read(name: str) -> str:
    p = Path(prompts_pkg.__file__).parent / "shared" / name
    return p.read_text()


def test_subagent_role_partial_describes_no_tools_contract() -> None:
    text = _read("section_subagent_role.yaml.j2")
    lower = text.lower()
    assert "no tools" in lower or "no other tools" in lower
    assert "submit_section" in text
    assert "open_questions" in text


def test_editor_role_partial_describes_final_assembly() -> None:
    text = _read("editor_role.yaml.j2")
    lower = text.lower()
    assert "submit_report" in text
    assert "thread" in lower or "weave" in lower or "narrative" in lower
    assert "cover" in lower


def test_partials_have_no_per_turn_interpolations() -> None:
    """Cache-friendly: nothing time/budget/request-specific in the bodies."""
    for name in ("section_subagent_role.yaml.j2", "editor_role.yaml.j2"):
        text = _read(name)
        assert "{{ current_date" not in text
        assert "{{ search_budget" not in text
