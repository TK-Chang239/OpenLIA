import pytest
from pydantic import ValidationError

from openlia.macro_research.payloads import (
    DebtCycleData,
    DashHeader,
    ScoreRow,
    Provenance,
)


def test_minimal_debt_cycle_payload_validates():
    data = DebtCycleData(
        header=DashHeader(title="T1", subtitle="April 2026 · Dalio", pills=[]),
        cardSummary="summary",
        scorecard={
            "rows": [
                ScoreRow(
                    name="Govt debt / GDP",
                    sub="Q4 2025",
                    current="125.2%",
                    currentTone="red",
                    currentMeta="CEIC",
                    threshold="> 100%",
                    status="Critical",
                    statusTone="red",
                    fillPct=93,
                    fillTone="red",
                )
            ]
        },
        phaseBox={"title": "Late plateau", "body": "...", "tone": "amber"},
        analogPair={
            "analog": {"title": "1968-80", "body": "..."},
            "timeToConstraint": {"title": "3-7y", "body": "..."},
        },
        policySpace={
            "cards": [
                {
                    "label": "Rate cut headroom",
                    "value": "~150bps",
                    "valueTone": "amber",
                    "unit": "to ELB",
                    "note": "...",
                }
            ]
        },
        assetThesis={
            "gold": {"title": "Gold", "body": "..."},
            "longBond": {"title": "Bonds", "body": "..."},
        },
        watchlist={"rows": [{"tone": "red", "name": "spiral", "body": "..."}]},
        verdict={"title": "synthesis", "body": "...", "tone": "amber"},
        sources="CEIC/BEA",
        provenance=Provenance.LIVE,
        generated_at="2026-06-03T00:00:00Z",
    )
    assert data.scorecard["rows"][0].fillPct == 93
    assert data.provenance == Provenance.LIVE


def test_invalid_tone_rejected():
    with pytest.raises(ValidationError):
        ScoreRow(
            name="x",
            sub="y",
            current="1",
            currentTone="purple",
            currentMeta="m",
            threshold="t",
            status="s",
            statusTone="red",
            fillPct=1,
            fillTone="red",
        )
