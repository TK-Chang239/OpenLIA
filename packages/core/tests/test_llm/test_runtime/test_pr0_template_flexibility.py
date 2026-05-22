"""PR 0.0 — template flexibility cleanup tests.

Covers:
- SectionSpec.min_words / tolerance_pct / expand_below_pct loaded from YAML
- prior_section_summarizer honours summary_word_cap parameter
- prompt text smoke: new substrings present, old hardcoded numerals absent
"""

from __future__ import annotations

from pathlib import Path

import openlia.prompts as _prompts_pkg
from openlia.llm.runtime.prior_section_summarizer import summarize_section_draft
from openlia.llm.runtime.section_draft import SectionDraft

# ---------------------------------------------------------------------------
# SectionSpec field loading
# ---------------------------------------------------------------------------


def test_section_spec_min_words_read_from_yaml() -> None:
    """A template section with min_words: 50 is loaded correctly."""
    from openlia.llm.runtime.report_v2.template_v2.loader_v2 import load_template_v2

    yaml_src = """
template_id: t_min_words
template_name: Test
department: equity_research
report_type: equity_research
engine_version_compat: "2.2"
sections:
  - id: intro
    name: Intro
    directive: "Write something."
    min_words: 50
    tolerance_pct: 15
    expand_below_pct: 75
"""
    spec, notices = load_template_v2(yaml_src, fmt="yaml")
    section = spec.sections[0]
    assert section.min_words == 50
    assert section.tolerance_pct == 15
    assert section.expand_below_pct == 75
    assert notices == []


def test_section_spec_defaults_when_fields_absent() -> None:
    """When per-section fields are not declared, defaults 200/20/80 apply."""
    from openlia.llm.runtime.report_v2.template_v2.loader_v2 import load_template_v2

    yaml_src = """
template_id: t_defaults
template_name: Test
department: equity_research
report_type: equity_research
engine_version_compat: "2.2"
sections:
  - id: intro
    name: Intro
    directive: "Write something."
"""
    spec, _ = load_template_v2(yaml_src, fmt="yaml")
    section = spec.sections[0]
    assert section.min_words == 200
    assert section.tolerance_pct == 20
    assert section.expand_below_pct == 80


def test_template_rail_required_quick_stats_loaded() -> None:
    """Template rail.required_quick_stats is loaded from YAML."""
    from openlia.llm.runtime.report_v2.template_v2.loader_v2 import load_template_v2

    yaml_src = """
template_id: t_rail
template_name: Test
department: equity_research
report_type: equity_research
engine_version_compat: "2.2"
rail:
  required_quick_stats:
    - "Market Cap"
    - "Sector"
sections:
  - id: intro
    name: Intro
    directive: "Write something."
"""
    spec, _ = load_template_v2(yaml_src, fmt="yaml")
    assert spec.rail.required_quick_stats == ["Market Cap", "Sector"]


def test_template_rail_null_required_quick_stats() -> None:
    """Template with rail.required_quick_stats: null loads with None."""
    from openlia.llm.runtime.report_v2.template_v2.loader_v2 import load_template_v2

    yaml_src = """
template_id: t_rail_null
template_name: Test
department: equity_research
report_type: equity_research
engine_version_compat: "2.2"
rail:
  required_quick_stats: null
sections:
  - id: intro
    name: Intro
    directive: "Write something."
"""
    spec, _ = load_template_v2(yaml_src, fmt="yaml")
    assert spec.rail.required_quick_stats is None


def test_template_threading_spec_loaded() -> None:
    """Template threading block is loaded correctly."""
    from openlia.llm.runtime.report_v2.template_v2.loader_v2 import load_template_v2

    yaml_src = """
template_id: t_threading
template_name: Test
department: equity_research
report_type: equity_research
engine_version_compat: "2.2"
threading:
  summary_word_cap: 150
  facts_cap: 3
sections:
  - id: intro
    name: Intro
    directive: "Write something."
"""
    spec, _ = load_template_v2(yaml_src, fmt="yaml")
    assert spec.threading.summary_word_cap == 150
    assert spec.threading.facts_cap == 3


# ---------------------------------------------------------------------------
# prior_section_summarizer parameter plumbing
# ---------------------------------------------------------------------------


def _draft(blocks: list[dict]) -> SectionDraft:
    return SectionDraft.model_validate(
        {
            "section_id": "test_section",
            "blocks": blocks,
            "citations_used": [],
            "word_count": sum(
                len(b.get("content", "").split()) for b in blocks if b.get("type") == "text"
            ),
            "open_questions": [],
        }
    )


def test_summarizer_honours_summary_word_cap_parameter() -> None:
    """Passing summary_word_cap=10 truncates at 10 words."""
    long_text = " ".join([f"word{i}" for i in range(300)])
    out = summarize_section_draft(
        _draft([{"type": "text", "content": long_text}]),
        title="Overview",
        summary_word_cap=10,
    )
    assert len(out.summary.split()) <= 10


def test_summarizer_honours_facts_cap_parameter() -> None:
    """Passing facts_cap=2 caps threading facts at 2 entries."""
    blocks = [
        {
            "type": "metric_cards",
            "metrics": [
                {"label": "A", "value": "1"},
                {"label": "B", "value": "2"},
                {"label": "C", "value": "3"},
                {"label": "D", "value": "4"},
                {"label": "E", "value": "5"},
                {"label": "F", "value": "6"},
            ],
        }
    ]
    out = summarize_section_draft(_draft(blocks), title="Metrics", facts_cap=2)
    assert len(out.key_facts_for_threading) <= 2


def test_summarizer_defaults_unchanged() -> None:
    """Default behaviour (no params) still truncates at 200 words."""
    long_text = " ".join([f"word{i}" for i in range(500)])
    out = summarize_section_draft(
        _draft([{"type": "text", "content": long_text}]), title="Overview"
    )
    assert len(out.summary.split()) <= 200


# ---------------------------------------------------------------------------
# Prompt text smoke tests
# ---------------------------------------------------------------------------


def _read_shared(name: str) -> str:
    p = Path(_prompts_pkg.__file__).parent / "shared" / name
    return p.read_text()


def test_editor_role_no_hardcoded_14() -> None:
    """editor_role.yaml.j2 must not contain the literal '14 section'."""
    text = _read_shared("editor_role.yaml.j2")
    assert "14 section" not in text


def test_editor_role_has_generic_section_drafts_phrase() -> None:
    """editor_role.yaml.j2 says 'All section drafts' not '14 section drafts'."""
    text = _read_shared("editor_role.yaml.j2")
    assert "All section drafts (blocks verbatim) from the subagents." in text


def test_editor_role_has_expand_below_pct_phrase() -> None:
    """editor_role.yaml.j2 uses expand_below_pct phrasing, not hardcoded 80%."""
    text = _read_shared("editor_role.yaml.j2")
    assert "expand_below_pct" in text
    # Old literal '80%' must be gone from the expand sentence.
    assert "below 80% of their plan" not in text


def test_section_subagent_role_has_tolerance_pct_phrase() -> None:
    """section_subagent_role.yaml.j2 uses tolerance_pct phrasing."""
    text = _read_shared("section_subagent_role.yaml.j2")
    assert "tolerance_pct" in text
    # Old literal '+/-20%' must be gone from the budget line.
    assert "within +/-20%" not in text


def test_report_schema_strictness_has_min_words_phrase() -> None:
    """report_schema_strictness.yaml.j2 uses min_words phrasing."""
    text = _read_shared("report_schema_strictness.yaml.j2")
    assert "min_words" in text
    # Old '6-word section' hardcoded phrase must be gone.
    assert "A 6-word section is always a quality failure" not in text
