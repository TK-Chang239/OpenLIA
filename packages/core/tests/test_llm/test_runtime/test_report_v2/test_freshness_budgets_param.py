"""Tests for the PR 3 lift: freshness budgets become an explicit parameter.

`check_freshness` accepts a `budgets` dict; the runner reads its value from the
active `TemplateSpec.freshness_budgets`. Default behavior is unchanged because
the equity-research template loader populates the same budgets that were
previously hardcoded in `freshness.FRESHNESS_BUDGETS`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from openlia.llm.runtime.report_v2.freshness import check_freshness
from openlia.llm.runtime.report_v2.types import Fact


def _fact(name: str, days_old: int) -> tuple[str, Fact]:
    as_of = datetime.now(UTC) - timedelta(days=days_old)
    return name, Fact(
        name=name,
        value=1.0,
        source_ids=[0],
        extractor="deterministic",
        data_as_of=as_of,
    )


def test_check_freshness_accepts_budgets_parameter() -> None:
    facts = dict([_fact("foo_metric", days_old=200)])

    violations = check_freshness(facts, as_of=datetime.now(UTC), budgets={"foo_metric": 30})

    assert len(violations) == 1
    assert violations[0].fact_name == "foo_metric"
    assert violations[0].severity == "hard_block"


def test_check_freshness_with_empty_budgets_blocks_nothing() -> None:
    facts = dict([_fact("current_price", days_old=400), _fact("revenue_annual", days_old=400)])

    violations = check_freshness(facts, as_of=datetime.now(UTC), budgets={})

    assert violations == []


def test_check_freshness_budgets_default_preserves_legacy_behavior() -> None:
    # When `budgets` is omitted the function still applies the module-level
    # FRESHNESS_BUDGETS so existing callers continue to work unchanged.
    facts = dict([_fact("current_price", days_old=30)])

    violations = check_freshness(facts, as_of=datetime.now(UTC))

    assert len(violations) == 1
    assert violations[0].fact_name == "current_price"


def test_default_template_carries_canonical_freshness_budgets() -> None:
    from openlia.llm.runtime.report_v2.freshness import FRESHNESS_BUDGETS
    from openlia.reports.frameworks.loaders.stock_initiation import (
        load_stock_initiation_template,
    )

    spec = load_stock_initiation_template()

    assert spec.freshness_budgets == FRESHNESS_BUDGETS
