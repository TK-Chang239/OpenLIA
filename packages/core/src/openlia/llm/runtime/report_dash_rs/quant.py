"""Deterministic retail-sentiment scoring + signal flags.

The LLM gathers and classifies the discussion; this module turns the counts
into the headline score, the bull/bear split, and the threshold-based signal
flags, so the numbers are computed rather than invented. Momentum is derived
from cached snapshot history by the run service.
"""

from __future__ import annotations

from dataclasses import dataclass, field

_BULLISH_CUTOFF = 0.15
_BEARISH_CUTOFF = -0.15


@dataclass(frozen=True)
class RetailSentimentInputs:
    bullish: int
    bearish: int
    neutral: int
    buzz_level: str  # "low" | "elevated" | "high"


@dataclass
class RetailSentimentClassification:
    sentiment_score: float
    direction: str
    bull_pct: float
    bear_pct: float
    signals: list[dict] = field(default_factory=list)


def classify_retail_sentiment(inp: RetailSentimentInputs) -> RetailSentimentClassification:
    total = inp.bullish + inp.bearish + inp.neutral
    if total <= 0:
        return RetailSentimentClassification(0.0, "neutral", 0.0, 0.0, [])
    score = round((inp.bullish - inp.bearish) / total, 4)
    if score > _BULLISH_CUTOFF:
        direction = "bullish"
    elif score < _BEARISH_CUTOFF:
        direction = "bearish"
    else:
        direction = "neutral"
    bull_pct = round(inp.bullish / total * 100, 1)
    bear_pct = round(inp.bearish / total * 100, 1)
    signals: list[dict] = []
    if inp.buzz_level == "high" and direction == "bearish":
        signals.append(
            {
                "name": "Panic",
                "severity": "alert",
                "note": "High buzz with negative tone — crowd anxiety.",
            }
        )
    if inp.buzz_level == "high" and direction == "bullish":
        signals.append(
            {
                "name": "FOMO / crowding",
                "severity": "caution",
                "note": "High buzz with bullish tone — possible crowding.",
            }
        )
    if inp.buzz_level == "low" and direction == "bullish":
        signals.append(
            {
                "name": "Stealth recovery",
                "severity": "info",
                "note": "Quiet tape with improving tone.",
            }
        )
    return RetailSentimentClassification(score, direction, bull_pct, bear_pct, signals)


def momentum_from_history(scores: list[float]) -> tuple[float | None, str]:
    """Momentum from sentiment-score history (oldest-first). Needs >= 2 points."""
    if len(scores) < 2:
        return None, "building history"
    delta = round(scores[-1] - scores[-2], 4)
    if delta > 0.05:
        label = "improving"
    elif delta < -0.05:
        label = "deteriorating"
    else:
        label = "flat"
    return delta, label
