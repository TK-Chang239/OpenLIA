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


# ---------------------------------------------------------------------------
# Lever 1: silent dedup on identical provenance.
#
# The mint module's header docstring promises that when a marker's
# `new_id` collides with an existing bundle fact and the existing fact
# was minted by an identical call, we reuse it instead of raising. The
# implementation only had within-section seen_markers dedup; the bundle
# case raised unconditionally. These tests cover the rescue path that
# unblocks the "two writers derive the same growth_rate" failure mode.
# ---------------------------------------------------------------------------


def _bundle_with_pre_minted_growth() -> ResearchBundle:
    """Bundle where some upstream stage (RESEARCH, COMPUTE, or an earlier
    WRITE mandate) already minted rev_growth_yoy from rev_fy25 / rev_fy24.
    The writer's natural choice of new_id will collide with this."""
    return ResearchBundle(
        tickers=["NVDA"],
        facts={
            "rev_fy25": BundleFact(id="rev_fy25", label="Revenue FY25", value=125.0, source=_src()),
            "rev_fy24": BundleFact(id="rev_fy24", label="Revenue FY24", value=100.0, source=_src()),
            "rev_growth_yoy": BundleFact(
                id="rev_growth_yoy",
                label="Rev Growth Yoy",
                value=0.25,
                unit="percent",
                source=ComputedSource(
                    method="growth_rate",
                    derived_from=["rev_fy25", "rev_fy24"],
                ),
            ),
        },
    )


def test_derive_marker_reuses_existing_when_identical_provenance():
    """When the new_id matches an existing ComputedSource fact with the
    same method + same derived_from, the mint step reuses the existing
    fact and emits a CITE marker — no MintError, no duplicate insert."""
    bundle = _bundle_with_pre_minted_growth()
    body = "Revenue grew {{DERIVE:growth_rate|rev_fy25,rev_fy24|rev_growth_yoy}} YoY."

    new_body, new_facts = mint_inline_facts(body, bundle, _mandate())

    assert new_body == "Revenue grew {{CITE:rev_growth_yoy}} YoY."
    # The existing fact stays; the mint step does NOT enqueue a duplicate
    # for state.bundle.add — that would trip ResearchBundle's
    # duplicate-id guard in WriteStage's bundle-rebuild step.
    assert new_facts == []


def test_derive_marker_raises_when_id_collides_with_different_method():
    """Same id, ComputedSource, but the method differs — the existing
    fact would not produce the same number as the writer's call. Must
    raise so we don't silently swap one value for another."""
    bundle = _bundle_with_pre_minted_growth()
    # Existing rev_growth_yoy is method='growth_rate'; this DERIVE
    # requests yoy_delta (absolute change, not a ratio).
    body = "X {{DERIVE:yoy_delta|rev_fy25,rev_fy24|rev_growth_yoy}}"

    with pytest.raises(MintError) as exc:
        mint_inline_facts(body, bundle, _mandate())

    msg = str(exc.value)
    assert "rev_growth_yoy" in msg
    # The error should give the writer enough to fix on its own — name
    # the conflicting method so a future repair tier (Lever 3) has
    # actionable signal, not just "collides."
    assert "yoy_delta" in msg or "growth_rate" in msg


def test_derive_marker_raises_when_id_collides_with_different_inputs():
    """Same id, same method, but the derived_from inputs differ — must
    raise. Reusing here would silently swap the writer's intended math
    (e.g. FY25 vs FY24 growth) for whatever upstream computed."""
    bundle = _bundle_with_pre_minted_growth()
    # Add a new fact rev_fy23 so the inputs vary plausibly:
    bundle.facts["rev_fy23"] = BundleFact(
        id="rev_fy23", label="Revenue FY23", value=80.0, source=_src()
    )
    # Existing rev_growth_yoy is derived_from=[rev_fy25, rev_fy24];
    # this call asks for derived_from=[rev_fy24, rev_fy23].
    mandate = SectionMandate(
        section_id="financials",
        covers="financial line items",
        does_not_cover="overview",
        chart_ids=[],
        relevant_fact_ids=["rev_fy25", "rev_fy24", "rev_fy23"],
    )
    body = "X {{DERIVE:growth_rate|rev_fy24,rev_fy23|rev_growth_yoy}}"

    with pytest.raises(MintError) as exc:
        mint_inline_facts(body, bundle, mandate)
    assert "rev_growth_yoy" in str(exc.value)


def test_derive_marker_raises_when_id_collides_with_non_computed_source():
    """Same id, but the existing fact came from a DataProviderSource (or
    any non-ComputedSource origin). The writer's DERIVE call cannot
    plausibly produce an identical fact — must raise. This is the
    `rev_fy25` case from the earlier test, now stated as the
    collision-with-different-content branch."""
    bundle = _bundle()  # rev_fy25 has DataProviderSource
    body = "X {{DERIVE:growth_rate|rev_fy24,rev_fy24|rev_fy25}}"
    with pytest.raises(MintError) as exc:
        mint_inline_facts(body, bundle, _mandate())
    msg = str(exc.value)
    assert "rev_fy25" in msg


def test_estimate_marker_reuses_existing_when_identical_basis_value_unit():
    """ESTIMATE mirror of the DERIVE dedup. When the new_id matches an
    existing EstimateSource fact with the same value + unit + basis,
    reuse — same docstring contract as DERIVE dedup."""
    bundle = _bundle()
    bundle.facts["upside_pct"] = BundleFact(
        id="upside_pct",
        label="Upside Pct",
        value=0.10,
        unit="percent",
        source=EstimateSource(
            basis="projection from margin-expansion thesis",
            derived_from=[],
            stage="synthesize",
        ),
    )
    body = (
        "We see {{ESTIMATE:upside_pct|0.10|percent|projection from "
        "margin-expansion thesis}} of upside."
    )

    new_body, new_facts = mint_inline_facts(body, bundle, _mandate())

    assert "{{CITE:upside_pct}}" in new_body
    assert new_facts == []


def test_estimate_marker_raises_when_id_collides_with_different_value():
    """ESTIMATE collision with a different value MUST raise — silently
    keeping the old value would change the writer's number under their
    feet."""
    bundle = _bundle()
    bundle.facts["upside_pct"] = BundleFact(
        id="upside_pct",
        label="Upside Pct",
        value=0.10,
        unit="percent",
        source=EstimateSource(basis="x", derived_from=[], stage="synthesize"),
    )
    body = "{{ESTIMATE:upside_pct|0.25|percent|different basis}}"
    with pytest.raises(MintError) as exc:
        mint_inline_facts(body, bundle, _mandate())
    assert "upside_pct" in str(exc.value)


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
