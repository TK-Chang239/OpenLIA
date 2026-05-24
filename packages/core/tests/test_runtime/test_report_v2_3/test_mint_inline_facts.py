"""Unit tests for the mint step that resolves DERIVE/ESTIMATE markers."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from openlia.llm.runtime.report_v2_3.schemas import (
    BundleFact,
    ComputedSource,
    DataProviderSource,
    EstimateSource,
    ResearchBundle,
    SectionMandate,
)
from openlia.llm.runtime.report_v2_3.stages._mint import MintError, mint_inline_facts


def _src() -> DataProviderSource:
    return DataProviderSource(
        provider="EODHD",
        endpoint="fundamentals/income_statement",
        period="FY2025",
        retrieved_at=datetime.now(UTC),
    )


def _bundle() -> ResearchBundle:
    return ResearchBundle(
        tickers=["NVDA"],
        facts={
            "rev_fy25": BundleFact(id="rev_fy25", label="Revenue FY25", value=125.0, source=_src()),
            "rev_fy24": BundleFact(id="rev_fy24", label="Revenue FY24", value=100.0, source=_src()),
        },
    )


def _mandate(section_id: str = "financials") -> SectionMandate:
    return SectionMandate(
        section_id=section_id,
        covers="financial line items",
        does_not_cover="overview",
        chart_ids=[],
        relevant_fact_ids=["rev_fy25", "rev_fy24"],
    )


def test_derive_marker_resolves_to_computed_fact_and_cite_marker():
    bundle = _bundle()
    body = "Revenue grew {{DERIVE:growth_rate|rev_fy25,rev_fy24|rev_growth_yoy}} YoY."

    new_body, new_facts = mint_inline_facts(body, bundle, _mandate())

    assert new_body == "Revenue grew {{CITE:rev_growth_yoy}} YoY."
    assert len(new_facts) == 1
    fact = new_facts[0]
    assert fact.id == "rev_growth_yoy"
    assert fact.value == pytest.approx(0.25)
    assert isinstance(fact.source, ComputedSource)
    assert fact.source.derived_from == ["rev_fy25", "rev_fy24"]


def test_estimate_marker_resolves_to_estimate_fact_and_cite_marker():
    bundle = _bundle()
    body = (
        "We see {{ESTIMATE:upside_pct|0.10|percent|projection from margin-expansion thesis}} "
        "of upside."
    )

    new_body, new_facts = mint_inline_facts(body, bundle, _mandate())

    assert new_body == "We see {{CITE:upside_pct}} of upside."
    assert len(new_facts) == 1
    fact = new_facts[0]
    assert fact.id == "upside_pct"
    assert fact.value == pytest.approx(0.10)
    assert fact.unit == "percent"
    assert isinstance(fact.source, EstimateSource)
    assert fact.source.basis == "projection from margin-expansion thesis"
    assert fact.source.stage == "write"


def test_repeated_identical_derive_dedupes_to_single_new_fact():
    bundle = _bundle()
    body = (
        "{{DERIVE:growth_rate|rev_fy25,rev_fy24|rev_growth_yoy}} versus "
        "{{DERIVE:growth_rate|rev_fy25,rev_fy24|rev_growth_yoy}} prior."
    )

    new_body, new_facts = mint_inline_facts(body, bundle, _mandate())

    assert new_body.count("{{CITE:rev_growth_yoy}}") == 2
    assert len(new_facts) == 1


def test_derive_marker_with_unknown_input_fact_raises_mint_error():
    bundle = _bundle()
    body = "X {{DERIVE:growth_rate|rev_fy25,rev_fy23|x}}"
    with pytest.raises(MintError) as exc:
        mint_inline_facts(body, bundle, _mandate())
    assert "rev_fy23" in str(exc.value)


def test_derive_marker_with_unknown_method_raises_mint_error():
    bundle = _bundle()
    body = "X {{DERIVE:nonexistent_method|rev_fy25,rev_fy24|x}}"
    with pytest.raises(MintError) as exc:
        mint_inline_facts(body, bundle, _mandate())
    assert "nonexistent_method" in str(exc.value)


def test_derive_marker_with_id_colliding_against_bundle_raises():
    bundle = _bundle()
    body = "X {{DERIVE:growth_rate|rev_fy25,rev_fy24|rev_fy25}}"
    with pytest.raises(MintError) as exc:
        mint_inline_facts(body, bundle, _mandate())
    assert "rev_fy25" in str(exc.value)


def test_mint_step_passes_through_body_with_no_markers_untouched():
    bundle = _bundle()
    body = "No markers here. Revenue {{CITE:rev_fy25}} stayed flat."
    new_body, new_facts = mint_inline_facts(body, bundle, _mandate())
    assert new_body == body
    assert new_facts == []


def test_mixed_derive_and_estimate_both_resolve():
    """The two-pass walk over DERIVE then ESTIMATE must handle both
    marker types in one body. This is the primary integration path —
    WriteStage will routinely emit a mix."""
    bundle = _bundle()
    body = (
        "Grew {{DERIVE:growth_rate|rev_fy25,rev_fy24|rev_growth_yoy}} "
        "with {{ESTIMATE:target_pe|25.0|x|consensus forward P/E}} target."
    )
    new_body, new_facts = mint_inline_facts(body, bundle, _mandate())
    assert "{{CITE:rev_growth_yoy}}" in new_body
    assert "{{CITE:target_pe}}" in new_body
    assert "{{DERIVE:" not in new_body
    assert "{{ESTIMATE:" not in new_body
    assert len(new_facts) == 2
    ids = {f.id for f in new_facts}
    assert ids == {"rev_growth_yoy", "target_pe"}


def test_cross_marker_id_collision_raises():
    """A DERIVE and an ESTIMATE sharing the same new_id must fail loud,
    not silently reuse the first mint's fact (which would drop the
    second marker's content)."""
    bundle = _bundle()
    body = (
        "{{DERIVE:growth_rate|rev_fy25,rev_fy24|shared_id}} and "
        "{{ESTIMATE:shared_id|0.1|percent|something different}}"
    )
    with pytest.raises(MintError) as exc:
        mint_inline_facts(body, bundle, _mandate())
    assert "shared_id" in str(exc.value)
