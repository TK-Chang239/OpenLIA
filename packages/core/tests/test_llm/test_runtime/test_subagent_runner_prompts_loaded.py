"""The runner must load section_subagent_role.yaml.j2 and editor_role.yaml.j2
as the cacheable role prompts passed to SubagentClient and EditorClient."""

from __future__ import annotations

from pathlib import Path

import openlia.prompts as prompts_pkg
from openlia.llm.runtime.subagent_runner import (
    load_editor_role,
    load_section_subagent_role,
)


def test_load_section_subagent_role_returns_partial_content() -> None:
    text = load_section_subagent_role()
    assert "submit_section" in text
    # Confirm we are reading from the shipped partials directory.
    p = Path(prompts_pkg.__file__).parent / "shared" / "section_subagent_role.yaml.j2"
    assert p.read_text().strip().startswith(text.strip()[:40])


def test_load_editor_role_returns_partial_content() -> None:
    text = load_editor_role()
    assert "submit_report" in text
