"""Engine-surface tests for OilPanel: ma_relative preset evaluates via Phase 17 surface."""

from __future__ import annotations

from openlia.formula import EvaluationContext, FormulaEngine, evaluate_ruleset
from openlia.panic_thermometer.panels.oil import OilPanel
from openlia.panic_thermometer.presets import PT_PRESETS


def _history(closes: list[float]) -> list[dict[str, float | str]]:
    return [
        {
            "date": f"2026-01-{i + 1:02d}",
            "open": c,
            "high": c + 0.5,
            "low": c - 0.5,
            "close": c,
            "volume": 0,
        }
        for i, c in enumerate(closes)
    ]


def test_ma_relative_preset_evaluates() -> None:
    """ma_relative preset evaluates against Phase 17 EvaluationContext.from_raw_series."""

    panel = OilPanel()
    # 250 bars: bars 0..199 around 70, bars 200..249 spike to 100 to push price above MA200*1.15.
    closes = [70.0] * 200 + [100.0] * 50
    built = panel.build_context(
        panel_config={"params": {"ticker": "BNO.US"}},
        payloads={"historical_prices": _history(closes), "stock_quote": None},
    )
    preset = PT_PRESETS["oil"]["ma_relative"]
    result = evaluate_ruleset(
        {
            "rules": preset["rules"],
            "streak_condition": preset["streak_condition"],
        },
        built.raw_series,
        scalars=built.scalars,
        params=preset["params"],
    )
    # ma200 == 70 across the run start; price 100 > 70*1.15 -> amber/red/dark_red.
    assert result.status in ("amber", "red", "dark_red")
    assert "ma200" in result.derived_scalars


def test_oil_context_uses_phase17_engine_surface() -> None:
    """OilPanel raw_series feeds EvaluationContext.from_raw_series cleanly."""

    panel = OilPanel()
    built = panel.build_context(
        panel_config={"params": {"ticker": "BNO.US"}},
        payloads={
            "historical_prices": _history([70.0] * 250),
            "stock_quote": {"price": 95.0, "previous_close": 70.0},
        },
    )
    ctx = EvaluationContext.from_raw_series(
        built.raw_series,
        scalars=built.scalars,
        params={"ma_multiplier": 1.15},
    )
    eng = FormulaEngine()
    assert eng.evaluate("price > ma200 * ma_multiplier", ctx) is True
