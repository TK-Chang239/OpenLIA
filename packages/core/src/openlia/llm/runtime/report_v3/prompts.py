"""System prompt builder for the v3 engine.

One function: ``build_system_prompt(request, catalog)`` produces the
single system message the model sees for the whole run. The prompt
intentionally short — it states the goal, lists the template
sections, enumerates the tools, and sets the citation contract. No
"MUST NOT" walls; no marker grammar to memorize beyond standard
Markdown footnote syntax.
"""

from __future__ import annotations

from .schemas import Language, ReportLength, ReviseContext, RunRequest, TemplateSpec
from .tools.registry import ToolCatalog

_LANGUAGE_LABELS: dict[Language, str] = {
    Language.EN: "English",
    Language.ZH_TW: "Traditional Chinese (zh-TW)",
}

# Approximate target word counts surfaced to the model as soft guidance.
# Not enforced server-side per the v3 design (decision #3); just a hint.
_LENGTH_TARGETS: dict[ReportLength, str] = {
    ReportLength.CONCISE: "~1,500 words total across all sections",
    ReportLength.NORMAL: "~3,500 words total across all sections",
    ReportLength.ELABORATIVE: "~6,000 words total across all sections",
}


def build_system_prompt(
    *,
    request: RunRequest,
    catalog: ToolCatalog,
) -> str:
    """Compose the v3 system prompt for one run.

    Two structural modes, decided by whether the template carries any
    sections:
      - templated: the section list is fixed; the model must write every
        section id before ``finalize``.
      - freeform (empty ``sections``): the model designs its own
        sections, guided by the analyst instructions and the subject.

    ``request.instructions`` (when present) is injected as an
    authoritative ``# Analyst instructions`` block. In freeform mode the
    instructions effectively define the report's shape.
    """
    template = request.template
    language_label = _LANGUAGE_LABELS.get(request.language, request.language.value)
    length_target = _LENGTH_TARGETS.get(request.length, "moderate length")

    tools_block = _render_tools_block(catalog)
    capability_index = _render_capability_index(catalog)

    return _PROMPT_TEMPLATE.format(
        subject=request.subject,
        language=language_label,
        length_target=length_target,
        template_name=template.name,
        shape_description=template.shape_description,
        instructions_block=_render_instructions_block(request.instructions),
        structure_block=_render_structure_block(template),
        tools_block=tools_block,
        capability_index=capability_index,
    )


def _render_instructions_block(instructions: str | None) -> str:
    """The ``# Analyst instructions`` block, or empty when none given.

    A trailing blank line keeps the surrounding template's spacing
    intact when the block is omitted.
    """
    if not instructions or not instructions.strip():
        return ""
    return (
        "# Analyst instructions\n\n"
        "The user provided the methodology and guidance below. Treat it as "
        "authoritative for how to approach this report — what to research and "
        "emphasize, how to reason, tone, and (where it specifies one) the "
        "report's structure.\n\n"
        f"{instructions.strip()}\n\n"
    )


def _render_structure_block(template: TemplateSpec) -> str:
    """Either the fixed section list (templated) or the freeform
    directive (empty ``sections``)."""
    if not template.sections:
        return _FREEFORM_STRUCTURE_BLOCK
    section_lines: list[str] = []
    for spec in template.sections:
        hints = ", ".join(spec.methodology_hints) if spec.methodology_hints else "none"
        section_lines.append(
            f"  - id: {spec.id}\n"
            f"    title: {spec.title}\n"
            f"    intent: {spec.intent}\n"
            f"    methodology_hints: {hints}"
        )
    sections_block = "\n".join(section_lines)
    return (
        "The report has these sections. You MUST produce a `write_section` "
        "call for every section id below before calling `finalize`.\n\n"
        f"{sections_block}"
    )


_FREEFORM_STRUCTURE_BLOCK = """\
No fixed section structure is imposed. Design the report's sections
yourself — guided by the analyst instructions above (if any) and the
subject. For each section call `write_section` with a short
`lowercase_snake_case` section id and a human-readable `title`. Aim for
a coherent, well-organized report; write at least one section before
calling `finalize`."""


def _render_tools_block(catalog: ToolCatalog) -> str:
    """One line per always-on core tool."""
    return "\n".join(
        f"  - {descriptor.name}: {descriptor.description}" for descriptor in catalog.descriptors
    )


def _render_capability_index(catalog: ToolCatalog) -> str:
    """Render the Layer-1 capability map (category -> summary).

    This advertises what can be summoned via ``find_tools`` without
    listing every individual schema — keeping always-on context flat
    while the model still knows the full surface exists.
    """
    if not catalog.category_index:
        return "  (no specialized tool categories registered)"
    return "\n".join(
        f"  - {category}: {summary}" for category, summary in sorted(catalog.category_index.items())
    )


_PROMPT_TEMPLATE = """\
You are an equity research analyst producing a report for a professional
investor. The report structure is fixed by the user's template (below).
Your job: research the subject, write each section, embed citations and
charts where they add value.

# Report subject
{subject}

# Report language
{language}

# Report length target
{length_target} (a soft target — write the length that fits the material).

# Template: {template_name}
{shape_description}

{instructions_block}# Report structure

{structure_block}

# Tools

You have these tools always available. Use them freely. Research
thoroughly, verify numbers before citing them, and run `run_dcf` /
`run_comps` / `run_sensitivity` when valuation is in scope. Corroborate
material claims across multiple independent sources rather than leaning
on any single outlet or domain; prefer primary sources — company
filings, official releases, first-party data — and use secondary
reporting to cross-check rather than as the sole basis for a claim.

{tools_block}

# Specialized tool library

Beyond the always-available tools above, a larger library of
specialized analysis tools exists. They are NOT loaded by default — to
keep your focus sharp you only load what a given subject needs. Call
`find_tools(query=..., category=...)` to discover and load them; the
matched tools become callable immediately and you cite their results
the same way (by the `source_id` each returns).

Capability categories you can search:

{capability_index}

Use `find_tools` whenever the subject calls for analysis the core
tools don't cover (e.g. a forensic accounting check or a
return-on-capital / business-quality panel). Don't force it — if the
core tools suffice, proceed without it.

# Citation rules

Every numeric or factual claim must cite a tool result. Cite inline
with Markdown footnote syntax: `[^source_id]` (e.g. `[^web_3]` or
`[^eodhd_1]`). When a tool returns, its result tells you the assigned
`source_id` — use that. After each web search, a follow-up message
lists the `[^web_N]` markers for the results it found; cite web facts
with those markers. Do NOT use the provider's own citation format
(e.g. `<cite index=...>` or `[^6-1]`) — only the `[^source_id]` markers
the tools and web-search notices give you resolve in the bibliography.

Unresolved citations cause `write_section` to reject. Fix the markers
and re-emit. Charts are referenced as `{{chart:<chart_id>}}` and must
be emitted via `emit_chart` before any section references them.

# Cover hero

Before calling `finalize()`, call `set_cover(...)` once with the
report's headline thesis. Pass a one-sentence `tagline`, 3-5 `tldr`
bullets distilling the most important takeaways, 3-6 `key_metrics`
cards (label + pre-formatted value with units like '$1.2B' or
'24.7%', plus an optional change like '+18% YoY'), and an investment
`rating` ('Buy' / 'Hold' / 'Overweight' / etc.; omit the field for
sector reports where a single-name rating does not apply). This
populates the report's cover hero panel — without it the cover
renders bare with just the subject + template label.

# When to call finalize()

When every template section has been written, `set_cover` has been
called, and you are satisfied with the report. If `finalize()`
reports missing sections, write the missing ones and call again."""


def build_revise_system_prompt(
    *,
    request: RunRequest,
    catalog: ToolCatalog,
    revise: ReviseContext,
) -> str:
    """Compose the v3 system prompt for a revision pass.

    Differences vs. the original prompt:
      - Surfaces the prior report verbatim so the model knows exactly
        what to change vs. preserve.
      - States the user's revision request as the goal (instead of
        "produce a full report").
      - Loosens the section-id contract: revisions can rewrite any
        existing section AND add new sections beyond the template.
      - Loosens the finalize gate: revisions can finalize after
        touching just one section.
    """
    template = request.template
    language_label = _LANGUAGE_LABELS.get(request.language, request.language.value)
    length_target = _LENGTH_TARGETS.get(request.length, "moderate length")

    section_lines: list[str] = []
    for spec in template.sections:
        hints = ", ".join(spec.methodology_hints) if spec.methodology_hints else "none"
        section_lines.append(
            f"  - id: {spec.id}\n"
            f"    title: {spec.title}\n"
            f"    intent: {spec.intent}\n"
            f"    methodology_hints: {hints}"
        )
    sections_block = "\n".join(section_lines)

    tools_block = _render_tools_block(catalog)
    capability_index = _render_capability_index(catalog)

    prior_lines: list[str] = []
    for section in revise.prior_sections:
        prior_lines.append(f"## {section.title} (id: {section.section_id})\n\n{section.markdown}")
    prior_block = "\n\n".join(prior_lines) if prior_lines else "(no prior sections)"

    prior_chart_lines = [
        f"  - {c.chart_id}: {c.chart_type} — {c.title}" for c in revise.prior_charts
    ]
    prior_charts_block = "\n".join(prior_chart_lines) if prior_chart_lines else "  (none)"

    return _REVISE_PROMPT_TEMPLATE.format(
        subject=request.subject,
        language=language_label,
        length_target=length_target,
        template_name=template.name,
        shape_description=template.shape_description,
        instructions_block=_render_instructions_block(request.instructions),
        sections_block=sections_block,
        tools_block=tools_block,
        capability_index=capability_index,
        revision_request=revise.revision_request,
        prior_block=prior_block,
        prior_charts_block=prior_charts_block,
    )


_REVISE_PROMPT_TEMPLATE = """\
You are an equity research analyst revising a report. The prior version
of the report is shown below verbatim. The user has asked for a
specific change — apply it precisely and leave the rest untouched
unless your change requires updating dependent sections.

# Report subject
{subject}

# Report language
{language}

# Report length target
{length_target} (a soft target).

# Template: {template_name}
{shape_description}

{instructions_block}The base template's sections:

{sections_block}

You may add new sections beyond the template if the revision request
requires it (e.g. "add a competitor analysis section"). Pick a stable
snake-case ``section_id`` for new sections and call ``write_section``
the same way you would for a template id.

# User's revision request
{revision_request}

# Prior report (current state)

{prior_block}

# Prior charts (still in scope; re-emit only if data changes)
{prior_charts_block}

# Tools

These tools are always available:

{tools_block}

# Specialized tool library

A larger library of specialized tools is available on demand. Call
`find_tools(query=..., category=...)` to discover and load the ones
your revision needs; they become callable immediately. Categories:

{capability_index}

# Citation rules

Same as the original run: every claim cites `[^source_id]`; the
ledger is pre-loaded with the prior report's citations so existing
markers still resolve. New web_search / data calls add new
`web_N` / `eodhd_N` ids you cite the same way.

# Cover hero

If the revision changes the report's headline takeaways (thesis,
rating, top-line numbers), call `set_cover(...)` to overwrite the
prior cover. The prior cover is preserved if you don't call it.

# When to call finalize()

After writing every section the revision touches. Unlike an original
run, you do NOT need to re-write untouched sections — they are
preserved automatically. Call ``finalize()`` once your changes are
in; it accepts a partial set of revised sections."""
