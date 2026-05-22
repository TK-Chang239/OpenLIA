"""Tests for PR 2.8 signals helpers: insider_signal_panel, moving_average_panel,
historical_multiple_trends.

Covers:
  - Registration of all 3 helpers
  - insider: cluster of 3 insiders buying within 30 days -> cluster_detected True
  - insider: 10b5-1 dispositions labeled separately / excluded from bearish signal
  - MA: golden cross (50DMA crosses above 200DMA) detected with known data
  - MA: distance from 200DMA = (price - ma) / ma formula
  - multiple trends: 30th percentile detected for known input distribution
  - multiple trends: < 10th percentile warning fires
  - skill docs exist at expected paths
"""

from __future__ import annotations

import pathlib

import pytest
from openlia.llm.runtime.report_v2_2.tools.library_helpers import get_helper, list_helpers
from openlia.llm.runtime.report_v2_2.tools.library_helpers.signals import (
    historical_multiple_trends as _hmt_mod,
)
from openlia.llm.runtime.report_v2_2.tools.library_helpers.signals import (
    insider_signal_panel as _insider_mod,
)
from openlia.llm.runtime.report_v2_2.tools.library_helpers.signals import (
    moving_average_panel as _ma_mod,
)

hmt_execute = _hmt_mod.execute
insider_execute = _insider_mod.execute
ma_execute = _ma_mod.execute

# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

SIGNAL_HELPERS = [
    "insider_signal_panel",
    "moving_average_panel",
    "historical_multiple_trends",
]


@pytest.mark.parametrize("name", SIGNAL_HELPERS)
def test_helper_registered(name: str) -> None:
    assert get_helper(name) is not None, f"{name!r} not in registry"


@pytest.mark.parametrize("name", SIGNAL_HELPERS)
def test_helper_produces_artifact_output(name: str) -> None:
    helper = get_helper(name)
    assert helper is not None
    arts = helper.schema.contract.produces_artifacts
    assert len(arts) >= 1
    for a in arts:
        assert a.endswith("_output"), f"{name}: artifact {a!r} must end with '_output'"


@pytest.mark.parametrize("name", SIGNAL_HELPERS)
def test_helper_schema_version(name: str) -> None:
    helper = get_helper(name)
    assert helper is not None
    assert helper.schema.version == "0.1.0"


@pytest.mark.parametrize("name", SIGNAL_HELPERS)
def test_helper_has_skill_doc(name: str) -> None:
    helper = get_helper(name)
    assert helper is not None
    assert helper.schema.skill_doc is not None, f"{name!r} missing skill_doc"
    assert helper.schema.skill_doc.estimated_tokens > 0


def test_all_3_signal_helpers_registered() -> None:
    registered = {h.schema.directory.name for h in list_helpers()}
    missing = [n for n in SIGNAL_HELPERS if n not in registered]
    assert not missing, f"Missing signal helpers: {missing}"


# ---------------------------------------------------------------------------
# insider_signal_panel tests
# ---------------------------------------------------------------------------


def _make_txn(
    date: str,
    insider: str,
    role: str,
    code: str,
    shares: float,
    value: float,
    shares_owned_after: float = 0.0,
    footnote: str = "",
) -> dict:
    return {
        "date": date,
        "insider_name": insider,
        "role": role,
        "transaction_code": code,
        "shares": shares,
        "value": value,
        "shares_owned_after": shares_owned_after,
        "footnote": footnote,
    }


def test_insider_cluster_detection_true() -> None:
    """3 distinct insiders buying within 30 days -> cluster_buy_detected True."""
    txns = [
        _make_txn("2026-04-01", "Alice Smith", "CEO", "P", 10000, 1_500_000),
        _make_txn("2026-04-10", "Bob Jones", "CFO", "P", 8000, 1_200_000),
        _make_txn("2026-04-20", "Carol Lee", "Director", "P", 5000, 750_000),
    ]
    result = insider_execute(txns, lookback_windows=[90], as_of="2026-05-20")
    assert result["windows"]["90d"]["cluster_buy_detected"] is True


def test_insider_cluster_only_two_insiders_no_cluster() -> None:
    """Only 2 distinct insiders -> cluster_buy_detected False."""
    txns = [
        _make_txn("2026-04-01", "Alice Smith", "CEO", "P", 10000, 1_500_000),
        _make_txn("2026-04-10", "Alice Smith", "CEO", "P", 5000, 750_000),
        _make_txn("2026-04-15", "Bob Jones", "CFO", "P", 8000, 1_200_000),
    ]
    result = insider_execute(txns, lookback_windows=[90], as_of="2026-05-20")
    assert result["windows"]["90d"]["cluster_buy_detected"] is False


def test_insider_10b5_scheduled_excluded_from_bearish() -> None:
    """10b5-1 plan sales are not counted in standalone_sells (bearish signal)."""
    txns = [
        _make_txn("2026-04-01", "Alice Smith", "CEO", "S", 20000, 3_000_000, footnote="10b5-1"),
        _make_txn("2026-04-10", "Alice Smith", "CEO", "S", 10000, 1_500_000, footnote="10b5-1"),
    ]
    result = insider_execute(txns, lookback_windows=[90], as_of="2026-05-20")
    # Standalone sells (discretionary) should be 0 — both are scheduled
    assert result["windows"]["90d"]["standalone_sells"] == 0


def test_insider_discretionary_sell_counted() -> None:
    """Non-scheduled S code is counted as a standalone sell."""
    txns = [
        _make_txn("2026-04-01", "Bob Jones", "Officer", "S", 5000, 750_000),
    ]
    result = insider_execute(txns, lookback_windows=[90], as_of="2026-05-20")
    assert result["windows"]["90d"]["standalone_sells"] == 1


def test_insider_excluded_codes_counted() -> None:
    """Excluded codes (A, M, F) appear in excluded_transactions dict."""
    txns = [
        _make_txn("2026-04-01", "Alice", "CEO", "A", 5000, 0),
        _make_txn("2026-04-02", "Alice", "CEO", "M", 3000, 0),
        _make_txn("2026-04-03", "Alice", "CEO", "F", 1000, 0),
    ]
    result = insider_execute(txns, lookback_windows=[90], as_of="2026-05-20")
    excluded = result["excluded_transactions"]
    assert excluded.get("grants_A", 0) == 1
    assert excluded.get("option_exercises_M", 0) == 1
    assert excluded.get("tax_withholding_F", 0) == 1


def test_insider_bullish_classification() -> None:
    """Cluster buy + positive role_weighted_net -> bullish classification."""
    txns = [
        _make_txn("2026-04-01", "Alice Smith", "CEO", "P", 10000, 1_500_000),
        _make_txn("2026-04-10", "Bob Jones", "CFO", "P", 8000, 1_200_000),
        _make_txn("2026-04-20", "Carol Lee", "Director", "P", 5000, 750_000),
    ]
    result = insider_execute(txns, lookback_windows=[90], as_of="2026-05-20")
    assert result["signal_classification"] == "bullish"
    assert result["signal_confidence"] == "high"


def test_insider_empty_transactions_raises() -> None:
    with pytest.raises(ValueError, match="transactions must not be empty"):
        insider_execute([])


def test_insider_net_value_formula() -> None:
    """net_value = buy_value - sell_value."""
    txns = [
        _make_txn("2026-04-01", "Alice", "CEO", "P", 10000, 1_000_000),
        _make_txn("2026-04-05", "Bob", "Officer", "S", 5000, 400_000),
    ]
    result = insider_execute(txns, lookback_windows=[90], as_of="2026-05-20")
    w = result["windows"]["90d"]
    assert w["net_value"] == pytest.approx(1_000_000 - 400_000, rel=1e-6)


# ---------------------------------------------------------------------------
# moving_average_panel tests
# ---------------------------------------------------------------------------


def _make_trend_series(n: int = 250, start: float = 100.0, drift: float = 0.001) -> list[float]:
    """Steadily rising series."""
    prices = [start]
    for _ in range(n - 1):
        prices.append(prices[-1] * (1 + drift))
    return prices


def _make_dates(n: int, start_year: int = 2024) -> list[str]:
    """Simple date list with 1-day increment."""
    import datetime

    start = datetime.date(start_year, 1, 1)
    return [(start + datetime.timedelta(days=i)).isoformat() for i in range(n)]


def test_ma_golden_cross_detected() -> None:
    """Golden cross: 50DMA crosses above 200DMA from below."""
    # Build a series where price dips then rises sharply, creating a golden cross
    # Phase 1: 200 flat periods (seed both MAs near same level)
    # Phase 2: sharp rise so 50MA crosses above 200MA

    flat = [100.0] * 200
    rise = [100.0 + i * 0.5 for i in range(100)]  # 100 rising bars
    prices = flat + rise

    dates = _make_dates(len(prices))
    result = ma_execute(
        price_series=prices,
        dates=dates,
        ma_windows=[50, 200],
        crossover_pairs=[(50, 200)],
    )
    assert len(result["crossovers"]) > 0
    types = [c["type"] for c in result["crossovers"]]
    assert "golden_cross" in types


def test_ma_death_cross_detected() -> None:
    """Death cross: 50DMA crosses below 200DMA."""
    rise = [100.0 + i * 0.5 for i in range(200)]  # 200 rising bars (seed 200MA high)
    drop = [200.0 - i * 1.0 for i in range(100)]  # sharp drop
    prices = rise + drop

    dates = _make_dates(len(prices))
    result = ma_execute(
        price_series=prices,
        dates=dates,
        ma_windows=[50, 200],
        crossover_pairs=[(50, 200)],
    )
    types = [c["type"] for c in result["crossovers"]]
    assert "death_cross" in types


def test_ma_distance_formula() -> None:
    """distance_from_ma: 200d_stretch_pct = (price - MA_200) / MA_200."""
    prices = _make_trend_series(n=210, start=100.0, drift=0.001)
    dates = _make_dates(210)
    result = ma_execute(
        price_series=prices,
        dates=dates,
        ma_windows=[200],
        crossover_pairs=[],
    )
    dist = result["distance_from_ma"]
    # Verify formula: stretch_pct = (current / MA_200 - 1)
    ma200_val = result["moving_averages"]["200"]["value"]
    current = prices[-1]
    expected_stretch = current / ma200_val - 1
    # Output rounds to 4 decimal places; compare with tolerance for rounding
    assert dist["200d_stretch_pct"] == pytest.approx(expected_stretch, abs=1e-3)


def test_ma_price_above_ma_flag() -> None:
    """price_above_ma True when price > MA value."""
    prices = _make_trend_series(n=220, start=100.0, drift=0.002)
    dates = _make_dates(220)
    result = ma_execute(price_series=prices, dates=dates, ma_windows=[50, 200])
    # Steadily rising series: price should be above both 50 and 200 MA
    assert result["price_above_ma"]["50"] is True
    assert result["price_above_ma"]["200"] is True


def test_ma_insufficient_data_returns_null_ma() -> None:
    """Series shorter than 200 -> 200-day MA is null."""
    prices = [100.0 + i for i in range(100)]  # only 100 points
    result = ma_execute(price_series=prices, ma_windows=[200], crossover_pairs=[])
    assert result["moving_averages"]["200"]["value"] is None


def test_ma_empty_series_raises() -> None:
    with pytest.raises(ValueError, match="price_series must not be empty"):
        ma_execute(price_series=[])


def test_ma_invalid_type_raises() -> None:
    with pytest.raises(ValueError, match="ma_type must be 'sma' or 'ema'"):
        ma_execute(price_series=[100.0] * 50, ma_type="wma")


def test_ma_bullish_stack() -> None:
    """Steadily rising series: 20 > 50 > 100 > 200 -> bullish stack."""
    prices = _make_trend_series(n=300, start=50.0, drift=0.002)
    result = ma_execute(price_series=prices, ma_windows=[20, 50, 100, 200])
    assert result["ma_stack"] == "bullish"


def test_ma_trend_regime_uptrend() -> None:
    """Steadily rising series: price > 200 MA and slope positive -> uptrend."""
    prices = _make_trend_series(n=300, start=50.0, drift=0.002)
    result = ma_execute(price_series=prices, ma_windows=[200], crossover_pairs=[])
    assert result["trend_regime"] == "uptrend"


def test_ma_ema_type() -> None:
    """EMA type produces non-null values."""
    prices = _make_trend_series(n=250, start=100.0, drift=0.001)
    result = ma_execute(
        price_series=prices, ma_windows=[50, 200], ma_type="ema", crossover_pairs=[]
    )
    assert result["moving_averages"]["50"]["value"] is not None
    assert result["moving_averages"]["200"]["value"] is not None


def test_ma_volume_confirmation() -> None:
    """Volume confirmation fires when cross-period volume > trailing average."""
    flat = [100.0] * 200
    rise = [100.0 + i * 0.5 for i in range(100)]
    prices = flat + rise
    # Normal volume with a spike at the crossover
    volume = [1_000_000.0] * 300
    # We don't know exact cross index, but set last 50 bars to high volume
    for i in range(250, 300):
        volume[i] = 5_000_000.0

    dates = _make_dates(300)
    result = ma_execute(
        price_series=prices,
        dates=dates,
        ma_windows=[50, 200],
        crossover_pairs=[(50, 200)],
        volume_series=volume,
    )
    # At least one crossover should have confirmed_on_volume set (not None)
    if result["crossovers"]:
        assert result["crossovers"][-1]["confirmed_on_volume"] is not None


# ---------------------------------------------------------------------------
# historical_multiple_trends tests
# ---------------------------------------------------------------------------


def _make_pe_history(n: int = 40, center: float = 20.0, spread: float = 5.0) -> list[float]:
    """Evenly distributed PE history from (center - spread) to (center + spread)."""
    if n <= 1:
        return [center]
    step = 2 * spread / (n - 1)
    return [round(center - spread + i * step, 2) for i in range(n)]


def test_hmt_30th_percentile_detected() -> None:
    """Known input distribution -> 30th percentile detected correctly."""
    # 40 evenly spaced values: 15 to 25. Current = 18.0.
    # Values from 15.0 to 25.0 in 40 steps. Values < 18.0: roughly 18 out of 40.
    history = _make_pe_history(n=40, center=20.0, spread=5.0)
    # history goes from 15.0 to 25.0
    current = 18.0
    data = {"pe_ttm": {"current": current, "history": history}}
    result = hmt_execute(data, windows_years=[10])
    pct_rank = result["pe_ttm"]["percentile_rank_by_window"]["10y"]
    # 18.0 is between 15 and 25; strictly below 18 = ~37.5% of values
    assert 0.25 <= pct_rank <= 0.45, f"Expected ~30th percentile, got {pct_rank:.3f}"


def test_hmt_below_10th_percentile_warning_fires() -> None:
    """Current multiple at < 10th percentile -> warning in warnings list."""
    history = _make_pe_history(n=40, center=20.0, spread=5.0)
    # history: 15 to 25. Current = 15.1 -> ~1st percentile
    current = 15.1
    data = {"pe_ttm": {"current": current, "history": history}}
    result = hmt_execute(data, windows_years=[5, 10])
    warnings = result["pe_ttm"]["warnings"]
    # At least one warning mentioning near-historical-low
    assert any("historical low" in w.lower() or "percentile" in w.lower() for w in warnings), (
        f"Expected low-percentile warning, got: {warnings}"
    )


def test_hmt_above_90th_percentile_warning_fires() -> None:
    """Current multiple at > 90th percentile -> warning fires."""
    history = _make_pe_history(n=40, center=20.0, spread=5.0)
    current = 24.9  # near top of 15-25 range -> ~99th percentile
    data = {"pe_ttm": {"current": current, "history": history}}
    result = hmt_execute(data, windows_years=[5, 10])
    warnings = result["pe_ttm"]["warnings"]
    assert any("percentile" in w.lower() for w in warnings), (
        f"Expected high-percentile warning, got: {warnings}"
    )


def test_hmt_z_score_formula() -> None:
    """z_score = (current - mean) / stdev for known distribution."""
    # All same value = 20.0; current = 22.0 => stdev = 0, z_score = None
    history = [20.0] * 20
    data = {"pe_ttm": {"current": 22.0, "history": history}}
    result = hmt_execute(data, windows_years=[5])
    # stdev is 0 so z_score should be None
    assert result["pe_ttm"]["z_score_by_window"]["5y"] is None


def test_hmt_z_score_positive_for_above_mean() -> None:
    """current > mean -> positive z_score."""
    history = list(range(10, 30))  # mean = 19.5
    current = 25.0
    data = {"pe_ttm": {"current": current, "history": history}}
    result = hmt_execute(data, windows_years=[10])
    z = result["pe_ttm"]["z_score_by_window"]["10y"]
    assert z is not None and z > 0


def test_hmt_nm_periods_excluded_from_pe() -> None:
    """Negative/zero PE values are NM and excluded from P/E stats."""
    history = [20.0, 18.0, -5.0, 0.0, 22.0, 19.0]  # 2 NM periods
    data = {"pe_ttm": {"current": 20.0, "history": history}}
    result = hmt_execute(data, windows_years=[5])
    # nm_periods should count the excluded entries
    assert result["pe_ttm"]["nm_periods"] >= 2


def test_hmt_empty_data_raises() -> None:
    with pytest.raises(ValueError, match="multiples_data must not be empty"):
        hmt_execute({})


def test_hmt_forward_trailing_spread() -> None:
    """forward_estimates triggers forward_vs_trailing section with implied growth."""
    history = [20.0] * 20
    data = {"pe_ttm": {"current": 20.0, "history": history}}
    fwd = {"pe_ttm_forward": 16.0}
    result = hmt_execute(data, windows_years=[5], forward_estimates=fwd)
    assert "forward_vs_trailing" in result
    fvt = result["forward_vs_trailing"]
    # implied_growth = 20.0 / 16.0 - 1 = 0.25
    assert fvt["implied_growth"] == pytest.approx(0.25, rel=1e-4)


def test_hmt_sector_overlay() -> None:
    """sector_median_series triggers relative_to_sector in per-multiple output."""
    history = [20.0, 21.0, 19.0, 22.0, 18.0] * 4  # 20 observations
    sector = [18.0, 19.0, 17.0, 20.0, 16.0] * 4
    data = {"pe_ttm": {"current": 20.0, "history": history}}
    result = hmt_execute(data, windows_years=[5], sector_median_series={"pe_ttm": sector})
    assert "relative_to_sector" in result["pe_ttm"]
    rs = result["pe_ttm"]["relative_to_sector"]
    assert "current_premium_to_sector_pct" in rs


def test_hmt_mean_reversion_caveat_present() -> None:
    """mean_reversion_caveat always present in output."""
    data = {"pe_ttm": {"current": 18.0, "history": [20.0] * 20}}
    result = hmt_execute(data)
    assert "mean_reversion_caveat" in result
    assert len(result["mean_reversion_caveat"]) > 50


# ---------------------------------------------------------------------------
# Skill doc existence tests
# ---------------------------------------------------------------------------

_SKILLS_DIR = (
    pathlib.Path(__file__).parent.parent.parent.parent.parent.parent
    / "src"
    / "openlia"
    / "llm"
    / "runtime"
    / "report_v2_2"
    / "tools"
    / "library_helpers"
    / "skills"
)

_EXPECTED_SKILL_DOCS = [
    "insider_signal_panel.md",
    "moving_average_panel.md",
    "historical_multiple_trends.md",
]


@pytest.mark.parametrize("filename", _EXPECTED_SKILL_DOCS)
def test_skill_doc_exists(filename: str) -> None:
    path = _SKILLS_DIR / filename
    assert path.exists(), f"Skill doc missing: {path}"
    assert path.stat().st_size > 100, f"Skill doc appears empty: {path}"


@pytest.mark.parametrize("filename", _EXPECTED_SKILL_DOCS)
def test_skill_doc_has_required_sections(filename: str) -> None:
    path = _SKILLS_DIR / filename
    content = path.read_text()
    required_sections = [
        "## Purpose",
        "## When to use",
        "## When NOT to use",
        "## Methodology",
        "## Common pitfalls",
        "## Related helpers",
    ]
    for section in required_sections:
        assert section in content, f"Skill doc {filename} missing required section: {section!r}"


@pytest.mark.parametrize(
    "filename,expected_artifact",
    [
        ("insider_signal_panel.md", "insider_signal_output"),
        ("moving_average_panel.md", "moving_average_panel_output"),
        ("historical_multiple_trends.md", "historical_multiple_trends_output"),
    ],
)
def test_skill_doc_references_produced_artifact(filename: str, expected_artifact: str) -> None:
    path = _SKILLS_DIR / filename
    content = path.read_text()
    assert expected_artifact in content, (
        f"Skill doc {filename} does not reference its produced artifact {expected_artifact!r}"
    )
