"""End-to-end five_forces dashboard run through the real tool-use loop.

Mirrors test_runner_all_weather.py: a fake adapter scripts three turns —
classify_five_forces, analyze_five_forces_network, then emit_dashboard with a
complete FiveForcesData payload. The runner is exercised for real (no mocking
of the loop); the assertions confirm the typed payload round-trips into
``RunResult`` and validates as FiveForcesData.
"""

import pytest
from openlia.llm.runtime.report_dash_mr import (
    LLMSession,
    MbDataTransports,
    Runner,
)
from openlia.llm.runtime.report_dash_mr.schemas import EnabledConnectors, RunRequest
from openlia.macro_research.payloads import FiveForcesData

from ._fakes import FakeLLMProvider, script_tool_calls


def _complete_five_forces_payload() -> dict:
    """A complete, valid FiveForcesData as a JSON-ready dict.

    Shape mirrors packages/core/tests/macro_research/test_payloads_five_forces.py.
    """
    return {
        "header": {
            "title": "Five interlocking forces - June 2026",
            "subtitle": "Dalio framework scored against current data",
            "badges": [
                {"tone": "red", "label": "3 Critical"},
                {"tone": "amber", "label": "1 High"},
            ],
        },
        "cardSummary": "3 of 5 forces active - elevated regime.",
        "scorecard": {
            "label": "Section A - force intensity scorecard",
            "rows": [
                {
                    "forceLabel": "Force 1",
                    "forceSub": "Debt & money cycle",
                    "pillTone": "red",
                    "pillLabel": "Critical",
                    "scorePct": 80,
                    "scoreTone": "red",
                    "scoreValue": "8.0 / 10",
                    "body": "Seeded from the cached Debt Cycle (Late Plateau).",
                },
            ],
        },
        "loops": {
            "label": "Section B - reinforcement loop analysis",
            "blocks": [
                {
                    "title": "Primary loop - debt -> politics",
                    "arrows": [
                        {"fromLabel": "F1 - Debt", "toLabel": "F2 - Populism"},
                    ],
                    "body": "High debt fuels populist gridlock.",
                },
            ],
            "active": {
                "countText": "3 / 5",
                "countTone": "amber",
                "title": "Elevated",
                "body": "Three forces simultaneously active.",
            },
            "network": {
                "label": "Influence network (current)",
                "edges": [
                    {"fromLabel": "Debt / money", "toLabel": "Internal politics", "strength": 0.48},
                ],
                "projections": [
                    {"force": "Debt / money", "current": 8.0, "projected": 7.8, "delta": -0.2},
                    {"force": "Internal politics", "current": 7.0, "projected": 7.4, "delta": 0.4},
                    {"force": "Geopolitical", "current": 5.0, "projected": 5.3, "delta": 0.3},
                    {"force": "Technology", "current": 7.0, "projected": 6.9, "delta": -0.1},
                    {"force": "Nature", "current": 4.0, "projected": 4.2, "delta": 0.2},
                ],
                "amplifier": "Debt / money",
                "absorber": "Internal politics",
                "contagion": 0.48,
                "contagionLabel": "Spreading",
            },
        },
        "signals": {
            "label": "Section C - current market data",
            "cards": [
                {
                    "label": "Gold spot",
                    "value": "~$3,200",
                    "unit": "per oz",
                    "note": "Correcting from ATH.",
                },
            ],
        },
        "goldAllocation": {
            "label": "Section D - gold allocation signal",
            "block": {
                "title": "Dalio allocation range",
                "ticks": ["0%", "5%", "10%", "15%"],
                "stats": [
                    {
                        "label": "Stress environment",
                        "value": "~15%",
                        "note": "Dalio guidance",
                        "highlight": True,
                    },
                ],
                "body": "Elevated regime supports a structural gold position.",
            },
        },
        "scenarios": {
            "label": "Section E - what would change the assessment",
            "cards": [
                {"variant": "bull", "title": "Bull case", "body": "Forces decouple."},
                {"variant": "bear", "title": "Bear case", "body": "All five intensify."},
            ],
        },
        "verdict": {
            "title": "Synthesis verdict",
            "body": "Three forces active; elevated but not yet a turning point.",
        },
        "sources": "CBO, World Gold Council. Not investment advice.",
        "provenance": "live",
        "generated_at": "2026-06-03T00:00:00Z",
    }


def _req() -> RunRequest:
    return RunRequest(
        dashboard_slug="five_forces",
        subject="Five Forces",
        template=None,
        provider_kind="stub",
        model="stub",
        enabled_connectors=EnabledConnectors(),
        data_context="F1 (debt/money): 8 (Late Plateau). F3 (geopolitical): 5 (Mid stage).",
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
async def test_runner_classify_then_emit_five_forces():
    payload = _complete_five_forces_payload()
    script = [
        script_tool_calls(
            (
                "classify_five_forces",
                {
                    "debt_money": 8,
                    "political": 7,
                    "geopolitical": 5,
                    "technology": 7,
                    "natural": 4,
                },
            )
        ),
        script_tool_calls(
            (
                "analyze_five_forces_network",
                {
                    "debt_money": 8,
                    "political": 7,
                    "geopolitical": 5,
                    "technology": 7,
                    "natural": 4,
                },
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
    assert result.template_id == "five_forces"

    validated = FiveForcesData.model_validate(result.payload)
    assert validated.header.badges[0].tone == "red"
    assert validated.scorecard.rows[0].scorePct == 80
    assert validated.loops.active.countText == "3 / 5"
    assert validated.scenarios.cards[1].variant == "bear"
    assert validated.verdict.title == "Synthesis verdict"
    assert validated.loops.network.amplifier == "Debt / money"
    assert validated.loops.network.contagionLabel == "Spreading"
