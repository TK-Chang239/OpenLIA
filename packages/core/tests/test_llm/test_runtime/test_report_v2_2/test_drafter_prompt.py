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
    """Structural template text must not contain the numeral '14'.

    Allowed in data sections (artifact content, thesis text, theme text).
    Tested by using no user data that contains '14' — any '14' in the
    rendered prompt must therefore come from the template scaffold itself.
    """
    section = _make_section()
    prompt = build_drafter_prompt(
        section=section,
        template_section_meta={"title": "DCF"},
        # Deliberately no '14' in user-supplied data.
        thesis="Strong buy.",
        themes=["Scale"],
    )
    # Identify the structural sections of the prompt: everything except artifact content.
    # Strategy: collect lines that are NOT inside an "### Artifact:" block.
    structural_lines: list[str] = []
    in_artifact_block = False
    for line in prompt.split("\n"):
        if line.startswith("### Artifact:"):
            in_artifact_block = True
        elif line.startswith("## ") and in_artifact_block:
            in_artifact_block = False
        if not in_artifact_block:
            structural_lines.append(line)

    lines_with_14 = [ln for ln in structural_lines if "14" in ln]
    assert len(lines_with_14) == 0, (
        f"Hardcoded '14' found in structural (non-artifact) lines: {lines_with_14}"
    )


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


# ---- template_id / ticker context ----


def test_prompt_includes_template_id_and_ticker_in_system_frame() -> None:
    """When template_id and ticker are provided, the system frame identifies them."""
    section = _make_section()
    prompt = build_drafter_prompt(
        section=section,
        template_section_meta={"title": "DCF"},
        thesis="T.",
        themes=[],
        template_id="stock_initiation_v2",
        ticker="MSFT",
    )
    assert "stock_initiation_v2" in prompt
    assert "MSFT" in prompt


def test_prompt_system_frame_format_matches_spec() -> None:
    """System frame must match 'You are drafting <template_id> for <ticker>.' per §6."""
    section = _make_section()
    prompt = build_drafter_prompt(
        section=section,
        template_section_meta={"title": "DCF"},
        thesis="T.",
        themes=[],
        template_id="banks_v2_2",
        ticker="JPM",
    )
    assert "You are drafting banks_v2_2 for JPM." in prompt


def test_prompt_no_template_ticker_frame_when_omitted() -> None:
    """When template_id and ticker are not provided, no 'You are drafting' line."""
    section = _make_section()
    prompt = build_drafter_prompt(
        section=section,
        template_section_meta={"title": "DCF"},
        thesis="T.",
        themes=[],
    )
    assert "You are drafting" not in prompt


def test_prompt_no_frame_when_only_one_of_template_ticker_provided() -> None:
    """Both must be present for the frame to appear."""
    section = _make_section()
    # Only template_id, no ticker
    prompt_no_ticker = build_drafter_prompt(
        section=section,
        template_section_meta={"title": "DCF"},
        thesis="T.",
        themes=[],
        template_id="stock_initiation_v2",
    )
    assert "You are drafting" not in prompt_no_ticker

    # Only ticker, no template_id
    prompt_no_template = build_drafter_prompt(
        section=section,
        template_section_meta={"title": "DCF"},
        thesis="T.",
        themes=[],
        ticker="MSFT",
    )
    assert "You are drafting" not in prompt_no_template


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
