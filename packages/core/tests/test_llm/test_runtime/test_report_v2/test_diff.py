"""Tests for the structured diff utility (report_v2/diff.py).

Fixture schema corrections vs. the plan's illustrative examples:
- TextBlock uses content= (not markdown=) and has no source_ids.
- KeyFindingBlock uses content= (not summary=).
- PullQuoteBlock uses text= (not quote=).
- QuoteBlock uses text= (not body=).
- ComparisonSplitBlock uses .left / .right (not .columns).
"""

from __future__ import annotations

from datetime import datetime

from openlia.llm.runtime.report_v2.diff import (
    _cover_metric_map,
    _section_word_count,
    diff_reports,
)
from openlia.reports.schema import (
    BulletListBlock,
    Citation,
    ComparisonColumn,
    ComparisonSplitBlock,
    Cover,
    KeyFindingBlock,
    Metric,
    PullQuoteBlock,
    QuoteBlock,
    ReportSchema,
    Section,
    TextBlock,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_report(
    *,
    section_count: int,
    citation_count: int,
    market_cap_value: str,
    body_words: int = 10,
) -> ReportSchema:
    """Build a minimal but valid ReportSchema for diffing."""
    body = " ".join(["w"] * body_words)
    return ReportSchema(
        schema_version="2.0",
        department="equity_research",
        generated_at=datetime(2026, 5, 17),
        cover=Cover(
            title="X",
            subtitle="Y",
            tagline="Z",
            key_metrics=[Metric(label="Market Cap", value=market_cap_value)],
        ),
        sections=[
            Section(
                id=f"s{i}",
                title=f"S{i}",
                blocks=[TextBlock(type="text", content=body)],
            )
            for i in range(section_count)
        ],
        citations=[
            Citation(id=f"c{i + 1}", title=f"Source {i + 1}") for i in range(citation_count)
        ],
    )


# ---------------------------------------------------------------------------
# _section_word_count unit tests
# ---------------------------------------------------------------------------


def test_section_word_count_text_block() -> None:
    s = Section(
        id="s1",
        title="S1",
        blocks=[TextBlock(type="text", content="hello world foo bar")],
    )
    assert _section_word_count(s) == 4


def test_section_word_count_key_finding_block() -> None:
    s = Section(
        id="s1",
        title="S1",
        blocks=[KeyFindingBlock(type="key_finding", content="alpha beta gamma")],
    )
    assert _section_word_count(s) == 3


def test_section_word_count_pull_quote_block() -> None:
    s = Section(
        id="s1",
        title="S1",
        blocks=[PullQuoteBlock(type="pull_quote", text="one two")],
    )
    assert _section_word_count(s) == 2


def test_section_word_count_quote_block() -> None:
    s = Section(
        id="s1",
        title="S1",
        blocks=[QuoteBlock(type="quote", text="a b c d")],
    )
    assert _section_word_count(s) == 4


def test_section_word_count_bullet_list_block() -> None:
    s = Section(
        id="s1",
        title="S1",
        blocks=[BulletListBlock(type="bullet_list", items=["foo bar", "baz"])],
    )
    assert _section_word_count(s) == 3


def test_section_word_count_comparison_split_block() -> None:
    s = Section(
        id="s1",
        title="S1",
        blocks=[
            ComparisonSplitBlock(
                type="comparison_split",
                left=ComparisonColumn(title="Pros", items=["good one", "great"]),
                right=ComparisonColumn(title="Cons", items=["bad"]),
            )
        ],
    )
    # "good one" = 2, "great" = 1, "bad" = 1
    assert _section_word_count(s) == 4


# ---------------------------------------------------------------------------
# _cover_metric_map unit tests
# ---------------------------------------------------------------------------


def test_cover_metric_map_returns_label_value_dict() -> None:
    report = _make_report(section_count=1, citation_count=0, market_cap_value="$30.2B")
    m = _cover_metric_map(report)
    assert m == {"Market Cap": "$30.2B"}


# ---------------------------------------------------------------------------
# diff_reports integration tests (the 4 required tests)
# ---------------------------------------------------------------------------


def test_diff_identical_reports_is_clean() -> None:
    a = _make_report(section_count=15, citation_count=12, market_cap_value="$30.2B")
    b = _make_report(section_count=15, citation_count=12, market_cap_value="$30.2B")
    d = diff_reports(a, b)
    assert d["section_count"]["match"] is True
    assert d["citation_count"]["match"] is True
    assert d["cover_metric_values"]["match"] is True
    assert d["section_word_counts"]["match"] is True


def test_diff_reports_section_count_mismatch_flagged() -> None:
    a = _make_report(section_count=15, citation_count=12, market_cap_value="$30.2B")
    b = _make_report(section_count=14, citation_count=12, market_cap_value="$30.2B")
    d = diff_reports(a, b)
    assert d["section_count"]["match"] is False
    assert d["section_count"]["classic"] == 15
    assert d["section_count"]["waved"] == 14


def test_diff_reports_cover_metric_value_drift_flagged() -> None:
    a = _make_report(section_count=15, citation_count=12, market_cap_value="$30.2B")
    b = _make_report(section_count=15, citation_count=12, market_cap_value="$32.0B")
    d = diff_reports(a, b)
    assert d["cover_metric_values"]["match"] is False
    assert "Market Cap" in d["cover_metric_values"]["mismatches"]


def test_diff_word_counts_within_tolerance_match_otherwise_flagged() -> None:
    """480/500 words = 4% diff — within ±20%; 200/500 = 60% diff — outside ±20%."""
    a = _make_report(section_count=2, citation_count=2, market_cap_value="$30.2B")
    # Override s0 body to 500 words
    a.sections[0].blocks = [TextBlock(type="text", content=" ".join(["w"] * 500))]

    b = _make_report(section_count=2, citation_count=2, market_cap_value="$30.2B")
    # 480 words — within 20% of 500
    b.sections[0].blocks = [TextBlock(type="text", content=" ".join(["w"] * 480))]
    d = diff_reports(a, b)
    assert d["section_word_counts"]["match"] is True

    # 200 words — outside 20% of 500
    b.sections[0].blocks = [TextBlock(type="text", content=" ".join(["w"] * 200))]
    d = diff_reports(a, b)
    assert d["section_word_counts"]["match"] is False
