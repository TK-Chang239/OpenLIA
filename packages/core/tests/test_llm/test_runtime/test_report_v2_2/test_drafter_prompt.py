"""Tests for Stage 7b drafter prompt builder.

Verifies:
- Prompt contains thesis, themes, section metadata, artifact contents.
- No hardcoded numerals (grep '14' == 0 matches that aren't in test data).
- Prompt is non-empty and well-formed.
"""

from __future__ import annotations

from openlia.llm.runtime.report_v2_2.drafter_prompt import build_drafter_prompt
from openlia.llm.runtime.report_v2_2.enums import Fidelity
from openlia.llm.runtime.report_v2_2.materialize import MaterializedSection, RenderedArtifact


def _make_section(
    section_id: str = "valuation_dcf",
    rendered_artifacts: list[RenderedArtifact] | None = None,
) -> MaterializedSection:
    return MaterializedSection(
        section_id=section_id,
        title="DCF Valuation",
        rendered_artifacts=rendered_artifacts or [],
        open_questions=[],
        cross_section_themes=[],
        materialization_warnings=[],
    )


def _make_artifact(artifact_id: str, content: str) -> RenderedArtifact:
    return RenderedArtifact(
        artifact_id=artifact_id,
        artifact_type=artifact_id,
        helper_name="dcf_valuation",
        fidelity=Fidelity.FULL,
        content=content,
        raw_data={"value": 312},
    )


# ---- Basic structure ----


def test_prompt_contains_thesis() -> None:
    section = _make_section()
    prompt = build_drafter_prompt(
        section=section,
        template_section_meta={"title": "DCF Valuation"},
        thesis="MSFT is undervalued with DCF fair value of $312.",
        themes=["Cloud acceleration", "AI monetisation"],
    )
    assert "MSFT is undervalued" in prompt
    assert "DCF fair value" in prompt


def test_prompt_contains_themes() -> None:
    section = _make_section()
    prompt = build_drafter_prompt(
        section=section,
        template_section_meta={"title": "DCF"},
        thesis="Strong thesis.",
        themes=["Cloud acceleration", "AI monetisation"],
    )
    assert "Cloud acceleration" in prompt
    assert "AI monetisation" in prompt


def test_prompt_contains_section_title() -> None:
    section = _make_section()
    prompt = build_drafter_prompt(
        section=section,
        template_section_meta={"title": "Discounted Cash Flow Valuation"},
        thesis="Thesis.",
        themes=[],
    )
    assert "Discounted Cash Flow Valuation" in prompt


def test_prompt_contains_artifact_content() -> None:
    art = _make_artifact("dcf_output", "- **dcf_value**: $312\n- **wacc**: 9.8%")
    section = _make_section(rendered_artifacts=[art])
    prompt = build_drafter_prompt(
        section=section,
        template_section_meta={"title": "DCF"},
        thesis="Thesis.",
        themes=[],
    )
    assert "dcf_value" in prompt
    assert "$312" in prompt
    assert "wacc" in prompt


def test_prompt_includes_artifact_provenance() -> None:
    """Prompt must label each artifact with helper name and fidelity."""
    art = _make_artifact("dcf_output", "some content")
    section = _make_section(rendered_artifacts=[art])
    prompt = build_drafter_prompt(
        section=section,
        template_section_meta={"title": "DCF"},
        thesis="Thesis.",
        themes=[],
    )
    assert "dcf_valuation" in prompt  # helper name
    assert "full" in prompt  # fidelity


def test_prompt_contains_open_questions() -> None:
    section = MaterializedSection(
        section_id="s1",
        title="S1",
        rendered_artifacts=[],
        open_questions=["What drives growth after year 5?"],
        cross_section_themes=[],
        materialization_warnings=[],
    )
    prompt = build_drafter_prompt(
        section=section,
        template_section_meta={"title": "S1"},
        thesis="T.",
        themes=[],
    )
    assert "What drives growth after year 5?" in prompt


def test_prompt_contains_threading_summaries() -> None:
    section = _make_section()
    prompt = build_drafter_prompt(
        section=section,
        template_section_meta={"title": "DCF"},
        thesis="T.",
        themes=[],
        threading_summaries=["Executive summary: MSFT buy, $312 PT."],
    )
    assert "Executive summary: MSFT buy, $312 PT." in prompt


def test_prompt_no_threading_when_empty() -> None:
    section = _make_section()
    prompt = build_drafter_prompt(
        section=section,
        template_section_meta={"title": "DCF"},
        thesis="T.",
        themes=[],
        threading_summaries=[],
    )
    assert "Prior Section Context" not in prompt


# ---- No hardcoded numerals in the structural template ----

_STRUCTURAL_SENTINEL = "14"  # the specific numeral banned from hardcoding


def test_no_hardcoded_14_in_structural_parts() -> None:
    """Prompt structure must not contain hardcoded '14' from template logic."""
    section = _make_section()
    prompt = build_drafter_prompt(
        section=section,
        template_section_meta={"title": "DCF"},
        thesis="Strong buy.",
        themes=["Scale"],
    )
    # Split on newlines and check structural lines (not data lines) don't contain '14'.
    structural_lines = [
        line
        for line in prompt.split("\n")
        if not any(c.isdigit() and c not in "0" for c in line[:3])  # skip data lines
        if "14" in line
    ]
    # Filter: '14' only allowed if it's part of user-supplied data (thesis/themes/artifacts).
    non_data_14 = [
        line for line in structural_lines if "14" not in "Strong buy." and "14" not in "Scale"
    ]
    assert len(non_data_14) == 0, f"Hardcoded '14' found in structural lines: {non_data_14}"


# ---- Prompt is non-empty and well-formed ----


def test_prompt_non_empty() -> None:
    section = _make_section()
    prompt = build_drafter_prompt(
        section=section,
        template_section_meta={"title": "DCF"},
        thesis="T.",
        themes=[],
    )
    assert len(prompt.strip()) > 100


def test_prompt_starts_with_role_instruction() -> None:
    section = _make_section()
    prompt = build_drafter_prompt(
        section=section,
        template_section_meta={"title": "DCF"},
        thesis="T.",
        themes=[],
    )
    assert "subagent" in prompt.lower() or "section" in prompt.lower()


def test_prompt_includes_output_instructions() -> None:
    section = _make_section()
    prompt = build_drafter_prompt(
        section=section,
        template_section_meta={"title": "My Section"},
        thesis="T.",
        themes=[],
    )
    assert "Output Instructions" in prompt


def test_prompt_includes_min_words_when_provided() -> None:
    section = _make_section()
    prompt = build_drafter_prompt(
        section=section,
        template_section_meta={"title": "DCF", "min_words": 300},
        thesis="T.",
        themes=[],
    )
    assert "300" in prompt


def test_prompt_no_min_words_when_absent() -> None:
    section = _make_section()
    prompt = build_drafter_prompt(
        section=section,
        template_section_meta={"title": "DCF"},
        thesis="T.",
        themes=[],
    )
    assert "Minimum words" not in prompt


def test_multiple_artifacts_all_present() -> None:
    arts = [
        _make_artifact("dcf_output", "DCF content here"),
        _make_artifact("peer_panel", "Peer comparison here"),
    ]
    section = _make_section(rendered_artifacts=arts)
    prompt = build_drafter_prompt(
        section=section,
        template_section_meta={"title": "Valuation"},
        thesis="T.",
        themes=[],
    )
    assert "DCF content here" in prompt
    assert "Peer comparison here" in prompt
