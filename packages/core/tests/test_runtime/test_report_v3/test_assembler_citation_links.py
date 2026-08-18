"""Audit C4 regression — in-text citation markers must render as links.

Previously ``rewrite_section_markdown`` produced ``[^1]`` but the
markdown renderer (commonmark, no footnote plugin) passed the caret
syntax through as literal text, so exported HTML/PDF showed raw
``[^1]`` (and unresolved ids as ``[^eodhd_1]``) with nothing linking
to the bibliography's ``#fn-N`` anchors.

The three forked assemblers (report_v3 / report_eu / report_mb) are
byte-identical; testing the v3 fork covers all three.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from openlia.llm.runtime.report_v3.rendering import assemble_html


@dataclass
class _FakeReport:
    subject: str = "ACME"
    template_id: str = "initiation"
    language: str = "en"


@dataclass
class _FakeSection:
    section_id: str
    section_index: int
    title: str
    markdown: str


@dataclass
class _FakeCitation:
    source_id: str
    tool_name: str
    display_index: int | None
    provenance: dict = field(default_factory=dict)


def _assemble(markdown: str, citations: list[_FakeCitation]) -> str:
    return assemble_html(
        report=_FakeReport(),
        sections=[
            _FakeSection(
                section_id="overview",
                section_index=0,
                title="Overview",
                markdown=markdown,
            )
        ],
        charts=[],
        citations=citations,
        now=datetime(2026, 8, 17, 12, 0),
    ).html


def test_resolved_marker_becomes_bibliography_link() -> None:
    html = _assemble(
        "Revenue reached $215.9B.[^eodhd_1]",
        [_FakeCitation("eodhd_1", "get_fundamentals", 1)],
    )
    assert '<a href="#fn-1">' in html
    assert "[^" not in html


def test_unresolved_marker_loses_caret() -> None:
    html = _assemble("Claim.[^mystery_9]", [])
    assert "[^" not in html
    assert "[mystery_9]" in html


def test_adjacent_markers_each_link() -> None:
    html = _assemble(
        "Both agree.[^eodhd_1][^web_2]",
        [
            _FakeCitation("eodhd_1", "get_fundamentals", 1),
            _FakeCitation("web_2", "web_search", 2, {"url": "https://x"}),
        ],
    )
    assert '<a href="#fn-1">' in html
    assert '<a href="#fn-2">' in html
    assert "[^" not in html
