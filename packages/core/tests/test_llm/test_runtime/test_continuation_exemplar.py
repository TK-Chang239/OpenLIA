"""Tests for the continuation exemplar (fix-chats, conditional injection).

The exemplar lives at shared/exemplars/continuation.yaml.j2 and gets
injected by the deterministic exemplar_selector when the user's message
matches a continuation trigger ("reformat", "redo", "do that", "expand",
"tighten", "shorten", "same thing for").

Directly addresses fix-chats issue #3.
"""

from __future__ import annotations

from pathlib import Path

import openlia


def _exemplar_path() -> Path:
    pkg_root = Path(openlia.__file__).resolve().parent
    return pkg_root / "prompts" / "shared" / "exemplars" / "continuation.yaml.j2"


def test_continuation_exemplar_file_exists() -> None:
    assert _exemplar_path().is_file(), "continuation.yaml.j2 exemplar must exist"


def test_continuation_exemplar_shows_prior_turn_context() -> None:
    """Exemplar must demonstrate that the source is the prior assistant turn."""
    body = _exemplar_path().read_text(encoding="utf-8")
    assert "Prior turn" in body, (
        "continuation exemplar must label the prior assistant turn so the "
        "model sees the multi-turn context pattern"
    )


def test_continuation_exemplar_enumerates_trigger_words() -> None:
    """The trigger pronouns + verbs must appear in the exemplar so the model
    learns they all map to the same behavior."""
    body = _exemplar_path().read_text(encoding="utf-8").lower()
    for trigger in ("this", "that", "it", "reformat", "redo", "expand", "tighten"):
        assert trigger in body, f"continuation exemplar missing trigger word: {trigger}"


def test_continuation_exemplar_forbids_repaste_request() -> None:
    """Exemplar must explicitly name the failure mode it prevents."""
    body = _exemplar_path().read_text(encoding="utf-8").lower()
    assert "re-paste" in body


def test_continuation_exemplar_demonstrates_format_reuse() -> None:
    """The 'You' response must show real reformatting work, not a placeholder."""
    body = _exemplar_path().read_text(encoding="utf-8")
    # Should contain a markdown table from the reformatted snapshot
    assert "| Index |" in body or "|-------|" in body
    # Anchor on the locked snapshot section names to confirm real reshape
    assert "Bottom line" in body
