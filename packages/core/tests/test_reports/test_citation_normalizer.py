"""Behavior tests for the inline-citation → numbered-footnote normalizer.

Tests the public `normalize_report` API only. The parser internals are
intentionally not directly tested — they're verified through observable
behavior on whole report payloads.
"""

from datetime import UTC, datetime

from openlia.reports.assembler import PageFurnitureConfig, assemble_report
from openlia.reports.citations import normalize_report


def _payload_with_text(content: str) -> dict:
    """Minimal v2 report payload with one section containing one TextBlock."""
    return {
        "schema_version": "2.0",
        "department": "equity_research",
        "cover": {"title": "Test", "subtitle": "", "ticker": None},
        "sections": [
            {
                "id": "s1",
                "title": "Section One",
                "blocks": [{"type": "text", "content": content}],
            }
        ],
        "citations": [],
    }


def test_single_web_citation_becomes_footnote_one():
    payload = _payload_with_text(
        'Apple beat Q1 estimates [Reuters, "Apple Q1 beats", 2026-05-12, '
        "reuters.com/business/apple-q1]."
    )

    out = normalize_report(payload)

    block_content = out["sections"][0]["blocks"][0]["content"]
    assert "[1]" in block_content
    assert "Reuters" not in block_content
    assert "reuters.com" not in block_content

    citations = out["citations"]
    assert len(citations) == 1
    c = citations[0]
    assert c["id"] == "1"
    assert c["title"] == "Apple Q1 beats"
    assert c["source"] == "Reuters"
    assert c["date"] == "2026-05-12"
    assert c["url"] == "https://reuters.com/business/apple-q1"


def test_same_url_with_query_and_case_dedupes_to_one_footnote():
    payload = _payload_with_text(
        'First mention [Reuters, "Apple Q1", 2026-05-12, reuters.com/business/apple-q1]. '
        'Second mention with junk [Reuters, "Apple Q1", 2026-05-12, '
        "https://Reuters.com/business/apple-q1/?utm=foo#frag]."
    )

    out = normalize_report(payload)

    text = out["sections"][0]["blocks"][0]["content"]
    assert text.count("[1]") == 2
    assert "[2]" not in text
    assert len(out["citations"]) == 1


def test_provider_tool_call_becomes_footnote_without_url():
    payload = _payload_with_text(
        "Apple's Q1 2026 revenue was $95.4B [get_fundamentals_data(AAPL.US)]."
    )

    out = normalize_report(payload)

    text = out["sections"][0]["blocks"][0]["content"]
    assert text == "Apple's Q1 2026 revenue was $95.4B [1]."

    assert len(out["citations"]) == 1
    c = out["citations"][0]
    assert c["id"] == "1"
    assert c["url"] is None
    assert c["source"] == "get_fundamentals_data"
    assert c["title"] is not None
    assert "AAPL.US" in c["title"]


def test_same_provider_call_cited_multiple_times_dedupes():
    payload = _payload_with_text(
        "Revenue $95.4B [get_fundamentals_data(AAPL.US)]. "
        "EPS $1.83 [get_fundamentals_data(AAPL.US)]. "
        "Margin 24% [get_fundamentals_data(AAPL.US)]."
    )

    out = normalize_report(payload)

    text = out["sections"][0]["blocks"][0]["content"]
    assert text.count("[1]") == 3
    assert len(out["citations"]) == 1


def test_numbering_follows_first_appearance_across_sections():
    payload = {
        "schema_version": "2.0",
        "department": "equity_research",
        "cover": {"title": "T", "subtitle": "", "ticker": None},
        "sections": [
            {
                "id": "s1",
                "title": "S1",
                "blocks": [
                    {
                        "type": "text",
                        "content": (
                            'A [Reuters, "First", 2026-05-12, reuters.com/a]. '
                            "B [get_fundamentals_data(AAPL.US)]."
                        ),
                    }
                ],
            },
            {
                "id": "s2",
                "title": "S2",
                "blocks": [
                    {
                        "type": "text",
                        "content": (
                            'C [Bloomberg, "Third", 2026-05-13, bloomberg.com/x]. '
                            'D [Reuters, "First", 2026-05-12, reuters.com/a].'
                        ),
                    }
                ],
            },
        ],
        "citations": [],
    }

    out = normalize_report(payload)

    s1 = out["sections"][0]["blocks"][0]["content"]
    s2 = out["sections"][1]["blocks"][0]["content"]
    assert s1 == "A [1]. B [2]."
    assert s2 == "C [3]. D [1]."

    ids = [c["id"] for c in out["citations"]]
    assert ids == ["1", "2", "3"]
    assert out["citations"][0]["source"] == "Reuters"
    assert out["citations"][1]["source"] == "get_fundamentals_data"
    assert out["citations"][2]["source"] == "Bloomberg"


def test_malformed_citation_still_gets_numbered():
    payload = _payload_with_text(
        "Management seemed confident [per CEO commentary]. Insiders bullish [per CEO commentary]."
    )

    out = normalize_report(payload)

    text = out["sections"][0]["blocks"][0]["content"]
    assert text.count("[1]") == 2
    assert "per CEO commentary" not in text

    assert len(out["citations"]) == 1
    c = out["citations"][0]
    assert c["id"] == "1"
    assert c["url"] is None
    assert c["title"] == "per CEO commentary"


def test_legacy_three_field_web_tuple_without_title_still_parses():
    payload = _payload_with_text(
        "Apple won an EU appeal [Reuters, 2026-05-12, reuters.com/eu-appeal]."
    )

    out = normalize_report(payload)

    text = out["sections"][0]["blocks"][0]["content"]
    assert text == "Apple won an EU appeal [1]."

    c = out["citations"][0]
    assert c["title"] is None  # no quoted title in input
    assert c["source"] == "Reuters"
    assert c["date"] == "2026-05-12"
    assert c["url"] == "https://reuters.com/eu-appeal"


def test_assemble_report_runs_normalizer_end_to_end():
    """Integration: an LLM-shaped payload with inline tuples flows through
    assemble_report and emerges with `[N]` markers and a populated
    citations array on the validated ReportSchema."""
    payload = {
        "schema_version": "2.0",
        "department": "equity_research",
        "cover": {
            "title": "Apple",
            "subtitle": "Q1 2026",
            "ticker": "AAPL",
            "tagline": "Q1 review",
        },
        "sections": [
            {
                "id": "s1",
                "title": "Overview",
                "blocks": [
                    {
                        "type": "text",
                        "content": (
                            'Apple beat Q1 [Reuters, "Apple Q1 beats", 2026-05-12, '
                            "reuters.com/apple-q1]. Revenue was $95.4B "
                            "[get_fundamentals_data(AAPL.US)]."
                        ),
                    }
                ],
            }
        ],
    }

    furniture = PageFurnitureConfig(
        header_left="OpenLIA",
        header_right_by_department={},
        footer_left_fmt="{date}",
        footer_center="Center",
        footer_right="Right",
        disclaimer="DYOR",
    )

    schema = assemble_report(
        payload,
        department="equity_research",
        furniture=furniture,
        now=datetime(2026, 5, 16, tzinfo=UTC),
    )

    block = schema.sections[0].blocks[0]
    assert block.type == "text"
    assert "[1]" in block.content
    assert "[2]" in block.content
    assert "Reuters" not in block.content
    assert "get_fundamentals_data" not in block.content

    ids = [c.id for c in schema.citations]
    assert ids == ["1", "2"]
    assert schema.citations[0].url == "https://reuters.com/apple-q1"
    assert schema.citations[1].url is None
    assert schema.citations[1].source == "get_fundamentals_data"


def test_existing_bracket_n_markers_are_left_alone_idempotent():
    payload = _payload_with_text(
        'Already numbered [1] and [2,3]. Plus a new [Reuters, "x", 2026-05-12, r.com/a].'
    )

    out = normalize_report(payload)
    out_again = normalize_report({**out, "citations": list(out["citations"])})

    text = out["sections"][0]["blocks"][0]["content"]
    text_again = out_again["sections"][0]["blocks"][0]["content"]
    assert "[1]" in text and "[2,3]" in text
    assert text_again == text
