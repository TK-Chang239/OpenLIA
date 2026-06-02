"""System prompt builder for the Morning Briefing engine.

One function: ``build_system_prompt(request)`` produces the single
system message the model sees for the whole run. The prompt states the
analyst's job, the template sections, the briefing context, and which
connectors are available this run — so the model knows which briefing
it is writing and which tools it may call before it calls any.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .schemas import (
    BriefingContext,
    EnabledConnectors,
    Language,
    ReportLength,
    RunRequest,
    TemplateSpec,
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
    """Compose the Morning Briefing system prompt for one run.

    Two structural modes, decided by whether the template carries any
    sections:
      - templated: the section list is fixed; the model must write every
        section id before ``finalize``.
      - freeform (empty ``sections``): the model designs its own
        sections, guided by the subject and briefing context.
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
        trigger_block=_render_briefing_block(request.briefing_context),
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


def _render_briefing_block(briefing: BriefingContext | None) -> str:
    """The briefing context block, or empty when no briefing given.

    Only non-None fields render, so a run that knows only the run date
    still produces a clean, accurate block. Tells the model which
    recurring market briefing it is writing and when it fires.
    """
    if briefing is None:
        return ""
    lines: list[str] = ["# Briefing you are writing", ""]
    lead = f"You are writing the {briefing.schedule_label or 'market briefing'}"
    lead += f" for {briefing.run_date}"
    if briefing.time_label:
        lead += f" at {briefing.time_label}"
    if briefing.timezone:
        lead += f" {briefing.timezone}"
    lead += "."
    lines.append(lead)
    lines.append(
        "Treat the run date as today. Cover the market backdrop, overnight "
        "and pre-market moves, the day's scheduled catalysts, and what they "
        "mean for the day ahead."
    )
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
No fixed section structure is imposed. Design the briefing's sections
yourself, guided by the briefing context and the subject. For each
section call `write_section` with a short `lowercase_snake_case` section
id and a human-readable `title`. Write at least one section before
calling `finalize`."""


def _render_connectors_block(
    connectors: EnabledConnectors,
    connector_tools: Sequence[ConnectorPromptInfo] = (),
) -> str:
    """List the tool groups available this run.

    When all connectors are off, state explicitly that no data tools are
    available so the model writes from the briefing context and its own
    knowledge rather than waiting on a disabled tool.
    """
    available: list[str] = []
    if connectors.eodhd:
        available.append(
            "  - Market data (EODHD): `get_quotes`, `get_historical_prices`, "
            "`get_news`, `get_economic_calendar`, `get_macro_indicators`. "
            "Read where indices and the names you cover are trading, the "
            "trend and recent moves, overnight and market-wide headlines, "
            "the day's scheduled releases, and the rates/volatility/dollar/"
            "commodity backdrop."
        )
    for info in connector_tools:
        tool_lines = "\n".join(f"    - {name}: {description}" for name, description in info.tools)
        available.append(
            f"  - {info.label} (additional connector tools you may call for context):\n{tool_lines}"
        )
    if connectors.web_search:
        available.append(
            "  - Web search: the provider's first-class web search. Use "
            "for narrative context and breaking developments the data "
            "feeds do not cover."
        )
    if not available:
        return (
            "No data tools are available this run. Write the briefing from "
            "the briefing context above and your own knowledge. Lean on the "
            "output tools (`write_section`, `set_cover`, `emit_chart`, "
            "`finalize`) only."
        )
    return (
        "These tool groups are enabled this run:\n\n"
        + "\n".join(available)
        + "\n\n"
        + _MARKET_DATA_PRIORITY
    )


# Connector-agnostic research directive. Appended whenever at least one data
# tool is enabled, so the model leans on primary market data regardless of
# which provider supplies it. Names no specific connector — a provider the
# user runs today may be swapped out tomorrow.
_MARKET_DATA_PRIORITY = (
    "Prioritize the data that defines a market briefing. Favor tools that "
    "return current index and asset levels, overnight and pre-market moves, "
    "the scheduled macro catalysts for the day, and the rates, volatility, "
    "and currency backdrop. When a tool group exposes a discovery interface "
    "(a list/describe/call pattern), use it to find and call the relevant "
    "market tools so the briefing rests on primary observed data."
)


_PROMPT_TEMPLATE = """\
You are a markets analyst writing a recurring market briefing for a
professional investor. Set the scene for the trading day: the global and
overnight backdrop, what moved and why, the scheduled catalysts ahead,
and what it all means for positioning. The report structure is fixed by
the user's template (below).

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

Produce the briefing by calling the output tools:
  - `write_section(section_id, markdown)` for every template section id.
  - `emit_chart(...)` when a simple chart (index performance, a sector or
    rates trend) clarifies the day; reference it from a section via
    `{{{{chart:<chart_id>}}}}`.
  - `set_cover(...)` once near the end with the headline read: a
    one-sentence `tagline`, 3-5 `tldr` bullets, and key metric cards for
    the levels that matter.
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
