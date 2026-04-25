"""Reserved derived scalars: hand-computed reference values."""

from __future__ import annotations

import math

import pytest
from openlia.formula import (
    RESERVED_NAMES,
    EvaluationContext,
    FormulaEngine,
    FormulaError,
    compute_derived_scalars,
    compute_derived_series,
)


def test_reserved_names_set_complete():
    expected = {
        "price",
        "prev_close",
        "change_pct",
        "ma20",
        "ma50",
        "ma100",
        "ma200",
        "atr_14",
        "std_20",
        "high_52w",
        "low_52w",
        "pct_from_high",
        "pct_from_low",
        "price_vs_ma200",
        "ma50_vs_ma200",
    }
    assert set(RESERVED_NAMES) == expected


def test_empty_series_returns_all_none():
    out = compute_derived_scalars({"price": []})
    for name in RESERVED_NAMES:
        assert out[name] is None


def test_price_is_last_close():
    out = compute_derived_scalars({"price": [10.0, 20.0, 30.0]})
    assert out["price"] == 30.0
    assert out["prev_close"] == 20.0


def test_change_pct_computed():
    out = compute_derived_scalars({"price": [100.0, 110.0]})
    assert out["change_pct"] == pytest.approx(10.0)


def test_ma20_short_history_is_none():
    out = compute_derived_scalars({"price": [10.0] * 19})
    assert out["ma20"] is None


def test_ma20_exact_window():
    closes = [float(i) for i in range(1, 21)]  # 1..20
    out = compute_derived_scalars({"price": closes})
    expected = sum(closes) / 20.0
    assert out["ma20"] == pytest.approx(expected)


def test_ma200_requires_200_bars():
    closes = [100.0] * 199
    out = compute_derived_scalars({"price": closes})
    assert out["ma200"] is None
    closes = [100.0] * 200
    out = compute_derived_scalars({"price": closes})
    assert out["ma200"] == pytest.approx(100.0)


def test_high_52w_under_252_bars():
    out = compute_derived_scalars({"price": [10.0, 20.0, 5.0, 15.0]})
    assert out["high_52w"] == 20.0
    assert out["low_52w"] == 5.0


def test_pct_from_high_negative_when_below():
    out = compute_derived_scalars({"price": [100.0, 80.0]})
    # high = 100, current = 80 -> -20%
    assert out["pct_from_high"] == pytest.approx(-20.0)


def test_atr_14_requires_14_bars():
    out = compute_derived_scalars(
        {
            "price": [100.0] * 13,
            "high": [101.0] * 13,
            "low": [99.0] * 13,
        }
    )
    assert out["atr_14"] is None


def test_atr_14_simple():
    out = compute_derived_scalars(
        {
            "price": [100.0] * 14,
            "high": [101.0] * 14,
            "low": [99.0] * 14,
        }
    )
    # First TR is high-low=2; subsequent TR = max(2, 1, 1) = 2 -> avg = 2
    assert out["atr_14"] == pytest.approx(2.0)


def test_std_20_requires_21_bars():
    out = compute_derived_scalars({"price": [100.0] * 20})
    assert out["std_20"] is None


def test_std_20_zero_for_constant_series():
    out = compute_derived_scalars({"price": [100.0] * 21})
    assert out["std_20"] == pytest.approx(0.0)


def test_price_vs_ma200_ratio():
    closes = [100.0] * 199 + [110.0]
    out = compute_derived_scalars({"price": closes})
    # ma200 = (199*100 + 110)/200 = 100.05
    expected_ma200 = (199 * 100 + 110) / 200
    assert out["ma200"] == pytest.approx(expected_ma200)
    assert out["price_vs_ma200"] == pytest.approx(110.0 / expected_ma200)


def test_compute_derived_series_lengths_match():
    closes = [float(i) for i in range(1, 51)]
    out = compute_derived_series({"price": closes, "high": closes, "low": closes})
    for name in RESERVED_NAMES:
        assert len(out[name]) == 50


def test_compute_derived_series_ma20_per_bar():
    closes = [100.0] * 50
    out = compute_derived_series({"price": closes})
    # First 19 bars: None; bar 19 onwards: 100.0
    for i in range(19):
        assert out["ma20"][i] is None
    for i in range(19, 50):
        assert out["ma20"][i] == pytest.approx(100.0)


def test_from_raw_series_shadow_guard_raises_for_scalars():
    with pytest.raises(FormulaError):
        EvaluationContext.from_raw_series(
            {"price": [1.0, 2.0]},
            scalars={"ma200": 50.0},
        )


def test_from_raw_series_shadow_guard_raises_for_params():
    with pytest.raises(FormulaError):
        EvaluationContext.from_raw_series(
            {"price": [1.0, 2.0]},
            scalars={},
            params={"price": 99.0},
        )


def test_from_raw_series_populates_reserved_into_context():
    closes = [100.0] * 250
    ctx = EvaluationContext.from_raw_series({"price": closes}, scalars={}, params={})
    eng = FormulaEngine()
    assert eng.evaluate("ma200", ctx) == pytest.approx(100.0)
    assert eng.evaluate("price", ctx) == 100.0


def test_from_raw_series_log_returns_for_std_20():
    # Log returns for a geometric series: each log return == constant -> std=0.
    closes = [100.0 * (1.01**i) for i in range(50)]
    out = compute_derived_scalars({"price": closes})
    assert out["std_20"] == pytest.approx(0.0, abs=1e-12)


def test_low_52w_correct_for_long_series():
    closes = [100.0] * 100 + [50.0] + [100.0] * 100
    out = compute_derived_scalars({"price": closes})
    assert out["low_52w"] == 50.0


def test_log_return_series_nonzero_std():
    # Random-ish closes -> non-zero std.
    closes = [100.0, 105.0, 95.0, 110.0, 90.0] * 10  # 50 bars
    out = compute_derived_scalars({"price": closes})
    assert out["std_20"] is not None
    assert out["std_20"] > 0
    # Hand-check: log(105/100), log(95/105), ...
    expected_returns = [
        math.log(closes[i] / closes[i - 1]) for i in range(len(closes) - 20, len(closes))
    ]
    mean_r = sum(expected_returns) / len(expected_returns)
    var = sum((r - mean_r) ** 2 for r in expected_returns) / (len(expected_returns) - 1)
    assert out["std_20"] == pytest.approx(math.sqrt(var))
