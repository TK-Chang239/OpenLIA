"""Test carry-over wiring 5b: summarize_section_draft honours threading config from template.

Verifies:
- Template with threading.summary_word_cap: 50 → summary truncated at 50 words.
- Template with threading.facts_cap: 2 → at most 2 key facts.
- No threading block → uses default 200 / 5.
- No framework_template_spec → uses defaults.
"""

from __future__ import annotations

from openlia.llm.runtime.prior_section_summarizer import summarize_section_draft
from openlia.llm.runtime.section_draft import SectionDraft
from openlia.llm.runtime.subagent_runner import _threading_caps_from_request

# ---- Helper: fake request ----


class _FakeRequest:
    def __init__(self, framework_template_spec=None):
        self.framework_template_spec = framework_template_spec


# ---- Helper: template spec dicts ----


def _spec_with_threading(summary_word_cap: int, facts_cap: int) -> dict:
    return {
        "template_id": "stock_initiation_v2",
        "template_name": "Stock Initiation",
        "department": "equity_research",
        "report_type": "stock_initiation",
        "engine_version_compat": "2.2",
        "sections": [{"id": "s", "name": "S", "directive": "Write."}],
        "threading": {
            "summary_word_cap": summary_word_cap,
            "facts_cap": facts_cap,
        },
    }


def _spec_without_threading() -> dict:
    return {
        "template_id": "t",
        "template_name": "T",
        "department": "d",
        "report_type": "r",
        "engine_version_compat": "2.2",
        "sections": [{"id": "s", "name": "S", "directive": "Write."}],
    }


# ---- Helper: SectionDraft ----


def _draft_with_words(n: int, facts: int = 0) -> SectionDraft:
    """Build a SectionDraft with n-word text block and optional metric_cards."""
    blocks = [{"type": "text", "content": " ".join(["word"] * n)}]
    if facts > 0:
        metrics = [{"label": f"Key{i}", "value": str(i)} for i in range(facts)]
        blocks.append({"type": "metric_cards", "metrics": metrics})
    return SectionDraft.model_validate(
        {
            "section_id": "s",
            "blocks": blocks,
            "citations_used": [],
            "word_count": n,
        }
    )


# ---- _threading_caps_from_request ----


def test_caps_returned_from_spec() -> None:
    req = _FakeRequest(framework_template_spec=_spec_with_threading(50, 2))
    cap, fc = _threading_caps_from_request(req)
    assert cap == 50
    assert fc == 2


def test_caps_none_when_no_spec() -> None:
    req = _FakeRequest(framework_template_spec=None)
    cap, fc = _threading_caps_from_request(req)
    assert cap is None
    assert fc is None


def test_caps_use_defaults_when_no_threading_block() -> None:
    # TemplateSpecV2.threading always has a ThreadingSpec (default 200/5).
    # When no explicit 'threading:' key is in the YAML, we get the schema defaults.
    req = _FakeRequest(framework_template_spec=_spec_without_threading())
    cap, fc = _threading_caps_from_request(req)
    # Returns default values from ThreadingSpec, not None.
    assert cap == 200
    assert fc == 5


def test_caps_none_when_spec_not_dict() -> None:
    req = _FakeRequest(framework_template_spec="bad")
    cap, fc = _threading_caps_from_request(req)
    assert cap is None
    assert fc is None


# ---- summarize_section_draft honours summary_word_cap ----


def test_summary_word_cap_50_truncates() -> None:
    draft = _draft_with_words(300)  # 300 words, cap at 50
    prior = summarize_section_draft(draft, title="S", summary_word_cap=50)
    # summary should be at most 50 words + "..." suffix
    summary_without_ellipsis = prior.summary.removesuffix("...")
    summary_words = summary_without_ellipsis.split()
    assert len(summary_words) <= 50, f"Expected ≤50 words, got {len(summary_words)}"
    assert prior.summary.endswith("...")


def test_summary_word_cap_default_200() -> None:
    draft = _draft_with_words(100)  # 100 words, default cap 200 → not truncated
    prior = summarize_section_draft(draft, title="S")
    # 100 words < 200 → no truncation, no "..."
    assert not prior.summary.endswith("...")
    assert "word" in prior.summary


def test_summary_word_cap_200_with_300_word_draft() -> None:
    draft = _draft_with_words(300)
    prior = summarize_section_draft(draft, title="S", summary_word_cap=200)
    summary_without_ellipsis = prior.summary.removesuffix("...")
    summary_words = summary_without_ellipsis.split()
    assert len(summary_words) <= 200
    assert prior.summary.endswith("...")


# ---- summarize_section_draft honours facts_cap ----


def test_facts_cap_2_limits_key_facts() -> None:
    draft = _draft_with_words(50, facts=10)  # 10 metric facts available
    prior = summarize_section_draft(draft, title="S", facts_cap=2)
    assert len(prior.key_facts_for_threading) <= 2


def test_facts_cap_default_5() -> None:
    draft = _draft_with_words(50, facts=10)
    prior = summarize_section_draft(draft, title="S")  # default facts_cap=5
    assert len(prior.key_facts_for_threading) <= 5


def test_facts_cap_5_is_schema_maximum() -> None:
    # PriorSection.key_facts_for_threading is capped at max_length=5 by the schema.
    # Even with facts_cap=5 and 10 available, at most 5 are returned.
    draft = _draft_with_words(50, facts=10)
    prior = summarize_section_draft(draft, title="S", facts_cap=5)
    assert len(prior.key_facts_for_threading) == 5


# ---- Template-driven: end-to-end via _threading_caps_from_request ----


def test_template_threading_cap_50_applied() -> None:
    """Full flow: resolve caps from request, pass to summarize_section_draft."""
    req = _FakeRequest(framework_template_spec=_spec_with_threading(50, 3))
    cap, fc = _threading_caps_from_request(req)

    draft = _draft_with_words(300, facts=8)

    kwargs = {"title": "Section"}
    if cap is not None:
        kwargs["summary_word_cap"] = cap
    if fc is not None:
        kwargs["facts_cap"] = fc

    prior = summarize_section_draft(draft, **kwargs)
    summary_without_ellipsis = prior.summary.removesuffix("...")
    summary_words = summary_without_ellipsis.split()
    assert len(summary_words) <= 50
    assert len(prior.key_facts_for_threading) <= 3


def test_no_template_uses_defaults() -> None:
    req = _FakeRequest(framework_template_spec=None)
    cap, fc = _threading_caps_from_request(req)
    # Both None → defaults (200, 5) used inside summarize_section_draft.
    assert cap is None
    assert fc is None

    draft = _draft_with_words(100, facts=3)
    prior = summarize_section_draft(draft, title="S")  # no overrides
    assert len(prior.key_facts_for_threading) <= 5
    assert len(prior.summary.split()) <= 200
