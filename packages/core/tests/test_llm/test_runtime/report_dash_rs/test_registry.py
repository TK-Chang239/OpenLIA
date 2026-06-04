from openlia.llm.runtime.report_dash_rs.tools.dashboard_tools import (
    CLASSIFY_TOOL_BY_SLUG,
    PAYLOAD_MODEL_BY_SLUG,
    implemented_dashboard_slugs,
)


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
