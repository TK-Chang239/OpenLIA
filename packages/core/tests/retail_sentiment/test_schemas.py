from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from openlia.retail_sentiment.schemas import (
    ClassificationLabel,
    ClassifiedItem,
    MetricSnapshot,
    RawSocialPost,
    SignalAlert,
    SpikeEvent,
)


def test_classification_label_values():
    for v in ("bullish", "bearish", "neutral"):
        assert ClassificationLabel(v).value == v


def test_classified_item_requires_matching_id():
    item = ClassifiedItem(
        id="post_1",
        classification="bullish",
        confidence=0.8,
        key_phrases=["strong guidance"],
    )
    assert item.id == "post_1"
    assert 0 <= item.confidence <= 1


def test_classified_item_confidence_bounds():
    with pytest.raises(ValidationError):
        ClassifiedItem(id="x", classification="bullish", confidence=1.5, key_phrases=[])


def test_raw_social_post_round_trip():
    p = RawSocialPost(
        id="t_1",
        ticker="AAPL",
        source="x_twitter",
        text="Loving $AAPL here",
        engagement={"likes": 120, "retweets": 10, "replies": 3},
        created_at=datetime.now(UTC),
    )
    assert p.engagement["likes"] == 120


def test_metric_snapshot_all_12_metrics():
    s = MetricSnapshot(
        ticker="AAPL",
        captured_at=datetime.now(UTC),
        sentiment_score=0.42,
        buzz_volume=1.8,
        sentiment_momentum=0.05,
        bull_bear_ratio=0.62,
        buzz_sentiment_divergence=1.2,
        social_velocity=0.3,
        cross_source_agreement=0.66,
        put_call_ratio=None,
        short_interest_pressure=None,
        narrative_concentration=0.45,
        institutional_retail_gap=None,
        event_sensitivity=1.7,
        source_breakdown={"financial_provider": 0.5, "social_media": 0.4, "cross_platform": 0.1},
    )
    assert -1 <= s.sentiment_score <= 1
    assert s.buzz_volume >= 0


def test_signal_alert_severity_enum():
    a = SignalAlert(
        ticker="AAPL",
        metric_id="buzz_sentiment_divergence",
        severity="panic",
        message="Divergence z=2.5 — high buzz with negative tone",
        value=2.5,
    )
    assert a.severity in {"panic", "stealth_recovery", "caution", "info"}


def test_spike_event_fields():
    e = SpikeEvent(
        ticker="AAPL",
        detected_at=datetime.now(UTC),
        buzz=2500,
        baseline_mean=800,
        baseline_stddev=200,
        z_score=8.5,
    )
    assert e.z_score > 2
