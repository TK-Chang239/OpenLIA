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


class DepartmentReadiness(BaseModel):
    id: str
    state: ReadinessState
    note: str | None = None
    basic: list[RequirementMapping]
    advanced: list[RequirementMapping]
    unmet: list[str]


class ReviewResult(BaseModel):
    summary: str
    departments: list[DepartmentReadiness]
