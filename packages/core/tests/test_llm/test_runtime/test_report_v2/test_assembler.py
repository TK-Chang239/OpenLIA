from __future__ import annotations

from datetime import UTC, datetime

from openlia.llm.runtime.report_v2.facts.pack import FactsPack
from openlia.llm.runtime.report_v2.manifest.manifest import Manifest
from openlia.llm.runtime.report_v2.packer.assembler import assemble_report
from openlia.llm.runtime.report_v2.types import Fact, SectionResult, SectionTerminalState
from openlia.reports.schema import ReportSchema

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 5, 17, 21, 0, 0, tzinfo=UTC)

_SECTION_MARKDOWN = """\
---
section_id: thesis
title: Investment Thesis
sources_used: [1, 2]
---

A strong growth story backed by durable competitive advantages. [1]

```key_finding
content: Revenue CAGR of 23% over three years.
source_ids: ["c1"]
```

Further elaboration on the market opportunity. [2]
"""

_EXHAUSTED_MARKDOWN = None  # EXHAUSTED sections have no markdown


def _make_manifest() -> Manifest:
    m = Manifest()
    m.append(
        kind="fetch",
        provider="eodhd",
        identifier="get_fundamentals_data/AAPL",
        raw_payload={"Highlights": {"MarketCapitalization": 3_000_000_000_000}},
        retrieved_at=_NOW,
    )
    m.append(
        kind="search",
        provider="tavily",
        identifier="AAPL competitive advantages",
        raw_payload={"results": []},
        retrieved_at=_NOW,
    )
    return m


def _make_facts_pack() -> FactsPack:
    return FactsPack(
        facts={
            "company_name": Fact(
                name="company_name",
                value="Apple Inc.",
                source_ids=[1],
                extractor="deterministic",
            ),
            "sector": Fact(
                name="sector",
                value="Technology",
                source_ids=[1],
                extractor="deterministic",
            ),
            "market_cap": Fact(
                name="market_cap",
                value=3_000_000_000_000,
                source_ids=[1],
                extractor="deterministic",
            ),
            "pe_ratio_ttm": Fact(
                name="pe_ratio_ttm",
                value=29.5,
                source_ids=[1],
                extractor="deterministic",
            ),
        }
    )


def _make_sections() -> list[SectionResult]:
    return [
        SectionResult(
            section_id="thesis",
            state=SectionTerminalState.SUCCESS,
            attempts=1,
            markdown=_SECTION_MARKDOWN,
        ),
        SectionResult(
            section_id="financials",
            state=SectionTerminalState.EXHAUSTED,
            attempts=3,
            markdown=None,
        ),
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_assemble_produces_valid_reportschema() -> None:
    report = assemble_report(
        manifest=_make_manifest(),
        facts_pack=_make_facts_pack(),
        sections=_make_sections(),
        department="equity_research",
        ticker="AAPL",
        generated_at=_NOW,
    )

    assert isinstance(report, ReportSchema)
    assert report.schema_version == "2.0"
    assert report.department == "equity_research"
    assert report.generated_at == _NOW

    # EXHAUSTED section must be skipped
    section_ids = [s.id for s in report.sections]
    assert "thesis" in section_ids
    assert "financials" not in section_ids

    # At least one block in the thesis section
    thesis = next(s for s in report.sections if s.id == "thesis")
    assert len(thesis.blocks) >= 1


def test_assemble_populates_rail_quick_stats_from_facts_pack() -> None:
    """Rail.quick_stats must be populated whenever the underlying facts
    are present. Previously the assembler returned rail=None entirely so
    the right sidebar rendered empty in the browser."""
    report = assemble_report(
        manifest=_make_manifest(),
        facts_pack=_make_facts_pack(),
        sections=_make_sections(),
        department="equity_research",
        ticker="AAPL",
        generated_at=_NOW,
    )

    assert report.rail is not None
    labels = {m.label for m in report.rail.quick_stats}
    # All four facts in the fixture should land in the rail
    assert "Sector" in labels
    assert "Market Cap" in labels
    assert "P/E (TTM)" in labels
    # Source attribution must travel with each metric
    for m in report.rail.quick_stats:
        assert m.source_ids and m.source_ids[0].startswith("c")


def test_assemble_populates_meta_stats_from_outputs() -> None:
    """MetaStats.sources_count and sections_count are deterministic from
    the assembled outputs. Sidebar stats panel renders these."""
    report = assemble_report(
        manifest=_make_manifest(),
        facts_pack=_make_facts_pack(),
        sections=_make_sections(),
        department="equity_research",
        ticker="AAPL",
        generated_at=_NOW,
    )

    assert report.meta_stats is not None
    assert report.meta_stats.sources_count == len(report.citations)
    assert report.meta_stats.sections_count == len(report.sections)
    # est_read_minutes is bounded by word count; never zero when sections have text
    assert report.meta_stats.est_read_minutes >= 1


def test_assemble_fills_cover_key_metrics_from_facts_pack() -> None:
    report = assemble_report(
        manifest=_make_manifest(),
        facts_pack=_make_facts_pack(),
        sections=_make_sections(),
        department="equity_research",
        ticker="AAPL",
        generated_at=_NOW,
    )

    cover = report.cover
    assert cover.ticker == "AAPL"
    assert cover.title == "Apple Inc."
    assert "Technology" in cover.subtitle

    metric_labels = [m.label for m in cover.key_metrics]
    assert "Market Cap" in metric_labels
    assert "P/E (TTM)" in metric_labels

    # Market cap formatted to human-readable string
    mc = next(m for m in cover.key_metrics if m.label == "Market Cap")
    assert mc.value == "$3.00T"

    # P/E formatted as a float string
    pe = next(m for m in cover.key_metrics if m.label == "P/E (TTM)")
    assert pe.value == "29.5x"

    # source_ids must reference manifest citation IDs (strings like "c1")
    assert "c1" in mc.source_ids


def test_assemble_citations_built_from_manifest() -> None:
    manifest = _make_manifest()
    report = assemble_report(
        manifest=manifest,
        facts_pack=_make_facts_pack(),
        sections=_make_sections(),
        department="equity_research",
        ticker="AAPL",
        generated_at=_NOW,
    )

    assert len(report.citations) == len(manifest.entries)

    c1 = next(c for c in report.citations if c.id == "c1")
    assert c1.source == "eodhd"
    assert c1.title == "get_fundamentals_data/AAPL"

    c2 = next(c for c in report.citations if c.id == "c2")
    assert c2.source == "tavily"
    assert c2.title == "AAPL competitive advantages"


# ---------------------------------------------------------------------------
# Malformed block handling
# ---------------------------------------------------------------------------

_MALFORMED_BAR_CHART_MARKDOWN = """\
---
section_id: financials
title: Financials
sources_used: [1]
---

Introduction paragraph.

```chart:bar
title: "Revenue by segment"
data:
  labels: ["A", "B", "C"]
  values: [10, 20, 30]
sources: [1]
```

Closing paragraph after the bad chart.
"""


def _make_sections_with_malformed_block() -> list[SectionResult]:
    return [
        SectionResult(
            section_id="financials",
            state=SectionTerminalState.SUCCESS,
            attempts=1,
            markdown=_MALFORMED_BAR_CHART_MARKDOWN,
        ),
    ]


def test_assemble_omits_block_on_assembly_error_continues() -> None:
    """Bad bar_chart (data instead of categories+series) must be dropped
    silently; section, surrounding prose, and other blocks must still be present.
    Diagnostic info is surfaced via the on_omitted_block callback and console,
    not via a user-visible placeholder block."""
    report = assemble_report(
        manifest=_make_manifest(),
        facts_pack=_make_facts_pack(),
        sections=_make_sections_with_malformed_block(),
        department="equity_research",
        ticker="AAPL",
        generated_at=_NOW,
    )

    # Section must be present despite the bad block
    section_ids = [s.id for s in report.sections]
    assert "financials" in section_ids

    financials = next(s for s in report.sections if s.id == "financials")

    # No placeholder leak: the old "[block omitted: ...]" text block was
    # diagnostic-only and ended up visible in PDFs — it must not appear.
    block_contents = [b.content for b in financials.blocks if hasattr(b, "content")]
    assert not any("block omitted" in c for c in block_contents), (
        "Failed blocks must be dropped silently, not rendered as a placeholder"
    )

    # The intro/closing prose TextBlocks must still be present (the bad
    # chart sits between them).
    assert len(block_contents) >= 1, "Prose blocks around the bad chart must survive"


def test_assemble_invokes_on_omitted_block_callback() -> None:
    """on_omitted_block callback must be called with (section_id, block_type, reason)."""
    calls: list[tuple[str, str, str]] = []

    def _cb(section_id: str, block_type: str, reason: str) -> None:
        calls.append((section_id, block_type, reason))

    assemble_report(
        manifest=_make_manifest(),
        facts_pack=_make_facts_pack(),
        sections=_make_sections_with_malformed_block(),
        department="equity_research",
        ticker="AAPL",
        generated_at=_NOW,
        on_omitted_block=_cb,
    )

    assert len(calls) == 1
    section_id, block_type, reason = calls[0]
    assert section_id == "financials"
    assert block_type == "chart:bar"
    assert reason  # non-empty exception class name


_DUPLICATE_HEADING_MARKDOWN = """---
section_id: company_overview
title: Company Overview
sources_used: [1]
---

## Company Overview

Salesforce.com Inc. is an enterprise software company [1].
"""


def test_assemble_strips_duplicate_leading_heading() -> None:
    """A leading "## Section Title" line in the first text block duplicates
    the section H2 already rendered by ReportSection. The assembler must
    strip it so the heading doesn't appear twice in the rendered PDF."""
    sections = [
        SectionResult(
            section_id="company_overview",
            state=SectionTerminalState.SUCCESS,
            attempts=1,
            markdown=_DUPLICATE_HEADING_MARKDOWN,
        ),
    ]
    report = assemble_report(
        manifest=_make_manifest(),
        facts_pack=_make_facts_pack(),
        sections=sections,
        department="equity_research",
        ticker="AAPL",
        generated_at=_NOW,
    )
    section = report.sections[0]
    assert section.title == "Company Overview"
    first = section.blocks[0]
    assert hasattr(first, "content")
    assert not first.content.lstrip().startswith("## Company Overview")
    assert "Salesforce.com Inc." in first.content
