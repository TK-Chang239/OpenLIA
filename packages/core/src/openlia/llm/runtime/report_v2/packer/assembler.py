"""Assembler: converts SectionResult list + FactsPack + Manifest into ReportSchema."""
from __future__ import annotations

import importlib
from collections.abc import Callable
from datetime import datetime
from typing import Any

from openlia.llm.runtime.report_v2.facts.pack import FactsPack
from openlia.llm.runtime.report_v2.manifest.manifest import Manifest
from openlia.llm.runtime.report_v2.packer.blocks.registry import default_block_registry
from openlia.llm.runtime.report_v2.packer.parser import (
    FencedBlockSegment,
    Segment,
    TextSegment,
    parse_section_file,
)
from openlia.llm.runtime.report_v2.types import Fact, SectionTerminalState
from openlia.reports.schema import (
    Block,
    Citation,
    Cover,
    Metric,
    ReportSchema,
    Section,
    TextBlock,
)

# Ensure all block modules register themselves before first use.
_BLOCK_MODULES = [
    "openlia.llm.runtime.report_v2.packer.blocks.text",
    "openlia.llm.runtime.report_v2.packer.blocks.table",
    "openlia.llm.runtime.report_v2.packer.blocks.metric_cards",
    "openlia.llm.runtime.report_v2.packer.blocks.key_finding",
    "openlia.llm.runtime.report_v2.packer.blocks.rating_badge",
    "openlia.llm.runtime.report_v2.packer.blocks.pull_quote",
    "openlia.llm.runtime.report_v2.packer.blocks.callout_grid",
    "openlia.llm.runtime.report_v2.packer.blocks.timeline",
    "openlia.llm.runtime.report_v2.packer.blocks.bullet_list",
    "openlia.llm.runtime.report_v2.packer.blocks.comparison_split",
    "openlia.llm.runtime.report_v2.packer.blocks.quote",
    "openlia.llm.runtime.report_v2.packer.blocks.chart_line",
    "openlia.llm.runtime.report_v2.packer.blocks.chart_bar",
    "openlia.llm.runtime.report_v2.packer.blocks.chart_area",
    "openlia.llm.runtime.report_v2.packer.blocks.chart_pie",
    "openlia.llm.runtime.report_v2.packer.blocks.chart_candlestick",
    "openlia.llm.runtime.report_v2.packer.blocks.chart_waterfall",
    "openlia.llm.runtime.report_v2.packer.blocks.chart_scatter",
    "openlia.llm.runtime.report_v2.packer.blocks.chart_heatmap",
    "openlia.llm.runtime.report_v2.packer.blocks.chart_treemap",
    "openlia.llm.runtime.report_v2.packer.blocks.chart_combo",
    "openlia.llm.runtime.report_v2.packer.blocks.group",
]

for _mod in _BLOCK_MODULES:
    importlib.import_module(_mod)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def assemble_report(
    *,
    manifest: Manifest,
    facts_pack: FactsPack,
    sections: list[Any],  # list[SectionResult]
    department: str,
    ticker: str,
    generated_at: datetime,
) -> ReportSchema:
    """Convert wave output into a validated ReportSchema."""
    id_map = _resolve_marker_to_cid(manifest)
    resolver = _make_resolver(id_map)
    citations = _build_citations(manifest)
    cover = _build_cover(facts_pack, ticker=ticker)

    assembled_sections: list[Section] = []
    for sr in sections:
        if sr.state == SectionTerminalState.EXHAUSTED:
            continue
        assert sr.markdown is not None
        parsed = parse_section_file(sr.markdown)
        fm = parsed.frontmatter
        section_id = fm.get("section_id", sr.section_id)
        title = fm.get("title", section_id)
        blocks: list[Block] = []
        for seg in parsed.segments:
            block = _segment_to_block(seg, manifest_resolver=resolver)
            if block is not None:
                blocks.append(block)
        assembled_sections.append(Section(id=section_id, title=title, blocks=blocks))

    return ReportSchema(
        schema_version="2.0",
        department=department,
        generated_at=generated_at,
        cover=cover,
        sections=assembled_sections,
        citations=citations,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_marker_to_cid(manifest: Manifest) -> dict[int, str]:
    """Map manifest integer IDs [N] -> citation string IDs "cN"."""
    return {entry.id: f"c{entry.id}" for entry in manifest.entries}


def _make_resolver(id_map: dict[int, str]) -> Callable[[list[int]], list[str]]:
    """Return a callable compatible with block assembler manifest_resolver signature.

    Block assemblers call: manifest_resolver(list[int]) -> list[str]
    where the ints are raw manifest marker IDs and the strings are "c{N}" citation IDs.
    """

    def _resolve(ids: list[int]) -> list[str]:
        return [id_map[n] for n in ids if n in id_map]

    return _resolve


def _segment_to_block(
    seg: Segment,
    *,
    manifest_resolver: Callable[[list[int]], list[str]],
) -> Block | None:
    """Dispatch one parsed segment to its schema block."""
    if isinstance(seg, TextSegment):
        return TextBlock(type="text", content=seg.text)

    if isinstance(seg, FencedBlockSegment):
        entry = default_block_registry.get(seg.block_type)
        if entry is None:
            # Unknown tag — fall back to text so nothing is silently dropped.
            return TextBlock(type="text", content=f"[unknown block: {seg.block_type}]")

        # Block YAML uses "sources" (integer manifest IDs), not "source_ids".
        sources_from_yaml: list[int] = [
            int(s)
            for s in (seg.data.get("sources") or [])
            if str(s).lstrip("-").isdigit()
        ]
        citation_ids = manifest_resolver(sources_from_yaml)
        return entry.assembler(
            data=seg.data,
            citation_ids=citation_ids,
            manifest_resolver=manifest_resolver,
        )

    return None  # unreachable; satisfies type checker


def _format_market_cap(value: float | int) -> str:
    """Format a raw market cap number to a human-readable string."""
    v = float(value)
    if v >= 1_000_000_000_000:
        return f"${v / 1_000_000_000_000:.2f}T"
    if v >= 1_000_000_000:
        return f"${v / 1_000_000_000:.2f}B"
    if v >= 1_000_000:
        return f"${v / 1_000_000:.2f}M"
    return f"${v:,.0f}"


def _build_cover(facts_pack: FactsPack, *, ticker: str) -> Cover:
    """Build Cover from FactsPack, populating rigid key_metrics slots."""
    facts = facts_pack.facts

    company_name = _fact_value(facts, "company_name", default=ticker)
    sector = _fact_value(facts, "sector", default="")
    market_cap_raw = _fact_value(facts, "market_cap", default=None)
    pe_ratio = _fact_value(facts, "pe_ratio_ttm", default=None)

    subtitle = sector if sector else ticker

    key_metrics: list[Metric] = []

    if market_cap_raw is not None:
        mc_source_ids = [f"c{sid}" for sid in facts["market_cap"].source_ids]
        key_metrics.append(
            Metric(
                label="Market Cap",
                value=_format_market_cap(market_cap_raw),
                source_ids=mc_source_ids,
            )
        )

    if pe_ratio is not None:
        pe_source_ids = [f"c{sid}" for sid in facts["pe_ratio_ttm"].source_ids]
        key_metrics.append(
            Metric(
                label="P/E (TTM)",
                value=f"{pe_ratio}x",
                source_ids=pe_source_ids,
            )
        )

    return Cover(
        title=company_name,
        subtitle=subtitle,
        ticker=ticker,
        tagline="Equity Research Initiation",
        key_metrics=key_metrics,
    )


def _build_citations(manifest: Manifest) -> list[Citation]:
    """Build one Citation per manifest entry."""
    return [
        Citation(
            id=f"c{entry.id}",
            title=entry.identifier,
            source=entry.provider,
        )
        for entry in manifest.entries
    ]


def _fact_value(facts: dict[str, Fact], name: str, *, default: Any) -> Any:
    if name in facts:
        return facts[name].value
    return default
