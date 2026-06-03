"""FourSeasonsData payload validation.

Fixture transcribed from frontend/src/lib/macro_research/dalio_copy/four_seasons.ts
(FOUR_SEASONS_FALLBACK) plus a `generated_at` timestamp. Asserts the typed
payload validates and round-trips the key fields the front end renders.
"""

import pytest
from openlia.macro_research.payloads import FourSeasonsData, Provenance
from pydantic import ValidationError


def _four_seasons_fixture() -> dict:
    """A complete, valid FourSeasonsData as a JSON-ready dict.

    Transcribed (trimmed prose) from FOUR_SEASONS_FALLBACK in four_seasons.ts.
    """
    return {
        "header": {
            "title": "T2 · Four-seasons diagnostic — US",
            "subtitle": "April 2026 · data as of 10 Apr 2026",
            "pills": [
                {"tone": "amber", "label": "Transitioning summer -> autumn"},
                {"tone": "purple", "label": "Mixed confidence"},
            ],
        },
        "cardSummary": (
            "Manufacturing PMI rising, Q4 GDP +0.5%, CPI 3.3%. "
            "Transitioning summer -> autumn (stagflation)."
        ),
        "scorecard": {
            "rows": [
                {
                    "name": "Manufacturing PMI",
                    "sub": "ISM Mar 2026",
                    "fillPct": 72,
                    "fillTone": "green",
                    "current": "52.7",
                    "currentTone": "green",
                    "currentMeta": "3rd month above 50",
                    "trend": "Jan 50.9 -> Feb 52.4 -> Mar 52.7. Modestly rising.",
                    "axisLabel": "Growth rising",
                    "axisTone": "green",
                    "direction": "up",
                    "directionLabel": "Rising",
                    "directionTone": "green",
                },
                {
                    "name": "HY credit spread (OAS)",
                    "sub": "ICE BofA / FRED Apr 2026",
                    "fillPct": 30,
                    "fillTone": "blue",
                    "current": "~2.9%",
                    "currentTone": "blue",
                    "currentMeta": "Apr 9 2026 - tight",
                    "trend": "~2.9% OAS historically tight - not pricing recession.",
                    "axisLabel": "Credit stable",
                    "axisTone": "green",
                    "direction": "flat",
                    "directionLabel": "Flat / tight",
                    "directionTone": "green",
                },
            ],
        },
        "quadrant": {
            "seasons": {
                "tl": {
                    "name": "Autumn",
                    "sub": "Growth falling · inflation rising (stagflation)",
                    "pillLabel": "Gold · real assets",
                    "tone": "red",
                },
                "tr": {
                    "name": "Summer",
                    "sub": "Growth rising · inflation rising",
                    "pillLabel": "Commodities · TIPS",
                    "tone": "amber",
                },
                "bl": {
                    "name": "Winter",
                    "sub": "Growth falling · inflation falling",
                    "pillLabel": "Long bonds · cash",
                    "tone": "blue",
                },
                "br": {
                    "name": "Spring",
                    "sub": "Growth rising · inflation falling",
                    "pillLabel": "Equities",
                    "tone": "green",
                },
            },
            "markers": [
                {"label": "Apr 2026", "xPct": 46, "yPct": 14, "variant": "now", "tone": "red"},
                {"label": "Jan 2026", "xPct": 50, "yPct": 30, "variant": "prev", "tone": "amber"},
            ],
        },
        "verdict": {
            "title": "Transitioning summer -> autumn",
            "body": "GDP collapsed from 4.4% to 0.5% annualised. Growth falling + inflation rising.",
            "sideCards": [
                {
                    "label": "Confidence level",
                    "value": "Mixed",
                    "valueTone": "amber",
                    "note": "Growth axis ambiguous; inflation axis clearer",
                },
                {
                    "label": "Nearest comparable period",
                    "value": "H1 2022",
                    "valueTone": "blue",
                    "note": "And early 1974 (oil shock + slowing growth)",
                },
            ],
        },
        "parallels": {
            "cards": [
                {
                    "title": "H1 2022 - the closer parallel",
                    "body": "Inflation re-accelerated driven by energy. Real GDP growth slowed.",
                },
                {
                    "title": "1973-74 - the structural analog",
                    "body": "Arab oil embargo triggered an energy spike while growth was decelerating.",
                },
            ],
        },
        "transitionRisk": {
            "intro": "The primary risk is a confirmed move into full autumn.",
            "bull": {
                "title": "If summer persists (bull case)",
                "body": "Iran ceasefire holds and oil retraces. Core inflation stays at 2.6%.",
            },
            "bear": {
                "title": "If autumn confirms (bear case)",
                "body": "Iran war drags on, energy inflation feeds into services. PMI rolls below 50.",
            },
            "keyIndicator": {
                "title": "Key indicator to watch",
                "body": "BEA Q1 2026 GDP advance estimate (Apr 30).",
            },
        },
        "assetPlaybook": {
            "cards": [
                {
                    "tone": "amber",
                    "label": "Commodities",
                    "posture": "Summer + autumn tailwind",
                    "body": "Energy is the most direct play on the Iran war.",
                },
                {
                    "tone": "red",
                    "label": "Gold",
                    "posture": "Autumn-specific signal strengthening",
                    "body": "Gold is the canonical autumn asset.",
                },
            ],
        },
        "notes": [
            {
                "title": "Portfolio stress test",
                "body": "A conventional 60/40 portfolio faces its worst structural alignment.",
            },
            {
                "title": "One key nuance: the growth signal is split",
                "body": "Manufacturing PMI at 52.7 but real GDP at +0.5% tells the opposite story.",
            },
        ],
        "sources": "ISM PMI Mar 2026; BLS CPI Mar 2026; BEA GDP Q4 2025. Not investment advice.",
        "generated_at": "2026-06-03T00:00:00Z",
    }


def test_four_seasons_payload_validates_and_round_trips():
    fixture = _four_seasons_fixture()

    data = FourSeasonsData.model_validate(fixture)

    assert data.header.title.startswith("T2")
    assert data.header.pills[1].tone == "purple"
    assert data.scorecard.rows[0].direction == "up"
    assert data.scorecard.rows[0].axisTone == "green"
    assert data.scorecard.rows[1].currentTone == "blue"
    assert data.quadrant.seasons.tl.tone == "red"
    assert data.quadrant.seasons.bl.tone == "blue"
    assert data.quadrant.markers[0].variant == "now"
    assert data.quadrant.markers[1].variant == "prev"
    assert data.verdict.sideCards[0].valueTone == "amber"
    assert data.parallels.cards[0].title.startswith("H1 2022")
    assert data.transitionRisk.bull.title.startswith("If summer")
    assert data.transitionRisk.keyIndicator.title == "Key indicator to watch"
    assert data.assetPlaybook.cards[1].tone == "red"
    assert data.notes[0].title == "Portfolio stress test"
    assert data.provenance == Provenance.LIVE

    # Round-trip: dumping and re-validating preserves the shape.
    dumped = data.model_dump(mode="json")
    again = FourSeasonsData.model_validate(dumped)
    assert again == data


def test_four_seasons_invalid_marker_variant_rejected():
    fixture = _four_seasons_fixture()
    fixture["quadrant"]["markers"][0]["variant"] = "future"

    with pytest.raises(ValidationError):
        FourSeasonsData.model_validate(fixture)


def test_four_seasons_invalid_direction_rejected():
    fixture = _four_seasons_fixture()
    fixture["scorecard"]["rows"][0]["direction"] = "sideways"

    with pytest.raises(ValidationError):
        FourSeasonsData.model_validate(fixture)
