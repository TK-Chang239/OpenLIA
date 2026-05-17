from __future__ import annotations

from pathlib import Path

import openlia.prompts as prompts_pkg


def test_revision_editor_role_partial_describes_revision_responsibilities() -> None:
    p = Path(prompts_pkg.__file__).parent / "shared" / "revision_editor_role.yaml.j2"
    text = p.read_text()
    lower = text.lower()
    # Must reference key concepts.
    assert "revision_brief" in text
    assert "chat" in lower and ("transcript" in lower or "discussion" in lower)
    assert "preserve" in lower or "keep" in lower
    assert "submit_report" in text


def test_revision_editor_role_partial_has_no_per_turn_interpolations() -> None:
    """Cacheable: no current_date / search_budget templating."""
    p = Path(prompts_pkg.__file__).parent / "shared" / "revision_editor_role.yaml.j2"
    text = p.read_text()
    assert "{{ current_date" not in text
    assert "{{ search_budget" not in text
