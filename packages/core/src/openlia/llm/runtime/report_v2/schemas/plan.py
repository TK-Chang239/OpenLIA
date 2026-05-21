"""Plan schema for stage 3 (Research planner) and stage 5 (Model planner).

See docs/superpowers/specs/2026-05-21-equity-research-v2.2-design.md §2 + §6.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ArtifactType = Literal["chart", "table", "kpi_strip", "excel", "quote_block"]
ArtifactSource = Literal["template", "composer", "planner"]


class ResearchStrand(BaseModel):
    id: str
    purpose: str
    allowed_tools: list[str] = Field(default_factory=list)


class ArtifactSpec(BaseModel):
    id: str
    type: ArtifactType
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    helper: str | None = None
    source_strand: str | None = None
    target_section_id: str | None = None
    source: ArtifactSource = "template"


class Plan(BaseModel):
    research_strands: list[ResearchStrand] = Field(default_factory=list)
    required_artifacts: list[ArtifactSpec] = Field(default_factory=list)
    optional_artifacts: list[ArtifactSpec] = Field(default_factory=list)
    section_dag: dict[str, list[str]] = Field(default_factory=dict)
    slipped_requests: list[str] = Field(default_factory=list)
