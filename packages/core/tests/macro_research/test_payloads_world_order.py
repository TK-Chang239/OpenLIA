"""WorldOrderData payload validation.

Fixture transcribed from frontend/src/lib/macro_research/dalio_copy/world_order.ts
(WORLD_ORDER_FALLBACK) plus a `generated_at` timestamp. Asserts the typed
payload validates and round-trips the key fields the front end renders.
"""

import pytest
from openlia.macro_research.payloads import Provenance, WorldOrderData
from pydantic import ValidationError


def _world_order_fixture() -> dict:
    """A complete, valid WorldOrderData as a JSON-ready dict.

    Transcribed (trimmed prose) from WORLD_ORDER_FALLBACK in world_order.ts.
    """
    return {
        "header": {
            "title": "T4 · World order assessment — US empire cycle",
            "subtitle": "April 2026 · Dalio framework · annual cadence",
            "pills": [
                {"tone": "red", "label": "Stage 5 — pre-breakdown"},
                {"tone": "amber", "label": "Wealth shift: mid-stage"},
            ],
        },
        "cardSummary": (
            "USD reserve share 56.9% (down from 71.2% in 1999), central banks "
            "bought 863t of gold in 2025. Stage 5 — pre-breakdown."
        ),
        "scorecard": {
            "label": "Section A — reserve currency health indicators",
            "rows": [
                {
                    "name": "USD share of global FX reserves",
                    "sub": "IMF COFER Q3 2025",
                    "current": "56.9%",
                    "currentTone": "amber",
                    "currentMeta": "Q3 2025",
                    "fillPct": 62,
                    "fillTone": "amber",
                    "trend": "Down from 71.2% in 1999. Lowest in decades.",
                    "signalLabel": "Gradual drift",
                    "signalTone": "amber",
                },
                {
                    "name": "Net central bank gold purchases",
                    "sub": "World Gold Council 2025 full year",
                    "current": "863t",
                    "currentTone": "red",
                    "currentMeta": "FY2025 net",
                    "fillPct": 86,
                    "fillTone": "red",
                    "trend": "4th consecutive year above 800t.",
                    "signalLabel": "Structural",
                    "signalTone": "red",
                },
            ],
        },
        "reserveChart": {
            "title": "USD reserve share - long-run decline (1999-2026)",
            "years": [1999, 2009, 2019, 2025],
            "series": [
                {
                    "label": "USD",
                    "isPrimary": True,
                    "values": [71.2, 61.9, 60.9, 56.9],
                },
                {
                    "label": "EUR",
                    "values": [17.9, 27.7, 20.1, 20.3],
                },
            ],
        },
        "empireCycle": {
            "label": "Section B — empire cycle stage",
            "stripTitle": "Dalio's Big Cycle — six stages (75-year typical arc)",
            "stages": [
                {
                    "num": "4",
                    "name": "Pressure",
                    "range": "2008-2020",
                    "state": "past",
                    "weight": 4,
                },
                {
                    "num": "5",
                    "name": "Pre-breakdown",
                    "range": "2020-now <-",
                    "state": "active",
                },
                {
                    "num": "6",
                    "name": "Breakdown",
                    "range": "ahead",
                    "state": "future",
                },
            ],
            "quote": {
                "title": "Dalio's direct classification — March 2026",
                "body": "We are now in a new Stage 5.",
                "attribution": "— Ray Dalio, Fortune, March 2026",
                "tone": "red",
            },
            "markersTitle": "Stage 5 markers — status check April 2026",
            "markers": [
                {
                    "tone": "red",
                    "pillLabel": "Confirmed",
                    "leadPhrase": "Large and rising government debts",
                    "body": "US debt/GDP at 125%.",
                },
                {
                    "tone": "amber",
                    "pillLabel": "Not yet",
                    "leadPhrase": "Hot war between major powers",
                    "body": "Stage 6 not yet reached.",
                },
            ],
        },
        "analogs": {
            "label": "Historical analog — similarities and differences",
            "cells": [
                {
                    "era": "Pre-1971 US (Bretton Woods late stage)",
                    "tone": "green",
                    "body": "Reserve currency under pressure from fiscal excess.",
                },
                {
                    "era": "British pound decline (1918-1944)",
                    "tone": "amber",
                    "body": "Reserve currency declining gradually over decades.",
                },
            ],
        },
        "wealthShift": {
            "label": "Section C — great wealth shift signals",
            "intro": "Dalio's shift from financial wealth to real wealth.",
            "rows": [
                {
                    "tone": "red",
                    "pillLabel": "Institutional",
                    "leadPhrase": "Central bank gold accumulation.",
                    "body": "Four consecutive years above 800t.",
                },
            ],
            "assessment": {
                "title": "Wealth shift stage assessment: mid-stage",
                "body": "The institutional signal is at full intensity.",
            },
        },
        "investment": {
            "label": "Section D — investment implications",
            "goldRange": {
                "title": "Gold allocation range — world order justification",
                "stats": [
                    {"label": "Normal env", "value": "5-10%", "highlight": False},
                    {"label": "T4 justified", "value": "~15%", "highlight": True},
                ],
                "body": "T4 world order reading justifies stress-environment guidance.",
            },
            "currency": {
                "title": "Currency exposure guidance",
                "rows": [
                    {
                        "name": "USD (long positions)",
                        "badgeLabel": "Reduce structural weight",
                        "badgeTone": "amber",
                        "body": "DXY down 9.4% in 2025.",
                    },
                    {
                        "name": "Gold (hard currency proxy)",
                        "badgeLabel": "Strategic core position",
                        "badgeTone": "red",
                        "body": "No counterparty risk.",
                    },
                ],
            },
            "sovereignBond": {
                "title": "Sovereign bond risk premium — T4 perspective",
                "intro": "The world order lens adds a structural risk premium.",
                "pair": {
                    "left": {
                        "title": "What the yield does NOT fully price",
                        "body": "The structural erosion of the foreign buyer base.",
                    },
                    "right": {
                        "title": "What would trigger a repricing event",
                        "body": "A disorderly abandonment of Treasuries.",
                    },
                },
            },
        },
        "verdict": {
            "title": "T4 synthesis — bottom line",
            "body": "Dalio has classified the US as Stage 5.",
            "tone": "amber",
        },
        "sources": "IMF COFER Q3 2025; WGC 2025; TIC Jan 2026. Not investment advice.",
        "generated_at": "2026-06-03T00:00:00Z",
    }


def test_world_order_payload_validates_and_round_trips():
    fixture = _world_order_fixture()

    data = WorldOrderData.model_validate(fixture)

    assert data.header.title.startswith("T4")
    assert data.scorecard.label == "Section A — reserve currency health indicators"
    assert data.scorecard.rows[0].signalTone == "amber"
    assert data.reserveChart.series[0].isPrimary is True
    assert data.reserveChart.series[1].isPrimary is False
    assert data.empireCycle.stages[1].state == "active"
    assert data.empireCycle.stages[1].weight is None
    assert data.empireCycle.stages[0].weight == 4
    assert data.wealthShift.assessment.title.startswith("Wealth shift")
    assert data.investment.goldRange.stats[1].highlight is True
    assert data.investment.sovereignBond.pair.left.title.startswith("What the yield")
    assert data.verdict.tone == "amber"
    assert data.provenance == Provenance.LIVE


def test_world_order_invalid_stage_state_rejected():
    fixture = _world_order_fixture()
    fixture["empireCycle"]["stages"][0]["state"] = "ancient"

    with pytest.raises(ValidationError):
        WorldOrderData.model_validate(fixture)
