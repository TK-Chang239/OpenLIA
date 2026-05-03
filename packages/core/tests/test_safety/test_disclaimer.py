"""Component C — disclaimer constants."""

from __future__ import annotations

import re

from openlia.safety.disclaimer import DISCLAIMER_TEXT, DISCLAIMER_VERSION


def test_version_is_semver() -> None:
    assert re.fullmatch(r"\d+\.\d+\.\d+", DISCLAIMER_VERSION)


def test_text_includes_canonical_phrases() -> None:
    assert "not a licensed financial advisor" in DISCLAIMER_TEXT
    assert "OpenLIA" in DISCLAIMER_TEXT
    assert "I understand" in DISCLAIMER_TEXT
    assert "Lia" in DISCLAIMER_TEXT
