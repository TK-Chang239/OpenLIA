from __future__ import annotations

import pytest
from openlia.llm.runtime.report_v2.types import (
    Fact,
    ManifestEntry,
    SectionResult,
    SectionTerminalState,
)
from pydantic import ValidationError


def test_manifest_entry_minimum() -> None:
    entry = ManifestEntry(
        id=1,
        kind="fetch",
        provider="eodhd",
        identifier="get_fundamentals_data/NET.US",
        raw_payload={"Highlights": {"MarketCapitalization": 30_200_000_000}},
        retrieved_at="2026-05-17T20:00:00Z",
    )
    assert entry.id == 1
    assert entry.provider == "eodhd"


def test_fact_default_provenance_empty_list_rejected() -> None:
    """Facts must carry at least one source_id — empty provenance is a bug."""
    with pytest.raises(ValidationError):
        Fact(
            name="current_price",
            value=89.43,
            source_ids=[],
            extractor="deterministic",
            depends_on=[],
        )


def test_fact_with_union_provenance_from_compute() -> None:
    fact = Fact(
        name="revenue_cagr_3y",
        value=0.234,
        source_ids=[7, 8, 9],
        extractor="compute",
        depends_on=["revenue_annual"],
    )
    assert fact.source_ids == [7, 8, 9]


def test_section_result_terminal_states() -> None:
    assert SectionTerminalState.SUCCESS.value == "success"
    assert SectionTerminalState.DEGRADED.value == "degraded"
    assert SectionTerminalState.EXHAUSTED.value == "exhausted"


def test_section_result_records_attempts() -> None:
    result = SectionResult(
        section_id="industry_overview",
        state=SectionTerminalState.DEGRADED,
        attempts=2,
        markdown="---\n...",
        failed_attempts=["first try output", "second try output"],
        validation_errors=["word_count: 412 < 600", "uncited_number: 28%"],
    )
    assert result.attempts == 2
    assert len(result.failed_attempts) == 2


def test_section_result_markdown_validation_degraded_empty_rejected() -> None:
    """Markdown required for degraded state."""
    with pytest.raises(ValidationError):
        SectionResult(
            section_id="overview",
            state=SectionTerminalState.DEGRADED,
            attempts=1,
            markdown="",
        )


def test_section_result_markdown_validation_exhausted_accepts_none() -> None:
    """Exhausted state allows None markdown."""
    result = SectionResult(
        section_id="overview",
        state=SectionTerminalState.EXHAUSTED,
        attempts=3,
        markdown=None,
    )
    assert result.markdown is None
