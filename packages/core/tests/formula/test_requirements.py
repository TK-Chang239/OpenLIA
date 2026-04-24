from __future__ import annotations

import pytest
from openlia.formula import RequirementRef, extract_requirements


def test_scalar_only_returns_single_ref_with_zero_lag():
    refs = extract_requirements("price > 85")
    assert refs == [RequirementRef(name="price", max_lag=0)]


def test_multiple_scalars_are_sorted_unique():
    refs = extract_requirements("ma50 > ma200 and ma200 > 0")
    assert refs == [
        RequirementRef(name="ma200", max_lag=0),
        RequirementRef(name="ma50", max_lag=0),
    ]


def test_historical_var_records_max_lag():
    refs = extract_requirements("price[t-5] + price[t-1]")
    assert refs == [RequirementRef(name="price", max_lag=5)]


def test_rolling_mean_records_lookback_minus_one():
    # rolling_mean(price, 20) needs the last 20 values -> max_lag == 19.
    refs = extract_requirements("rolling_mean(price, 20)")
    assert refs == [RequirementRef(name="price", max_lag=19)]


def test_pct_change_records_lookback():
    # pct_change(price, 5) needs entries at lag 0 and lag 5 -> max_lag == 5.
    refs = extract_requirements("pct_change(price, 5)")
    assert refs == [RequirementRef(name="price", max_lag=5)]


def test_lag_records_lookback():
    refs = extract_requirements("lag(cpi, 12)")
    assert refs == [RequirementRef(name="cpi", max_lag=12)]


def test_last_single_arg_zero_lag():
    refs = extract_requirements("last(price)")
    assert refs == [RequirementRef(name="price", max_lag=0)]


def test_last_n_arg_records_lookback_minus_one():
    refs = extract_requirements("last(price, 12)")
    assert refs == [RequirementRef(name="price", max_lag=11)]


def test_maximum_lag_wins_across_references():
    refs = extract_requirements("price[t-3] + rolling_mean(price, 20)")
    assert refs == [RequirementRef(name="price", max_lag=19)]


def test_function_only_references_are_counted():
    refs = extract_requirements("mean(1, 2, 3)")
    assert refs == []


def test_parse_error_propagates():
    from openlia.formula import FormulaError

    with pytest.raises(FormulaError):
        extract_requirements("1 + ")
