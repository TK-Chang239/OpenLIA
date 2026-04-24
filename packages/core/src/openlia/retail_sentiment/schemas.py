"""Pydantic DTOs shared across classifier, metrics, runner, routes."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ClassificationLabel(StrEnum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class RawSocialPost(BaseModel):
    """A single raw social post or news article prior to classification."""

    model_config = ConfigDict(frozen=True)

    id: str
    ticker: str
    source: str
    text: str
    engagement: dict[str, int] = Field(default_factory=dict)
    created_at: datetime


class ClassifiedItem(BaseModel):
    """Result of a single NLP classification for one post."""

    model_config = ConfigDict(frozen=True)

    id: str
    classification: ClassificationLabel
    confidence: float = Field(ge=0.0, le=1.0)
    key_phrases: list[str] = Field(default_factory=list)


class MetricSnapshot(BaseModel):
    """All 12 metrics for a single ticker at a point in time."""

    model_config = ConfigDict(frozen=True)

    ticker: str
    captured_at: datetime

    sentiment_score: float
    buzz_volume: float
    sentiment_momentum: float
    bull_bear_ratio: float
    buzz_sentiment_divergence: float
    social_velocity: float
    cross_source_agreement: float
    put_call_ratio: float | None = None
    short_interest_pressure: float | None = None
    narrative_concentration: float | None = None
    institutional_retail_gap: float | None = None
    event_sensitivity: float | None = None
    source_breakdown: dict[str, float] = Field(default_factory=dict)


SignalSeverity = Literal["panic", "stealth_recovery", "caution", "info"]


class SignalAlert(BaseModel):
    """An active signal fired by the metric engine at snapshot time."""

    model_config = ConfigDict(frozen=True)

    ticker: str
    metric_id: str
    severity: SignalSeverity
    message: str
    value: float


class SpikeEvent(BaseModel):
    """A 7-day volume spike detection result."""

    model_config = ConfigDict(frozen=True)

    ticker: str
    detected_at: datetime
    buzz: float
    baseline_mean: float
    baseline_stddev: float
    z_score: float
