from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

TaskType = Literal[
    "clarification",
    "research_strand",
    "model_component",
    "section_draft",
    "trigger_eval",
    "verification",
    "output_render",
]

Status = Literal["OK", "SKIPPED", "DEGRADED", "FAILED"]


class TaskOutcome(BaseModel):
    task_type: TaskType
    task_name: str
    status: Status
    notes: str | None = None
    duration_ms: int = 0


class RunSummary(BaseModel):
    engine_version: str
    template_id: str
    template_name: str
    composer_inputs: dict = Field(default_factory=dict)
    outcomes: list[TaskOutcome] = Field(default_factory=list)
    unsupported_requests_dismissed: list[str] = Field(default_factory=list)
    unsupported_requests_slipped: list[str] = Field(default_factory=list)
    total_duration_ms: int = 0
    total_token_cost: int | None = None
    cache_stats: dict = Field(default_factory=dict)
