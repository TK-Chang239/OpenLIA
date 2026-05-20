"""WS5: the assembler must populate the deterministic consensus block on
the Cover hero from the analyst_consensus_rating / analyst_target_mean /
consensus_upside_pct facts. The LLM never authors these fields. Absent
facts must surface as None so the renderer can degrade gracefully.
"""

from __future__ import annotations

from datetime import UTC, datetime

from openlia.llm.runtime.report_v2.facts.pack import FactsPack
from openlia.llm.runtime.report_v2.manifest.manifest import Manifest
from openlia.llm.runtime.report_v2.packer.assembler import assemble_report
from openlia.llm.runtime.report_v2.types import Fact, SectionResult, SectionTerminalState

_NOW = datetime(2026, 5, 20, 9, 0, 0, tzinfo=UTC)


def _make_manifest() -> Manifest:
    m = Manifest()
    m.append(
        kind="fetch",
        provider="eodhd",
        identifier="get_fundamentals_data/AAPL",
        raw_payload={"Highlights": {"MarketCapitalization": 3_000_000_000_000}},
        retrieved_at=_NOW,
    )
    return m


_SECTION_MARKDOWN = (
    "---\nsection_id: thesis\ntitle: Investment Thesis\nsources_used: [1]\n---\n\nProse body. [1]\n"
)


def _make_sections() -> list[SectionResult]:
    return [
        SectionResult(
            section_id="thesis",
            state=SectionTerminalState.SUCCESS,
            attempts=1,
            markdown=_SECTION_MARKDOWN,
        ),
    ]


def _facts_with_consensus() -> FactsPack:
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
            "analyst_consensus_rating": Fact(
                name="analyst_consensus_rating",
                value="Buy",
                source_ids=[1],
                extractor="deterministic",
            ),
            "analyst_target_mean": Fact(
                name="analyst_target_mean",
                value=245.5,
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


def _facts_without_consensus() -> FactsPack:
    return FactsPack(
        facts={
            "company_name": Fact(
                name="company_name",
                value="Microcap Inc.",
                source_ids=[1],
                extractor="deterministic",
            ),
            "sector": Fact(
                name="sector",
                value="Industrials",
                source_ids=[1],
                extractor="deterministic",
            ),
        }
    )


def test_cover_carries_consensus_rating_target_upside_when_facts_present() -> None:
    report = assemble_report(
        manifest=_make_manifest(),
        facts_pack=_facts_with_consensus(),
        sections=_make_sections(),
        department="equity_research",
        ticker="AAPL",
        generated_at=_NOW,
    )
    cover = report.cover
    assert cover.consensus_rating == "Buy"
    assert cover.consensus_target_mean == 245.5
    assert cover.consensus_upside_pct == 0.225
    # Source citation IDs travel with the consensus block so the renderer
    # can attach the inline [N] marker back to the AnalystRatings entry.
    assert cover.consensus_source_ids == ["c1"]


def test_cover_consensus_fields_are_none_when_facts_absent() -> None:
    report = assemble_report(
        manifest=_make_manifest(),
        facts_pack=_facts_without_consensus(),
        sections=_make_sections(),
        department="equity_research",
        ticker="MCAP",
        generated_at=_NOW,
    )
    cover = report.cover
    assert cover.consensus_rating is None
    assert cover.consensus_target_mean is None
    assert cover.consensus_upside_pct is None
    assert cover.consensus_source_ids == []


def test_cover_consensus_partial_only_rating_present() -> None:
    """When only the rating fact resolves (no target/upside), the cover
    still emits the rating with citations and leaves numeric fields as
    None. The renderer's graceful-absence path handles this."""
    facts = FactsPack(
        facts={
            "company_name": Fact(
                name="company_name",
                value="Partial Corp.",
                source_ids=[1],
                extractor="deterministic",
            ),
            "sector": Fact(
                name="sector",
                value="Energy",
                source_ids=[1],
                extractor="deterministic",
            ),
            "analyst_consensus_rating": Fact(
                name="analyst_consensus_rating",
                value="Hold",
                source_ids=[1],
                extractor="deterministic",
            ),
        }
    )
    report = assemble_report(
        manifest=_make_manifest(),
        facts_pack=facts,
        sections=_make_sections(),
        department="equity_research",
        ticker="PART",
        generated_at=_NOW,
    )
    cover = report.cover
    assert cover.consensus_rating == "Hold"
    assert cover.consensus_target_mean is None
    assert cover.consensus_upside_pct is None
    assert cover.consensus_source_ids == ["c1"]
