"""Unit tests for the deterministic derivation library.

The library exists so writers cannot type naked arithmetic. Each function
takes BundleFacts, runs pure math, and emits a new BundleFact with a
ComputedSource derived_from chain the bundle validator will walk.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from openlia.llm.runtime.report_v2_3.derivations import (
    DerivationError,
    growth_rate,
    ratio,
    yoy_delta,
)
from openlia.llm.runtime.report_v2_3.schemas import (
    BundleFact,
    ComputedSource,
    DataProviderSource,
)


def _src() -> DataProviderSource:
    return DataProviderSource(
        provider="EODHD",
        endpoint="fundamentals/income_statement",
        period="FY2025",
        retrieved_at=datetime.now(UTC),
    )


def test_growth_rate_computes_pct_change_and_attaches_provenance():
    cur = BundleFact(id="rev_fy25", label="Revenue FY25", value=125.0, source=_src())
    prev = BundleFact(id="rev_fy24", label="Revenue FY24", value=100.0, source=_src())

    out = growth_rate(cur, prev, new_id="rev_growth_yoy", label="Revenue YoY")

    assert isinstance(out, BundleFact)
    assert out.id == "rev_growth_yoy"
    assert out.value == pytest.approx(0.25)
    assert out.unit == "percent"
    assert isinstance(out.source, ComputedSource)
    assert out.source.method == "growth_rate"
    assert out.source.derived_from == ["rev_fy25", "rev_fy24"]


def test_yoy_delta_emits_absolute_difference():
    cur = BundleFact(
        id="op_inc_fy25", label="Op income FY25", value=42.0, unit="usd_millions", source=_src()
    )
    prev = BundleFact(
        id="op_inc_fy24", label="Op income FY24", value=30.0, unit="usd_millions", source=_src()
    )

    out = yoy_delta(cur, prev, new_id="op_inc_yoy", label="Op income YoY")

    assert out.value == pytest.approx(12.0)
    assert out.unit == "usd_millions"
    assert out.source.method == "yoy_delta"
    assert out.source.derived_from == ["op_inc_fy25", "op_inc_fy24"]


def test_ratio_emits_numerator_over_denominator():
    num = BundleFact(id="gross_profit", label="Gross profit", value=60.0, source=_src())
    den = BundleFact(id="rev_ttm", label="Revenue TTM", value=100.0, source=_src())

    out = ratio(num, den, new_id="gross_margin", label="Gross margin")

    assert out.value == pytest.approx(0.60)
    assert out.source.method == "ratio"
    assert out.source.derived_from == ["gross_profit", "rev_ttm"]


def test_growth_rate_raises_on_zero_denominator():
    cur = BundleFact(id="x", label="x", value=10.0, source=_src())
    prev = BundleFact(id="y", label="y", value=0.0, source=_src())
    with pytest.raises(DerivationError):
        growth_rate(cur, prev, new_id="z", label="z")


def test_growth_rate_raises_on_non_numeric_input():
    cur = BundleFact(id="x", label="x", value="some_string", source=_src())
    prev = BundleFact(id="y", label="y", value=100.0, source=_src())
    with pytest.raises(DerivationError):
        growth_rate(cur, prev, new_id="z", label="z")


def test_ratio_raises_on_zero_denominator():
    num = BundleFact(id="x", label="x", value=10.0, source=_src())
    den = BundleFact(id="y", label="y", value=0.0, source=_src())
    with pytest.raises(DerivationError):
        ratio(num, den, new_id="z", label="z")
