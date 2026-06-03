"""AllWeatherData payload validation.

Fixture transcribed from frontend/src/lib/macro_research/dalio_copy/all_weather.ts
(ALL_WEATHER_FALLBACK) plus a `generated_at` timestamp. Asserts the typed
payload validates and round-trips the key fields the front end renders.
"""

import pytest
from openlia.macro_research.payloads import AllWeatherData, Provenance
from pydantic import ValidationError


def _all_weather_fixture() -> dict:
    """A complete, valid AllWeatherData as a JSON-ready dict.

    Transcribed (trimmed prose) from ALL_WEATHER_FALLBACK in all_weather.ts.
    """
    return {
        "header": {
            "title": "T3 · All-Weather allocation audit",
            "subtitle": "Benchmark: 60/40 (SPY/TLT) · April 2026",
            "pills": [
                {"tone": "red", "label": "Risk concentration: critical"},
                {"tone": "amber", "label": "Gold gap: 0% held vs ~15% guidance"},
            ],
        },
        "cardSummary": (
            "60/40 audit: 0% gold vs ~15% guidance, no autumn coverage. Equity vol dominates risk."
        ),
        "comparison": {
            "label": "Portfolio under audit vs All-Weather reference",
            "benchmark": {
                "title": "60/40 benchmark",
                "slices": [
                    {"label": "Equities", "pct": 60, "tone": "accent"},
                    {"label": "Long bonds", "pct": 40, "tone": "olive"},
                ],
            },
            "reference": {
                "title": "All-Weather reference",
                "slices": [
                    {"label": "Equities", "pct": 30, "tone": "accent"},
                    {"label": "Long bonds", "pct": 40, "tone": "olive"},
                    {"label": "Int. bonds", "pct": 15, "tone": "neutral"},
                    {"label": "Gold", "pct": 7.5, "tone": "amber"},
                    {"label": "Commodities", "pct": 7.5, "tone": "rust"},
                ],
            },
        },
        "coverage": {
            "label": "Section A — season coverage map",
            "cells": [
                {
                    "title": "Autumn (stagflation)",
                    "badgeLabel": "Exposed",
                    "badgeTone": "red",
                    "bodyTone": "red",
                    "body": "60/40 has no autumn coverage.",
                    "bridgeLabel": "All-Weather coverage",
                    "bridge": "gold (7.5%) + commodities (7.5%) = 15%.",
                },
            ],
        },
        "riskParity": {
            "label": "Section B — risk parity audit",
            "intro": "The core insight: capital weight != risk weight.",
            "benchmarkTitle": "60/40 — risk contribution by asset class",
            "benchmarkBars": [
                {"label": "Equities", "pct": 68},
                {"label": "Long bonds", "pct": 32},
            ],
            "referenceTitle": "All-Weather — risk contribution by asset class",
            "referenceBars": [
                {"label": "Equities", "pct": 38},
                {"label": "Long bonds", "pct": 35},
                {"label": "Int. bonds", "pct": 8},
                {"label": "Gold", "pct": 9},
                {"label": "Commodities", "pct": 10},
            ],
            "mechanism": {
                "title": "The risk parity mechanism explained",
                "body": "In the 60/40, equities at 60% capital weight dominate risk.",
            },
        },
        "gold": {
            "label": "Section C — gold allocation check",
            "title": "60/40 gold weight vs Dalio guidance ranges",
            "needles": [
                {"label": "60/40: 0%", "leftPct": 0, "tone": "red"},
                {"label": "AW base: 7.5%", "leftPct": 50, "tone": "amber"},
                {"label": "Stress env: ~15%", "leftPct": 75, "tone": "green"},
            ],
            "stats": [
                {
                    "label": "Current gold weight",
                    "value": "0%",
                    "valueTone": "red",
                    "note": "No gold in 60/40",
                },
                {
                    "label": "Allocation gap",
                    "value": "-15 pp",
                    "valueTone": "red",
                    "note": "To reach stress-env guidance from zero",
                },
            ],
            "rationale": {
                "title": "Gold allocation rationale",
                "body": "T1 + T2 + T5 all point to the same conclusion.",
            },
        },
        "caveats": {
            "label": "Section D — retail investor caveats",
            "cards": [
                {
                    "title": "Leverage assumption",
                    "body": "Designed for institutional investors with leverage.",
                },
                {
                    "title": "Bond allocation risk",
                    "body": "High bond allocation underperforms in inflationary regimes.",
                },
            ],
        },
        "stressTest": {
            "label": "Section E — Monte-Carlo stress test",
            "intro": "10,000-path 1-year simulation under baked reference parameters.",
            "distribution": {
                "title": "Base-case 1-year return distribution (user vs reference)",
                "bars": [
                    {"label": "5th pct", "userPct": -0.18, "refPct": -0.09},
                    {"label": "Median", "userPct": 0.06, "refPct": 0.05},
                    {"label": "95th pct", "userPct": 0.31, "refPct": 0.20},
                ],
            },
            "scenarios": [
                {
                    "name": "Equity crash / deleveraging",
                    "userMedianPct": -0.22,
                    "userP5Pct": -0.41,
                    "refMedianPct": -0.08,
                    "refP5Pct": -0.19,
                    "tone": "red",
                }
            ],
            "note": "Stress carried by scenario overlays; Gaussian draws.",
        },
        "verdict": {
            "title": "Synthesis verdict",
            "body": "The 60/40 concentrates ~87% of risk in the equity sleeve.",
        },
        "sources": "Volatility estimates: S&P 500 ~16-17%. Not investment advice.",
        "provenance": "live",
        "generated_at": "2026-06-03T00:00:00Z",
    }


def test_all_weather_payload_validates() -> None:
    data = AllWeatherData.model_validate(_all_weather_fixture())
    assert data.header.title.startswith("T3")
    assert len(data.header.pills) == 2
    assert data.comparison.benchmark.slices[0].tone == "accent"
    assert data.comparison.reference.slices[4].tone == "rust"
    assert data.coverage.cells[0].badgeTone == "red"
    assert data.riskParity.benchmarkBars[0].pct == 68
    assert data.gold.needles[0].tone == "red"
    assert data.verdict.title == "Synthesis verdict"
    assert data.provenance == Provenance.LIVE


def test_all_weather_provenance_defaults_to_live() -> None:
    fixture = _all_weather_fixture()
    del fixture["provenance"]
    data = AllWeatherData.model_validate(fixture)
    assert data.provenance == Provenance.LIVE


def test_all_weather_rejects_invalid_slice_tone() -> None:
    fixture = _all_weather_fixture()
    fixture["comparison"]["benchmark"]["slices"][0]["tone"] = "magenta"
    with pytest.raises(ValidationError):
        AllWeatherData.model_validate(fixture)


def test_all_weather_stress_test_validates() -> None:
    data = AllWeatherData.model_validate(_all_weather_fixture())
    assert data.stressTest.distribution.bars[0].userPct == -0.18
    row = data.stressTest.scenarios[0]
    assert row.name == "Equity crash / deleveraging"
    assert row.tone == "red"
    assert row.userP5Pct == -0.41
