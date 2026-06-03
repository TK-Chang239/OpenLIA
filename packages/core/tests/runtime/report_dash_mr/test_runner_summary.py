"""End-to-end summary dashboard run through the real tool-use loop.

Mirrors test_runner_five_forces.py, but Summary is a pure aggregation view
with NO classifier: the fake adapter scripts a single turn — emit_dashboard
with a complete SummaryData payload synthesized from the five framework states
injected via data_context. The runner is exercised for real (no mocking of the
loop); the assertions confirm the typed payload round-trips into ``RunResult``,
validates as SummaryData, and serializes the dependency-map edge with the JSON
key ``from`` (the model field is ``from_``).
"""

import pytest
from openlia.llm.runtime.report_dash_mr import (
    LLMSession,
    MbDataTransports,
    Runner,
)
from openlia.llm.runtime.report_dash_mr.schemas import EnabledConnectors, RunRequest
from openlia.macro_research.payloads import SummaryData

from ._fakes import FakeLLMProvider, script_tool_calls


def _complete_summary_payload() -> dict:
    """A complete, valid SummaryData as a JSON-ready dict.

    Shape mirrors packages/core/tests/macro_research/test_payloads_summary.py.
    """
    return {
        "hero": {
            "eyebrow": "Macro - June 2026 - ",
            "eyebrowStrong": "3 of 5 forces critical - regime: late-plateau / autumn",
            "headline": "Three forces critical, simultaneously.",
            "headlineAccent": "Late plateau, tipping into autumn.",
            "lede": "All five Dalio frameworks point in the same direction.",
            "stats": [
                {"k": "Active forces", "v": "3 / 5", "status": "bad"},
                {"k": "Aggregate", "v": "8.3 / 10", "status": "bad"},
            ],
        },
        "liaTake": {
            "label": "LIA's cross-framework take",
            "timestamp": "Jun 3 - 14:22 ET",
            "paragraphs": ["Five frameworks. One read."],
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
                {"k": "T1 - Debt Cycle", "v": "Late plateau", "status": "bad", "sub": "3/8 warn"},
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
                    "miniVisual": "bars",
                    "miniData": [62.0, 48.0, 71.0],
                    "stats": [{"k": "Debt / GDP", "v": "125%", "status": "bad"}],
                    "footLabel": "Open T1 dashboard",
                },
                {
                    "tcode": "T5",
                    "slug": "five_forces",
                    "title": "Five Forces",
                    "stamp": {"label": "3 / 5 critical", "status": "bad"},
                    "summary": "Three forces active.",
                    "miniVisual": "forces",
                    "miniData": {"active": True, "index": 2},
                    "stats": [{"k": "Aggregate", "v": "8.3"}],
                    "footLabel": "Open T5 dashboard",
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
            ],
            "edges": [
                {"from": "t1", "to": "t5", "label": "F1 input", "variant": "solid"},
            ],
        },
        "cascade": {
            "label": "Gold thesis - cross-framework cascade",
            "subLabel": "How four frameworks compose to one position",
            "sub": "The gold tilt in T3 is the cleanest expression of coherence.",
            "row1": [
                {"badge": "T1 - debt", "title": "Real yields lower", "body": "DFII10 +1.94%."},
            ],
            "row2": [
                {
                    "badge": "T3 - IMPLEMENT",
                    "title": "Gold 7.5% -> 10%",
                    "body": "+2.5pp",
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
                    "desc": "The biggest credit-side confirmation of T2's autumn call.",
                    "fromTabs": "From T2 - T3",
                },
            ],
        },
        "sources": "CEIC / BEA / CBO / WGC / IMF COFER. Not investment advice.",
        "provenance": "live",
        "generated_at": "2026-06-03T00:00:00Z",
    }


def _req() -> RunRequest:
    return RunRequest(
        dashboard_slug="summary",
        subject="Summary",
        template=None,
        provider_kind="stub",
        model="stub",
        enabled_connectors=EnabledConnectors(),
        data_context=(
            "T1 - Debt Cycle: Late Plateau. T2 - Four Seasons: Autumn. "
            "T4 - World Order: Late empire. T3 - All-Weather: Tactical tilt. "
            "T5 - Five Forces: Elevated. Active forces: 3 / 5."
        ),
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
async def test_runner_emit_summary_no_classifier():
    payload = _complete_summary_payload()
    # Summary has no classifier: the single scripted turn is emit_dashboard.
    script = [
        script_tool_calls(("emit_dashboard", {"payload": payload})),
    ]
    session = LLMSession.create(provider_kind="stub", model="stub")
    session.attach_adapter(FakeLLMProvider(scripted_responses=script))
    runner = Runner(request=_req(), transports=_transports(), max_turns=10)

    result = await runner.run(session=session)

    assert result.status == "completed"
    assert result.payload is not None
    assert result.template_id == "summary"

    validated = SummaryData.model_validate(result.payload)
    assert validated.hero.headline == "Three forces critical, simultaneously."
    assert len(validated.liaTake.pulls) == 4
    assert validated.frameworkStatus.cards[0].tcode == "T1"
    assert validated.depMap.edges[0].from_ == "t1"

    # The serialized RunResult payload must carry the JSON key `from`, not the
    # Python field name `from_`, so the front end reads the dependency-map edge.
    edge = result.payload["depMap"]["edges"][0]
    assert "from" in edge
    assert "from_" not in edge
    assert edge["from"] == "t1"
