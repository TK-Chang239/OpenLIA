"""Extended TemplateSpec for v2.2.

Sees §4.2 of docs/superpowers/specs/2026-05-21-equity-research-v2.2-design.md.
One report type per template (locked); composer_inputs typed; trigger_when as
the single conditionality mechanism; required_artifacts MUST attempt.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field

ComposerInputType = Literal[
    "ticker",
    "ticker_list",
    "sector",
    "string",
    "enum",
    "int",
    "bool",
    "date_range",
]

ArtifactType = Literal["chart", "table", "kpi_strip", "excel", "quote_block"]

ArtifactSource = Literal["template", "composer", "planner"]


class ComposerInputSpec(BaseModel):
    name: str
    type: ComposerInputType
    label: str
    required: bool = False
    enum_options: list[str] | None = None
    default: Any | None = None


class ArtifactSpec(BaseModel):
    id: str
    type: ArtifactType
    description: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    helper: str | None = None
    source_strand: str | None = None
    target_section_id: str | None = None
    source: ArtifactSource = "template"


class SectionSpec(BaseModel):
    id: str
    name: str
    directive: str
    depends_on: list[str] = Field(default_factory=list)
    trigger_when: str | None = None
    # Per-section word count and tolerance controls.
    # Default 200 / 20 / 80 preserve the previously hardcoded prompt behaviour.
    min_words: int = 200
    tolerance_pct: int = 20
    expand_below_pct: int = 80


class RailSpec(BaseModel):
    """Rail configuration declared in the template YAML under the ``rail:`` key.

    ``required_quick_stats`` replaces the hardcoded ``_REQUIRED_RAIL_QUICK_STATS``
    dict that previously lived in ``validator.py``. If absent (``None``), rail
    validation is skipped entirely for this template.
    """

    required_quick_stats: list[str] | None = None


class ThreadingSpec(BaseModel):
    """Threading configuration declared under the ``threading:`` key.

    Callers pass ``summary_word_cap`` and ``facts_cap`` to
    ``summarize_section_draft``; unset fields default to 200/5 (existing
    hardcoded values) so behaviour is bit-for-bit unchanged when the block
    is absent.
    """

    summary_word_cap: int = 200
    facts_cap: int = 5


class TemplateSpecV2(BaseModel):
    template_id: str
    template_name: str
    department: str
    report_type: str
    engine_version_compat: str
    composer_inputs: list[ComposerInputSpec] = Field(default_factory=list)
    required_artifacts: list[ArtifactSpec] = Field(default_factory=list)
    output_artifacts: list[ArtifactSpec] = Field(default_factory=list)
    sections: list[SectionSpec]
    verifier_severity_overrides: dict[str, str] = Field(default_factory=dict)
    rail: RailSpec = Field(default_factory=RailSpec)
    threading: ThreadingSpec = Field(default_factory=ThreadingSpec)
