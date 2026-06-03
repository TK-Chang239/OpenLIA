"""System prompt builder for the Macro Research dashboard engine.

One function: ``build_system_prompt(request)`` produces the single system
message the model sees for the whole run. This engine is always in
dashboard mode: the model gathers data, runs the deterministic
classifier, and emits one complete typed dashboard payload via
``emit_dashboard``. The prompt states the analyst's job, the dashboard
workflow, the payload shape the model must emit, which connectors are
available this run, and the citation discipline.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from .schemas import (
    EnabledConnectors,
    Language,
    ReportLength,
    RunRequest,
)

_LANGUAGE_LABELS: dict[Language, str] = {
    Language.EN: "English",
    Language.ZH_TW: "Traditional Chinese (zh-TW)",
}

# Approximate target word counts surfaced to the model as soft guidance
# for the narrative fields inside the dashboard payload.
_LENGTH_TARGETS: dict[ReportLength, str] = {
    ReportLength.CONCISE: "tight, ~1-2 sentences per narrative field",
    ReportLength.NORMAL: "balanced, ~2-4 sentences per narrative field",
    ReportLength.ELABORATIVE: "thorough, ~4-6 sentences per narrative field",
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
    """Compose the dashboard system prompt for one run.

    This engine is always dashboard-mode: it produces the dashboard named
    by ``request.dashboard_slug`` (debt_cycle today) by gathering inputs,
    classifying, and emitting one typed payload. The vestigial template is
    not used to shape the prompt.
    """
    language_label = _LANGUAGE_LABELS.get(request.language, request.language.value)
    length_target = _LENGTH_TARGETS.get(request.length, "balanced length")

    return _PROMPT_TEMPLATE.format(
        dashboard_slug=request.dashboard_slug,
        subject=request.subject,
        language=language_label,
        length_target=length_target,
        instructions_block=_render_instructions_block(request.instructions),
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
        "authoritative for how to approach this dashboard — what to research and "
        "emphasize, how to reason, and which tools/endpoints to favor.\n\n"
        f"{instructions.strip()}\n\n"
    )


def _render_connectors_block(
    connectors: EnabledConnectors,
    connector_tools: Sequence[ConnectorPromptInfo] = (),
) -> str:
    """List the tool groups available this run.

    When all data connectors are off, state explicitly that the model
    should gather the indicators from its own knowledge of the latest
    official figures rather than wait on a disabled tool.
    """
    available: list[str] = []
    if connectors.eodhd:
        available.append(
            "  - Market data (EODHD): `get_quotes`, `get_historical_prices`, "
            "`get_news`, `get_economic_calendar`, `get_macro_indicators`. Read "
            "the latest levels for the US dollar index and TIPS real yields, and "
            "any macro series the indicators rely on."
        )
    for info in connector_tools:
        tool_lines = "\n".join(f"    - {name}: {description}" for name, description in info.tools)
        available.append(
            f"  - {info.label} (additional connector tools you may call for context):\n{tool_lines}"
        )
    if connectors.web_search:
        available.append(
            "  - Web search: the provider's first-class web search. Favor "
            "official sources (FRED, IMF, US Treasury, CBO, BEA) for the four "
            "indicators and any figure you cite."
        )
    if not available:
        return (
            "No data tools are enabled this run. Gather the four indicators from "
            "your knowledge of the most recent official figures (FRED, IMF, US "
            "Treasury, CBO, BEA), state the value and as-of date for each, then "
            "classify and emit."
        )
    return "These tool groups are enabled this run:\n\n" + "\n".join(available)


_PROMPT_TEMPLATE = """\
You are a macro strategist producing the {dashboard_slug} Macro Research
dashboard for a professional investor. Your job is to gather the latest
inputs, run the deterministic classifier, and emit one complete, typed
dashboard payload that the front end renders verbatim.

# Dashboard subject
{subject}

# Language
{language}

# Narrative length
{length_target} (a soft target — write what the read requires).

{instructions_block}# Workflow

Work in this order:
  1. Gather the four debt-cycle indicators, each with a value and an
     as-of date:
       - Government gross debt as a percent of GDP
       - Federal interest expense as a percent of revenue
       - 10-year TIPS real yield (percent)
       - US dollar index (DXY) level
     Prefer the enabled connector tools first; fall back to `web_search`
     of official sources (FRED, IMF, US Treasury, CBO, BEA).
  2. Call `classify_debt_cycle` with those four values. Use the returned
     `phase`, `severity`, `indicator_statuses`, and `monetary_space`
     verbatim — do not invent or override the computed numbers.
  3. Write each narrative field from the data and citations you gathered.
  4. Call `emit_dashboard` exactly once with the full DebtCycleData
     object in `payload`. This finalizes the run.

# Available tools
{connectors_block}

# DebtCycleData payload shape

`emit_dashboard`'s `payload` is one JSON object with these keys:
  - `header`: {{title, subtitle, pills: [{{tone, label}}]}} — tone is one
    of red/amber/green/blue.
  - `cardSummary`: one-paragraph string summarizing the read.
  - `scorecard`: {{rows: [{{name, sub, current, currentTone, currentMeta,
    threshold, status, statusTone, fillPct, fillTone}}]}} — one row per
    indicator; the *Tone fields are red/amber/green/blue, `fillPct` is an
    integer 0-100.
  - `phaseBox`: {{title, body, tone}} — the cycle phase from the
    classifier (use its `phase` and `severity`).
  - `analogPair`: {{analog: {{title, body}}, timeToConstraint: {{title,
    body}}}}.
  - `policySpace`: {{cards: [{{label, value, valueTone, unit, note}}]}} —
    grounded in the classifier's `monetary_space`.
  - `assetThesis`: {{gold: {{title, body}}, longBond: {{title, body}}}}.
  - `watchlist`: {{rows: [{{tone, name, body}}]}}.
  - `verdict`: {{title, body, tone}} — the synthesis.
  - `sources`: a short string naming the sources you used.
  - `generated_at`: an ISO-8601 timestamp for the run.

# Citation discipline

Ground every numeric field in a tool result or `classify_debt_cycle`
output. Name your sources in the `sources` field and state the as-of
date for each indicator inside the scorecard rows so the read is
traceable to the official figures it rests on."""
