"""End-to-end four_seasons dashboard run through the real tool-use loop.

Mirrors test_runner_world_order.py: a fake adapter scripts two turns —
classify_four_seasons, then emit_dashboard with a complete FourSeasonsData
payload. The runner is exercised for real (no mocking of the loop); the
assertions confirm the typed payload round-trips into ``RunResult`` and
validates as FourSeasonsData.
"""

import pytest
from openlia.llm.runtime.report_dash_mr import (
    LLMSession,
    MbDataTransports,
    Runner,
)
from openlia.llm.runtime.report_dash_mr.schemas import EnabledConnectors, RunRequest
from openlia.macro_research.payloads import FourSeasonsData

from ._fakes import FakeLLMProvider, script_tool_calls


def _complete_four_seasons_payload() -> dict:
    """A complete, valid FourSeasonsData as a JSON-ready dict.

    Shape mirrors packages/core/tests/macro_research/test_payloads_four_seasons.py.
    """
    return {
        "header": {
            "title": "Four Seasons",
            "subtitle": "June 2026 · Dalio",
            "pills": [
                {"tone": "amber", "label": "Transitioning summer -> autumn"},
                {"tone": "purple", "label": "Mixed confidence"},
            ],
        },
        "cardSummary": "Growth slowing while inflation re-accelerates; stagflation risk.",
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
                    "trend": "Modestly rising over the quarter.",
                    "axisLabel": "Growth rising",
                    "axisTone": "green",
                    "direction": "up",
                    "directionLabel": "Rising",
                    "directionTone": "green",
                }
            ],
        },
        "quadrant": {
            "seasons": {
                "tl": {
                    "name": "Autumn",
                    "sub": "Growth falling · inflation rising",
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
                {
                    "label": "Jun 2026",
                    "xPct": 77,
                    "yPct": 80,
                    "variant": "now",
                    "tone": "red",
                }
            ],
        },
        "verdict": {
            "title": "Transitioning summer -> autumn",
            "body": "Growth falling + inflation rising = the autumn quadrant.",
            "sideCards": [
                {
                    "label": "Confidence level",
                    "value": "Mixed",
                    "valueTone": "amber",
                    "note": "Growth axis ambiguous",
                }
            ],
        },
        "parallels": {
            "cards": [
                {
                    "title": "H1 2022 - the closer parallel",
                    "body": "Energy-driven inflation while growth slowed.",
                }
            ],
        },
        "transitionRisk": {
            "intro": "Primary risk is a confirmed move into full autumn.",
            "bull": {
                "title": "If summer persists",
                "body": "Oil retraces and growth rebounds.",
            },
            "bear": {
                "title": "If autumn confirms",
                "body": "Energy inflation feeds into services; PMI rolls below 50.",
            },
            "keyIndicator": {
                "title": "Key indicator to watch",
                "body": "Next GDP advance estimate.",
            },
        },
        "assetPlaybook": {
            "cards": [
                {
                    "tone": "red",
                    "label": "Gold",
                    "posture": "Autumn signal strengthening",
                    "body": "Canonical autumn asset.",
                }
            ],
        },
        "notes": [
            {
                "title": "Portfolio stress test",
                "body": "A 60/40 portfolio faces its worst structural alignment.",
            }
        ],
        "sources": "ISM PMI, BLS CPI, BEA GDP. Not investment advice.",
        "provenance": "live",
        "generated_at": "2026-06-03T00:00:00Z",
    }


def _req() -> RunRequest:
    return RunRequest(
        dashboard_slug="four_seasons",
        subject="Four Seasons",
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
async def test_runner_classify_then_emit_four_seasons():
    payload = _complete_four_seasons_payload()
    script = [
        script_tool_calls(
            (
                "classify_four_seasons",
                {
                    "pmi": 47.0,
                    "gdp_yoy": 0.2,
                    "cpi_yoy": 4.0,
                    "credit_spread": 0.04,
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
    assert result.template_id == "four_seasons"

    validated = FourSeasonsData.model_validate(result.payload)
    assert validated.scorecard.rows
    assert validated.quadrant.markers[0].variant == "now"
    assert validated.quadrant.seasons.tl.tone == "red"
    assert validated.header.pills[1].tone == "purple"
