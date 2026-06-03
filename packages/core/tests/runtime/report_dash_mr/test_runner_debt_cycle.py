"""End-to-end debt_cycle dashboard run through the real tool-use loop.

Mirrors the report_mb runner test: a fake adapter scripts two turns —
classify_debt_cycle, then emit_dashboard with a complete DebtCycleData
payload. The runner is exercised for real (no mocking of the loop); the
assertions confirm the typed payload round-trips into ``RunResult``.
"""

import pytest
from openlia.llm.runtime.report_dash_mr import (
    LLMSession,
    MbDataTransports,
    Runner,
)
from openlia.llm.runtime.report_dash_mr.schemas import EnabledConnectors, RunRequest

from ._fakes import FakeLLMProvider, script_tool_calls


def _complete_debt_cycle_payload() -> dict:
    """A complete, valid DebtCycleData as a JSON-ready dict.

    Shape mirrors packages/core/tests/macro_research/test_payloads.py.
    """
    return {
        "header": {
            "title": "Debt Cycle",
            "subtitle": "June 2026 · Dalio",
            "pills": [{"tone": "red", "label": "Late Plateau"}],
        },
        "cardSummary": "Debt burden critical; monetary space narrowing.",
        "scorecard": {
            "rows": [
                {
                    "name": "Govt debt / GDP",
                    "sub": "Q1 2026",
                    "current": "125.0%",
                    "currentTone": "red",
                    "currentMeta": "IMF",
                    "threshold": "> 120%",
                    "status": "Critical",
                    "statusTone": "red",
                    "fillPct": 95,
                    "fillTone": "red",
                }
            ]
        },
        "phaseBox": {
            "title": "Late Plateau",
            "body": "One red, multiple amber indicators.",
            "tone": "red",
        },
        "analogPair": {
            "analog": {"title": "1968-80", "body": "Stagflationary debt plateau."},
            "timeToConstraint": {"title": "3-7y", "body": "Window to the constraint."},
        },
        "policySpace": {
            "cards": [
                {
                    "label": "Rate cut headroom",
                    "value": "~470bps",
                    "valueTone": "amber",
                    "unit": "to neutral",
                    "note": "Real yields low.",
                }
            ]
        },
        "assetThesis": {
            "gold": {"title": "Gold", "body": "Debasement hedge."},
            "longBond": {"title": "Long bond", "body": "Vulnerable to fiscal dominance."},
        },
        "watchlist": {
            "rows": [{"tone": "red", "name": "Debt spiral", "body": "Interest/revenue rising."}]
        },
        "verdict": {
            "title": "Synthesis",
            "body": "Late-cycle debt dynamics with narrowing monetary space.",
            "tone": "red",
        },
        "sources": "IMF, BEA, FRED, ICE",
        "provenance": "live",
        "generated_at": "2026-06-03T00:00:00Z",
    }


def _req() -> RunRequest:
    return RunRequest(
        dashboard_slug="debt_cycle",
        subject="Debt Cycle",
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
async def test_runner_classify_then_emit_dashboard():
    payload = _complete_debt_cycle_payload()
    script = [
        script_tool_calls(
            (
                "classify_debt_cycle",
                {
                    "debt_gdp": 125.0,
                    "interest_revenue": 18.0,
                    "tips_real_yield": 0.3,
                    "dxy": 97.0,
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
    assert result.payload["phaseBox"]["title"] == "Late Plateau"
    assert result.payload["header"]["title"] == "Debt Cycle"
    assert result.template_id == "debt_cycle"


@pytest.mark.asyncio
async def test_runner_rejects_incomplete_payload_then_succeeds():
    """An invalid emit_dashboard payload comes back as a tool error; the
    model corrects and emits a complete payload on the next turn."""
    good = _complete_debt_cycle_payload()
    script = [
        script_tool_calls(("emit_dashboard", {"payload": {"header": {"title": "x"}}})),
        script_tool_calls(("emit_dashboard", {"payload": good})),
    ]
    session = LLMSession.create(provider_kind="stub", model="stub")
    session.attach_adapter(FakeLLMProvider(scripted_responses=script))
    runner = Runner(request=_req(), transports=_transports(), max_turns=10)

    result = await runner.run(session=session)

    assert result.status == "completed"
    assert result.payload is not None
    assert result.payload["verdict"]["tone"] == "red"
