"""7-day volume spike detector."""

from __future__ import annotations

import math
from collections.abc import Sequence
from datetime import datetime

from openlia.retail_sentiment.schemas import MetricSnapshot, SpikeEvent

SPIKE_Z_THRESHOLD = 2.0


def detect_spike(
    *,
    ticker: str,
    detected_at: datetime,
    current_buzz: float,
    recent_snapshots: Sequence[MetricSnapshot],
) -> SpikeEvent | None:
    """Return a SpikeEvent if ``current_buzz`` exceeds mean + 2 stddev over
    the provided recent (7-day) snapshot history."""
    if len(recent_snapshots) < 3:
        return None
    buzz = [s.buzz_volume for s in recent_snapshots]
    mean = sum(buzz) / len(buzz)
    variance = sum((v - mean) ** 2 for v in buzz) / len(buzz)
    stddev = math.sqrt(variance)
    if stddev == 0:
        return None
    z = (current_buzz - mean) / stddev
    if z < SPIKE_Z_THRESHOLD:
        return None
    return SpikeEvent(
        ticker=ticker,
        detected_at=detected_at,
        buzz=current_buzz,
        baseline_mean=mean,
        baseline_stddev=stddev,
        z_score=z,
    )
