"""End-to-end retail_sentiment dashboard run through the real tool-use loop.

Mirrors the report_dash_mr runner tests: a fake adapter scripts two turns —
classify_retail_sentiment, then emit_dashboard with a complete
RetailSentimentData payload.  The runner is exercised for real (no mocking
of the loop); the assertions confirm the typed payload round-trips into
``RunResult``.
"""

import pytest
from _fakes import FakeLLMProvider, script_tool_calls
from openlia.llm.runtime.report_dash_mr import (
    LLMSession,
    MbDataTransports,
)
from openlia.llm.runtime.report_dash_rs import Runner
from openlia.llm.runtime.report_dash_rs.schemas import EnabledConnectors, RunRequest


def _complete_retail_sentiment_payload() -> dict:
    """A complete, valid RetailSentimentData as a JSON-ready dict."""
    return {
        "subject": "AAPL",
        "sentiment_score": 0.42,
        "direction": "bullish",
        "momentum": 0.1,
        "trend_label": "Rising",
        "buzz_level": "elevated",
        "buzz_note": "Active discussion around earnings beat.",
        "bull_pct": 70.0,
        "bear_pct": 20.0,
        "narratives": ["earnings beat", "guidance raise"],
        "signals": [
            {"name": "FOMO / crowding", "severity": "caution", "note": "High buzz + bullish tone."}
        ],
        "evidence": [
            {
                "title": "AAPL pops on earnings",
                "url": "https://reddit.com/r/stocks/1",
                "source": "reddit",
                "classification": "bullish",
                "published_at": "2026-06-03T00:00:00Z",
            }
        ],
        "narrative": "Retail tone is decidedly bullish heading into the next catalyst.",
        "aggregated_sentiment": 0.45,
        "analyst_gap": -0.05,
        "captured_at": "2026-06-03T00:00:00Z",
    }


def _req() -> RunRequest:
    return RunRequest(
        dashboard_slug="retail_sentiment",
        subject="AAPL",
        template=None,
        provider_kind="stub",
        model="stub",
        enabled_connectors=EnabledConnectors(web_search=False),
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
    payload = _complete_retail_sentiment_payload()
    script = [
        script_tool_calls(
            (
                "classify_retail_sentiment",
                {
                    "bullish": 70,
                    "bearish": 20,
                    "neutral": 10,
                    "buzz_level": "elevated",
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
    assert result.payload["subject"] == "AAPL"
    assert result.payload["direction"] in {"bullish", "bearish", "neutral"}
    assert result.template_id == "retail_sentiment"


@pytest.mark.asyncio
async def test_runner_rejects_incomplete_payload_then_succeeds():
    """An invalid emit_dashboard payload comes back as a tool error; the
    model corrects and emits a complete payload on the next turn."""
    good = _complete_retail_sentiment_payload()
    script = [
        script_tool_calls(("emit_dashboard", {"payload": {"subject": "AAPL"}})),
        script_tool_calls(("emit_dashboard", {"payload": good})),
    ]
    session = LLMSession.create(provider_kind="stub", model="stub")
    session.attach_adapter(FakeLLMProvider(scripted_responses=script))
    runner = Runner(request=_req(), transports=_transports(), max_turns=10)

    result = await runner.run(session=session)

    assert result.status == "completed"
    assert result.payload is not None
    assert result.payload["direction"] == "bullish"
