from datetime import UTC, datetime

import pytest
from openlia.macro_research.payloads import DebtCycleData, FiveForcesData, FourSeasonsData
from openlia.macro_research.snapshot import (
    active_force_count_from_payload,
    debt_cycle_phase_from_payload,
    economic_season_from_payload,
    snapshot_value_for,
)


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


def _season(name: str) -> dict:
    return {"name": name, "sub": "s", "pillLabel": "p", "tone": "amber"}


def _four_seasons(markers: list[dict]) -> FourSeasonsData:
    return FourSeasonsData(
        header={"title": "T2", "subtitle": "s", "pills": []},
        cardSummary="x",
        scorecard={"rows": []},
        quadrant={
            "seasons": {
                "tl": _season("Stagflation"),
                "tr": _season("Reflation"),
                "bl": _season("Deflation"),
                "br": _season("Goldilocks"),
            },
            "markers": markers,
        },
        verdict={"title": "v", "body": "b", "sideCards": []},
        parallels={"cards": []},
        transitionRisk={
            "intro": "i",
            "bull": {"title": "bu", "body": "b"},
            "bear": {"title": "be", "body": "b"},
            "keyIndicator": {"title": "k", "body": "b"},
        },
        assetPlaybook={"cards": []},
        notes=[],
        sources="s",
        generated_at=datetime.now(UTC),
    )


def _marker(x: int, y: int, variant: str = "now") -> dict:
    return {"label": "now", "xPct": x, "yPct": y, "variant": variant, "tone": "amber"}


def test_economic_season_top_left():
    payload = _four_seasons([_marker(x=20, y=20)])
    assert economic_season_from_payload(payload) == "Stagflation"


def test_economic_season_top_right():
    payload = _four_seasons([_marker(x=80, y=20)])
    assert economic_season_from_payload(payload) == "Reflation"


def test_economic_season_bottom_left():
    payload = _four_seasons([_marker(x=20, y=80)])
    assert economic_season_from_payload(payload) == "Deflation"


def test_economic_season_bottom_right():
    payload = _four_seasons([_marker(x=80, y=80)])
    assert economic_season_from_payload(payload) == "Goldilocks"


def test_economic_season_selects_now_marker_over_others():
    payload = _four_seasons(
        [
            _marker(x=20, y=20, variant="prev"),
            _marker(x=80, y=80, variant="now"),
        ]
    )
    assert economic_season_from_payload(payload) == "Goldilocks"


def test_economic_season_falls_back_to_first_marker_when_no_now():
    payload = _four_seasons([_marker(x=80, y=20, variant="prev")])
    assert economic_season_from_payload(payload) == "Reflation"


def test_economic_season_raises_when_no_markers():
    payload = _four_seasons([])
    with pytest.raises(ValueError):
        economic_season_from_payload(payload)


def _five_forces(count_text: str) -> FiveForcesData:
    return FiveForcesData(
        header={"title": "T5", "subtitle": "s", "badges": []},
        cardSummary="x",
        scorecard={"label": "A", "rows": []},
        loops={
            "label": "B",
            "blocks": [],
            "active": {
                "countText": count_text,
                "countTone": "red",
                "title": "t",
                "body": "b",
            },
        },
        signals={"label": "C", "cards": []},
        goldAllocation={
            "label": "D",
            "block": {"title": "g", "ticks": [], "stats": [], "body": "b"},
        },
        scenarios={"label": "E", "cards": []},
        verdict={"title": "v", "body": "b"},
        sources="s",
        generated_at=datetime.now(UTC),
    )


def test_active_force_count_parses_leading_int_with_slash():
    assert active_force_count_from_payload(_five_forces("3 / 5")) == 3


def test_active_force_count_parses_leading_int_with_word():
    assert active_force_count_from_payload(_five_forces("3 active")) == 3


def test_active_force_count_raises_on_malformed_count_text():
    with pytest.raises(ValueError):
        active_force_count_from_payload(_five_forces("all active"))


def _debt_cycle_payload_dict(phase_title: str = "Late Plateau") -> dict:
    """A complete, valid DebtCycleData as a JSON-ready dict."""
    return {
        "header": {"title": "T1", "subtitle": "s", "pills": []},
        "cardSummary": "x",
        "scorecard": {"rows": []},
        "phaseBox": {"title": phase_title, "body": "b", "tone": "amber"},
        "analogPair": {
            "analog": {"title": "a", "body": "b"},
            "timeToConstraint": {"title": "t", "body": "b"},
        },
        "policySpace": {"cards": []},
        "assetThesis": {
            "gold": {"title": "g", "body": "b"},
            "longBond": {"title": "l", "body": "b"},
        },
        "watchlist": {"rows": []},
        "verdict": {"title": "v", "body": "b", "tone": "amber"},
        "sources": "s",
        "generated_at": "2026-06-03T00:00:00Z",
    }


def _five_forces_payload_dict(count_text: str = "3 / 5") -> dict:
    """A complete, valid FiveForcesData as a JSON-ready dict."""
    return {
        "header": {"title": "T5", "subtitle": "s", "badges": []},
        "cardSummary": "x",
        "scorecard": {"label": "A", "rows": []},
        "loops": {
            "label": "B",
            "blocks": [],
            "active": {
                "countText": count_text,
                "countTone": "red",
                "title": "t",
                "body": "b",
            },
        },
        "signals": {"label": "C", "cards": []},
        "goldAllocation": {
            "label": "D",
            "block": {"title": "g", "ticks": [], "stats": [], "body": "b"},
        },
        "scenarios": {"label": "E", "cards": []},
        "verdict": {"title": "v", "body": "b"},
        "sources": "s",
        "generated_at": "2026-06-03T00:00:00Z",
    }


def test_snapshot_value_for_unknown_dashboard_returns_none():
    assert snapshot_value_for("summary", {"anything": True}) is None


def test_snapshot_value_for_malformed_payload_returns_none():
    assert snapshot_value_for("debt_cycle", {}) is None


def test_snapshot_value_for_valid_debt_cycle_returns_phase_title():
    payload = _debt_cycle_payload_dict("Late Plateau")
    assert snapshot_value_for("debt_cycle", payload) == "Late Plateau"


def test_snapshot_value_for_valid_five_forces_returns_active_count():
    payload = _five_forces_payload_dict("3 / 5")
    assert snapshot_value_for("five_forces", payload) == 3
