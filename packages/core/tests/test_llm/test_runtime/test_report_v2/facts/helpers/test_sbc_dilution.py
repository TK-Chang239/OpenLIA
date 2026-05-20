"""Tests for `facts.helpers.sbc_dilution`."""

from __future__ import annotations

import pytest
from openlia.llm.runtime.report_v2.facts.helpers.sbc_dilution import sbc_dilution_bridge


def test_sbc_dilution_bridge_balances() -> None:
    out = sbc_dilution_bridge(
        beginning_shares=1000.0,
        sbc_issuances=50.0,
        buybacks_in_shares=20.0,
        ending_shares=1030.0,
        revenue_ttm=10_000.0,
        fcf_ttm=2_000.0,
    )
    assert out["computed_ending"] == 1030.0
    assert out["reconciliation_gap"] == 0.0
    assert out["net_dilution_pct"] == pytest.approx(0.03)
    assert out["sbc_pct_revenue"] == pytest.approx(0.005)
    assert out["sbc_pct_fcf"] == pytest.approx(0.025)


def test_sbc_dilution_bridge_reports_gap_when_imbalanced() -> None:
    out = sbc_dilution_bridge(
        beginning_shares=1000.0,
        sbc_issuances=50.0,
        buybacks_in_shares=20.0,
        ending_shares=1050.0,  # 20 share gap (options exercised, secondaries, etc.)
        revenue_ttm=10_000.0,
        fcf_ttm=2_000.0,
    )
    assert out["reconciliation_gap"] == 20.0


def test_sbc_dilution_bridge_zero_fcf_returns_none() -> None:
    out = sbc_dilution_bridge(
        beginning_shares=1000.0,
        sbc_issuances=50.0,
        buybacks_in_shares=0.0,
        ending_shares=1050.0,
        revenue_ttm=10_000.0,
        fcf_ttm=0.0,
    )
    assert out["sbc_pct_fcf"] is None
