"""Pydantic models for subagent output.

A subagent returns a ``SectionDraft`` via a forced ``submit_section``
tool call. The orchestrator collapses each draft into a ``PriorSection``
summary that is passed to subsequent subagents for narrative threading.
"""

from __future__ import annotations

from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class OpenQuestion(_Strict):
    section_id: str
    question: str


class SectionDraft(_Strict):
    section_id: str
    blocks: Annotated[list[dict[str, Any]], Field(min_length=1)]
    citations_used: list[str] = Field(default_factory=list)
    word_count: int = Field(ge=0)
    open_questions: list[str] = Field(default_factory=list)


class PriorSection(_Strict):
    section_id: str
    title: str
    summary: str
    key_facts_for_threading: Annotated[list[str], Field(min_length=0, max_length=5)] = Field(
        default_factory=list
    )
