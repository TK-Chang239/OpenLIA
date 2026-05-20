"""Tests for `facts.helpers.distressed`."""

from __future__ import annotations

from datetime import date

import pytest
from openlia.llm.runtime.report_v2.facts.helpers.distressed import (
    debt_maturity_wall,
    recovery_waterfall,
)


def test_debt_maturity_wall_aggregates_per_year() -> None:
    out = debt_maturity_wall(
        [
            {"amount": 100.0, "maturity_date": "2027-06-30", "coupon": 0.05},
            {"amount": 200.0, "maturity_date": date(2027, 12, 1), "coupon": 0.06},
            {"amount": 50.0, "maturity_date": "2028-01-15", "coupon": 0.04},
        ]
    )
    assert out["by_year"][2027] == 300.0
    assert out["by_year"][2028] == 50.0
    assert out["total_principal"] == 350.0
    assert out["rows"][0]["year"] == 2027


def test_debt_maturity_wall_unparseable_date_raises() -> None:
    with pytest.raises(ValueError):
        debt_maturity_wall([{"amount": 100.0, "maturity_date": "soon", "coupon": 0.05}])


def test_recovery_waterfall_typical() -> None:
    out = recovery_waterfall(
        pre_petition_capital_structure=[
            {"class": "secured", "claim_amount": 1000.0, "seniority_rank": 1},
            {"class": "unsecured", "claim_amount": 500.0, "seniority_rank": 2},
            {"class": "equity", "claim_amount": 200.0, "seniority_rank": 3},
        ],
        plan_of_reorganization_recoveries=[
            {"class": "secured", "recovery_amount": 950.0, "form": "cash"},
            {"class": "unsecured", "recovery_amount": 100.0, "form": "new_equity"},
            {"class": "equity", "recovery_amount": 6.0, "form": "warrants"},
        ],
    )
    rows = {r["class"]: r for r in out["rows"]}
    assert rows["secured"]["recovery_pct"] == pytest.approx(0.95)
    assert rows["equity"]["recovery_pct"] == pytest.approx(0.03)
    assert out["total_claims"] == 1700.0
    assert out["total_recovery"] == 1056.0
    assert out["blended_recovery_pct"] == pytest.approx(1056.0 / 1700.0)


def test_recovery_waterfall_missing_recovery_is_zero() -> None:
    out = recovery_waterfall(
        pre_petition_capital_structure=[{"class": "x", "claim_amount": 100.0, "seniority_rank": 1}],
        plan_of_reorganization_recoveries=[],
    )
    assert out["rows"][0]["recovery_amount"] == 0.0
    assert out["rows"][0]["recovery_pct"] == 0.0
