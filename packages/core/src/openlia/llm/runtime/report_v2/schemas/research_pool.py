"""ResearchPool and Citation schemas for stage 4 (gather).

See docs/superpowers/specs/2026-05-21-equity-research-v2.2-design.md §4.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class Citation(BaseModel):
    id: str
    source_type: Literal["tool_call", "web_fetch", "user_upload", "internal_model"]
    tool: str | None = None
    url: str | None = None
    title: str
    retrieved_at: datetime
    snippet: str | None = None
    served_from_cache: bool = False


class ResearchPool(BaseModel):
    findings_by_strand: dict[str, str] = Field(default_factory=dict)
    citations: list[Citation] = Field(default_factory=list)
    failed_strands: list[str] = Field(default_factory=list)
    cache_hits: int = 0
    cache_misses: int = 0
