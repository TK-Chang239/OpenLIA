"""Typed contracts for the report_dash_rs engine.

Run-level types (RunRequest/RunResult/EnabledConnectors/...) are shared with
report_dash_mr and re-exported here so the engine's relative imports resolve.
Only the RS dashboard payload is RS-specific.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from ..report_dash_mr.schemas import (  # noqa: F401
    ChartDataPoint,
    ChartSpec,
    ChartType,
    CitationLogEntry,
    EnabledConnectors,
    RunRequest,
    RunResult,
    RunStatus,
)


class Signal(BaseModel):
    name: str
    severity: Literal["info", "caution", "alert"]
    note: str


class EvidenceItem(BaseModel):
    title: str
    url: str
    source: str
    classification: Literal["bullish", "bearish", "neutral"]
    published_at: str | None = None


class RetailSentimentData(BaseModel):
    """Single-ticker retail-sentiment dashboard payload."""

    subject: str
    sentiment_score: float = Field(ge=-1.0, le=1.0)
    direction: Literal["bullish", "bearish", "neutral"]
    momentum: float | None = None
    trend_label: str | None = None
    buzz_level: Literal["low", "elevated", "high"]
    buzz_note: str
    bull_pct: float = Field(ge=0.0, le=100.0)
    bear_pct: float = Field(ge=0.0, le=100.0)
    narratives: list[str]
    signals: list[Signal]
    evidence: list[EvidenceItem]
    narrative: str
    aggregated_sentiment: float | None = None
    analyst_gap: float | None = None
    captured_at: str | None = None
