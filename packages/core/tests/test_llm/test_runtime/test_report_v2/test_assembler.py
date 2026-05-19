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
    # Sector and Market Cap are always present when the facts exist.
    # P/E falls back to TTM when Forward isn't in the fixture.
    assert "Sector" in labels
    assert "Market Cap" in labels
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
    # First text block in the section (the deterministic identity card may
    # be prepended ahead of LLM-authored content under the new policy)
    text_block = next(b for b in section.blocks if hasattr(b, "content"))
    assert not text_block.content.lstrip().startswith("## Company Overview")
    assert "Salesforce.com Inc." in text_block.content


# ---------------------------------------------------------------------------
# Cover/Rail enrichment (lift structured blocks from synthesis sections)
# ---------------------------------------------------------------------------


_COVER_SECTION_WITH_STRUCTURED_BLOCKS = """\
---
section_id: cover
title: Apple Inc.
sources_used: [1]
---

Apple is a high-quality consumer hardware franchise with deepening services attach. [1]

```pull_quote
text: Apple's services flywheel turns 2bn+ devices into durable recurring revenue.
sources: [1]
```

```bullet_list
items:
  - Hardware demand has stabilized after a two-year reset, easing the top-line drag.
  - Services and accessories now contribute a growing share of operating profit.
  - Capital returns remain aggressive even as gross margins reach new highs.
  - AI integration adds a credible refresh-cycle driver into 2027.
```

```metric_cards
metrics:
  - label: "Market Cap"
    value: "$3.10T"
    source_ids: ["c1"]
  - label: "P/E (TTM)"
    value: "30.1x"
    source_ids: ["c1"]
  - label: "Revenue (TTM)"
    value: "$385.0B"
    source_ids: ["c1"]
  - label: "Gross Margin"
    value: "45.2%"
    source_ids: ["c1"]
```

Closing context paragraph for the cover body. [1]
"""


_INVESTMENT_REC_SECTION_WITH_RATING = """\
---
section_id: investment_recommendation
title: Investment Recommendation
sources_used: [1]
---

We initiate at BUY with conviction. [1]

```rating_badge
rating: BUY
previous_rating: HOLD
change_date: "2026-05-19"
```

```metric_cards
metrics:
  - label: "Price Target"
    value: "$245"
    source_ids: ["c1"]
  - label: "Upside"
    value: "+18%"
    source_ids: ["c1"]
  - label: "Time Horizon"
    value: "12 months"
    source_ids: ["c1"]
```

The thesis rests on services attach and AI-driven refresh. [1]
"""


def _make_cover_and_rec_sections() -> list[SectionResult]:
    return [
        SectionResult(
            section_id="cover",
            state=SectionTerminalState.SUCCESS,
            attempts=1,
            markdown=_COVER_SECTION_WITH_STRUCTURED_BLOCKS,
        ),
        SectionResult(
            section_id="investment_recommendation",
            state=SectionTerminalState.SUCCESS,
            attempts=1,
            markdown=_INVESTMENT_REC_SECTION_WITH_RATING,
        ),
    ]


def test_cover_lifts_bullet_list_into_tldr_with_executive_summary_label() -> None:
    report = assemble_report(
        manifest=_make_manifest(),
        facts_pack=_make_facts_pack(),
        sections=_make_cover_and_rec_sections(),
        department="equity_research",
        ticker="AAPL",
        generated_at=_NOW,
    )
    assert len(report.cover.tldr) == 4
    assert report.cover.tldr[0].startswith("Hardware demand")
    assert report.cover.tldr_label == "Executive Summary"


def test_cover_lifts_pull_quote_into_tagline() -> None:
    report = assemble_report(
        manifest=_make_manifest(),
        facts_pack=_make_facts_pack(),
        sections=_make_cover_and_rec_sections(),
        department="equity_research",
        ticker="AAPL",
        generated_at=_NOW,
    )
    assert "services flywheel" in report.cover.tagline
    assert report.cover.tagline != "Equity Research Initiation"


def test_cover_lifts_metric_cards_when_larger_than_deterministic() -> None:
    """LLM-authored metric_cards override the deterministic 2-metric fallback
    when they contain at least as many metrics."""
    report = assemble_report(
        manifest=_make_manifest(),
        facts_pack=_make_facts_pack(),
        sections=_make_cover_and_rec_sections(),
        department="equity_research",
        ticker="AAPL",
        generated_at=_NOW,
    )
    labels = [m.label for m in report.cover.key_metrics]
    assert "Revenue (TTM)" in labels
    assert "Gross Margin" in labels


def test_cover_eyebrow_populated_from_generated_at() -> None:
    report = assemble_report(
        manifest=_make_manifest(),
        facts_pack=_make_facts_pack(),
        sections=_make_sections(),
        department="equity_research",
        ticker="AAPL",
        generated_at=_NOW,
    )
    assert report.cover.eyebrow == "Research Briefing · 2026-05-17"


def test_cover_lifted_blocks_removed_from_body_section() -> None:
    """Lifted blocks must not appear twice (hero panel + body)."""
    report = assemble_report(
        manifest=_make_manifest(),
        facts_pack=_make_facts_pack(),
        sections=_make_cover_and_rec_sections(),
        department="equity_research",
        ticker="AAPL",
        generated_at=_NOW,
    )
    cover_section = next(s for s in report.sections if s.id == "cover")
    types_in_body = {type(b).__name__ for b in cover_section.blocks}
    assert "BulletListBlock" not in types_in_body
    assert "PullQuoteBlock" not in types_in_body
    assert "MetricCardsBlock" not in types_in_body
    # Prose text blocks must survive
    assert "TextBlock" in types_in_body


def test_rail_verdict_is_none_when_no_analyst_facts() -> None:
    """Under the no-advocacy policy, rail.verdict comes from
    deterministic analyst facts (not from LLM rating_badge). With no
    analyst_consensus_rating fact in the pack, verdict must be None."""
    report = assemble_report(
        manifest=_make_manifest(),
        facts_pack=_make_facts_pack(),
        sections=_make_cover_and_rec_sections(),
        department="equity_research",
        ticker="AAPL",
        generated_at=_NOW,
    )
    assert report.rail.verdict is None


def test_llm_rating_badge_is_stripped_from_analyst_section() -> None:
    """The LLM is no longer allowed to emit a rating_badge in the
    analyst_view section. Defense-in-depth: if it does, the assembler
    must strip it before the report ships."""
    report = assemble_report(
        manifest=_make_manifest(),
        facts_pack=_make_facts_pack(),
        sections=_make_cover_and_rec_sections(),
        department="equity_research",
        ticker="AAPL",
        generated_at=_NOW,
    )
    analyst = next(s for s in report.sections if s.id == "investment_recommendation")
    types = {type(b).__name__ for b in analyst.blocks}
    assert "RatingBadgeBlock" not in types


def test_analyst_section_title_normalized_to_analyst_view() -> None:
    report = assemble_report(
        manifest=_make_manifest(),
        facts_pack=_make_facts_pack(),
        sections=_make_cover_and_rec_sections(),
        department="equity_research",
        ticker="AAPL",
        generated_at=_NOW,
    )
    analyst = next(s for s in report.sections if s.id == "investment_recommendation")
    assert analyst.title == "Analyst View"


def _facts_pack_with_analyst_data() -> FactsPack:
    """Facts pack carrying the deterministic analyst-section inputs."""
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
            "analyst_consensus_rating": Fact(
                name="analyst_consensus_rating",
                value="Buy",
                source_ids=[1],
                extractor="deterministic",
            ),
            "analyst_target_mean": Fact(
                name="analyst_target_mean",
                value=245.0,
                source_ids=[1],
                extractor="deterministic",
            ),
            "analyst_count": Fact(
                name="analyst_count",
                value=42,
                source_ids=[1],
                extractor="deterministic",
            ),
            "analyst_rating_distribution": Fact(
                name="analyst_rating_distribution",
                value={"StrongBuy": 18, "Buy": 16, "Hold": 6, "Sell": 2},
                source_ids=[1],
                extractor="deterministic",
            ),
            "current_price": Fact(
                name="current_price",
                value=200.0,
                source_ids=[1],
                extractor="deterministic",
            ),
            "consensus_upside_pct": Fact(
                name="consensus_upside_pct",
                value=0.225,
                source_ids=[1],
                extractor="compute",
            ),
        }
    )


def test_analyst_section_gets_deterministic_rating_distribution_chart() -> None:
    """When analyst facts are present, the assembler prepends a bar_chart
    of the rating distribution and a metric_cards consensus card to the
    analyst_view section, ahead of any LLM-authored content."""
    report = assemble_report(
        manifest=_make_manifest(),
        facts_pack=_facts_pack_with_analyst_data(),
        sections=_make_cover_and_rec_sections(),
        department="equity_research",
        ticker="AAPL",
        generated_at=_NOW,
    )
    analyst = next(s for s in report.sections if s.id == "investment_recommendation")
    type_names = [type(b).__name__ for b in analyst.blocks]
    # Deterministic blocks must come FIRST
    assert type_names[0] == "BarChartBlock"
    assert type_names[1] == "MetricCardsBlock"
    # Rating distribution should carry the labelled buckets in order
    bar = analyst.blocks[0]
    assert bar.title == "Analyst rating distribution"
    assert bar.categories == ["Strong Buy", "Buy", "Hold", "Sell"]
    assert bar.series[0].values == [18.0, 16.0, 6.0, 2.0]


def test_rail_verdict_built_from_analyst_consensus_facts() -> None:
    report = assemble_report(
        manifest=_make_manifest(),
        facts_pack=_facts_pack_with_analyst_data(),
        sections=_make_cover_and_rec_sections(),
        department="equity_research",
        ticker="AAPL",
        generated_at=_NOW,
    )
    assert report.rail.verdict is not None
    assert report.rail.verdict.rating == "Consensus: Buy"
    assert report.rail.verdict.target == "$245.00"
    assert "+22.5%" in report.rail.verdict.upside


def test_analyst_section_omits_block_when_no_coverage() -> None:
    """When analyst facts are absent, no deterministic block is prepended;
    the section falls through to whatever LLM-authored content shipped
    (or nothing). Rail.verdict is also None."""
    report = assemble_report(
        manifest=_make_manifest(),
        facts_pack=_make_facts_pack(),  # no analyst facts in this fixture
        sections=_make_cover_and_rec_sections(),
        department="equity_research",
        ticker="AAPL",
        generated_at=_NOW,
    )
    analyst = next(s for s in report.sections if s.id == "investment_recommendation")
    types = [type(b).__name__ for b in analyst.blocks]
    assert "BarChartBlock" not in types
    assert report.rail.verdict is None


def test_cover_falls_back_when_synthesis_blocks_missing() -> None:
    """When the cover section omits structured blocks, the deterministic
    tagline (`Company Research Briefing`) and empty tldr remain in place.
    Rail verdict is None because no analyst facts were registered."""
    report = assemble_report(
        manifest=_make_manifest(),
        facts_pack=_make_facts_pack(),
        sections=_make_sections(),  # no cover section
        department="equity_research",
        ticker="AAPL",
        generated_at=_NOW,
    )
    assert report.cover.tagline == "Company Research Briefing"
    assert report.cover.tldr == []
    assert report.cover.tldr_label is None
    assert report.rail.verdict is None
