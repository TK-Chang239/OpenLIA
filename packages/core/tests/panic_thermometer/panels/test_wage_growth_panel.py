"""Per-panel core tests for WageGrowthPanel."""

from __future__ import annotations

from openlia.formula import evaluate_ruleset
from openlia.panic_thermometer.panels.wage_growth import WageGrowthPanel


def _events(values: list[float]) -> list[dict[str, str | float]]:
    return [
        {
            "date": f"2026-{i + 1:02d}-15",
            "event_name": "Average Hourly Earnings",
            "actual": v,
        }
        for i, v in enumerate(values)
    ]


def test_wage_panel_picks_latest_value_and_consecutive_count() -> None:
    panel = WageGrowthPanel()
    built = panel.build_context(
        panel_config={"params": panel.default_ruleset["params"]},
        payloads={"economic_events": _events([0.3, 0.6, 0.7])},
    )
    assert built.scalars["value"] == 0.7
    assert built.scalars["prev_value"] == 0.6
    assert built.scalars["consecutive_count"] == 2


def test_wage_default_rules_amber_at_threshold() -> None:
    panel = WageGrowthPanel()
    built = panel.build_context(
        panel_config={"params": panel.default_ruleset["params"]},
        payloads={"economic_events": _events([0.45])},
    )
    engine_scalars = {
        k: v
        for k, v in built.scalars.items()
        if v is None or isinstance(v, (bool, int, float, str))
    }
    result = evaluate_ruleset(
        {
            "rules": panel.default_ruleset["rules"],
            "streak_condition": None,
        },
        built.raw_series,
        scalars=engine_scalars,
        params=panel.default_ruleset["params"],
    )
    assert result.status == "amber"


def test_wage_panel_prefers_mom_over_yoy_when_both_present() -> None:
    # EODHD publishes Average Hourly Earnings as two identically-named rows on
    # the same date (mom ~0.3, yoy ~3.5). The panel's thresholds are MoM, so it
    # must read the month-over-month figure, not the year-over-year one.
    panel = WageGrowthPanel()
    events = [
        {
            "date": "2026-08-07",
            "event_name": "Average Hourly Earnings",
            "actual": 0.3,
            "comparison": "mom",
        },
        {
            "date": "2026-08-07",
            "event_name": "Average Hourly Earnings",
            "actual": 3.5,
            "comparison": "yoy",
        },
    ]
    built = panel.build_context(
        panel_config={"params": panel.default_ruleset["params"]},
        payloads={"economic_events": events},
    )
    assert built.scalars["value"] == 0.3


def test_wage_panel_no_events_returns_warning() -> None:
    panel = WageGrowthPanel()
    built = panel.build_context(
        panel_config={"params": panel.default_ruleset["params"]},
        payloads={"economic_events": []},
    )
    assert built.scalars["value"] is None
    assert any("no AHE events" in w for w in built.warnings)
