"""End-to-end world_order dashboard run through the real tool-use loop.

Mirrors test_runner_debt_cycle.py: a fake adapter scripts two turns —
classify_world_order, then emit_dashboard with a complete WorldOrderData
payload. The runner is exercised for real (no mocking of the loop); the
assertions confirm the typed payload round-trips into ``RunResult`` and
validates as WorldOrderData.
"""

import pytest
from openlia.llm.runtime.report_dash_mr import (
    LLMSession,
    MbDataTransports,
    Runner,
)
from openlia.llm.runtime.report_dash_mr.schemas import EnabledConnectors, RunRequest
from openlia.macro_research.payloads import WorldOrderData

from ._fakes import FakeLLMProvider, script_tool_calls


def _complete_world_order_payload() -> dict:
    """A complete, valid WorldOrderData as a JSON-ready dict.

    Shape mirrors packages/core/tests/macro_research/test_payloads_world_order.py.
    """
    return {
        "header": {
            "title": "World Order",
            "subtitle": "June 2026 · Dalio",
            "pills": [{"tone": "red", "label": "Stage 5 - pre-breakdown"}],
        },
        "cardSummary": "USD reserve share eroding; central banks accumulating gold.",
        "scorecard": {
            "label": "Section A - reserve currency health indicators",
            "rows": [
                {
                    "name": "USD share of global FX reserves",
                    "sub": "IMF COFER Q1 2026",
                    "current": "56.9%",
                    "currentTone": "amber",
                    "currentMeta": "Q1 2026",
                    "fillPct": 62,
                    "fillTone": "amber",
                    "trend": "Down from 71.2% in 1999.",
                    "signalLabel": "Gradual drift",
                    "signalTone": "amber",
                }
            ],
        },
        "reserveChart": {
            "title": "USD reserve share - long-run decline",
            "years": [1999, 2025],
            "series": [
                {"label": "USD", "isPrimary": True, "values": [71.2, 56.9]},
                {"label": "EUR", "values": [17.9, 20.3]},
            ],
        },
        "empireCycle": {
            "label": "Section B - empire cycle stage",
            "stripTitle": "Dalio's Big Cycle - six stages",
            "stages": [
                {
                    "num": "4",
                    "name": "Pressure",
                    "range": "2008-2020",
                    "state": "past",
                    "weight": 4,
                },
                {"num": "5", "name": "Pre-breakdown", "range": "2020-now", "state": "active"},
                {"num": "6", "name": "Breakdown", "range": "ahead", "state": "future"},
            ],
            "quote": {
                "title": "Dalio classification",
                "body": "We are now in a new Stage 5.",
                "attribution": "- Ray Dalio, March 2026",
                "tone": "red",
            },
            "markersTitle": "Stage 5 markers",
            "markers": [
                {
                    "tone": "red",
                    "pillLabel": "Confirmed",
                    "leadPhrase": "Rising government debts",
                    "body": "US debt/GDP at 125%.",
                }
            ],
        },
        "analogs": {
            "label": "Historical analog",
            "cells": [
                {
                    "era": "Pre-1971 US",
                    "tone": "green",
                    "body": "Reserve currency under fiscal pressure.",
                }
            ],
        },
        "wealthShift": {
            "label": "Section C - great wealth shift signals",
            "intro": "Shift from financial wealth to real wealth.",
            "rows": [
                {
                    "tone": "red",
                    "pillLabel": "Institutional",
                    "leadPhrase": "Central bank gold accumulation.",
                    "body": "Four consecutive years above 800t.",
                }
            ],
            "assessment": {
                "title": "Wealth shift stage assessment: mid-stage",
                "body": "Institutional signal at full intensity.",
            },
        },
        "investment": {
            "label": "Section D - investment implications",
            "goldRange": {
                "title": "Gold allocation range",
                "stats": [
                    {"label": "Normal env", "value": "5-10%", "highlight": False},
                    {"label": "T4 justified", "value": "~15%", "highlight": True},
                ],
                "body": "World order reading justifies stress-environment guidance.",
            },
            "currency": {
                "title": "Currency exposure guidance",
                "rows": [
                    {
                        "name": "USD",
                        "badgeLabel": "Reduce structural weight",
                        "badgeTone": "amber",
                        "body": "DXY down 9.4% in 2025.",
                    }
                ],
            },
            "sovereignBond": {
                "title": "Sovereign bond risk premium",
                "intro": "World order lens adds a structural risk premium.",
                "pair": {
                    "left": {
                        "title": "What the yield does NOT fully price",
                        "body": "Erosion of the foreign official buyer base.",
                    },
                    "right": {
                        "title": "What would trigger a repricing event",
                        "body": "A disorderly abandonment of Treasuries.",
                    },
                },
            },
        },
        "verdict": {
            "title": "T4 synthesis",
            "body": "Dalio has classified the US as Stage 5.",
            "tone": "amber",
        },
        "sources": "IMF COFER, WGC, US Treasury TIC. Not investment advice.",
        "provenance": "live",
        "generated_at": "2026-06-03T00:00:00Z",
    }


def _req() -> RunRequest:
    return RunRequest(
        dashboard_slug="world_order",
        subject="World Order",
        template=None,
        provider_kind="stub",
        model="stub",
        enabled_connectors=EnabledConnectors(),
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
async def test_runner_classify_then_emit_world_order():
    payload = _complete_world_order_payload()
    script = [
        script_tool_calls(
            (
                "classify_world_order",
                {
                    "usd_reserve_share": 56.9,
                    "cb_gold_purchases": 863.0,
                    "foreign_treasury_trend": 8.0,
                    "dxy": 98.7,
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
    assert result.template_id == "world_order"

    validated = WorldOrderData.model_validate(result.payload)
    assert validated.scorecard.rows
    assert validated.verdict.tone in {"red", "amber", "green", "blue"}
    assert validated.empireCycle.stages[1].state == "active"
