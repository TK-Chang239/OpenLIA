from openlia.llm.runtime.report_dash_rs.schemas import (
    EvidenceItem,
    RetailSentimentData,
    Signal,
)


def test_retail_sentiment_data_minimal_valid():
    data = RetailSentimentData(
        subject="AAPL",
        sentiment_score=0.42,
        direction="bullish",
        buzz_level="elevated",
        buzz_note="Active discussion on earnings beat.",
        bull_pct=70.0,
        bear_pct=20.0,
        narratives=["earnings beat", "guidance raise"],
        signals=[
            Signal(name="FOMO / crowding", severity="caution", note="High buzz + bullish tone.")
        ],
        evidence=[
            EvidenceItem(
                title="AAPL pops", url="https://x", source="reddit", classification="bullish"
            )
        ],
        narrative="Retail tone is bullish into the print.",
    )
    assert data.subject == "AAPL"
    assert data.momentum is None
    assert data.aggregated_sentiment is None


def test_sentiment_score_out_of_range_rejected():
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        RetailSentimentData(
            subject="AAPL",
            sentiment_score=2.0,
            direction="bullish",
            buzz_level="low",
            buzz_note="",
            bull_pct=1,
            bear_pct=0,
            narratives=[],
            signals=[],
            evidence=[],
            narrative="",
        )
