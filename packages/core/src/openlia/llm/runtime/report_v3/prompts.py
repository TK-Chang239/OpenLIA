"""System prompt builder for the v3 engine.

One function: ``build_system_prompt(request, catalog)`` produces the
single system message the model sees for the whole run. The prompt
intentionally short — it states the goal, lists the template
sections, enumerates the tools, and sets the citation contract. No
"MUST NOT" walls; no marker grammar to memorize beyond standard
Markdown footnote syntax.
"""

from __future__ import annotations

from .schemas import Language, ReportLength, RunRequest
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
    """Compose the v3 system prompt for one run."""
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

    tool_lines: list[str] = []
    for descriptor in catalog.descriptors:
        tool_lines.append(f"  - {descriptor.name}: {descriptor.description}")
    tools_block = "\n".join(tool_lines)

    return _PROMPT_TEMPLATE.format(
        subject=request.subject,
        language=language_label,
        length_target=length_target,
        template_name=template.name,
        shape_description=template.shape_description,
        sections_block=sections_block,
        tools_block=tools_block,
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

The report has these sections. You MUST produce a `write_section` call
for every section id below before calling `finalize`.

{sections_block}

# Tools

You have these tools. Use them freely. Research thoroughly, verify
numbers before citing them, and run `run_dcf` / `run_comps` /
`run_sensitivity` when valuation is in scope.

{tools_block}

# Citation rules

Every numeric or factual claim must cite a tool result. Cite inline
with Markdown footnote syntax: `[^source_id]` (e.g. `[^web_3]` or
`[^eodhd_1]`). When a tool returns, its result tells you the assigned
`source_id` — use that. Web search results assigned by the provider's
native tool also get `web_N` ids you can cite the same way.

Unresolved citations cause `write_section` to reject. Fix the markers
and re-emit. Charts are referenced as `{{chart:<chart_id>}}` and must
be emitted via `emit_chart` before any section references them.

# When to call finalize()

When every template section has been written and you are satisfied
with the report. If `finalize()` reports missing sections, write the
missing ones and call again."""
