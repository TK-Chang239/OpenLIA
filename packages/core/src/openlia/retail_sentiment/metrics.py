"""12-metric Retail Sentiment engine.

Computes the basic 7 metrics + the 5 optional metrics per the
RetailSentimentPageSpec. Optional inputs (options chains, short
interest, institutional holdings, historical prices) are gated:
the metric is `None` when its provider payload is missing or
malformed (graceful degrade per Design Rule 9).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import datetime
from itertools import pairwise
from typing import Any

from openlia.retail_sentiment.reliability import (
    DEFAULT_SOURCE_WEIGHTS,
    _normalize_weights,
)
from openlia.retail_sentiment.schemas import (
    ClassificationLabel,
    ClassifiedItem,
    MetricSnapshot,
    RawSocialPost,
)


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
    """Compute the 12-metric snapshot for a single ticker.

    Optional metrics return `None` when their provider input is missing.
    """
    classifications_by_id = {c.id: c for c in classifications}
    items = [(p, classifications_by_id.get(p.id)) for p in posts]
    classified = [(p, c) for p, c in items if c is not None]

    # Metric 1: mean sentiment.
    if classified:
        scores = [_score_for_label(c.classification) for _, c in classified]
        sentiment_score = sum(scores) / len(scores)
    else:
        sentiment_score = 0.0

    # Metric 2: buzz volume.
    # `buzz_count` keeps the raw integer; `buzz_volume` is the
    # spec-defined ratio of today / 30-day-mean (1.0 baseline when
    # there is no history). The historical baseline is taken from
    # `prior_snapshots[*].buzz_count` (back-fills from `buzz_volume` for
    # rows persisted before the rename).
    buzz_count = float(len(posts))
    history_counts = [
        float(getattr(s, "buzz_count", None) or s.buzz_volume) for s in prior_snapshots
    ]
    if history_counts:
        baseline_mean = sum(history_counts) / len(history_counts)
        buzz_volume = (buzz_count / baseline_mean) if baseline_mean > 0 else 0.0
    else:
        buzz_volume = 1.0 if buzz_count > 0 else 0.0

    # Metric 3: momentum vs prior snapshot.
    if prior_snapshots:
        sentiment_momentum = sentiment_score - prior_snapshots[-1].sentiment_score
    else:
        sentiment_momentum = 0.0

    # Metric 4: bull / bear ratio.
    bulls = sum(1 for _, c in classified if c.classification is ClassificationLabel.BULLISH)
    bears = sum(1 for _, c in classified if c.classification is ClassificationLabel.BEARISH)
    bull_bear_ratio = float(bulls) / float(max(bears, 1))

    # Metric 5: buzz-sentiment divergence (z-score gap).
    if len(prior_snapshots) >= 2:
        prior_buzz = [s.buzz_volume for s in prior_snapshots]
        prior_sent = [s.sentiment_score for s in prior_snapshots]
        buzz_z = _z_score(buzz_volume, prior_buzz)
        sent_z = _z_score(sentiment_score, prior_sent)
        buzz_sentiment_divergence = abs(buzz_z) - abs(sent_z)
    else:
        buzz_sentiment_divergence = 0.0

    # Metric 6: social velocity (posts per hour over last 24h window).
    if posts:
        latest = max(p.created_at for p in posts)
        window_start = latest.timestamp() - 24 * 3600
        recent = [p for p in posts if p.created_at.timestamp() >= window_start]
        social_velocity = len(recent) / 24.0
    else:
        social_velocity = 0.0

    # Metric 7 + 12: cross-source agreement + breakdown.
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

    # Metric 10: narrative concentration (top-3 phrase share).
    # NOTE: NeutralClassifier emits no key_phrases, so this metric is
    # only populated when an LLM-backed classifier is wired.
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

    optional = optional_inputs or {}
    put_call_ratio = _put_call_sentiment_ratio(optional.get("options_data"), sentiment_score)
    short_interest_pressure = _short_interest_pressure(optional.get("short_interest"))
    institutional_retail_gap = _institutional_retail_gap(
        optional.get("institutional_holdings"), sentiment_score
    )
    event_sensitivity = _event_sensitivity(optional.get("historical_prices"))

    return MetricSnapshot(
        ticker=ticker,
        captured_at=captured_at,
        sentiment_score=sentiment_score,
        buzz_volume=buzz_volume,
        buzz_count=buzz_count,
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


# ---------------------------------------------------------------------------
# Optional metrics
# ---------------------------------------------------------------------------


def _put_call_sentiment_ratio(payload: Any, sentiment_score: float) -> float | None:
    """Metric 8: Put/Call Sentiment Ratio. Returns None when the options
    payload is missing or unusable. Formula: (puts / calls) * (1 - sentiment).

    Expected payload shape: dict with `puts` + `calls` numeric volume.
    """
    if not isinstance(payload, dict):
        return None
    puts = payload.get("puts")
    calls = payload.get("calls")
    if not isinstance(puts, int | float) or not isinstance(calls, int | float):
        return None
    if calls <= 0:
        return None
    pc = float(puts) / float(calls)
    return float(pc * (1.0 - sentiment_score))


def _short_interest_pressure(payload: Any) -> float | None:
    """Metric 9: Short Interest Pressure = short_pct_float * days_to_cover.
    None when either field missing."""
    if not isinstance(payload, dict):
        return None
    short_pct = payload.get("short_pct_float")
    days = payload.get("days_to_cover")
    if not isinstance(short_pct, int | float) or not isinstance(days, int | float):
        return None
    return float(short_pct) * float(days)


def _institutional_retail_gap(payload: Any, sentiment_score: float) -> float | None:
    """Metric 11: Institutional-Retail Gap = institutional_change_pct -
    retail_sentiment. None when institutional change% missing."""
    if not isinstance(payload, dict):
        return None
    inst_change = payload.get("change_pct")
    if not isinstance(inst_change, int | float):
        return None
    return float(inst_change) - float(sentiment_score)


def _event_sensitivity(payload: Any) -> float | None:
    """Metric 12: Event Sensitivity Score over last 30 trading days.

    Returns None on cold start (<30 daily samples). Spec page handles
    the "Insufficient data (N/30 days)" message in the UI.

    Computed as the std-dev of daily simple returns; expresses how
    reactive price has been to news flow over the window.
    """
    if not isinstance(payload, list) or len(payload) < 30:
        return None
    closes: list[float] = []
    for entry in payload[-30:]:
        if isinstance(entry, dict):
            close = entry.get("close") or entry.get("adjusted_close")
        else:
            close = entry
        if not isinstance(close, int | float):
            return None
        closes.append(float(close))
    if len(closes) < 30:
        return None
    returns: list[float] = []
    for prev, cur in pairwise(closes):
        if prev <= 0:
            return None
        returns.append((cur - prev) / prev)
    if not returns:
        return None
    mean = sum(returns) / len(returns)
    variance = sum((r - mean) ** 2 for r in returns) / len(returns)
    return float(math.sqrt(variance))
