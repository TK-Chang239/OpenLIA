"""End-to-end all_weather dashboard run through the real tool-use loop.

Mirrors test_runner_world_order.py: a fake adapter scripts two turns —
classify_all_weather (with the weights from the injected data_context),
then emit_dashboard with a complete AllWeatherData payload. The runner is
exercised for real (no mocking of the loop); the assertions confirm the
typed payload round-trips into ``RunResult`` and validates as AllWeatherData.
"""

import pytest
from openlia.llm.runtime.report_dash_mr import (
    LLMSession,
    MbDataTransports,
    Runner,
)
from openlia.llm.runtime.report_dash_mr.schemas import EnabledConnectors, RunRequest
from openlia.macro_research.payloads import AllWeatherData

from ._fakes import FakeLLMProvider, script_tool_calls


def _complete_all_weather_payload() -> dict:
    """A complete, valid AllWeatherData as a JSON-ready dict.

    Shape mirrors packages/core/tests/macro_research/test_payloads_all_weather.py.
    """
    return {
        "header": {
            "title": "T3 - All-Weather allocation audit",
            "subtitle": "Benchmark: 60/40 - June 2026",
            "pills": [{"tone": "red", "label": "Risk concentration: critical"}],
        },
        "cardSummary": "60/40 audit: equity vol dominates risk; no autumn coverage.",
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
            "label": "Section A - season coverage map",
            "cells": [
                {
                    "title": "Autumn (stagflation)",
                    "badgeLabel": "Exposed",
                    "badgeTone": "red",
                    "bodyTone": "red",
                    "body": "60/40 has no autumn coverage.",
                    "bridgeLabel": "All-Weather coverage",
                    "bridge": "gold + commodities = 15%.",
                }
            ],
        },
        "riskParity": {
            "label": "Section B - risk parity audit",
            "intro": "Capital weight != risk weight.",
            "benchmarkTitle": "60/40 - risk contribution",
            "benchmarkBars": [
                {"label": "Equities", "pct": 68},
                {"label": "Long bonds", "pct": 32},
            ],
            "referenceTitle": "All-Weather - risk contribution",
            "referenceBars": [
                {"label": "Equities", "pct": 38},
                {"label": "Long bonds", "pct": 35},
            ],
            "mechanism": {"title": "Mechanism", "body": "Equity vol dominates a 60/40."},
        },
        "gold": {
            "label": "Section C - gold allocation check",
            "title": "60/40 gold weight vs guidance",
            "needles": [{"label": "60/40: 0%", "leftPct": 0, "tone": "red"}],
            "stats": [
                {
                    "label": "Current gold weight",
                    "value": "0%",
                    "valueTone": "red",
                    "note": "No gold in 60/40",
                }
            ],
            "rationale": {"title": "Rationale", "body": "Debasement precondition active."},
        },
        "caveats": {
            "label": "Section D - retail investor caveats",
            "cards": [{"title": "Leverage assumption", "body": "Designed for leverage."}],
        },
        "verdict": {
            "title": "Synthesis verdict",
            "body": "The 60/40 concentrates risk in equities.",
        },
        "sources": "Volatility estimates. Not investment advice.",
        "provenance": "live",
        "generated_at": "2026-06-03T00:00:00Z",
    }


def _req() -> RunRequest:
    return RunRequest(
        dashboard_slug="all_weather",
        subject="All-Weather",
        template=None,
        provider_kind="stub",
        model="stub",
        enabled_connectors=EnabledConnectors(),
        data_context="Portfolio weights: equities 0.6, long_bonds 0.4",
    )


def _transports() -> MbDataTransports:
    return MbDataTransports(
        quotes=lambda tickers: [],
        prices=lambda ticker, rng: [],
        news=lambda **kwargs: [],
        economic_calendar=lambda window: [],
        macro_indicators=lambda keys: {},
    )


@pytest.mark.asyncio
async def test_runner_classify_then_emit_all_weather():
    payload = _complete_all_weather_payload()
    script = [
        script_tool_calls(
            (
                "classify_all_weather",
                {"weights": {"equities": 0.6, "long_bonds": 0.4}},
            )
        ),
        script_tool_calls(("emit_dashboard", {"payload": payload})),
    ]
    session = LLMSession.create(provider_kind="stub", model="stub")
    session.attach_adapter(FakeLLMProvider(scripted_responses=script))
    runner = Runner(request=_req(), transports=_transports(), max_turns=10)

    result = await runner.run(session=session)

    assert result.status == "completed"
    assert result.payload is not None
    assert result.template_id == "all_weather"

    validated = AllWeatherData.model_validate(result.payload)
    assert validated.comparison.benchmark.slices[0].tone == "accent"
    assert validated.gold.needles[0].tone == "red"
    assert validated.verdict.title == "Synthesis verdict"
