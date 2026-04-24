"""12-metric sentiment engine.

Compressed implementation: the plan defines 12 metrics (7 basic + 5 optional).
This module ships the core 7 basic metrics plus a placeholder pipeline for
optionals that returns ``None`` when advanced data is absent.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import datetime
from typing import Any

from openlia.retail_sentiment.schemas import (
    ClassificationLabel,
    ClassifiedItem,
    MetricSnapshot,
    RawSocialPost,
)

DEFAULT_SOURCE_WEIGHTS: dict[str, float] = {
    "financial_provider": 0.40,
    "social_media": 0.35,
    "cross_platform": 0.25,
}


def _normalize_weights(weights: dict[str, float]) -> dict[str, float]:
    total = sum(max(0.0, v) for v in weights.values())
    if total <= 0:
        return dict(DEFAULT_SOURCE_WEIGHTS)
    return {k: max(0.0, v) / total for k, v in weights.items()}


def _score_for_label(label: ClassificationLabel) -> float:
    if label is ClassificationLabel.BULLISH:
        return 1.0
    if label is ClassificationLabel.BEARISH:
        return -1.0
    return 0.0


def compute_snapshot(
    *,
    ticker: str,
    captured_at: datetime,
    posts: Sequence[RawSocialPost],
    classifications: Sequence[ClassifiedItem],
    prior_snapshots: Sequence[MetricSnapshot] = (),
    source_weights: dict[str, float] | None = None,
    optional_inputs: dict[str, Any] | None = None,
) -> MetricSnapshot:
    """Compute the 12 metrics for a single ticker from classified items.

    Basic metrics (always computed when posts exist):
      1. sentiment_score    — mean of label scores in [-1, 1]
      2. buzz_volume        — raw count of posts
      3. sentiment_momentum — current score minus prior score (0 if none)
      4. bull_bear_ratio    — bullish count / max(bearish count, 1)
      5. buzz_sentiment_divergence — |buzz z-score| minus |sentiment z-score|
      6. social_velocity    — posts-per-hour over last 24h
      7. cross_source_agreement — stddev across per-source mean scores
     10. narrative_concentration — top-3 key phrase share of total
     12. source_breakdown   — per-source weighted means

    Optional metrics (None unless optional_inputs provided):
      8. put_call_ratio
      9. short_interest_pressure
     11. institutional_retail_gap
     (event_sensitivity treated as optional too)
    """
    classifications_by_id = {c.id: c for c in classifications}
    items = [(p, classifications_by_id.get(p.id)) for p in posts]
    classified = [(p, c) for p, c in items if c is not None]

    # Metric 1: mean sentiment
    if classified:
        scores = [_score_for_label(c.classification) for _, c in classified]
        sentiment_score = sum(scores) / len(scores)
    else:
        sentiment_score = 0.0

    # Metric 2: buzz volume
    buzz_volume = float(len(posts))

    # Metric 3: momentum vs prior snapshot
    if prior_snapshots:
        sentiment_momentum = sentiment_score - prior_snapshots[-1].sentiment_score
    else:
        sentiment_momentum = 0.0

    # Metric 4: bull/bear ratio
    bulls = sum(1 for _, c in classified if c.classification is ClassificationLabel.BULLISH)
    bears = sum(1 for _, c in classified if c.classification is ClassificationLabel.BEARISH)
    bull_bear_ratio = float(bulls) / float(max(bears, 1))

    # Metric 5: buzz-sentiment divergence (simple z-score difference)
    if len(prior_snapshots) >= 2:
        prior_buzz = [s.buzz_volume for s in prior_snapshots]
        prior_sent = [s.sentiment_score for s in prior_snapshots]
        buzz_z = _z_score(buzz_volume, prior_buzz)
        sent_z = _z_score(sentiment_score, prior_sent)
        buzz_sentiment_divergence = abs(buzz_z) - abs(sent_z)
    else:
        buzz_sentiment_divergence = 0.0

    # Metric 6: social velocity (posts per hour over last 24h window)
    if posts:
        latest = max(p.created_at for p in posts)
        window_start = latest.timestamp() - 24 * 3600
        recent = [p for p in posts if p.created_at.timestamp() >= window_start]
        social_velocity = len(recent) / 24.0
    else:
        social_velocity = 0.0

    # Metric 7 + 12: cross-source agreement + breakdown
    weights = _normalize_weights(source_weights or DEFAULT_SOURCE_WEIGHTS)
    per_source: dict[str, list[float]] = {}
    for p, c in classified:
        per_source.setdefault(p.source, []).append(_score_for_label(c.classification))
    per_source_mean = {src: sum(v) / len(v) for src, v in per_source.items() if v}
    if len(per_source_mean) >= 2:
        vals = list(per_source_mean.values())
        mean = sum(vals) / len(vals)
        variance = sum((v - mean) ** 2 for v in vals) / len(vals)
        cross_source_agreement = 1.0 - min(1.0, math.sqrt(variance))
    else:
        cross_source_agreement = 1.0 if per_source_mean else 0.0

    # Metric 10: narrative concentration (top-3 phrase share)
    phrase_counts: dict[str, int] = {}
    for _, c in classified:
        for phrase in c.key_phrases:
            phrase_counts[phrase] = phrase_counts.get(phrase, 0) + 1
    total_phrases = sum(phrase_counts.values())
    if total_phrases > 0:
        top3 = sorted(phrase_counts.values(), reverse=True)[:3]
        narrative_concentration = float(sum(top3)) / float(total_phrases)
    else:
        narrative_concentration = None

    # Optional metrics gated on optional_inputs
    optional = optional_inputs or {}
    put_call_ratio = optional.get("put_call_ratio")
    short_interest_pressure = optional.get("short_interest_pressure")
    institutional_retail_gap = optional.get("institutional_retail_gap")
    event_sensitivity = optional.get("event_sensitivity")

    return MetricSnapshot(
        ticker=ticker,
        captured_at=captured_at,
        sentiment_score=sentiment_score,
        buzz_volume=buzz_volume,
        sentiment_momentum=sentiment_momentum,
        bull_bear_ratio=bull_bear_ratio,
        buzz_sentiment_divergence=buzz_sentiment_divergence,
        social_velocity=social_velocity,
        cross_source_agreement=cross_source_agreement,
        put_call_ratio=put_call_ratio,
        short_interest_pressure=short_interest_pressure,
        narrative_concentration=narrative_concentration,
        institutional_retail_gap=institutional_retail_gap,
        event_sensitivity=event_sensitivity,
        source_breakdown={
            src: per_source_mean.get(src, 0.0) * weights.get(src, 0.0)
            for src in set(weights) | set(per_source_mean)
        },
    )


def _z_score(value: float, history: Sequence[float]) -> float:
    if len(history) < 2:
        return 0.0
    mean = sum(history) / len(history)
    variance = sum((v - mean) ** 2 for v in history) / len(history)
    stddev = math.sqrt(variance)
    if stddev == 0:
        return 0.0
    return (value - mean) / stddev
