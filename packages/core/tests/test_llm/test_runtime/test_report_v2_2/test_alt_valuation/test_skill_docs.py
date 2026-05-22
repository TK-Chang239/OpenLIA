"""Verify skill docs exist at expected paths and contain required frontmatter sections."""

from __future__ import annotations

import pathlib

import pytest

_SKILLS_DIR = (
    pathlib.Path(__file__).parent.parent.parent.parent.parent.parent
    / "src"
    / "openlia"
    / "llm"
    / "runtime"
    / "report_v2_2"
    / "tools"
    / "library_helpers"
    / "skills"
)

_EXPECTED_SKILL_DOCS = [
    "ddm_family.md",
    "justified_multiples.md",
    "sotp_builder.md",
]


@pytest.mark.parametrize("filename", _EXPECTED_SKILL_DOCS)
def test_skill_doc_exists(filename: str) -> None:
    path = _SKILLS_DIR / filename
    assert path.exists(), f"Skill doc missing: {path}"
    assert path.stat().st_size > 100, f"Skill doc appears empty: {path}"


@pytest.mark.parametrize("filename", _EXPECTED_SKILL_DOCS)
def test_skill_doc_has_required_sections(filename: str) -> None:
    """Each skill doc must have: Purpose, When to use, When NOT to use, Methodology."""
    path = _SKILLS_DIR / filename
    content = path.read_text()
    required_sections = [
        "## Purpose",
        "## When to use",
        "## When NOT to use",
        "## Methodology",
        "## Common pitfalls",
        "## Related helpers",
    ]
    for section in required_sections:
        assert section in content, f"Skill doc {filename} is missing required section: {section!r}"


@pytest.mark.parametrize(
    "filename,expected_artifact",
    [
        ("ddm_family.md", "ddm_output"),
        ("justified_multiples.md", "justified_multiples_output"),
        ("sotp_builder.md", "sotp_output"),
    ],
)
def test_skill_doc_declares_produced_artifact(filename: str, expected_artifact: str) -> None:
    path = _SKILLS_DIR / filename
    content = path.read_text()
    assert expected_artifact in content, (
        f"Skill doc {filename} does not reference its produced artifact {expected_artifact!r}"
    )
