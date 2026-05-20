"""Tests for `facts.helpers.working_capital`."""

from __future__ import annotations

import pytest
from openlia.llm.runtime.report_v2.facts.helpers.working_capital import cycle_days


def test_cycle_days_typical() -> None:
    out = cycle_days(receivables=100.0, inventory=50.0, payables=30.0, revenue=365.0, cogs=365.0)
    # DSO = (100/365)*365 = 100; DIO = (50/365)*365 = 50; DPO = 30; CCC = 100+50-30 = 120
    assert out["dso"] == pytest.approx(100.0)
    assert out["dio"] == pytest.approx(50.0)
    assert out["dpo"] == pytest.approx(30.0)
    assert out["ccc"] == pytest.approx(120.0)


def test_cycle_days_zero_revenue_raises() -> None:
    with pytest.raises(ValueError):
        cycle_days(receivables=100.0, inventory=50.0, payables=30.0, revenue=0.0, cogs=365.0)


def test_cycle_days_zero_cogs_raises() -> None:
    with pytest.raises(ValueError):
        cycle_days(receivables=100.0, inventory=50.0, payables=30.0, revenue=365.0, cogs=0.0)
