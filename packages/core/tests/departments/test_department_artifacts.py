"""Drift-safety tests for per-department artifacts (spec §5.5)."""

from __future__ import annotations

from pathlib import Path

import pytest
from openlia.departments import get_registered_department_ids
from openlia.departments.loader import (
    load_routing_context,
)

_DEPT_DIR = Path(__file__).resolve().parents[2] / "src" / "openlia" / "departments"

_REQUIRED_H2_SECTIONS = (
    "## What this department does",
    "## Data this department needs access to",
    "## Out-of-scope topics",
    "## Example prompts and the data they imply",
)

# Approximate token-count floor: ~300 tokens ≈ ~225 words at the
# usual GPT/Claude tokenizer ratio. We use words rather than chars
# to stay tokenizer-agnostic.
_MIN_WORDS = 225


def _all_dept_ids() -> list[str]:
    return get_registered_department_ids()


@pytest.mark.parametrize("department_id", _all_dept_ids())
def test_routing_context_exists_and_has_required_sections(department_id: str) -> None:
    text = load_routing_context(department_id)
    word_count = len(text.split())
    assert word_count >= _MIN_WORDS, (
        f"{department_id}.routing_context.md has {word_count} words; "
        f"need at least {_MIN_WORDS} (~300 tokens)."
    )
    for header in _REQUIRED_H2_SECTIONS:
        assert header in text, (
            f"{department_id}.routing_context.md missing required H2 section: {header!r}"
        )


def test_load_routing_context_missing_raises() -> None:
    with pytest.raises(FileNotFoundError):
        load_routing_context("not_a_real_department")
