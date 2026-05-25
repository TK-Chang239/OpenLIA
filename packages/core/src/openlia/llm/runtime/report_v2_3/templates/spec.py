"""Structured template schema for the v2.3 equity-research engine.

A ``TemplateSpec`` is the user-facing source of truth for a report's
structure: the section list, per-section intent, optional methodology
hints, and metadata like default length. The engine's job is to fill
each section with researched facts and prose; the engine does not
invent which sections exist or what they are about — that comes from
the template.

Built-in templates live in ``builtins.py`` (one per ``ReportType``);
user-uploaded templates will eventually land in a separate persistence
layer (Phase 1.5). Either way the loaded template flows through every
stage via ``ReportState.template``.
"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from ..schemas import ReportLength


class SectionSpec(BaseModel):
    """One section in a template — id, title, intent, optional hints.

    ``id`` is the stable identifier the engine carries through PLAN,
    SYNTHESIZE, WRITE, ASSEMBLE. ``intent`` is one short line the
    planner / writer LLMs read directly; it is the closest thing the
    template has to a directive. ``methodology_hints`` is informational
    only in Phase 1 (no enforcement) — the planner LLM may consult them
    when selecting fact_ids and the writer LLM when shaping prose.
    """

    id: str = Field(..., min_length=1, pattern=r"^[a-z0-9_]+$")
    title: str = Field(..., min_length=1)
    intent: str = Field(..., min_length=1)
    methodology_hints: list[str] = Field(default_factory=list)


class TemplateSpec(BaseModel):
    """A complete template — the structure the engine fills in.

    ``shape_description`` replaces the per-``ReportType`` paragraph that
    used to live in the CLARIFY prompt's ``_BUILTIN_TEMPLATE_SHAPES``
    map. It is fed verbatim to the clarifier LLM so the run's context
    includes what kind of report the user is asking for. Keep it short
    (one paragraph, ~3 sentences).

    ``ticker_anchored`` signals whether the report requires a subject
    ticker. CLARIFY reads this flag — when false, it skips the
    forced-ticker question for topic-only prompts. Macro / thematic /
    sector-level templates flip it false. ``default_length`` is a soft
    default the runner may apply when the request does not specify a
    length.
    """

    template_id: str = Field(..., min_length=1, pattern=r"^[a-z0-9_]+$")
    name: str = Field(..., min_length=1)
    shape_description: str = Field(..., min_length=1)
    ticker_anchored: bool = True
    default_length: ReportLength | None = None
    sections: list[SectionSpec] = Field(..., min_length=1)

    @model_validator(mode="after")
    def _check_unique_section_ids(self) -> TemplateSpec:
        seen: set[str] = set()
        for section in self.sections:
            if section.id in seen:
                raise ValueError(f"duplicate section id: {section.id!r}")
            seen.add(section.id)
        return self
