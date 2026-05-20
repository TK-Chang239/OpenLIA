from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


# Extractor tier — how a registered fact is produced.
#   deterministic: pure JSONPath/Pydantic against fixed-shape payloads (e.g. EODHD)
#   compute: pure-math on already-extracted facts (e.g. CAGR, margins)
#   llm: tiny Haiku structured-output call for fuzzy judgment (e.g. peer_set)
ExtractorTier = Literal["deterministic", "compute", "llm"]

# Manifest entry kind — what produced the source.
#   fetch: structured tool call against a data provider
#   search: web/news search query
ManifestKind = Literal["fetch", "search"]


class ManifestEntry(_Strict):
    """One source of truth, citable as [N] across the run."""

    id: int = Field(ge=1)
    kind: ManifestKind
    provider: str
    identifier: str  # tool name + args fingerprint, or search query
    raw_payload: Any
    retrieved_at: datetime | str


# Source-tier provenance class.
#   vendor: pulled from a data vendor (e.g. EODHD fundamentals/live)
#   primary_filing: extracted from a primary filing (10-K, 10-Q, 8-K, press release)
#   derived: computed from other facts (compute tier)
SourceTier = Literal["vendor", "primary_filing", "derived"]


class Fact(_Strict):
    """A named, citation-tagged value produced by the registry."""

    name: str
    value: Any
    source_ids: list[int] = Field(min_length=1)
    extractor: ExtractorTier
    depends_on: list[str] = Field(default_factory=list)
    # Date the underlying data was captured/filed. For vendor fundamentals,
    # this is the most recent filing date present in the payload; for live
    # price snapshots, the snapshot date; for analyst data, the ManifestEntry
    # retrieval timestamp. None when the upstream payload lacks any date.
    data_as_of: datetime | str | None = None
    source_tier: SourceTier = "vendor"


class SectionTerminalState(StrEnum):
    SUCCESS = "success"
    DEGRADED = "degraded"
    DEGRADED_CAP_HIT = "degraded_cap_hit"
    EXHAUSTED = "exhausted"


class SectionResult(_Strict):
    section_id: str
    state: SectionTerminalState
    attempts: int = Field(ge=1)
    markdown: str | None = None
    failed_attempts: list[str] = Field(default_factory=list)
    validation_errors: list[str] = Field(default_factory=list)
    synthesis_hooks: dict[str, Any] | None = None

    @field_validator("markdown")
    @classmethod
    def _markdown_required_unless_exhausted(cls, v: str | None, info: Any) -> str | None:
        state = info.data.get("state")
        if state in (SectionTerminalState.EXHAUSTED, SectionTerminalState.DEGRADED_CAP_HIT):
            return v
        if v is None or not v.strip():
            raise ValueError("markdown required for success/degraded states")
        return v
