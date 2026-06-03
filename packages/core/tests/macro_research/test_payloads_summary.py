"""SummaryData payload validation.

Fixture transcribed from frontend/src/lib/macro_research/dalio_copy/summary.ts
(SUMMARY_FALLBACK) plus a `generated_at` timestamp. Summary is an aggregation
view: it has no deterministic classifier, so its payload synthesizes the other
five dashboards' cached states. Asserts the typed payload validates and that
the `from` alias on dependency-map edges round-trips on serialization (the
field is `from_` in Python; the front end reads `from`).
"""

import pytest
from openlia.macro_research.payloads import SummaryData
from pydantic import ValidationError


def _summary_fixture() -> dict:
    """A complete, valid SummaryData as a JSON-ready dict.

    Transcribed (trimmed prose) from SUMMARY_FALLBACK in summary.ts. The
    frameworkStatus cards are authored inline here rather than derived from the
    other dashboards (as the front end does) so the fixture exercises every
    SummaryData field, including the spotlight chart on the T1 card.
    """
    return {
        "hero": {
            "eyebrow": "Macro - April 2026 - ",
            "eyebrowStrong": "3 of 5 forces critical - regime: late-plateau / autumn",
            "headline": "Three forces critical, simultaneously.",
            "headlineAccent": "Late plateau, tipping into autumn.",
            "lede": "All five Dalio frameworks point in the same direction.",
            "stats": [
                {"k": "Active forces", "v": "3 / 5", "status": "bad"},
                {"k": "Aggregate", "v": "8.3 / 10", "status": "bad"},
                {"k": "Tactical alpha", "v": "+5.5pp", "status": "ok"},
                {"k": "Conviction", "v": "71 / 100", "status": "info"},
                {"k": "Last refresh", "v": "Apr 14 - 14:22 ET", "status": "flat"},
            ],
        },
        "liaTake": {
            "label": "LIA's cross-framework take",
            "timestamp": "Apr 14 - 14:22 ET",
            "paragraphs": [
                "Five frameworks. One read.",
                "The clean expression is the gold thesis cascade.",
                "The risk is that T2's autumn read is conviction-62.",
            ],
            "pulls": [
                {"k": "Action", "v": "Adopt T3 tactical tilt"},
                {"k": "Window", "v": "Quarterly review"},
                {"k": "Top trigger", "v": "HY OAS >= 3.5%"},
                {"k": "Top rejection", "v": "Core PCE < 2% x 2m"},
            ],
        },
        "regimeBar": {
            "label": "Regime - at-a-glance",
            "subLabel": "Today's verdict per framework",
            "segments": [
                {
                    "k": "T1 - Debt Cycle",
                    "v": "Late plateau",
                    "status": "bad",
                    "sub": "3 / 8 indicators in warn",
                },
                {
                    "k": "T2 - Season",
                    "v": "Autumn",
                    "status": "warn",
                    "sub": "Growth slowing - CPI re-accelerating",
                },
            ],
        },
        "frameworkStatus": {
            "label": "Frameworks - drill-in",
            "subLabel": "5 cards - click for full detail",
            "cards": [
                {
                    "tcode": "T1",
                    "slug": "debt_cycle",
                    "title": "Debt & Money Cycle",
                    "stamp": {"label": "Late plateau", "status": "bad"},
                    "summary": "Late plateau; monetary headroom limited.",
                    "verdictLine": "Late plateau; monetary headroom limited.",
                    "miniVisual": "bars",
                    "miniData": [62.0, 48.0, 71.0],
                    "stats": [
                        {"k": "Debt / GDP", "v": "125%", "status": "bad"},
                        {"k": "Int / Rev", "v": "18%", "status": "warn"},
                        {"k": "TIPS real", "v": "+1.94%", "status": "ok"},
                    ],
                    "footLabel": "Open T1 dashboard",
                    "spotlight": True,
                    "spotlightChart": {
                        "yLabel": "Debt / GDP",
                        "yUnit": "%",
                        "yMin": 40.0,
                        "yMax": 140.0,
                        "data": [
                            {"year": 2020, "value": 126.4},
                            {"year": 2026, "value": 125.2},
                        ],
                        "current": {"year": 2026, "value": 125.2},
                    },
                },
                {
                    "tcode": "T2",
                    "slug": "four_seasons",
                    "acid": True,
                    "title": "Four Seasons",
                    "stamp": {"label": "Autumn", "status": "warn"},
                    "summary": "Summer tipping into autumn.",
                    "miniVisual": "quadrant",
                    "miniData": {"active": True, "index": 3},
                    "stats": [
                        {"k": "PMI", "v": "48.6", "status": "warn"},
                        {"k": "GDP Q1", "v": "1.6%", "status": "warn"},
                        {"k": "CPI y/y", "v": "3.4%", "status": "bad"},
                    ],
                    "footLabel": "Open T2 dashboard",
                },
            ],
        },
        "depMap": {
            "label": "Cross-framework dependency map",
            "subLabel": "How signals flow between T1-T5",
            "sub": "Each framework consumes upstream readings and emits a verdict downstream.",
            "nodes": [
                {
                    "id": "t1",
                    "tcode": "T1",
                    "name": "Debt Cycle",
                    "status": "bad",
                    "statusLabel": "CRITICAL",
                    "position": "left-top",
                },
                {
                    "id": "t5",
                    "tcode": "T5",
                    "name": "Five Forces",
                    "status": "bad",
                    "statusLabel": "3 / 5 CRITICAL",
                    "position": "center",
                },
                {
                    "id": "t3",
                    "tcode": "T3",
                    "name": "All-Weather",
                    "status": "ok",
                    "statusLabel": "TACTICAL TILT",
                    "position": "right",
                },
            ],
            "edges": [
                {"from": "t1", "to": "t5", "label": "F1 input", "variant": "solid"},
                {"from": "t5", "to": "t3", "label": "confluence response", "variant": "accent"},
            ],
        },
        "cascade": {
            "label": "Gold thesis - cross-framework cascade",
            "subLabel": "How four frameworks compose to one position",
            "sub": "The gold tilt in T3 is the cleanest expression of cross-framework coherence.",
            "row1": [
                {
                    "badge": "T1 - debt",
                    "title": "Real yields trending lower",
                    "body": "DFII10 +1.94% - monetary headroom limited.",
                },
            ],
            "row2": [
                {
                    "badge": "T3 - IMPLEMENT",
                    "title": "Gold 7.5% -> 10%",
                    "body": "+2.5pp now, fund from long bonds.",
                    "target": True,
                },
            ],
        },
        "watchlist": {
            "label": "Consolidated watchlist - 6 triggers",
            "subLabel": "Top signals across T1-T5",
            "triggers": [
                {
                    "status": "bad",
                    "name": "HY OAS widens through 3.5%",
                    "source": "ICE BAML - daily",
                    "desc": "The single biggest credit-side confirmation of T2's autumn call.",
                    "fromTabs": "From T2 - T3",
                },
            ],
        },
        "sources": "CEIC / BEA / CBO / WGC / IMF COFER. Not investment advice.",
        "provenance": "live",
        "generated_at": "2026-06-03T00:00:00Z",
    }


def test_summary_payload_validates() -> None:
    data = SummaryData.model_validate(_summary_fixture())
    assert data.hero.headline == "Three forces critical, simultaneously."
    assert data.hero.eyebrowStrong is not None
    assert len(data.liaTake.pulls) == 4
    assert data.liaTake.pulls[2].v == "HY OAS >= 3.5%"
    assert data.frameworkStatus.cards[0].tcode == "T1"
    assert data.frameworkStatus.cards[0].miniData == [62.0, 48.0, 71.0]
    assert data.frameworkStatus.cards[0].spotlightChart is not None
    assert data.frameworkStatus.cards[0].spotlightChart.current.year == 2026
    assert data.frameworkStatus.cards[1].miniData.active is True
    assert data.frameworkStatus.cards[1].acid is True
    assert data.depMap.edges[0].from_ == "t1"
    assert data.cascade.row2[0].target is True
    assert data.watchlist.triggers[0].status == "bad"


def test_summary_payload_round_trips_the_from_alias() -> None:
    """`from` is a Python keyword; the model field is `from_`. Serialization
    must emit the JSON key `from` (not `from_`) so the front end reads it."""
    dumped = SummaryData.model_validate(_summary_fixture()).model_dump(mode="json", by_alias=True)
    edge = dumped["depMap"]["edges"][0]
    assert "from" in edge
    assert "from_" not in edge
    assert edge["from"] == "t1"


def test_summary_payload_rejects_bad_status() -> None:
    bad = _summary_fixture()
    bad["hero"]["stats"][0]["status"] = "purple"
    with pytest.raises(ValidationError):
        SummaryData.model_validate(bad)
