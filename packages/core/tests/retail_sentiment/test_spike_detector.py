"""Tests for detect_spike."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from openlia.retail_sentiment.schemas import MetricSnapshot
from openlia.retail_sentiment.spike_detector import detect_spike


def _snap(captured: datetime, buzz: float) -> MetricSnapshot:
    return MetricSnapshot(
        ticker="AAPL",
        captured_at=captured,
        sentiment_score=0.0,
        buzz_volume=buzz,
        sentiment_momentum=0.0,
        bull_bear_ratio=1.0,
        buzz_sentiment_divergence=0.0,
        social_velocity=0.0,
        cross_source_agreement=0.0,
    )


def test_no_spike_below_threshold():
    base = datetime(2026, 4, 23, 12, 0, tzinfo=UTC)
    history = [_snap(base - timedelta(days=i), 10.0) for i in range(7)]
    assert (
        detect_spike(
            ticker="AAPL",
            detected_at=base,
            current_buzz=11.0,
            recent_snapshots=history,
        )
        is None
    )


def test_spike_fires_above_two_stddev():
    base = datetime(2026, 4, 23, 12, 0, tzinfo=UTC)
    # 7 low-volume days, then a big spike
    history = [_snap(base - timedelta(days=i), 10.0 + i * 0.1) for i in range(7)]
    spike = detect_spike(
        ticker="AAPL",
        detected_at=base,
        current_buzz=100.0,
        recent_snapshots=history,
    )
    assert spike is not None
    assert spike.z_score > 2.0
    assert spike.ticker == "AAPL"


def test_insufficient_history_returns_none():
    base = datetime(2026, 4, 23, 12, 0, tzinfo=UTC)
    assert (
        detect_spike(
            ticker="AAPL",
            detected_at=base,
            current_buzz=100.0,
            recent_snapshots=[_snap(base, 10.0)],
        )
        is None
    )
