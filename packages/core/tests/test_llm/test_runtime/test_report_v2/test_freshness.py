"""Tests for the per-fact freshness budgets (WS10-B)."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from openlia.llm.runtime.report_v2.freshness import (
    FRESHNESS_BUDGETS,
    FreshnessViolation,
    StaleDataError,
    check_freshness,
    oldest_data_as_of,
)
from openlia.llm.runtime.report_v2.types import Fact, ManifestEntry


def _fact(name: str, *, data_as_of) -> Fact:
    return Fact(
        name=name,
        value=1.0,
        source_ids=[1],
        extractor="deterministic",
        data_as_of=data_as_of,
    )


def test_recent_facts_pass() -> None:
    now = datetime(2026, 5, 20, tzinfo=UTC)
    facts = {
        "current_price": _fact("current_price", data_as_of="2026-05-19"),
        "revenue_annual": _fact("revenue_annual", data_as_of="2025-12-31"),
        "analyst_consensus_rating": _fact(
            "analyst_consensus_rating", data_as_of="2026-05-15T00:00:00Z"
        ),
    }
    violations = check_freshness(facts, as_of=now)
    assert violations == []


def test_stale_current_price_hard_blocks() -> None:
    now = datetime(2026, 5, 20, tzinfo=UTC)
    facts = {"current_price": _fact("current_price", data_as_of="2026-05-01")}
    violations = check_freshness(facts, as_of=now)
    assert len(violations) == 1
    v = violations[0]
    assert v.fact_name == "current_price"
    assert v.severity == "hard_block"
    assert v.budget_days == 7
    assert v.age_days is not None and v.age_days > 7


def test_stale_revenue_annual_hard_blocks() -> None:
    now = datetime(2026, 5, 20, tzinfo=UTC)
    # 2024-12-31 is more than 380 days before 2026-05-20.
    facts = {"revenue_annual": _fact("revenue_annual", data_as_of="2024-12-31")}
    violations = check_freshness(facts, as_of=now)
    assert len(violations) == 1
    v = violations[0]
    assert v.fact_name == "revenue_annual"
    assert v.severity == "hard_block"
    assert v.budget_days == 380


def test_missing_data_as_of_reported_as_missing_not_block() -> None:
    now = datetime(2026, 5, 20, tzinfo=UTC)
    facts = {"current_price": _fact("current_price", data_as_of=None)}
    violations = check_freshness(facts, as_of=now)
    assert len(violations) == 1
    v = violations[0]
    assert v.severity == "missing"
    assert v.age_days is None


def test_override_flag_bypasses_hard_block() -> None:
    """The override is enforced by the runner, but verify the exception
    carries the structured violation list as `.violations`."""
    now = datetime(2026, 5, 20, tzinfo=UTC)
    facts = {"current_price": _fact("current_price", data_as_of="2026-05-01")}
    violations = check_freshness(facts, as_of=now)
    hard = [v for v in violations if v.severity == "hard_block"]
    assert hard
    err = StaleDataError(hard)
    assert err.violations == hard
    assert "current_price" in str(err)


def test_unbudgeted_fact_skipped() -> None:
    now = datetime(2026, 5, 20, tzinfo=UTC)
    facts = {"sector": _fact("sector", data_as_of="2020-01-01")}
    # `sector` is not in FRESHNESS_BUDGETS; it should be skipped, not flagged.
    violations = check_freshness(facts, as_of=now)
    assert violations == []


def test_consensus_prefix_matches_14d_budget() -> None:
    now = datetime(2026, 5, 20, tzinfo=UTC)
    # `consensus_upside_pct` matches the `consensus_` prefix bucket (14d).
    facts = {"consensus_upside_pct": _fact("consensus_upside_pct", data_as_of="2026-05-01")}
    violations = check_freshness(facts, as_of=now)
    assert len(violations) == 1
    assert violations[0].budget_days == 14


def test_analyst_prefix_matches_30d_budget() -> None:
    now = datetime(2026, 5, 20, tzinfo=UTC)
    facts = {
        "analyst_target_mean": _fact("analyst_target_mean", data_as_of="2026-04-01"),
    }
    violations = check_freshness(facts, as_of=now)
    assert len(violations) == 1
    assert violations[0].budget_days == 30
    assert violations[0].severity == "hard_block"


def test_oldest_data_as_of_returns_earliest() -> None:
    facts = {
        "a": _fact("a", data_as_of="2026-05-19"),
        "b": _fact("b", data_as_of="2024-12-31"),
        "c": _fact("c", data_as_of="2025-06-15"),
    }
    assert oldest_data_as_of(facts) == "2024-12-31"


def test_oldest_data_as_of_skips_missing() -> None:
    facts = {
        "a": _fact("a", data_as_of=None),
        "b": _fact("b", data_as_of="2025-06-15"),
    }
    assert oldest_data_as_of(facts) == "2025-06-15"


def test_oldest_data_as_of_all_missing_returns_none() -> None:
    facts = {"a": _fact("a", data_as_of=None)}
    assert oldest_data_as_of(facts) is None


def test_freshness_budgets_contain_required_buckets() -> None:
    """Lock the plan's WS10-B budget table into the source-of-truth dict."""
    assert FRESHNESS_BUDGETS["current_price"] == 7
    assert FRESHNESS_BUDGETS["pe_ratio_ttm"] == 7
    assert FRESHNESS_BUDGETS["market_cap"] == 7
    assert FRESHNESS_BUDGETS["consensus_"] == 14
    assert FRESHNESS_BUDGETS["analyst_"] == 30
    assert FRESHNESS_BUDGETS["revenue_annual"] == 380
    assert FRESHNESS_BUDGETS["eps_annual"] == 380


# ---------------------------------------------------------------------------
# Fact model — round-trip and defaults for the new fields.
# ---------------------------------------------------------------------------


def test_fact_new_fields_default_sanely() -> None:
    f = Fact(name="x", value=1, source_ids=[1], extractor="deterministic")
    assert f.data_as_of is None
    assert f.source_tier == "vendor"


def test_fact_round_trip_through_pydantic() -> None:
    f = Fact(
        name="revenue_annual",
        value=[1, 2, 3],
        source_ids=[1],
        extractor="deterministic",
        data_as_of="2024-12-31",
        source_tier="vendor",
    )
    dumped = f.model_dump()
    reloaded = Fact.model_validate(dumped)
    assert reloaded.data_as_of == "2024-12-31"
    assert reloaded.source_tier == "vendor"


def test_fact_accepts_datetime_data_as_of() -> None:
    when = datetime(2026, 5, 19, tzinfo=UTC)
    f = Fact(
        name="market_cap",
        value=1.0,
        source_ids=[1],
        extractor="deterministic",
        data_as_of=when,
        source_tier="vendor",
    )
    assert f.data_as_of == when


def test_fact_source_tier_primary_filing_accepted() -> None:
    f = Fact(
        name="revenue_annual",
        value=1.0,
        source_ids=[1],
        extractor="deterministic",
        source_tier="primary_filing",
    )
    assert f.source_tier == "primary_filing"


# ---------------------------------------------------------------------------
# Extractor smoke — given a fundamentals payload, `revenue_annual` carries
# a data_as_of derived from the latest yearly key.
# ---------------------------------------------------------------------------

FIXTURE = (
    Path(__file__).parent.parent.parent.parent
    / "fixtures"
    / "report_v2"
    / "eodhd_fundamentals_net.json"
)


@pytest.fixture
def fundamentals_manifest() -> list[ManifestEntry]:
    payload = json.loads(FIXTURE.read_text())
    return [
        ManifestEntry(
            id=1,
            kind="fetch",
            provider="eodhd",
            identifier="get_fundamentals_data/NET.US",
            raw_payload=payload,
            retrieved_at="2026-05-17T20:00:00Z",
        )
    ]


def test_extractor_populates_data_as_of_from_yearly_key(
    fundamentals_manifest: list[ManifestEntry],
) -> None:
    """`revenue_annual` data_as_of should be the latest yearly key (2024-12-31
    in the NET fixture). This validates the WS10-A plumbing end-to-end for
    annual facts."""
    from openlia.llm.runtime.report_v2.facts.extractors import stock_initiation  # noqa: F401
    from openlia.llm.runtime.report_v2.facts.pack import compile_pack
    from openlia.llm.runtime.report_v2.facts.registry import default_registry

    pack = compile_pack(
        registry=default_registry,
        manifest=fundamentals_manifest,
        requested_facts=["revenue_annual"],
    )
    fact = pack.get("revenue_annual")
    assert fact.data_as_of == "2024-12-31"
    assert fact.source_tier == "vendor"


def test_extractor_highlights_fact_uses_retrieved_at(
    fundamentals_manifest: list[ManifestEntry],
) -> None:
    """`market_cap` is sourced from `Highlights`, which lacks any filing date,
    so the extractor falls back to the ManifestEntry's `retrieved_at`."""
    from openlia.llm.runtime.report_v2.facts.extractors import stock_initiation  # noqa: F401
    from openlia.llm.runtime.report_v2.facts.pack import compile_pack
    from openlia.llm.runtime.report_v2.facts.registry import default_registry

    pack = compile_pack(
        registry=default_registry,
        manifest=fundamentals_manifest,
        requested_facts=["market_cap"],
    )
    fact = pack.get("market_cap")
    assert fact.data_as_of == "2026-05-17T20:00:00Z"
    assert fact.source_tier == "vendor"


def test_check_freshness_against_extracted_facts(
    fundamentals_manifest: list[ManifestEntry],
) -> None:
    """Smoke: fixture-extracted facts behave correctly under the gate.

    `market_cap` was retrieved 2026-05-17; as of 2026-05-20 it is 3 days
    old (< 7d budget). `revenue_annual` has data_as_of=2024-12-31; against
    a 2026-05-20 evaluation date that exceeds the 380d budget."""
    from openlia.llm.runtime.report_v2.facts.extractors import stock_initiation  # noqa: F401
    from openlia.llm.runtime.report_v2.facts.pack import compile_pack
    from openlia.llm.runtime.report_v2.facts.registry import default_registry

    pack = compile_pack(
        registry=default_registry,
        manifest=fundamentals_manifest,
        requested_facts=["market_cap", "revenue_annual"],
    )
    now = datetime(2026, 5, 20, tzinfo=UTC)
    violations = {v.fact_name: v for v in check_freshness(pack.facts, as_of=now)}
    assert "market_cap" not in violations  # fresh
    assert violations["revenue_annual"].severity == "hard_block"


def test_freshness_violation_is_dataclass_with_expected_fields() -> None:
    """Lock the FreshnessViolation public surface."""
    now = datetime(2026, 5, 20, tzinfo=UTC)
    facts = {"current_price": _fact("current_price", data_as_of=now - timedelta(days=10))}
    violations = check_freshness(facts, as_of=now)
    assert len(violations) == 1
    v = violations[0]
    assert isinstance(v, FreshnessViolation)
    assert v.fact_name == "current_price"
    assert v.age_days == 10
    assert v.budget_days == 7
    assert v.severity == "hard_block"
