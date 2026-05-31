"""System prompt builder for the Earnings Update v2 engine.

One function: ``build_system_prompt(request)`` produces the single
system message the model sees for the whole run. The prompt states the
analyst's job, the template sections, the earnings trigger context, and
which connectors are available this run — so the model knows the
release it is covering and which tools it may call before it calls any.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .schemas import (
    EnabledConnectors,
    Language,
    ReportLength,
    RunRequest,
    TemplateSpec,
    TriggerContext,
)

_LANGUAGE_LABELS: dict[Language, str] = {
    Language.EN: "English",
    Language.ZH_TW: "Traditional Chinese (zh-TW)",
}

# Approximate target word counts surfaced to the model as soft guidance.
_LENGTH_TARGETS: dict[ReportLength, str] = {
    ReportLength.CONCISE: "~1,200 words total across all sections",
    ReportLength.NORMAL: "~2,500 words total across all sections",
    ReportLength.ELABORATIVE: "~4,500 words total across all sections",
}


@dataclass(frozen=True)
class ConnectorPromptInfo:
    """One enabled dispatcher connector's tools, for the prompt block.

    ``label`` is the provider label (e.g. ``"newsapi_ai"``); ``tools`` is
    a tuple of ``(tool_name, description)`` pairs the model may call.
    """

    label: str
    tools: tuple[tuple[str, str], ...]


def build_system_prompt(
    request: RunRequest,
    *,
    connector_tools: Sequence[ConnectorPromptInfo] = (),
) -> str:
    """Compose the EU v2 system prompt for one run.

    Two structural modes, decided by whether the template carries any
    sections:
      - templated: the section list is fixed; the model must write every
        section id before ``finalize``.
      - freeform (empty ``sections``): the model designs its own
        sections, guided by the subject and trigger context.
    """
    template = request.template
    language_label = _LANGUAGE_LABELS.get(request.language, request.language.value)
    length_target = _LENGTH_TARGETS.get(request.length, "moderate length")

    return _PROMPT_TEMPLATE.format(
        subject=request.subject,
        language=language_label,
        length_target=length_target,
        template_name=template.name,
        shape_description=template.shape_description,
        instructions_block=_render_instructions_block(request.instructions),
        trigger_block=_render_trigger_block(request.trigger_context),
        structure_block=_render_structure_block(template),
        connectors_block=_render_connectors_block(request.enabled_connectors, connector_tools),
    )


def _render_instructions_block(instructions: str | None) -> str:
    """The analyst-instructions block, or empty when none provided.

    Ends with two newlines so spacing collapses cleanly when absent.
    """
    if not instructions or not instructions.strip():
        return ""
    return (
        "# Analyst instructions\n\n"
        "The user provided the methodology and guidance below. Treat it as "
        "authoritative for how to approach this report — what to research and "
        "emphasize, how to reason, tone, which tools/endpoints to favor, and "
        "(where it specifies one) the report's structure.\n\n"
        f"{instructions.strip()}\n\n"
    )


def _render_trigger_block(trigger: TriggerContext | None) -> str:
    """The earnings-event context block, or empty when no trigger given.

    Only non-None fields render, so on-demand runs that know only the
    ticker still produce a clean, accurate block.
    """
    if trigger is None:
        return ""
    lines: list[str] = ["# Earnings event you are covering", ""]
    head = trigger.ticker
    if trigger.company_name:
        head = f"{trigger.company_name} ({trigger.ticker})"
    lead = f"You are covering: {head}"
    if trigger.fiscal_period:
        lead += f" {trigger.fiscal_period}"
    if trigger.report_date:
        lead += f", reported {trigger.report_date}"
    if trigger.release_timing:
        lead += f" ({trigger.release_timing})"
    lead += "."
    lines.append(lead)
    estimate_bits: list[str] = []
    if trigger.eps_estimate:
        estimate_bits.append(f"consensus EPS {trigger.eps_estimate}")
    if trigger.revenue_estimate:
        estimate_bits.append(f"consensus revenue {trigger.revenue_estimate}")
    if estimate_bits:
        lines.append("Score the print against: " + ", ".join(estimate_bits) + ".")
    return "\n".join(lines) + "\n\n"


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
        "Write a `write_section` call for every section id below before "
        "calling `finalize`.\n\n"
        f"{sections_block}"
    )


_FREEFORM_STRUCTURE_BLOCK = """\
No fixed section structure is imposed. Design the report's sections
yourself, guided by the earnings event and the subject. For each section
call `write_section` with a short `lowercase_snake_case` section id and a
human-readable `title`. Write at least one section before calling
`finalize`."""


def _render_connectors_block(
    connectors: EnabledConnectors,
    connector_tools: Sequence[ConnectorPromptInfo] = (),
) -> str:
    """List the tool groups available this run.

    When all connectors are off, state explicitly that no data tools are
    available so the model writes from the trigger context and its own
    knowledge rather than waiting on a disabled tool.
    """
    available: list[str] = []
    if connectors.eodhd:
        available.append(
            "  - Financial data & earnings calendar (EODHD): "
            "`get_fundamentals`, `get_historical_prices`, "
            "`get_company_news`, `get_earnings_calendar`. Pull reported "
            "line items, price action, and recent headlines; confirm the "
            "release and pull consensus estimates to score the print "
            "against."
        )
    for info in connector_tools:
        tool_lines = "\n".join(f"    - {name}: {description}" for name, description in info.tools)
        available.append(
            f"  - {info.label} (additional connector tools you may call for context):\n{tool_lines}"
        )
    if connectors.web_search:
        available.append(
            "  - Web search: the provider's first-class web search. Use "
            "for management commentary, call transcripts, and context the "
            "data feeds do not cover."
        )
    if not available:
        return (
            "No data tools are available this run. Write the report from "
            "the earnings event context above and your own knowledge. Do "
            "not attempt to call data, calendar, or web-search tools — "
            "only the output tools (`write_section`, `set_cover`, "
            "`emit_chart`, `finalize`) are available."
        )
    return "These tool groups are enabled this run:\n\n" + "\n".join(available)


_PROMPT_TEMPLATE = """\
You are an earnings analyst producing a post-earnings update for a
professional investor. Assess the quarter against expectations and the
prior investment thesis: what beat, what missed, what changed, and what
it means going forward. The report structure is fixed by the user's
template (below).

# Report subject
{subject}

# Report language
{language}

# Report length target
{length_target} (a soft target — write the length that fits the material).

# Template: {template_name}
{shape_description}

{instructions_block}{trigger_block}# Report structure

{structure_block}

# Available tools
{connectors_block}

# Output discipline

Produce the report by calling the output tools:
  - `write_section(section_id, markdown)` for every template section id.
  - `emit_chart(...)` when a simple chart (revenue/EPS vs estimate,
    segment trends) clarifies the quarter; reference it from a section
    via `{{{{chart:<chart_id>}}}}`.
  - `set_cover(...)` once near the end with the headline verdict: a
    one-sentence `tagline`, 3-5 `tldr` bullets, key metric cards, and a
    `rating`.
  - `finalize()` after every section is written and the cover is set. If
    `finalize()` reports missing sections, write them and call again.

# Citation rules

Cite every numeric or factual claim with Markdown footnote syntax:
`[^source_id]` (e.g. `[^eodhd_1]` or `[^web_3]`). When a tool returns,
its result tells you the assigned `source_id` — use that exact id.
After a web search, a follow-up message lists the `[^web_N]` markers for
the results it found; cite web facts with those. Use only the
`[^source_id]` markers the tools give you — they resolve in the
bibliography. Unresolved citations cause `write_section` to reject; fix
the markers and re-emit."""
