"""Pydantic models for the report plan emitted by the flagship in the
planning phase of the subagent runner.

The flagship calls `plan_report` once. Its arguments — validated as
`ReportPlan` — drive eager fetching, per-section subagent dispatch, and
the editor pass.
"""

from __future__ import annotations

from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DataPath(_Strict):
    """A single data dependency for a section.

    Set EITHER ``ref`` (reference an existing payload from a prior data
    path in this plan) OR (``tool_name`` + ``tool_arguments``) to declare
    a new tool dispatch. Optional ``path`` slices into the result.
    """

    ref: str | None = None
    tool_name: str | None = None
    tool_arguments: dict[str, Any] | None = None
    path: str | None = None
    purpose: str

    @model_validator(mode="after")
    def _one_source_only(self) -> DataPath:
        has_ref = self.ref is not None
        has_tool = self.tool_name is not None
        if has_ref == has_tool:
            raise ValueError("DataPath must set exactly one of `ref` or `tool_name`.")
        if has_tool and self.tool_arguments is None:
            raise ValueError("DataPath with `tool_name` must also set `tool_arguments`.")
        return self


class SectionPlan(_Strict):
    section_id: str
    title: str
    narrative_goal: str
    key_questions: Annotated[list[str], Field(min_length=3, max_length=6)]
    target_depth: Literal["brief", "standard", "deep"]
    word_budget: int = Field(ge=100, le=2000)
    data_paths: list[DataPath] = Field(default_factory=list)
    cross_refs: list[str] = Field(default_factory=list)


class ReportPlan(_Strict):
    company_thesis: str
    sections: Annotated[list[SectionPlan], Field(min_length=1)]
    cross_section_themes: Annotated[list[str], Field(min_length=2, max_length=4)]

    @model_validator(mode="after")
    def _section_ids_unique(self) -> ReportPlan:
        ids = [s.section_id for s in self.sections]
        if len(ids) != len(set(ids)):
            raise ValueError("Section IDs must be unique within a plan.")
        return self
