"""Retail Sentiment core package — classification, metrics, reliability, spikes."""

from openlia.retail_sentiment.schemas import (
    ClassificationLabel,
    ClassifiedItem,
    MetricSnapshot,
    RawSocialPost,
    SignalAlert,
    SpikeEvent,
)

__all__ = [
    "ClassificationLabel",
    "ClassifiedItem",
    "MetricSnapshot",
    "RawSocialPost",
    "SignalAlert",
    "SpikeEvent",
]
