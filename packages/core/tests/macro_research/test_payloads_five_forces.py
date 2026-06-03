"""FiveForcesData payload validation.

Fixture transcribed from frontend/src/lib/macro_research/dalio_copy/five_forces.ts
(FIVE_FORCES_FALLBACK) plus a `generated_at` timestamp. Asserts the typed
payload validates and round-trips the key fields the front end renders.
"""

import pytest
from openlia.macro_research.payloads import FiveForcesData, Provenance
from pydantic import ValidationError


def _five_forces_fixture() -> dict:
    """A complete, valid FiveForcesData as a JSON-ready dict.

    Transcribed (trimmed prose) from FIVE_FORCES_FALLBACK in five_forces.ts.
    """
    return {
        "header": {
            "title": "Five interlocking forces - April 2026",
            "subtitle": "Dalio framework scored against current data",
            "badges": [
                {"tone": "red", "label": "4 Critical"},
                {"tone": "amber", "label": "1 High"},
            ],
        },
        "cardSummary": "5 of 5 forces active - 4 Critical, 1 High.",
        "scorecard": {
            "label": "Section A - force intensity scorecard",
            "rows": [
                {
                    "forceLabel": "Force 1",
                    "forceSub": "Debt & money cycle",
                    "pillTone": "red",
                    "pillLabel": "Critical",
                    "scorePct": 92,
                    "scoreTone": "red",
                    "scoreValue": "9.2 / 10",
                    "body": "US debt/GDP now ~122.5%.",
                },
                {
                    "forceLabel": "Force 4",
                    "forceSub": "Technology wave",
                    "pillTone": "amber",
                    "pillLabel": "High",
                    "scorePct": 72,
                    "scoreTone": "amber",
                    "scoreValue": "7.2 / 10",
                    "body": "35.9% of US workers used generative AI by Dec 2025.",
                },
            ],
        },
        "loops": {
            "label": "Section B - reinforcement loop analysis",
            "blocks": [
                {
                    "title": "Primary loop - debt -> politics -> more debt",
                    "arrows": [
                        {"fromLabel": "F1 - Debt crisis", "toLabel": "F2 - Populist anger"},
                        {"fromLabel": "F2 - Gridlock", "toLabel": "F1 - No consolidation"},
                    ],
                    "body": "High debt constrains government and fuels populism.",
                },
            ],
            "active": {
                "countText": "5 / 5",
                "countTone": "red",
                "title": "All forces simultaneously active",
                "body": "Co-activation of all five is historically rare.",
            },
        },
        "signals": {
            "label": "Section C - current market data",
            "cards": [
                {
                    "label": "Gold spot (XAUUSD)",
                    "value": "~$3,200",
                    "unit": "per troy oz, Apr 2026",
                    "note": "ATH $5,595 hit Jan 2026.",
                },
            ],
        },
        "goldAllocation": {
            "label": "Section D - gold allocation signal",
            "block": {
                "title": "Dalio allocation range vs current environment",
                "ticks": ["0%", "5%", "10%", "15%", "20%+"],
                "stats": [
                    {
                        "label": "All-Weather baseline",
                        "value": "7.5%",
                        "note": "Normal macro regime",
                        "highlight": False,
                    },
                    {
                        "label": "Stress environment (Oct 2025)",
                        "value": "~15%",
                        "note": "Dalio's explicit guidance",
                        "highlight": True,
                    },
                ],
                "body": "With all five forces active, the environment satisfies Dalio's criteria.",
            },
        },
        "scenarios": {
            "label": "Section E - what would change the assessment",
            "cards": [
                {
                    "variant": "bull",
                    "title": "Bull case for forces decoupling",
                    "body": "US fiscal grand bargain reduces deficit trajectory.",
                },
                {
                    "variant": "bear",
                    "title": "Bear case for all five intensifying",
                    "body": "Hormuz closure triggers stagflation spike.",
                },
            ],
        },
        "verdict": {
            "title": "Synthesis verdict",
            "body": "The five-forces framework registers its most extreme reading.",
        },
        "sources": "CRFB, CBO, World Gold Council. Not investment advice.",
        "provenance": "live",
        "generated_at": "2026-06-03T00:00:00Z",
    }


def test_five_forces_payload_validates() -> None:
    data = FiveForcesData.model_validate(_five_forces_fixture())
    assert data.header.title.startswith("Five interlocking forces")
    assert len(data.header.badges) == 2
    assert data.header.badges[0].tone == "red"
    assert data.scorecard.rows[0].pillTone == "red"
    assert data.scorecard.rows[0].scorePct == 92
    assert data.loops.blocks[0].arrows[0].fromLabel == "F1 - Debt crisis"
    assert data.loops.active.countText == "5 / 5"
    assert data.loops.active.countTone == "red"
    assert data.signals.cards[0].label == "Gold spot (XAUUSD)"
    assert data.goldAllocation.block.stats[1].highlight is True
    assert data.scenarios.cards[0].variant == "bull"
    assert data.scenarios.cards[1].variant == "bear"
    assert data.verdict.title == "Synthesis verdict"
    assert data.provenance == Provenance.LIVE


def test_five_forces_provenance_defaults_to_live() -> None:
    fixture = _five_forces_fixture()
    del fixture["provenance"]
    data = FiveForcesData.model_validate(fixture)
    assert data.provenance == Provenance.LIVE


def test_five_forces_rejects_invalid_badge_tone() -> None:
    fixture = _five_forces_fixture()
    fixture["header"]["badges"][0]["tone"] = "magenta"
    with pytest.raises(ValidationError):
        FiveForcesData.model_validate(fixture)


def test_five_forces_rejects_invalid_scenario_variant() -> None:
    fixture = _five_forces_fixture()
    fixture["scenarios"]["cards"][0]["variant"] = "sideways"
    with pytest.raises(ValidationError):
        FiveForcesData.model_validate(fixture)
