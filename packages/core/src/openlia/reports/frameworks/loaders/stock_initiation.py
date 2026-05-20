"""Default `stock_initiation` template loader.

PR 1 contract: the loader re-exports the existing runner constants — section
list, briefs, style guide, system role, word targets — as a `TemplateSpec`
without moving the constants themselves. The runner still reads from its own
hardcoded values; the loader output is a parallel structured view that PR 2
will make load-bearing by deleting the runner's constants and having the
runner read from the spec.

Optional declarative fields (freshness budgets, identity equations, cover
bindings, industry modes, scanner event classes) are left empty in PR 1 and
populated by later PRs as each Bucket-B lift lands.
"""

from __future__ import annotations

from openlia.llm.runtime.report_v2.runner import (
    BODY_SECTIONS_STOCK_INITIATION,
    DEFAULT_BRIEFS,
    DEFAULT_STYLE_GUIDE,
    DEFAULT_SYSTEM_ROLE,
    DEFAULT_WORD_TARGETS,
    SYNTHESIS_SECTIONS_STOCK_INITIATION,
)
from openlia.reports.frameworks.registry import default_registry
from openlia.reports.frameworks.template_spec import SectionSpec, TemplateSpec


def _build_sections(section_ids: tuple[str, ...]) -> tuple[SectionSpec, ...]:
    sections = []
    for sid in section_ids:
        sections.append(
            SectionSpec(
                id=sid,
                title=sid.replace("_", " ").title(),
                brief=DEFAULT_BRIEFS[sid],
                word_target=DEFAULT_WORD_TARGETS[sid],
            )
        )
    return tuple(sections)


def load_stock_initiation_template() -> TemplateSpec:
    return TemplateSpec(
        name="stock_initiation",
        global_preface="",
        body_sections=_build_sections(BODY_SECTIONS_STOCK_INITIATION),
        synthesis_sections=_build_sections(SYNTHESIS_SECTIONS_STOCK_INITIATION),
        style_guide=DEFAULT_STYLE_GUIDE,
        system_role=DEFAULT_SYSTEM_ROLE,
        default_word_targets=dict(DEFAULT_WORD_TARGETS),
        web_search_budget_default=20,
    )


default_registry.register("stock_initiation", load_stock_initiation_template)
