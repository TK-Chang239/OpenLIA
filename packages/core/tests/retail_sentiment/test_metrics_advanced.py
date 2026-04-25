"""Tests for the optional metrics 8/9/11/12 + spec-correct buzz_volume."""

from __future__ import annotations

from datetime import UTC, datetime

from openlia.retail_sentiment.metrics import compute_snapshot
from openlia.retail_sentiment.schemas import (
    ClassificationLabel,
    ClassifiedItem,
    MetricSnapshot,
    RawSocialPost,
)


def _post(pid: str, source: str = "social_media") -> RawSocialPost:
    return RawSocialPost(
        id=pid,
        ticker="AAPL",
        source=source,
        text="text",
        engagement={},
        created_at=datetime(2026, 4, 23, 12, 0, tzinfo=UTC),
    )


def _bullish(pid: str) -> ClassifiedItem:
    return ClassifiedItem(
        id=pid,
        classification=ClassificationLabel.BULLISH,
        confidence=0.9,
        key_phrases=[],
    )


def _prior_snapshot(captured_at: datetime, *, count: float, sentiment: float) -> MetricSnapshot:
    return MetricSnapshot(
        ticker="AAPL",
        captured_at=captured_at,
        sentiment_score=sentiment,
        buzz_volume=1.0,
        buzz_count=count,
        sentiment_momentum=0.0,
        bull_bear_ratio=1.0,
        buzz_sentiment_divergence=0.0,
        social_velocity=0.0,
        cross_source_agreement=1.0,
    )


# ---------------------------------------------------------------------------
# Metric 2 — Buzz Volume = today / 30d-avg ratio
# ---------------------------------------------------------------------------


def test_buzz_volume_ratio_uses_history_baseline():
    posts = [_post(f"p{i}") for i in range(20)]
    cls = [_bullish(f"p{i}") for i in range(20)]
    prior = [
        _prior_snapshot(
            datetime(2026, 4, 22, 12, 0, tzinfo=UTC),
            count=5.0,
            sentiment=0.0,
        ),
        _prior_snapshot(
            datetime(2026, 4, 21, 12, 0, tzinfo=UTC),
            count=15.0,
            sentiment=0.0,
        ),
    ]
    snap = compute_snapshot(
        ticker="AAPL",
        captured_at=datetime(2026, 4, 23, 12, 0, tzinfo=UTC),
        posts=posts,
        classifications=cls,
        prior_snapshots=prior,
    )
    # mean(5, 15) = 10; 20 / 10 = 2.0
    assert snap.buzz_count == 20.0
    assert snap.buzz_volume == 2.0


# ---------------------------------------------------------------------------
# Metric 8 — Put/Call Sentiment Ratio
# ---------------------------------------------------------------------------


def test_put_call_metric_returns_none_when_input_missing():
    snap = compute_snapshot(
        ticker="AAPL",
        captured_at=datetime(2026, 4, 23, 12, 0, tzinfo=UTC),
        posts=[],
        classifications=[],
        optional_inputs=None,
    )
    assert snap.put_call_ratio is None


def test_put_call_metric_uses_options_payload():
    snap = compute_snapshot(
        ticker="AAPL",
        captured_at=datetime(2026, 4, 23, 12, 0, tzinfo=UTC),
        posts=[_post("p1")],
        classifications=[_bullish("p1")],
        optional_inputs={"options_data": {"puts": 800, "calls": 1000}},
    )
    # puts/calls = 0.8; sentiment = 1.0 (single bullish) → 0.8 * (1 - 1) = 0.0
    assert snap.put_call_ratio == 0.0


# ---------------------------------------------------------------------------
# Metric 9 — Short Interest Pressure
# ---------------------------------------------------------------------------


def test_short_interest_metric_returns_none_when_input_missing():
    snap = compute_snapshot(
        ticker="AAPL",
        captured_at=datetime(2026, 4, 23, 12, 0, tzinfo=UTC),
        posts=[],
        classifications=[],
    )
    assert snap.short_interest_pressure is None


def test_short_interest_metric_multiplies_pct_and_days():
    snap = compute_snapshot(
        ticker="AAPL",
        captured_at=datetime(2026, 4, 23, 12, 0, tzinfo=UTC),
        posts=[],
        classifications=[],
        optional_inputs={"short_interest": {"short_pct_float": 0.15, "days_to_cover": 4}},
    )
    assert snap.short_interest_pressure == 0.6


# ---------------------------------------------------------------------------
# Metric 11 — Institutional/Retail Gap
# ---------------------------------------------------------------------------


def test_institutional_gap_returns_none_when_input_missing():
    snap = compute_snapshot(
        ticker="AAPL",
        captured_at=datetime(2026, 4, 23, 12, 0, tzinfo=UTC),
        posts=[],
        classifications=[],
    )
    assert snap.institutional_retail_gap is None


def test_institutional_gap_subtracts_sentiment():
    snap = compute_snapshot(
        ticker="AAPL",
        captured_at=datetime(2026, 4, 23, 12, 0, tzinfo=UTC),
        posts=[_post("p1")],
        classifications=[_bullish("p1")],
        optional_inputs={"institutional_holdings": {"change_pct": 0.5}},
    )
    # 0.5 - 1.0 = -0.5
    assert abs(snap.institutional_retail_gap - (-0.5)) < 1e-9


# ---------------------------------------------------------------------------
# Metric 12 — Event Sensitivity (cold-start gating)
# ---------------------------------------------------------------------------


def test_event_sensitivity_returns_none_when_history_too_short():
    snap = compute_snapshot(
        ticker="AAPL",
        captured_at=datetime(2026, 4, 23, 12, 0, tzinfo=UTC),
        posts=[],
        classifications=[],
        optional_inputs={"historical_prices": [{"close": 100.0}] * 10},
    )
    assert snap.event_sensitivity is None


def test_event_sensitivity_computes_return_stddev():
    closes = [{"close": 100.0 + i * 0.5} for i in range(35)]
    snap = compute_snapshot(
        ticker="AAPL",
        captured_at=datetime(2026, 4, 23, 12, 0, tzinfo=UTC),
        posts=[],
        classifications=[],
        optional_inputs={"historical_prices": closes},
    )
    assert snap.event_sensitivity is not None
    assert snap.event_sensitivity > 0.0
