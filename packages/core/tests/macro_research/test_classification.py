import pytest

from openlia.macro_research.quant.classification import (
    DebtCycleInputs,
    DebtCycleClassification,
    classify_debt_cycle,
)


def test_two_red_indicators_yields_deleveraging():
    out = classify_debt_cycle(
        DebtCycleInputs(debt_gdp=125.2, interest_revenue=20.1, tips_real_yield=1.94, dxy=104.0)
    )
    assert isinstance(out, DebtCycleClassification)
    assert out.indicator_statuses["debt_gdp"] == "red"
    assert out.indicator_statuses["interest_revenue"] == "red"
    assert out.phase == "Deleveraging"
    assert out.severity == "red"


def test_all_green_yields_expansion():
    out = classify_debt_cycle(
        DebtCycleInputs(debt_gdp=80.0, interest_revenue=8.0, tips_real_yield=2.0, dxy=105.0)
    )
    assert out.phase == "Expansion"
    assert out.severity == "green"


def test_low_tips_yield_flags_amber():
    out = classify_debt_cycle(
        DebtCycleInputs(debt_gdp=80.0, interest_revenue=8.0, tips_real_yield=0.2, dxy=105.0)
    )
    assert out.indicator_statuses["tips_yield"] == "amber"


def test_threshold_boundaries():
    # At the warn boundary: debt_gdp=100 → amber, interest_revenue=15 → amber.
    out = classify_debt_cycle(
        DebtCycleInputs(debt_gdp=100.0, interest_revenue=15.0, tips_real_yield=2.0, dxy=105.0)
    )
    assert out.indicator_statuses["debt_gdp"] == "amber"
    assert out.indicator_statuses["interest_revenue"] == "amber"

    # At the critical boundary: debt_gdp=120 → red, interest_revenue=20 → red.
    out2 = classify_debt_cycle(
        DebtCycleInputs(debt_gdp=120.0, interest_revenue=20.0, tips_real_yield=2.0, dxy=105.0)
    )
    assert out2.indicator_statuses["debt_gdp"] == "red"
    assert out2.indicator_statuses["interest_revenue"] == "red"


def test_late_plateau_one_red_one_amber():
    out = classify_debt_cycle(
        DebtCycleInputs(debt_gdp=125.0, interest_revenue=16.0, tips_real_yield=2.0, dxy=105.0)
    )
    assert out.phase == "Late Plateau"
    assert out.severity == "red"


def test_plateau_two_amber():
    out = classify_debt_cycle(
        DebtCycleInputs(debt_gdp=110.0, interest_revenue=16.0, tips_real_yield=2.0, dxy=105.0)
    )
    assert out.phase == "Plateau"
    assert out.severity == "amber"


def test_lone_red_falls_through_to_expansion():
    # Documents current ported behavior: a single red indicator with no amber falls through
    # to Expansion because no phase rule matches (red==1, amber==0).
    out = classify_debt_cycle(
        DebtCycleInputs(debt_gdp=125.0, interest_revenue=5.0, tips_real_yield=2.0, dxy=105.0)
    )
    assert out.phase == "Expansion"


def test_monetary_space_values():
    out = classify_debt_cycle(
        DebtCycleInputs(debt_gdp=125.0, interest_revenue=20.1, tips_real_yield=1.94, dxy=104.0)
    )
    assert out.monetary_space["rate_cut_headroom"] == pytest.approx(3.06)
    assert out.monetary_space["qe_credibility"] == "amber"
    assert out.monetary_space["currency_debasement_risk"] == "green"
