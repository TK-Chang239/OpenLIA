"""Per-panel core tests for FedLanguagePanel."""

from __future__ import annotations

from openlia.formula import evaluate_ruleset
from openlia.panic_thermometer.panels.fed_language import FedLanguagePanel


def test_fed_panel_detects_hawkish_keyword() -> None:
    panel = FedLanguagePanel()
    built = panel.build_context(
        panel_config={
            "params": {
                "dovish_keywords": ["transitory"],
                "neutral_keywords": ["data dependent"],
                "hawkish_keywords": ["persistent inflation"],
                "crisis_keywords": ["unanchored"],
            }
        },
        payloads={
            "company_news": [
                {
                    "date": "2026-04-22",
                    "headline": "Fed warns of persistent inflation",
                    "summary": "Officials cite persistent inflation pressures.",
                }
            ],
            "economic_events": [],
        },
    )
    assert built.scalars["hawkish_keyword_detected"] is True
    assert built.scalars["matched_phrase"] == "persistent inflation"


def test_fed_panel_default_ruleset_evaluates_red() -> None:
    panel = FedLanguagePanel()
    cfg = {"params": panel.default_ruleset["params"]}
    built = panel.build_context(
        panel_config=cfg,
        payloads={
            "company_news": [
                {
                    "date": "2026-04-22",
                    "headline": "Persistent inflation persists",
                    "summary": "concerns about persistent inflation",
                }
            ],
            "economic_events": [],
        },
    )
    # filter scalars to engine-friendly subset
    engine_scalars = {
        k: v
        for k, v in built.scalars.items()
        if v is None or isinstance(v, (bool, int, float, str))
    }
    result = evaluate_ruleset(
        {
            "rules": panel.default_ruleset["rules"],
            "streak_condition": panel.default_ruleset["streak_condition"],
        },
        built.raw_series,
        scalars=engine_scalars,
        params=panel.default_ruleset["params"],
    )
    assert result.status in ("red", "dark_red")


def test_fed_panel_no_news_falls_through_green() -> None:
    panel = FedLanguagePanel()
    built = panel.build_context(
        panel_config={"params": panel.default_ruleset["params"]},
        payloads={"company_news": [], "economic_events": []},
    )
    assert built.scalars["hawkish_keyword_detected"] is False
    assert built.scalars["crisis_keyword_detected"] is False
