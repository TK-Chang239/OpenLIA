"""Shipped preset libraries for Panic Thermometer panels."""

from __future__ import annotations

from typing import Any

from openlia.panic_thermometer.panels import PANELS


def _oil_ma_relative() -> dict[str, Any]:
    return {
        "rules": [
            {
                "status": "dark_red",
                "formula": "streak_days >= streak_dark_red",
                "label": "{streak_days} days above MA200*1.15",
            },
            {
                "status": "red",
                "formula": "streak_days >= streak_red",
                "label": "{streak_days} days above MA200*1.15",
            },
            {
                "status": "amber",
                "formula": "price > ma200 * ma_multiplier",
                "label": "Above MA200 band",
            },
            {
                "status": "green",
                "formula": "true",
                "label": "Within MA200 band",
            },
        ],
        "params": {
            "ticker": "BNO.US",
            "ma_multiplier": 1.15,
            "streak_amber": 1,
            "streak_red": 30,
            "streak_dark_red": 90,
            "history_lookback_months": 12,
        },
        "streak_condition": "price > ma200 * ma_multiplier",
    }


def _oil_volatility_adjusted() -> dict[str, Any]:
    return {
        "rules": [
            {
                "status": "dark_red",
                "formula": "streak_days >= streak_dark_red",
                "label": "{streak_days} days > 2 ATR band",
            },
            {
                "status": "red",
                "formula": "streak_days >= streak_red",
                "label": "{streak_days} days > 2 ATR band",
            },
            {
                "status": "amber",
                "formula": "price > ma200 + atr_14 * atr_multiplier",
                "label": "Above 2 ATR band",
            },
            {
                "status": "green",
                "formula": "true",
                "label": "Within 2 ATR band",
            },
        ],
        "params": {
            "ticker": "BNO.US",
            "atr_multiplier": 2.0,
            "streak_amber": 1,
            "streak_red": 30,
            "streak_dark_red": 90,
            "history_lookback_months": 12,
        },
        "streak_condition": "price > ma200 + atr_14 * atr_multiplier",
    }


def _inflation_pure_tip() -> dict[str, Any]:
    return {
        "rules": [
            {
                "status": "red",
                "formula": (
                    "tip_price_latest > ma200 and "
                    "pct_change(tip_price, slope_lookback_days) > slope_threshold"
                ),
                "label": "TIP rising fast",
            },
            {
                "status": "amber",
                "formula": "tip_price_latest > ma200",
                "label": "TIP above 200-day MA",
            },
            {
                "status": "green",
                "formula": "true",
                "label": "TIP below 200-day MA",
            },
        ],
        "params": {
            "primary_ticker": "TIP.US",
            "slope_lookback_days": 30,
            "slope_threshold": 0.02,
        },
        "streak_condition": None,
    }


def _inflation_relative_to_history() -> dict[str, Any]:
    return {
        "rules": [
            {
                "status": "red",
                "formula": "michigan_5y >= michigan_p90",
                "label": "Michigan 90th pct",
            },
            {
                "status": "amber",
                "formula": "michigan_5y >= michigan_p75",
                "label": "Michigan 75th pct",
            },
            {
                "status": "green",
                "formula": "true",
                "label": "Within normal range",
            },
        ],
        "params": {
            "primary_ticker": "TIP.US",
            "michigan_p75": 2.75,
            "michigan_p90": 3.15,
        },
        "streak_condition": None,
    }


def _fed_conservative_keywords() -> dict[str, Any]:
    base = PANELS["fed_language"].default_ruleset
    return {
        "rules": base["rules"],
        "params": {
            **base["params"],
            "hawkish_keywords": [
                "concerning",
                "elevated risks",
                "broadly-based price pressures",
                "persistent inflation",
                "policy tightening",
            ],
            "crisis_keywords": [
                "unanchored",
                "emergency",
                "expedited",
                "rapid tightening",
            ],
        },
        "streak_condition": None,
    }


def _fed_aggressive_keywords() -> dict[str, Any]:
    base = PANELS["fed_language"].default_ruleset
    return {
        "rules": base["rules"],
        "params": {
            **base["params"],
            "hawkish_keywords": [
                "rate hike",
                "tightening",
                "inflation",
                "restrictive",
                "concerned",
            ],
            "crisis_keywords": ["emergency", "expedited", "unanchored", "crisis"],
        },
        "streak_condition": None,
    }


def _wage_acceleration() -> dict[str, Any]:
    return {
        "rules": [
            {
                "status": "red",
                "formula": "pct_change(value, 1) > 0 and value > wage_threshold_red",
                "label": "Wages hot + accelerating",
            },
            {
                "status": "amber",
                "formula": "value > wage_threshold_amber",
                "label": "Elevated ({value}%)",
            },
            {
                "status": "green",
                "formula": "true",
                "label": "Normal",
            },
        ],
        "params": {
            "event_type_filter": "Average Hourly Earnings",
            "wage_threshold_amber": 0.4,
            "wage_threshold_red": 0.5,
            "consecutive_required": 2,
            "history_lookback_months": 12,
        },
        "streak_condition": None,
    }


def _wage_dynamic_threshold() -> dict[str, Any]:
    return {
        "rules": [
            {
                "status": "red",
                "formula": "value > rolling_mean(value, 12) + std_20",
                "label": "Above 1-sigma of trailing avg",
            },
            {
                "status": "amber",
                "formula": "value > rolling_mean(value, 12)",
                "label": "Above 12m avg",
            },
            {
                "status": "green",
                "formula": "true",
                "label": "Below trailing avg",
            },
        ],
        "params": {
            "event_type_filter": "Average Hourly Earnings",
            "history_lookback_months": 24,
            "std_20": 0.1,
        },
        "streak_condition": None,
    }


def _diplomacy_short_window() -> dict[str, Any]:
    base = PANELS["diplomacy"].default_ruleset
    return {
        "rules": base["rules"],
        "params": {**base["params"], "window_days": 14, "window_amber_pct": 50},
        "streak_condition": None,
    }


def _diplomacy_long_window() -> dict[str, Any]:
    base = PANELS["diplomacy"].default_ruleset
    return {
        "rules": base["rules"],
        "params": {**base["params"], "window_days": 60, "window_amber_pct": 75},
        "streak_condition": None,
    }


PT_PRESETS: dict[str, dict[str, dict[str, Any]]] = {
    "oil": {
        "report_defaults": PANELS["oil"].default_ruleset,
        "ma_relative": _oil_ma_relative(),
        "volatility_adjusted": _oil_volatility_adjusted(),
    },
    "inflation": {
        "report_defaults": PANELS["inflation"].default_ruleset,
        "ma_relative": _inflation_pure_tip(),
        "volatility_adjusted": _inflation_relative_to_history(),
    },
    "fed_language": {
        "report_defaults": PANELS["fed_language"].default_ruleset,
        "ma_relative": _fed_conservative_keywords(),
        "volatility_adjusted": _fed_aggressive_keywords(),
    },
    "wage_growth": {
        "report_defaults": PANELS["wage_growth"].default_ruleset,
        "ma_relative": _wage_acceleration(),
        "volatility_adjusted": _wage_dynamic_threshold(),
    },
    "diplomacy": {
        "report_defaults": PANELS["diplomacy"].default_ruleset,
        "ma_relative": _diplomacy_short_window(),
        "volatility_adjusted": _diplomacy_long_window(),
    },
}
