"""Tests for the compute_snapshot metric engine."""

from __future__ import annotations

from datetime import UTC, datetime

from openlia.retail_sentiment.metrics import compute_snapshot
from openlia.retail_sentiment.schemas import (
    ClassificationLabel,
    ClassifiedItem,
    RawSocialPost,
)


def _post(pid: str, source: str, minutes_ago: int = 0) -> RawSocialPost:
    return RawSocialPost(
        id=pid,
        ticker="AAPL",
        source=source,
        text="text",
        engagement={},
        created_at=datetime(2026, 4, 23, 12, 0, tzinfo=UTC),
    )


def _c(pid: str, label: ClassificationLabel, phrases: list[str] | None = None) -> ClassifiedItem:
    return ClassifiedItem(
        id=pid,
        classification=label,
        confidence=0.9,
        key_phrases=phrases or [],
    )


def test_empty_inputs_produce_zero_snapshot():
    snap = compute_snapshot(
        ticker="AAPL",
        captured_at=datetime(2026, 4, 23, 12, 0, tzinfo=UTC),
        posts=[],
        classifications=[],
    )
    assert snap.ticker == "AAPL"
    assert snap.sentiment_score == 0.0
    assert snap.buzz_volume == 0.0
    assert snap.bull_bear_ratio == 0.0


def test_mixed_sentiment_scores():
    posts = [
        _post("1", "social_media"),
        _post("2", "social_media"),
        _post("3", "financial_provider"),
    ]
    cls = [
        _c("1", ClassificationLabel.BULLISH, ["ai", "chip"]),
        _c("2", ClassificationLabel.BEARISH, ["chip"]),
        _c("3", ClassificationLabel.BULLISH),
    ]
    snap = compute_snapshot(
        ticker="AAPL",
        captured_at=datetime(2026, 4, 23, 12, 0, tzinfo=UTC),
        posts=posts,
        classifications=cls,
    )
    # 2 bullish + 1 bearish in 3 posts: (1 + 1 - 1)/3 = 0.333...
    assert abs(snap.sentiment_score - (1 / 3)) < 1e-9
    assert snap.buzz_volume == 3.0
    assert snap.bull_bear_ratio == 2.0
    assert snap.narrative_concentration is not None
    assert "social_media" in snap.source_breakdown
