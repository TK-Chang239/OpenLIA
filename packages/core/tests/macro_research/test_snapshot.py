from datetime import UTC, datetime

from openlia.macro_research.payloads import DebtCycleData
from openlia.macro_research.snapshot import debt_cycle_phase_from_payload


def _payload(phase_title: str) -> DebtCycleData:
    return DebtCycleData(
        header={"title": "T1", "subtitle": "s", "pills": []},
        cardSummary="x",
        scorecard={"rows": []},
        phaseBox={"title": phase_title, "body": "b", "tone": "amber"},
        analogPair={
            "analog": {"title": "a", "body": "b"},
            "timeToConstraint": {"title": "t", "body": "b"},
        },
        policySpace={"cards": []},
        assetThesis={"gold": {"title": "g", "body": "b"}, "longBond": {"title": "l", "body": "b"}},
        watchlist={"rows": []},
        verdict={"title": "v", "body": "b", "tone": "amber"},
        sources="s",
        generated_at=datetime.now(UTC),
    )


def test_phase_extracted_from_phasebox_title():
    assert debt_cycle_phase_from_payload(_payload("Phase: late plateau")) == "Phase: late plateau"
