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
    BarChartBlock,
    BarSeries,
    Block,
    BulletListBlock,
    Citation,
    Cover,
    MetaStats,
    Metric,
    MetricCardsBlock,
    PullQuoteBlock,
    Rail,
    RatingBadgeBlock,
    ReportSchema,
    Section,
    TableBlock,
    TableHeader,
    TextBlock,
    Verdict,
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
    on_omitted_block: Callable[[str, str, str], None] | None = None,
) -> ReportSchema:
    """Convert wave output into a validated ReportSchema."""
    id_map = _resolve_marker_to_cid(manifest)
    resolver = _make_resolver(id_map)
    citations = _build_citations(manifest)
    cover = _build_cover(facts_pack, ticker=ticker, generated_at=generated_at)
    rail = _build_rail(facts_pack, generated_at=generated_at)

    assembled_sections: list[Section] = []
    for sr in sections:
        if sr.state == SectionTerminalState.EXHAUSTED:
            continue
        if sr.state in (
            SectionTerminalState.SKIPPED_REQUIRED_FACTS,
            SectionTerminalState.DEGRADED_CAP_HIT,
        ):
            assembled_sections.append(
                Section(
                    id=sr.section_id,
                    title=sr.section_id.replace("_", " ").title(),
                    blocks=[_build_skip_banner_block(sr)],
                )
            )
            continue
        assert sr.markdown is not None
        parsed = parse_section_file(sr.markdown)
        fm = parsed.frontmatter
        section_id = fm.get("section_id", sr.section_id)
        title = fm.get("title", section_id)
        blocks: list[Block] = []
        for idx, seg in enumerate(parsed.segments):
            block_type = seg.block_type if isinstance(seg, FencedBlockSegment) else "text"
            try:
                block = _segment_to_block(seg, manifest_resolver=resolver)
                if block is not None:
                    blocks.append(block)
            except Exception as exc:
                summary = str(exc)[:120]
                print(
                    f"[assembler] section {section_id} block #{idx} ({block_type}): "
                    f"omitted due to assembly error: {type(exc).__name__}: {summary}",
                    flush=True,
                )
                if on_omitted_block is not None:
                    on_omitted_block(section_id, block_type, type(exc).__name__)
                # Drop the failed block silently — telemetry above is the
                # diagnostic channel. Earlier versions emitted a user-visible
                # "[block omitted: ...]" text block, which leaked into PDFs.
        _strip_leading_title_heading(blocks, title)
        assembled_sections.append(Section(id=section_id, title=title, blocks=blocks))

    _enrich_cover_and_rail_from_sections(cover, rail, assembled_sections, facts_pack)
    meta_stats = _build_meta_stats(citations=citations, sections=assembled_sections)

    return ReportSchema(
        schema_version="2.0",
        department=department,
        generated_at=generated_at,
        cover=cover,
        sections=assembled_sections,
        rail=rail,
        citations=citations,
        meta_stats=meta_stats,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_skip_banner_block(sr: Any) -> Block:
    """Render an admonition-style TextBlock for skipped/degraded sections.

    PR 15: makes custom-template failure modes surface in the rendered output
    instead of silently dropping the section. The banner names the section
    and (for SKIPPED_REQUIRED_FACTS) the missing facts so the template author
    can react. We piggy-back on TextBlock to avoid a schema change; the
    leading `> **Section omitted:**` prefix renders as a blockquote callout in
    the existing markdown viewer.
    """
    from openlia.reports.schema import TextBlock as _TextBlock

    if sr.state == SectionTerminalState.SKIPPED_REQUIRED_FACTS:
        missing = sr.validation_errors or []
        detail = ", ".join(f"`{name}`" for name in missing) if missing else "(unspecified)"
        content = (
            f"> **Section omitted.** Required fact(s) unavailable for this subject: "
            f"{detail}. Other sections continue to render."
        )
    else:  # DEGRADED_CAP_HIT
        content = (
            "> **Section degraded.** Tool-call round budget exhausted before all "
            "requested helpers were invoked; the prose below reflects only the "
            "partial data the writer was able to gather."
        )
    return _TextBlock(type="text", content=content)


def _strip_leading_title_heading(blocks: list[Block], section_title: str) -> None:
    """Drop a leading "# Title" or "## Title" line from the first text block
    when it duplicates the section title.

    The section title is already rendered as an H2 by ReportSection; LLMs
    reliably also emit it as a markdown heading on the first line of prose,
    which causes the title to appear twice in the rendered report.
    Compares case-insensitively and ignores trailing punctuation/whitespace.
    """
    if not blocks or not section_title:
        return
    head = blocks[0]
    content = getattr(head, "content", None)
    if not isinstance(content, str) or not content:
        return
    lines = content.split("\n", 1)
    first = lines[0].strip()
    rest = lines[1] if len(lines) > 1 else ""
    if not (first.startswith("# ") or first.startswith("## ")):
        return
    heading_text = first.lstrip("# ").strip().rstrip(":.,;").strip()
    if heading_text.casefold() != section_title.strip().casefold():
        return
    head.content = rest.lstrip("\n")


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
            int(s) for s in (seg.data.get("sources") or []) if str(s).lstrip("-").isdigit()
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


def _format_price(value: float) -> str:
    """Render a stock price in dollars with two decimals."""
    return f"${float(value):,.2f}"


def _format_pct(value: float) -> str:
    """Render a decimal margin/growth as a one-decimal percent."""
    return f"{float(value) * 100:.1f}%"


def _format_int_compact(value: float) -> str:
    """Render a large integer (e.g., share volume) in compact form."""
    v = float(value)
    if v >= 1_000_000_000:
        return f"{v / 1_000_000_000:.2f}B"
    if v >= 1_000_000:
        return f"{v / 1_000_000:.1f}M"
    if v >= 1_000:
        return f"{v / 1_000:.0f}K"
    return f"{v:,.0f}"


def _build_cover(facts_pack: FactsPack, *, ticker: str, generated_at: datetime) -> Cover:
    """Build the cover hero panel from FactsPack.

    Five-slot key_metrics in priority order: Current Price, Market Cap,
    Forward P/E (fallback TTM), Revenue (TTM), Net Margin (fallback Gross).
    Tagline/tldr/tldr_label may be overwritten by
    `_enrich_cover_and_rail_from_sections` once the LLM-authored cover
    body section has been assembled. The deterministic shape below is the
    floor — never fewer cards than this.
    """
    facts = facts_pack.facts

    company_name = _fact_value(facts, "company_name", default=ticker)
    sector = _fact_value(facts, "sector", default="")
    subtitle = sector if sector else ticker
    eyebrow = f"Research Briefing · {generated_at.date().isoformat()}"

    key_metrics: list[Metric] = []

    def _add(label: str, value: str, fact_name: str) -> None:
        source_ids = [f"c{sid}" for sid in facts[fact_name].source_ids]
        key_metrics.append(Metric(label=label, value=value, source_ids=source_ids))

    price = _fact_value(facts, "current_price", default=None)
    if price is not None:
        _add("Current Price", _format_price(price), "current_price")

    market_cap = _fact_value(facts, "market_cap", default=None)
    if market_cap is not None:
        _add("Market Cap", _format_market_cap(market_cap), "market_cap")

    fwd_pe = _fact_value(facts, "pe_ratio_forward", default=None)
    if fwd_pe is not None:
        _add("P/E (Fwd)", f"{float(fwd_pe):.1f}x", "pe_ratio_forward")
    else:
        ttm_pe = _fact_value(facts, "pe_ratio_ttm", default=None)
        if ttm_pe is not None:
            _add("P/E (TTM)", f"{float(ttm_pe):.1f}x", "pe_ratio_ttm")

    revenue_ttm = _fact_value(facts, "revenue_ttm", default=None)
    if revenue_ttm is not None:
        _add("Revenue (TTM)", _format_market_cap(revenue_ttm), "revenue_ttm")
    else:
        rev_series = _fact_value(facts, "revenue_annual", default=None)
        if rev_series and isinstance(rev_series, list) and rev_series[-1] is not None:
            _add(
                "Revenue (FY)",
                _format_market_cap(float(rev_series[-1])),
                "revenue_annual",
            )

    net_margin = _fact_value(facts, "net_margin_ttm", default=None)
    if net_margin is not None:
        _add("Net Margin", _format_pct(net_margin), "net_margin_ttm")
    else:
        gm = _fact_value(facts, "gross_margin_ttm", default=None)
        if gm is not None:
            _add("Gross Margin", _format_pct(gm), "gross_margin_ttm")

    # Deterministic consensus block (WS5). Pulls rating / target / upside
    # straight from the analyst facts so the cover hero can render the
    # market verdict above the fold rather than burying it in the body.
    consensus_rating: str | None = None
    consensus_target_mean: float | None = None
    consensus_upside_pct_val: float | None = None
    consensus_source_ids: list[str] = []
    rating_fact = facts.get("analyst_consensus_rating")
    if rating_fact is not None and rating_fact.value:
        consensus_rating = str(rating_fact.value)
        consensus_source_ids = [f"c{sid}" for sid in rating_fact.source_ids]
    target_fact = facts.get("analyst_target_mean")
    if target_fact is not None and target_fact.value is not None:
        consensus_target_mean = float(target_fact.value)
    upside_fact = facts.get("consensus_upside_pct")
    if upside_fact is not None and upside_fact.value is not None:
        consensus_upside_pct_val = float(upside_fact.value)

    return Cover(
        title=company_name,
        subtitle=subtitle,
        eyebrow=eyebrow,
        ticker=ticker,
        tagline="Company Research Briefing",
        key_metrics=key_metrics,
        consensus_rating=consensus_rating,
        consensus_target_mean=consensus_target_mean,
        consensus_upside_pct=consensus_upside_pct_val,
        consensus_source_ids=consensus_source_ids,
    )


def _build_rail(facts_pack: FactsPack, *, generated_at: datetime) -> Rail:
    """Build the right-rail summary from FactsPack.

    The verdict is sourced from analyst consensus facts (deterministic,
    NEVER from LLM rating_badge under the no-advocacy policy). The
    quick_stats block carries the market-data identity strip (Sector,
    Exchange, Market Cap, 52W Range, ADTV (3mo), Forward P/E) plus a
    couple of profitability tiles. Sparkline is still deferred — needs
    a dedicated EOD-history fact extractor for the points payload.
    """
    facts = facts_pack.facts
    quick_stats: list[Metric] = []

    def _push_fact(label: str, fact_name: str, formatter: Callable[[Any], str]) -> None:
        if fact_name not in facts:
            return
        fact = facts[fact_name]
        if fact.value is None:
            return
        source_ids = [f"c{sid}" for sid in fact.source_ids]
        quick_stats.append(Metric(label=label, value=formatter(fact.value), source_ids=source_ids))

    _push_fact("Sector", "sector", lambda v: str(v))
    _push_fact("Exchange", "exchange", lambda v: str(v))
    _push_fact("Market Cap", "market_cap", _format_market_cap)
    _push_fact(
        "52W Range",
        "price_range_52w",
        lambda v: f"{_format_price(v['low'])}-{_format_price(v['high'])}",
    )
    _push_fact("ADTV (3mo)", "avg_daily_volume_3m", _format_int_compact)
    _push_fact("P/E (Fwd)", "pe_ratio_forward", lambda v: f"{float(v):.1f}x")
    _push_fact("Gross Margin", "gross_margin_ttm", _format_pct)
    _push_fact("Revenue CAGR (3y)", "revenue_cagr_3y", _format_pct)

    verdict = _build_verdict(facts_pack, generated_at=generated_at)
    return Rail(quick_stats=quick_stats, verdict=verdict)


def _build_verdict(facts_pack: FactsPack, *, generated_at: datetime) -> Verdict | None:
    """Build Rail.verdict from analyst consensus facts.

    Returns None when there is no analyst coverage (microcaps, foreign
    tickers, illiquid names) so the rail simply omits the verdict card
    rather than render a placeholder.
    """
    facts = facts_pack.facts
    rating = _fact_value(facts, "analyst_consensus_rating", default=None)
    if not rating:
        return None
    target = _fact_value(facts, "analyst_target_mean", default=None)
    upside = _fact_value(facts, "consensus_upside_pct", default=None)
    return Verdict(
        rating=f"Consensus: {rating}",
        target=_format_price(target) if target is not None else None,
        upside=f"{upside * 100:+.1f}%" if upside is not None else None,
        as_of=generated_at.date().isoformat(),
    )


_ANALYST_RATING_BUCKET_LABELS: tuple[tuple[str, str], ...] = (
    ("StrongBuy", "Strong Buy"),
    ("Buy", "Buy"),
    ("Hold", "Hold"),
    ("Sell", "Sell"),
    ("StrongSell", "Strong Sell"),
)


def _enrich_cover_and_rail_from_sections(
    cover: Cover, rail: Rail, sections: list[Section], facts_pack: FactsPack
) -> None:
    """Lift LLM-authored structured blocks from the synthesis sections into
    the cover hero panel, and inject deterministic analyst blocks into the
    analyst-view section.

    Cover lifts (LLM → hero):
    - ``bullet_list`` -> ``Cover.tldr`` (label "Executive Summary")
    - ``pull_quote`` -> ``Cover.tagline``
    - ``metric_cards`` -> ``Cover.key_metrics`` (only when LLM emits more
      cards than the deterministic baseline)

    Analyst-view section (id=investment_recommendation) — deterministic
    blocks are PREPENDED so the section starts with the analyst data and
    the LLM-authored Bull/Bear comparison_split follows:
    - rating-distribution ``bar_chart``
    - consensus-target ``metric_cards``
    - any LLM-emitted ``rating_badge`` is stripped (advocacy-shaped,
      always wrong under the no-advocacy policy).
    The section title is normalized to "Analyst View" regardless of what
    the LLM emitted.
    """
    cover_section = next((s for s in sections if s.id == "cover"), None)
    if cover_section is not None:
        kept_blocks: list[Block] = []
        bullet_lifted = False
        quote_lifted = False
        metrics_lifted = False
        for block in cover_section.blocks:
            if not bullet_lifted and isinstance(block, BulletListBlock):
                cover.tldr = list(block.items)
                cover.tldr_label = "Executive Summary"
                bullet_lifted = True
                continue
            if not quote_lifted and isinstance(block, PullQuoteBlock):
                cover.tagline = block.text
                quote_lifted = True
                continue
            if (
                not metrics_lifted
                and isinstance(block, MetricCardsBlock)
                and len(block.metrics) >= len(cover.key_metrics)
            ):
                cover.key_metrics = list(block.metrics)
                metrics_lifted = True
                continue
            kept_blocks.append(block)
        cover_section.blocks = kept_blocks

    overview_section = next((s for s in sections if s.id == "company_overview"), None)
    if overview_section is not None:
        identity_card = _build_identity_card(facts_pack)
        if identity_card is not None:
            overview_section.blocks = [identity_card, *overview_section.blocks]

    hist_section = next((s for s in sections if s.id == "historical_financials"), None)
    if hist_section is not None:
        hist_blocks = _build_historical_financial_tables(facts_pack)
        if hist_blocks:
            hist_section.blocks = [*hist_blocks, *hist_section.blocks]

    fin_section = next((s for s in sections if s.id == "financial_analysis"), None)
    if fin_section is not None:
        margin_table = _build_margin_progression_table(facts_pack)
        if margin_table is not None:
            fin_section.blocks = [margin_table, *fin_section.blocks]

    analyst_section = next((s for s in sections if s.id == "investment_recommendation"), None)
    if analyst_section is not None:
        analyst_section.title = "Analyst View"
        # Strip any LLM-emitted rating_badge — it would necessarily be a
        # rating the LLM made up, which the no-advocacy policy bans.
        analyst_section.blocks = [
            b for b in analyst_section.blocks if not isinstance(b, RatingBadgeBlock)
        ]
        analyst_blocks = _build_analyst_blocks(facts_pack)
        if analyst_blocks:
            analyst_section.blocks = [*analyst_blocks, *analyst_section.blocks]


def _build_analyst_blocks(facts_pack: FactsPack) -> list[Block]:
    """Build deterministic blocks for the Analyst View section header from
    EODHD AnalystRatings facts. Returns an empty list when no analyst
    coverage exists, signalling that the section should fall through to
    whatever LLM-authored prose / comparison_split was emitted (or nothing).
    """
    facts = facts_pack.facts
    distribution = _fact_value(facts, "analyst_rating_distribution", default=None)
    rating_label = _fact_value(facts, "analyst_consensus_rating", default=None)
    target_mean = _fact_value(facts, "analyst_target_mean", default=None)
    analyst_n = _fact_value(facts, "analyst_count", default=None)
    upside = _fact_value(facts, "consensus_upside_pct", default=None)

    if not distribution and rating_label is None and target_mean is None:
        return []

    out: list[Block] = []

    if distribution:
        cats: list[str] = []
        vals: list[float] = []
        for key, label in _ANALYST_RATING_BUCKET_LABELS:
            count = distribution.get(key)
            if count is None or count <= 0:
                continue
            cats.append(label)
            vals.append(float(count))
        if cats:
            source_ids = [f"c{sid}" for sid in facts["analyst_rating_distribution"].source_ids]
            out.append(
                BarChartBlock(
                    type="bar_chart",
                    title="Analyst rating distribution",
                    categories=cats,
                    series=[BarSeries(name="Analysts", values=vals)],
                    orientation="horizontal",
                    source_ids=source_ids,
                )
            )

    target_cards: list[Metric] = []
    if rating_label is not None:
        target_cards.append(
            Metric(
                label="Consensus rating",
                value=rating_label,
                source_ids=[f"c{sid}" for sid in facts["analyst_consensus_rating"].source_ids],
                highlight=True,
            )
        )
    if target_mean is not None:
        target_cards.append(
            Metric(
                label="Mean target",
                value=_format_price(target_mean),
                source_ids=[f"c{sid}" for sid in facts["analyst_target_mean"].source_ids],
            )
        )
    if upside is not None:
        target_cards.append(
            Metric(
                label="Upside vs current",
                value=f"{float(upside) * 100:+.1f}%",
                source_ids=[f"c{sid}" for sid in facts["consensus_upside_pct"].source_ids],
            )
        )
    if analyst_n is not None and analyst_n > 0:
        target_cards.append(
            Metric(
                label="Covering analysts",
                value=str(int(analyst_n)),
                source_ids=[f"c{sid}" for sid in facts["analyst_count"].source_ids],
            )
        )
    if target_cards:
        out.append(MetricCardsBlock(type="metric_cards", metrics=target_cards))

    return out


def _build_meta_stats(*, citations: list[Citation], sections: list[Section]) -> MetaStats:
    """Build server-authoritative report stats.

    Deterministic from assembler inputs — model_id, tokens_used, and
    web_search_queries would require threading through from the runner,
    so they stay None here and can be patched in by the runtime layer
    if needed."""
    word_count = 0
    for section in sections:
        for block in section.blocks:
            content = getattr(block, "content", None)
            if isinstance(content, str):
                word_count += len(content.split())
    est_read_minutes = max(1, round(word_count / 250)) if word_count else 0

    return MetaStats(
        sources_count=len(citations),
        sections_count=len(sections),
        est_read_minutes=est_read_minutes,
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


# ---------------------------------------------------------------------------
# Deterministic always-included blocks (company identity card,
# historical financial tables, margin progression). Each builder returns
# None / [] when the underlying facts are absent so the section can
# simply skip the block rather than render a half-populated one.
# ---------------------------------------------------------------------------


def _year_from_iso(date_str: str) -> str:
    """Pull the year off an ISO YYYY-MM-DD string; pass through on shape mismatch."""
    if isinstance(date_str, str) and len(date_str) >= 4 and date_str[:4].isdigit():
        return date_str[:4]
    return str(date_str)


def _build_identity_card(facts_pack: FactsPack) -> MetricCardsBlock | None:
    """Server-built metric_cards: Founded, HQ, Employees, Exchange,
    Revenue (TTM), EBITDA (TTM). Each cell only ships when its source
    fact is present."""
    facts = facts_pack.facts
    cards: list[Metric] = []

    def _add(label: str, value: str, fact_name: str) -> None:
        source_ids = [f"c{sid}" for sid in facts[fact_name].source_ids]
        cards.append(Metric(label=label, value=value, source_ids=source_ids))

    ipo = _fact_value(facts, "ipo_date", default=None)
    if ipo:
        _add("Founded", _year_from_iso(ipo), "ipo_date")
    hq = _fact_value(facts, "headquarters", default=None)
    if hq:
        _add("Headquarters", str(hq), "headquarters")
    emp = _fact_value(facts, "employees", default=None)
    if emp is not None:
        try:
            _add("Employees", f"{int(emp):,}", "employees")
        except (TypeError, ValueError):
            pass
    exch = _fact_value(facts, "exchange", default=None)
    if exch:
        _add("Exchange", str(exch), "exchange")
    rev_ttm = _fact_value(facts, "revenue_ttm", default=None)
    if rev_ttm is not None:
        _add("Revenue (TTM)", _format_market_cap(rev_ttm), "revenue_ttm")
    ebitda = _fact_value(facts, "ebitda_ttm", default=None)
    if ebitda is not None:
        _add("EBITDA (TTM)", _format_market_cap(ebitda), "ebitda_ttm")
    sector_val = _fact_value(facts, "sector", default=None)
    if sector_val:
        _add("Sector", str(sector_val), "sector")

    if not cards:
        return None
    return MetricCardsBlock(type="metric_cards", metrics=cards)


def _fmt_money(value: Any) -> str:
    try:
        return _format_market_cap(float(value))
    except (TypeError, ValueError):
        return "—"


def _fmt_eps(value: Any) -> str:
    try:
        return f"${float(value):,.2f}"
    except (TypeError, ValueError):
        return "—"


def _yoy_pct(curr: Any, prev: Any) -> str:
    try:
        c = float(curr)
        p = float(prev)
    except (TypeError, ValueError):
        return "—"
    if p == 0:
        return "—"
    return f"{(c - p) / abs(p) * 100:+.1f}%"


def _build_historical_financial_tables(facts_pack: FactsPack) -> list[Block]:
    """Server-built 5y income statement and balance sheet tables. Each
    table is emitted only when at least the first column (Revenue or
    Total Assets respectively) is available — partial fact coverage
    renders the missing columns as em-dashes."""
    facts = facts_pack.facts
    years = _fact_value(facts, "revenue_years", default=None)
    if not years:
        return []

    out: list[Block] = []

    revenue = _fact_value(facts, "revenue_annual", default=None)
    if revenue:
        cogs = _fact_value(facts, "cogs_annual", default=None) or []
        gross = _fact_value(facts, "gross_profit_annual", default=None) or []
        opinc = _fact_value(facts, "operating_income_annual", default=None) or []
        netinc = _fact_value(facts, "net_income_annual", default=None) or []
        eps = _fact_value(facts, "eps_annual", default=None) or []
        # All series are aligned to the last N years; trim to len(years)
        # for safety in case the upstream series ordering drifts.
        n = min(len(years), len(revenue))
        rows: list[dict[str, Any]] = []
        for i in range(n):
            prev_rev = revenue[i - 1] if i > 0 and i - 1 < len(revenue) else None
            prev_eps = eps[i - 1] if i > 0 and i - 1 < len(eps) else None
            rows.append(
                {
                    "year": _year_from_iso(years[i]),
                    "revenue": _fmt_money(revenue[i]),
                    "cogs": _fmt_money(cogs[i]) if i < len(cogs) else "—",
                    "gross": _fmt_money(gross[i]) if i < len(gross) else "—",
                    "opinc": _fmt_money(opinc[i]) if i < len(opinc) else "—",
                    "netinc": _fmt_money(netinc[i]) if i < len(netinc) else "—",
                    "eps": _fmt_eps(eps[i]) if i < len(eps) else "—",
                    "rev_yoy": _yoy_pct(revenue[i], prev_rev) if prev_rev is not None else "—",
                    "eps_yoy": _yoy_pct(eps[i], prev_eps)
                    if i < len(eps) and prev_eps is not None
                    else "—",
                }
            )
        income_source_ids = sorted(
            {
                f"c{sid}"
                for f in (
                    facts.get("revenue_annual"),
                    facts.get("net_income_annual"),
                    facts.get("operating_income_annual"),
                )
                if f
                for sid in f.source_ids
            }
        )
        out.append(
            TableBlock(
                type="table",
                title="Income statement — five-year summary",
                headers=[
                    TableHeader(key="year", label="Year"),
                    TableHeader(key="revenue", label="Revenue", align="right"),
                    TableHeader(key="cogs", label="COGS", align="right"),
                    TableHeader(key="gross", label="Gross Profit", align="right"),
                    TableHeader(key="opinc", label="Operating Income", align="right"),
                    TableHeader(key="netinc", label="Net Income", align="right"),
                    TableHeader(key="eps", label="EPS", align="right"),
                    TableHeader(key="rev_yoy", label="Revenue YoY", align="right"),
                    TableHeader(key="eps_yoy", label="EPS YoY", align="right"),
                ],
                rows=rows,
                source_ids=income_source_ids,
            )
        )

    assets = _fact_value(facts, "total_assets_annual", default=None)
    if assets:
        liab = _fact_value(facts, "total_liabilities_annual", default=None) or []
        equity = _fact_value(facts, "equity_annual", default=None) or []
        cash = _fact_value(facts, "cash_annual", default=None) or []
        debt = _fact_value(facts, "total_debt_annual", default=None) or []
        n = min(len(years), len(assets))
        rows = []
        for i in range(n):
            rows.append(
                {
                    "year": _year_from_iso(years[i]),
                    "assets": _fmt_money(assets[i]),
                    "liab": _fmt_money(liab[i]) if i < len(liab) else "—",
                    "equity": _fmt_money(equity[i]) if i < len(equity) else "—",
                    "cash": _fmt_money(cash[i]) if i < len(cash) else "—",
                    "debt": _fmt_money(debt[i]) if i < len(debt) else "—",
                }
            )
        bs_source_ids = sorted(
            {
                f"c{sid}"
                for f in (
                    facts.get("total_assets_annual"),
                    facts.get("total_liabilities_annual"),
                    facts.get("equity_annual"),
                )
                if f
                for sid in f.source_ids
            }
        )
        out.append(
            TableBlock(
                type="table",
                title="Balance sheet — five-year summary",
                headers=[
                    TableHeader(key="year", label="Year"),
                    TableHeader(key="assets", label="Total Assets", align="right"),
                    TableHeader(key="liab", label="Total Liabilities", align="right"),
                    TableHeader(key="equity", label="Equity", align="right"),
                    TableHeader(key="cash", label="Cash", align="right"),
                    TableHeader(key="debt", label="Total Debt", align="right"),
                ],
                rows=rows,
                source_ids=bs_source_ids,
            )
        )

    return out


def _build_margin_progression_table(facts_pack: FactsPack) -> TableBlock | None:
    """Server-built five-year margin progression: Gross / Operating / Net."""
    facts = facts_pack.facts
    years = _fact_value(facts, "revenue_years", default=None)
    gm = _fact_value(facts, "gross_margin_annual", default=None)
    om = _fact_value(facts, "operating_margin_annual", default=None)
    nm = _fact_value(facts, "net_margin_annual", default=None)
    if not years or not gm:
        return None
    n = min(len(years), len(gm))
    rows: list[dict[str, Any]] = []
    for i in range(n):
        rows.append(
            {
                "year": _year_from_iso(years[i]),
                "gross": _format_pct(gm[i]) if gm[i] is not None else "—",
                "op": _format_pct(om[i]) if om and i < len(om) and om[i] is not None else "—",
                "net": _format_pct(nm[i]) if nm and i < len(nm) and nm[i] is not None else "—",
            }
        )
    source_ids = sorted(
        {
            f"c{sid}"
            for f in (
                facts.get("gross_margin_annual"),
                facts.get("operating_margin_annual"),
                facts.get("net_margin_annual"),
            )
            if f
            for sid in f.source_ids
        }
    )
    return TableBlock(
        type="table",
        title="Margin progression — five-year",
        headers=[
            TableHeader(key="year", label="Year"),
            TableHeader(key="gross", label="Gross Margin", align="right"),
            TableHeader(key="op", label="Operating Margin", align="right"),
            TableHeader(key="net", label="Net Margin", align="right"),
        ],
        rows=rows,
        source_ids=source_ids,
    )
