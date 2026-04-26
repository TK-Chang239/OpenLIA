"""Pydantic schema for AI review output."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel


class ReadinessState(StrEnum):
    READY = "ready"
    GAPS = "gaps"
    DISABLED = "disabled"
    BLOCKED = "blocked"


class RequirementMapping(BaseModel):
    type: str
    provider: str | None
    confidence: float
    provider_id: str | None = None
    provider_label: str | None = None
    provider_mode: str | None = None
    provider_url: str | None = None
    provider_status: str | None = None


class DepartmentReadiness(BaseModel):
    id: str
    state: ReadinessState
    note: str | None = None
    basic: list[RequirementMapping]
    advanced: list[RequirementMapping]
    unmet: list[str]
    check_status: str = "pending"


class ReviewResult(BaseModel):
    summary: str
    departments: list[DepartmentReadiness]
