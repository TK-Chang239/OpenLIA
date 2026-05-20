"""Compile a `ParsedTemplate` into a `TemplateSpec` dict (PR 13).

The parser (PR 11) splits markdown into sections; this service maps the
result onto the `TemplateSpec` schema consumed by the runner. All sections
land in `body_sections` by default; per-section `dispatch_tier` frontmatter
moves a section into the synthesis or meta tier. Document-level frontmatter
populates the optional declarative fields (freshness_budgets, cover_bindings,
etc.) when present.
"""

from __future__ import annotations

from typing import Any

from openlia_server.services.template_parser import ParsedSection, ParsedTemplate

_SECTION_FRONTMATTER_KEYS = {
    "voice",
    "word_target",
    "dispatch_tier",
    "preload_helpers",
    "lazy_helpers",
    "required_facts",
}

_DOCUMENT_FRONTMATTER_KEYS = {
    "name",
    "style_guide",
    "system_role",
    "default_word_targets",
    "web_search_budget_default",
    "freshness_budgets",
    "identity_equations",
    "material_event_classes",
    "catalyst_classes",
    "industry_modes",
    "cover_bindings",
}


def _section_to_dict(section: ParsedSection) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": section.id,
        "title": section.title,
        "brief": section.brief,
    }
    fm = section.frontmatter or {}
    if "voice" in fm:
        out["voice"] = fm["voice"]
    if "word_target" in fm:
        out["word_target"] = fm["word_target"]
    if "dispatch_tier" in fm:
        out["dispatch_tier"] = fm["dispatch_tier"]
    if "preload_helpers" in fm:
        out["eager_helpers"] = tuple(fm["preload_helpers"])
    if "lazy_helpers" in fm:
        out["lazy_helpers"] = tuple(fm["lazy_helpers"])
    if "required_facts" in fm:
        out["required_facts"] = tuple(fm["required_facts"])
    return out


def compile_template_spec(
    parsed: ParsedTemplate,
    *,
    name: str,
) -> dict[str, Any]:
    """Materialize a TemplateSpec dict from a `ParsedTemplate`.

    Sections with `dispatch_tier: synthesis` or `meta` in their frontmatter
    are routed to the matching tier. The remainder land in `body_sections`.
    Document-level frontmatter keys overwrite the optional declarative
    fields; unknown keys are silently dropped.
    """

    body: list[dict[str, Any]] = []
    synthesis: list[dict[str, Any]] = []
    meta: list[dict[str, Any]] = []
    for section in parsed.sections:
        tier = (section.frontmatter or {}).get("dispatch_tier", "body")
        section_dict = _section_to_dict(section)
        if tier == "synthesis":
            synthesis.append(section_dict)
        elif tier == "meta":
            # Meta sections live in synthesis_sections with dispatch_tier=meta —
            # the runner reads them via TemplateSpec.meta_sections.
            section_dict["dispatch_tier"] = "meta"
            meta.append(section_dict)
        else:
            body.append(section_dict)

    spec: dict[str, Any] = {
        "name": (parsed.document_frontmatter or {}).get("name", name),
        "global_preface": parsed.global_preface,
        "body_sections": body,
        "synthesis_sections": synthesis + meta,
    }
    for key in _DOCUMENT_FRONTMATTER_KEYS:
        if key == "name":
            continue
        if key in (parsed.document_frontmatter or {}):
            spec[key] = parsed.document_frontmatter[key]
    return spec
