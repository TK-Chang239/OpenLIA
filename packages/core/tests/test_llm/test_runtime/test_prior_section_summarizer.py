from __future__ import annotations

from openlia.llm.runtime.prior_section_summarizer import summarize_section_draft
from openlia.llm.runtime.section_draft import SectionDraft


def _draft(blocks: list[dict]) -> SectionDraft:
    return SectionDraft.model_validate(
        {
            "section_id": "company_overview",
            "blocks": blocks,
            "citations_used": [],
            "word_count": sum(
                len(b.get("content", "").split()) for b in blocks if b.get("type") == "text"
            ),
            "open_questions": [],
        }
    )


def test_summary_truncates_text_to_two_hundred_words() -> None:
    long_text = " ".join([f"word{i}" for i in range(500)])
    out = summarize_section_draft(
        _draft([{"type": "text", "content": long_text}]), title="Overview"
    )
    assert out.section_id == "company_overview"
    assert out.title == "Overview"
    assert len(out.summary.split()) <= 200


def test_summary_includes_metric_card_bullets_as_threading_facts() -> None:
    blocks = [
        {"type": "text", "content": "Microsoft posted record revenue."},
        {
            "type": "metric_cards",
            "metrics": [
                {"label": "Revenue", "value": "$245B"},
                {"label": "Op margin", "value": "44%"},
                {"label": "EPS", "value": "$12.93"},
            ],
        },
    ]
    out = summarize_section_draft(_draft(blocks), title="Overview")
    joined = " ".join(out.key_facts_for_threading)
    assert "Revenue" in joined and "$245B" in joined
    assert len(out.key_facts_for_threading) <= 5


def test_summary_includes_chart_titles_as_threading_facts() -> None:
    blocks = [
        {"type": "text", "content": "Overview."},
        {
            "type": "line_chart",
            "title": "Revenue Trend FY21-FY25",
            "series": [{"name": "Revenue", "data": [1, 2, 3]}],
        },
    ]
    out = summarize_section_draft(_draft(blocks), title="Trends")
    assert any("Revenue Trend FY21-FY25" in fact for fact in out.key_facts_for_threading)


def test_table_block_contributes_first_row_summary() -> None:
    blocks = [
        {
            "type": "table",
            "title": "Comps",
            "headers": [{"key": "ticker", "label": "Ticker"}, {"key": "pe", "label": "P/E"}],
            "rows": [{"ticker": "MSFT", "pe": 35}, {"ticker": "GOOGL", "pe": 28}],
        }
    ]
    out = summarize_section_draft(_draft(blocks), title="Comps")
    joined = " ".join(out.key_facts_for_threading)
    assert "ticker" in joined and "pe" in joined
