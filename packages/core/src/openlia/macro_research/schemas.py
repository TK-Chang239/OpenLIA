"""Pydantic DTOs shared across the MR department."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field

SeverityLevel = Literal["green", "amber", "red", "neutral"]


@dataclass(frozen=True)
class SnapshotEntry:
    """One dashboard's contribution to the cross-department MRSnapshot:
    the already-derived value (debt-cycle phase, economic season, or active-
    force count) plus when that dashboard payload was generated."""

    value: str | int
    generated_at: datetime


class MRSnapshot(BaseModel):
    """Read-only cross-department view. Consumed by Morning Briefing."""

    debt_cycle_phase: str | None = None
    economic_season: str | None = None
    active_force_count: int | None = None
    generated_at: datetime | None = None
    is_stale: bool = False


class DashboardTierOutput(BaseModel):
    """Output of a single tier for a dashboard."""

    tier: Literal["T1", "T2", "T3", "T4", "T5"]
    data: dict[str, Any] = Field(default_factory=dict)
    errors: list[str] = Field(default_factory=list)
    generated_at: datetime | None = None


class DashboardResult(BaseModel):
    """Full result of running one dashboard through T1-T5."""

    slug: str
    display_name: str
    severity: SeverityLevel = "neutral"
    tiers: list[DashboardTierOutput] = Field(default_factory=list)
    headline: str | None = None
    generated_at: datetime
    smart_mode_active: bool = False
