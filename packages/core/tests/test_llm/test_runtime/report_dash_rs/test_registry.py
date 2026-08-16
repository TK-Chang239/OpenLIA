from openlia.llm.runtime.report_dash_rs.schemas import RetailSentimentData
from openlia.llm.runtime.report_dash_rs.tools.dashboard_tools import (
    CLASSIFY_TOOL_BY_SLUG,
    PAYLOAD_MODEL_BY_SLUG,
    build_emit_dashboard_tool,
    implemented_dashboard_slugs,
)


class _FakeWorkspace:
    """Minimal workspace capturing the validated payload emit_dashboard sets."""

    def __init__(self) -> None:
        self.payload: RetailSentimentData | None = None

    def set_payload(self, payload: RetailSentimentData) -> None:
        self.payload = payload


def _minimal_payload_without_crosscheck() -> dict:
    """A complete RetailSentimentData dict that omits the optional cross-check
    fields (aggregated_sentiment / analyst_gap) — the shape a run produces when
    web search surfaces no citable aggregated-sentiment or analyst figure."""
    return {
        "subject": "AAPL",
        "sentiment_score": 0.42,
        "direction": "bullish",
        "buzz_level": "elevated",
        "buzz_note": "Active discussion on earnings beat.",
        "bull_pct": 70.0,
        "bear_pct": 20.0,
        "narratives": ["earnings beat"],
        "signals": [{"name": "FOMO / crowding", "severity": "caution", "note": "High buzz."}],
        "evidence": [
            {
                "title": "AAPL pops",
                "url": "https://x",
                "source": "reddit",
                "classification": "bullish",
            }
        ],
        "narrative": "Retail tone is bullish into the print.",
    }


def test_registry_has_retail_sentiment_slug():
    assert implemented_dashboard_slugs() == frozenset({"retail_sentiment"})
    assert "retail_sentiment" in PAYLOAD_MODEL_BY_SLUG
    assert "retail_sentiment" in CLASSIFY_TOOL_BY_SLUG


def test_classify_tool_executes():
    builder = CLASSIFY_TOOL_BY_SLUG["retail_sentiment"][0]
    tool = builder()
    res = tool.execute({"bullish": 70, "bearish": 20, "neutral": 10, "buzz_level": "elevated"})
    assert res.payload["direction"] == "bullish"
    assert res.payload["bull_pct"] == 70.0


def test_emit_dashboard_accepts_payload_without_crosscheck_fields():
    """A run that cannot obtain aggregated_sentiment / analyst_gap omits both,
    and emit_dashboard still validates the payload (fields default to None)."""
    ws = _FakeWorkspace()
    tool = build_emit_dashboard_tool(ws, RetailSentimentData)
    res = tool.execute({"payload": _minimal_payload_without_crosscheck()})
    assert res.payload["ok"] is True
    assert ws.payload is not None
    assert ws.payload.aggregated_sentiment is None
    assert ws.payload.analyst_gap is None
