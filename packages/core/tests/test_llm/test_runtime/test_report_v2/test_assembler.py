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
