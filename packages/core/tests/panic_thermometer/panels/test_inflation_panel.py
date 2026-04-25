"""Engine-surface tests for InflationPanel: pure_tip preset evaluates."""

from __future__ import annotations

from openlia.formula import evaluate_ruleset
from openlia.panic_thermometer.panels.inflation import InflationPanel
from openlia.panic_thermometer.presets import PT_PRESETS


def _history(closes: list[float]) -> list[dict[str, float | str]]:
    return [
        {
            "date": f"2026-01-{i + 1:02d}",
            "open": c,
            "high": c,
            "low": c,
            "close": c,
            "volume": 0,
        }
        for i, c in enumerate(closes)
    ]


def test_pure_tip_preset_evaluates() -> None:
    """ma_relative (pure-TIP) preset evaluates without Michigan survey via raw_series."""

    panel = InflationPanel()
    # tip price ramping from 100 to 110 on 250 bars; ma200 ~= 100.x; latest 110 > ma200.
    closes = [100.0 + i * 0.04 for i in range(250)]
    quote = {"price": closes[-1], "previous_close": closes[-2]}
    built = panel.build_context(
        panel_config={"params": {"primary_ticker": "TIP.US"}},
        payloads={
            "historical_prices": _history(closes),
            "stock_quote": quote,
            "economic_events": [],
        },
    )
    preset = PT_PRESETS["inflation"]["ma_relative"]
    result = evaluate_ruleset(
        {
            "rules": preset["rules"],
            "streak_condition": preset["streak_condition"],
        },
        built.raw_series,
        scalars=built.scalars,
        params=preset["params"],
    )
    # tip_price_latest > ma200 -> amber or red.
    assert result.status in ("amber", "red")
    assert result.derived_scalars.get("ma200") is not None
