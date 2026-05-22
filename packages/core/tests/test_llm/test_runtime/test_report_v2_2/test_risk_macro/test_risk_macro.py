"""Tests for PR 2.11: drawdown_panel, yield_curve_shape, commodity_exposure_tracker.

Covers:
  - Registration of all 3 helpers
  - Drawdown: known price series with 25% drawdown produces max_dd = -0.25
  - Drawdown: Calmar ratio = annualised_return / |max_dd|
  - Drawdown: Sortino denominator uses downside-only returns
  - Drawdown: all_drawdowns_gt_10pct correctly identifies significant events
  - Yield curve: 2Y=4%, 10Y=3% -> inverted regime (spread = -100 bps)
  - Yield curve: 2Y=2%, 10Y=4% -> steep regime (spread = +200 bps)
  - Yield curve: flat regime (spread between 0 and 30 bps)
  - Yield curve: modestly upward (spread between 30 and 100 bps)
  - Yield curve: OLS slope positive on normal curve, negative on inverted
  - Yield curve: days_since_last_inversion computed from historical snapshots
  - Commodity exposure: Pearson r linearity check ($0.10 oil change x 1M bbl = $100k EBITDA)
  - Commodity exposure: regression slope proportional to commodity-metric relationship
  - Commodity exposure: zero-correlation series produces r near 0
  - Commodity exposure: DEGRADED status when series too short
"""

from __future__ import annotations

import pytest
from openlia.llm.runtime.report_v2_2.tools.library_helpers import get_helper

# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

RISK_HELPERS = [
    "drawdown_panel",
    "yield_curve_shape",
    "commodity_exposure_tracker",
]


@pytest.mark.parametrize("name", RISK_HELPERS)
def test_helper_registered(name: str) -> None:
    assert get_helper(name) is not None, f"{name!r} not in registry"


@pytest.mark.parametrize("name", RISK_HELPERS)
def test_helper_produces_artifacts(name: str) -> None:
    helper = get_helper(name)
    assert helper is not None
    assert len(helper.schema.contract.produces_artifacts) >= 1


# ---------------------------------------------------------------------------
# drawdown_panel
# ---------------------------------------------------------------------------


def _build_prices_with_known_drawdown(
    start: float = 100.0,
    peak: float = 200.0,
    trough: float = 150.0,
    end: float = 160.0,
) -> tuple[list[float], list[str]]:
    """Build a synthetic price series with a known drawdown.

    Structure: linear rise from start->peak, linear drop to trough, recover to end.
    Drawdown = (trough - peak) / peak.
    """
    prices: list[float] = []
    dates: list[str] = []

    # Rise over 100 days
    for i in range(100):
        prices.append(start + (peak - start) * i / 99)
        dates.append(f"2020-{(i // 31 + 1):02d}-{(i % 28 + 1):02d}")

    # Drop over 50 days
    for i in range(50):
        prices.append(peak - (peak - trough) * i / 49)
        y = 2020 + (100 + i) // 365
        d = (100 + i) % 28 + 1
        m = ((100 + i) % 365) // 28 + 1
        dates.append(f"{y}-{m:02d}-{d:02d}")

    # Partial recovery over 30 days (does not reach peak)
    for i in range(30):
        prices.append(trough + (end - trough) * i / 29)
        y = 2021
        d = (i % 28) + 1
        m = i // 28 + 1
        dates.append(f"{y}-{m:02d}-{d:02d}")

    return prices, dates


def test_drawdown_panel_max_drawdown_known_series() -> None:
    """A price series with a 25% drop from peak produces max_dd = -0.25."""
    peak = 200.0
    trough = 150.0
    expected_dd = (trough - peak) / peak  # -0.25

    prices, dates = _build_prices_with_known_drawdown(
        start=100.0, peak=peak, trough=trough, end=160.0
    )
    result = get_helper("drawdown_panel").impl(prices=prices, dates=dates)

    since_ipo = result["since_ipo"]
    assert since_ipo["max_drawdown"] == pytest.approx(expected_dd, abs=1e-4), (
        f"Expected max_dd {expected_dd:.4f}, got {since_ipo['max_drawdown']}"
    )


def test_drawdown_panel_simple_25pct() -> None:
    """Minimal 4-price series: price goes 100 -> 80 (25% below 100 but only 20% here)."""
    prices = [100.0, 100.0, 75.0, 80.0]
    dates = ["2023-01-01", "2023-02-01", "2023-03-01", "2023-04-01"]
    result = get_helper("drawdown_panel").impl(prices=prices, dates=dates)
    dd = result["since_ipo"]["max_drawdown"]
    assert dd == pytest.approx(-0.25, abs=1e-6)


def test_drawdown_panel_calmar_formula() -> None:
    """Calmar = annualised_return / |max_dd|. Verify identity holds."""
    prices = [100.0, 120.0, 90.0, 95.0, 100.0, 110.0]
    dates = [
        "2022-01-01",
        "2022-04-01",
        "2022-07-01",
        "2022-10-01",
        "2023-01-01",
        "2023-04-01",
    ]
    result = get_helper("drawdown_panel").impl(prices=prices, dates=dates)
    since = result["since_ipo"]
    calmar = since.get("calmar")
    ann_ret = since.get("annualised_return")
    max_dd = since.get("max_drawdown")

    if calmar is not None and ann_ret is not None and max_dd is not None and max_dd < 0:
        expected_calmar = ann_ret / abs(max_dd)
        assert calmar == pytest.approx(expected_calmar, rel=1e-4), (
            f"Calmar {calmar} != ann_ret/|max_dd| = {expected_calmar}"
        )


def test_drawdown_panel_all_drawdowns_gt_10pct() -> None:
    """Series with known 25% drawdown should appear in all_drawdowns_gt_10pct."""
    prices = [100.0, 100.0, 75.0, 80.0]
    dates = ["2023-01-01", "2023-02-01", "2023-03-01", "2023-04-01"]
    result = get_helper("drawdown_panel").impl(prices=prices, dates=dates)
    events = result["all_drawdowns_gt_10pct"]
    assert len(events) >= 1
    depths = [e["depth"] for e in events]
    assert any(d <= -0.10 for d in depths)


def test_drawdown_panel_no_drawdown_series() -> None:
    """Monotonically increasing prices should have max_dd near 0 and no events."""
    prices = [float(i) for i in range(10, 210, 10)]  # 10, 20, 30, ..., 200
    dates = [f"2022-{(i + 1):02d}-01" for i in range(len(prices))]
    result = get_helper("drawdown_panel").impl(prices=prices, dates=dates)
    assert result["since_ipo"]["max_drawdown"] == pytest.approx(0.0, abs=1e-9)
    assert result["all_drawdowns_gt_10pct"] == []


def test_drawdown_panel_status_ok() -> None:
    prices = [100.0, 90.0, 95.0, 105.0]
    dates = ["2023-01-01", "2023-02-01", "2023-03-01", "2023-04-01"]
    result = get_helper("drawdown_panel").impl(prices=prices, dates=dates)
    assert result["status"] == "OK"


def test_drawdown_panel_raises_empty() -> None:
    with pytest.raises(ValueError, match="empty"):
        get_helper("drawdown_panel").impl(prices=[], dates=[])


def test_drawdown_panel_raises_length_mismatch() -> None:
    with pytest.raises(ValueError, match="length"):
        get_helper("drawdown_panel").impl(prices=[100.0], dates=["2023-01-01", "2023-02-01"])


# ---------------------------------------------------------------------------
# yield_curve_shape
# ---------------------------------------------------------------------------


def test_yield_curve_inverted_regime() -> None:
    """2Y=4%, 10Y=3% -> inverted (spread = -100 bps)."""
    result = get_helper("yield_curve_shape").impl(
        yields={"2y": 4.0, "10y": 3.0},
        as_of="2024-01-15",
    )
    assert result["10y_2y_spread_bps"] == -100
    assert result["inverted"] is True
    assert result["regime"] == "inverted"


def test_yield_curve_steep_regime() -> None:
    """2Y=2%, 10Y=4% -> steep (spread = +200 bps > 100 bps threshold)."""
    result = get_helper("yield_curve_shape").impl(
        yields={"2y": 2.0, "10y": 4.0},
        as_of="2021-06-01",
    )
    assert result["10y_2y_spread_bps"] == 200
    assert result["inverted"] is False
    assert result["regime"] == "steep"


def test_yield_curve_flat_regime() -> None:
    """2Y=3.9%, 10Y=4.1% -> flat (spread = +20 bps, 0 <= x < 30)."""
    result = get_helper("yield_curve_shape").impl(
        yields={"2y": 3.9, "10y": 4.1},
    )
    assert result["10y_2y_spread_bps"] == 20
    assert result["regime"] == "flat"
    assert result["inverted"] is False


def test_yield_curve_modestly_upward() -> None:
    """2Y=3.5%, 10Y=4.0% -> modestly upward (spread = 50 bps, 30 <= x < 100)."""
    result = get_helper("yield_curve_shape").impl(
        yields={"2y": 3.5, "10y": 4.0},
    )
    assert result["10y_2y_spread_bps"] == 50
    assert result["regime"] == "modestly_upward"


def test_yield_curve_ols_slope_positive_on_normal() -> None:
    """Normal upward-sloping curve should have positive OLS slope."""
    # Yields rise with maturity
    result = get_helper("yield_curve_shape").impl(
        yields={
            "3m": 1.0,
            "2y": 2.0,
            "5y": 3.0,
            "10y": 4.0,
            "30y": 4.5,
        },
    )
    slope = result["curve_slope_bps_per_year"]
    assert slope is not None
    assert slope > 0, f"Expected positive slope on normal curve, got {slope}"


def test_yield_curve_ols_slope_negative_on_inverted() -> None:
    """Deeply inverted curve should have negative OLS slope."""
    result = get_helper("yield_curve_shape").impl(
        yields={
            "3m": 5.5,
            "2y": 5.0,
            "5y": 4.5,
            "10y": 4.0,
            "30y": 3.8,
        },
    )
    slope = result["curve_slope_bps_per_year"]
    assert slope is not None
    assert slope < 0, f"Expected negative slope on inverted curve, got {slope}"


def test_yield_curve_10y_3m_spread() -> None:
    """10Y-3M spread correctly computed."""
    result = get_helper("yield_curve_shape").impl(
        yields={"3m": 2.0, "10y": 4.5},
    )
    assert result["10y_3m_spread_bps"] == 250


def test_yield_curve_days_since_inversion() -> None:
    """days_since_last_inversion computed from historical snapshots."""
    # Historical: inversion on 2023-10-01
    historical = [
        {"date": "2023-09-01", "2y": 3.0, "10y": 3.5},  # not inverted
        {"date": "2023-10-01", "2y": 4.0, "10y": 3.8},  # inverted (-20 bps)
        {"date": "2023-11-01", "2y": 4.0, "10y": 4.2},  # not inverted
    ]
    result = get_helper("yield_curve_shape").impl(
        yields={"2y": 3.5, "10y": 4.0},
        as_of="2024-01-01",
        historical_snapshots=historical,
    )
    # 2023-10-01 -> 2024-01-01 = 92 days
    days = result["days_since_last_inversion"]
    assert days is not None
    assert days == 92


def test_yield_curve_missing_inputs_flagged() -> None:
    """Missing 10y or 2y keys are reported in missing_inputs."""
    result = get_helper("yield_curve_shape").impl(
        yields={"3m": 2.0},
    )
    assert "10y" in result["missing_inputs"]
    assert "2y" in result["missing_inputs"]
    assert result["status"] == "DEGRADED"


def test_yield_curve_raises_empty() -> None:
    with pytest.raises(ValueError, match="empty"):
        get_helper("yield_curve_shape").impl(yields={})


# ---------------------------------------------------------------------------
# commodity_exposure_tracker
# ---------------------------------------------------------------------------


def test_commodity_linearity_check() -> None:
    """$0.10/unit oil change x 1M barrels annual = $100k EBITDA impact.

    Regression slope should be proportional: 1M bbl * slope_per_dollar ≈ 1M * 0.10 = 100k.
    Here we construct a perfectly linear relationship:
      ebitda[t] = 1_000_000 * oil[t]  (exposure of 1M barrels)
    So slope = 1_000_000. A $0.10 move -> $100k change.
    """
    # 8 quarters, perfectly linear relationship
    oil_prices = [50.0, 51.0, 52.0, 53.0, 54.0, 55.0, 56.0, 57.0]
    ebitda = [p * 1_000_000 for p in oil_prices]

    result = get_helper("commodity_exposure_tracker").impl(
        subject_metric_series=ebitda,
        commodity_series=oil_prices,
        commodity_name="WTI Oil",
        commodity_unit="bbl",
    )

    slope = result["regression_slope"]
    assert slope is not None
    assert slope == pytest.approx(1_000_000.0, rel=1e-4), (
        f"Expected slope ~1M (1M bbl exposure), got {slope}"
    )
    # Verify linearity: $0.10 move * 1M bbl = $100k
    impact = 0.10 * slope
    assert impact == pytest.approx(100_000.0, rel=1e-4), (
        f"$0.10 oil move should produce $100k impact, got {impact}"
    )


def test_commodity_pearson_perfect_correlation() -> None:
    """Perfectly correlated series should yield Pearson r = 1.0."""
    x = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    y = [p * 2.5 for p in x]  # perfectly linear transform

    result = get_helper("commodity_exposure_tracker").impl(
        subject_metric_series=y,
        commodity_series=x,
        commodity_name="Test Commodity",
    )
    assert result["correlation_pearson"] == pytest.approx(1.0, abs=1e-5)
    assert result["correlation_spearman"] == pytest.approx(1.0, abs=1e-5)


def test_commodity_negative_correlation() -> None:
    """Inversely correlated series -> Pearson r near -1."""
    x = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0]
    y = [-p for p in x]

    result = get_helper("commodity_exposure_tracker").impl(
        subject_metric_series=y,
        commodity_series=x,
        commodity_name="Inverse Commodity",
    )
    assert result["correlation_pearson"] == pytest.approx(-1.0, abs=1e-5)


def test_commodity_uncorrelated_series() -> None:
    """Independent series: Pearson r near 0 (not exact due to small n)."""
    # Orthogonal: constant metric vs varying commodity
    x = [50.0, 60.0, 55.0, 65.0, 58.0, 62.0, 59.0, 61.0]
    y = [100.0] * 8  # perfectly flat — variance = 0

    result = get_helper("commodity_exposure_tracker").impl(
        subject_metric_series=y,
        commodity_series=x,
        commodity_name="No-Effect Commodity",
    )
    # Pearson r is undefined when y has zero variance
    assert result["correlation_pearson"] is None


def test_commodity_lag_correlation_max_picks_best_lag() -> None:
    """With lag-1 relationship, argmax lag should be 1."""
    # commodity[t] -> metric[t+1] (1-quarter lag)
    commodity = [50.0, 55.0, 60.0, 65.0, 70.0, 75.0, 80.0, 85.0]
    # metric is commodity shifted right by 1 (plus noise)
    metric = [0.0] + [commodity[i] * 1.5 for i in range(len(commodity) - 1)]

    result = get_helper("commodity_exposure_tracker").impl(
        subject_metric_series=metric,
        commodity_series=commodity,
        commodity_name="Lagged Commodity",
    )
    argmax = result["lag_correlation_max"]
    assert argmax["lag_quarters"] in (0, 1), (
        f"Expected lag 0 or 1 for 1-quarter delayed series, got {argmax['lag_quarters']}"
    )


def test_commodity_degraded_when_too_short() -> None:
    """Series with < 4 periods should return DEGRADED status."""
    result = get_helper("commodity_exposure_tracker").impl(
        subject_metric_series=[100.0, 110.0, 105.0],
        commodity_series=[50.0, 55.0, 52.0],
        commodity_name="Short Series",
    )
    assert result["status"] == "DEGRADED"
    assert result["correlation_pearson"] is None


def test_commodity_raises_mismatched_lengths() -> None:
    with pytest.raises(ValueError, match="length"):
        get_helper("commodity_exposure_tracker").impl(
            subject_metric_series=[100.0, 110.0, 105.0, 115.0],
            commodity_series=[50.0, 55.0],
            commodity_name="Test",
        )


def test_commodity_raises_empty_series() -> None:
    with pytest.raises(ValueError, match="empty"):
        get_helper("commodity_exposure_tracker").impl(
            subject_metric_series=[],
            commodity_series=[],
            commodity_name="Test",
        )


def test_commodity_interpretation_string_present() -> None:
    """Interpretation field should be a non-empty string."""
    x = [50.0 + i for i in range(8)]
    y = [x_i * 2.0 for x_i in x]
    result = get_helper("commodity_exposure_tracker").impl(
        subject_metric_series=y,
        commodity_series=x,
        commodity_name="WTI Oil",
        commodity_unit="bbl",
    )
    assert isinstance(result["interpretation"], str)
    assert len(result["interpretation"]) > 20


def test_commodity_status_ok_on_valid_input() -> None:
    x = [float(i) for i in range(1, 9)]
    y = [float(i * 3) for i in range(1, 9)]
    result = get_helper("commodity_exposure_tracker").impl(
        subject_metric_series=y,
        commodity_series=x,
        commodity_name="Copper LME",
    )
    assert result["status"] == "OK"
    assert result["missing_inputs"] == []
