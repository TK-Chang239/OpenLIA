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
