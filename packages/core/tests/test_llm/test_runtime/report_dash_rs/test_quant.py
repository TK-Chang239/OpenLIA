from openlia.llm.runtime.report_dash_rs.quant import (
    RetailSentimentInputs,
    classify_retail_sentiment,
    momentum_from_history,
)


def test_classify_bullish():
    out = classify_retail_sentiment(
        RetailSentimentInputs(bullish=70, bearish=20, neutral=10, buzz_level="elevated")
    )
    assert out.direction == "bullish"
    assert abs(out.sentiment_score - 0.5) < 1e-9
    assert abs(out.bull_pct - 70.0) < 1e-9


def test_classify_zero_volume_is_neutral():
    out = classify_retail_sentiment(
        RetailSentimentInputs(bullish=0, bearish=0, neutral=0, buzz_level="low")
    )
    assert out.direction == "neutral"
    assert out.sentiment_score == 0.0
    assert out.signals == []


def test_panic_signal_high_buzz_negative_tone():
    out = classify_retail_sentiment(
        RetailSentimentInputs(bullish=10, bearish=70, neutral=20, buzz_level="high")
    )
    assert any(s["name"].lower().startswith("panic") for s in out.signals)


def test_momentum_from_history():
    m, label = momentum_from_history([0.1, 0.2, 0.45])
    assert m is not None and m > 0
    assert label == "improving"
    assert momentum_from_history([0.4]) == (None, "building history")
