"""Template specification — the per-template configuration container.

A `TemplateSpec` carries everything the runner needs to dispatch a report against
a specific template: section list, briefs, style guide, optional declarative fields
for freshness budgets, identity equations, voice rules, cover bindings, industry
modes, and material/catalyst event classes.

The default equity-research template is built declaratively via a Python loader
(`openlia.reports.frameworks.loaders.stock_initiation`) and carries every optional
field. User-uploaded templates are constructed mechanically from parsed markdown
and typically populate only the required fields plus any frontmatter overrides.

Universal runtime mechanics (block shape gates, citation system, tombstone check,
year-label slip detection, retry loop) operate template-agnostically and need no
spec fields. Anything template-specific lives here.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, model_validator

VoiceFlag = Literal["any", "third_person_only"]
DispatchTier = Literal["body", "synthesis", "meta"]


class SectionSpec(BaseModel):
    """One section in a report template.

    `brief` is the prose passed verbatim to the section-writing LLM as the
    section's instruction. For the default template this is hand-authored
    markdown; for uploaded templates it is whatever prose appeared under the
    section's heading in the source document.
    """

    model_config = ConfigDict(frozen=True)

    id: str
    title: str
    brief: str

    voice: VoiceFlag = "any"
    word_target: int | None = None
    dispatch_tier: DispatchTier = "body"
    eager_helpers: tuple[str, ...] = ()
    lazy_helpers: tuple[str, ...] = ()
    required_facts: tuple[str, ...] = ()


class TemplateSpec(BaseModel):
    """Per-template configuration consumed by the runner.

    Required fields (`name`, `global_preface`, `body_sections`, `synthesis_sections`)
    are the minimum needed to dispatch. All other fields are optional declarative
    overrides; the default equity template populates them, uploaded templates start
    empty and may climb toward declarative rigor via the markdown frontmatter
    convention.
    """

    model_config = ConfigDict(frozen=True)

    name: str
    global_preface: str
    body_sections: tuple[SectionSpec, ...]
    synthesis_sections: tuple[SectionSpec, ...]

    style_guide: str = ""
    system_role: str = "You are a research section writer."
    default_word_targets: dict[str, int] = {}
    web_search_budget_default: int = 10
    freshness_budgets: dict[str, int] = {}
    identity_equations: tuple = ()
    material_event_classes: tuple[object, ...] = ()
    catalyst_classes: tuple[object, ...] = ()
    industry_modes: tuple[object, ...] = ()
    cover_bindings: dict[str, str] = {}

    @model_validator(mode="after")
    def _assert_partition_invariant(self) -> TemplateSpec:
        for section in (*self.body_sections, *self.synthesis_sections):
            overlap = set(section.eager_helpers) & set(section.lazy_helpers)
            if overlap:
                raise ValueError(
                    f"section {section.id!r}: eager_helpers and lazy_helpers must be disjoint; "
                    f"overlap: {sorted(overlap)}"
                )
        return self

    def section_by_id(self, section_id: str) -> SectionSpec | None:
        for section in (*self.body_sections, *self.synthesis_sections):
            if section.id == section_id:
                return section
        return None
