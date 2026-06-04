"""System prompt builder for the Retail Sentiment dashboard engine.

One function: ``build_system_prompt(request)`` produces the single system
message the model sees for the whole run. This engine is always in
dashboard mode: the model gathers retail-discussion data via web search,
runs the deterministic ``classify_retail_sentiment`` classifier, and
emits one complete typed dashboard payload via ``emit_dashboard``. The
prompt states the analyst's job, the dashboard workflow, the payload
shape the model must emit, which connectors are available this run, and
the citation discipline.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from ..report_dash_mr.schemas import Language, ReportLength
from .schemas import (
    EnabledConnectors,
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


@dataclass(frozen=True)
class DashboardPromptSpec:
    """Per-dashboard prompt content: the numbered workflow, the payload-shape
    description block, and the indicator-sourcing hint for the connectors block."""

    workflow: str
    payload_shape: str
    indicator_hint: str


def build_system_prompt(
    request: RunRequest,
    *,
    connector_tools: Sequence[ConnectorPromptInfo] = (),
) -> str:
    """Compose the dashboard system prompt for one run.

    This engine is always dashboard-mode: it produces the retail sentiment
    dashboard named by ``request.dashboard_slug`` by gathering retail
    discussion via web search, classifying, and emitting one typed payload.
    """
    spec = DASHBOARD_PROMPT_SPECS.get(request.dashboard_slug)
    if spec is None:
        raise ValueError(f"no prompt spec for dashboard {request.dashboard_slug!r}")

    language_label = _LANGUAGE_LABELS.get(request.language, request.language.value)
    length_target = _LENGTH_TARGETS.get(request.length, "balanced length")

    return _PROMPT_TEMPLATE.format(
        dashboard_slug=request.dashboard_slug,
        subject=request.subject,
        language=language_label,
        length_target=length_target,
        data_context_block=_render_data_context_block(request.data_context),
        instructions_block=_render_instructions_block(request.instructions),
        workflow=spec.workflow,
        payload_shape=spec.payload_shape,
        connectors_block=_render_connectors_block(
            request.enabled_connectors,
            connector_tools,
            indicator_hint=spec.indicator_hint,
        ),
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


def _render_data_context_block(data_context: str | None) -> str:
    """The server-injected ground-truth inputs block, or empty when none.

    Ends with two newlines so spacing collapses cleanly when absent.
    """
    if not data_context or not data_context.strip():
        return ""
    return (
        "# Provided inputs for this run\n\n"
        "The following data was gathered for you by the system. Treat it as "
        "authoritative ground truth for this run; do not contradict it.\n\n"
        f"{data_context.strip()}\n\n"
    )


def _render_connectors_block(
    connectors: EnabledConnectors,
    connector_tools: Sequence[ConnectorPromptInfo] = (),
    *,
    indicator_hint: str,
) -> str:
    """List the tool groups available this run.

    When all data connectors are off, state explicitly that the model
    should gather retail sentiment discussion from its training knowledge
    rather than wait on a disabled tool. ``indicator_hint`` names the
    specific context this dashboard reads from financial data connectors.
    """
    available: list[str] = []
    if connectors.eodhd:
        available.append(
            "  - Market data (EODHD): `get_quotes`, `get_historical_prices`, "
            "`get_news`, `get_economic_calendar`, `get_macro_indicators`. Use "
            f"for {indicator_hint}"
        )
    for info in connector_tools:
        tool_lines = "\n".join(f"    - {name}: {description}" for name, description in info.tools)
        available.append(
            f"  - {info.label} (additional connector tools you may call for context):\n{tool_lines}"
        )
    if connectors.web_search:
        available.append(
            "  - Web search: the provider's first-class web search. Use it to "
            "read current retail discussion from Reddit (r/investing, r/wallstreetbets, "
            "r/stocks), StockTwits, X/Twitter, and investing forums, plus recent news "
            "articles and analyst commentary for the subject ticker."
        )
    if not available:
        return (
            "No data tools are enabled this run. Draw on your knowledge of recent "
            "retail sentiment discussion for the subject ticker, state the approximate "
            "recency of your knowledge, then classify and emit."
        )
    return "These tool groups are enabled this run:\n\n" + "\n".join(available)


_PROMPT_TEMPLATE = """\
You are a retail-sentiment analyst producing the {dashboard_slug} Retail Sentiment
dashboard for a professional investor. Your job is to gather current retail
discussion about the subject ticker, run the deterministic classifier, and emit
one complete, typed dashboard payload that the front end renders verbatim.

# Dashboard subject
{subject}

# Language
{language}

# Narrative length
{length_target} (a soft target — write what the read requires).

{data_context_block}{instructions_block}# Workflow

{workflow}

# Available tools
{connectors_block}

{payload_shape}

# Citation discipline

Ground every numeric field in a tool result or a classifier output. Cite
concrete threads, articles, or posts in the `evidence` field and name your
sources in the `narrative` synthesis. State the approximate recency for the
discussion you read so the read is traceable."""


_RETAIL_SENTIMENT_WORKFLOW = """\
Work in this order:
  1. Use web_search to read current retail discussion for the subject ticker.
     Search across Reddit (r/investing, r/wallstreetbets, r/stocks),
     StockTwits, X/Twitter, and investing forums. Also search for recent news
     articles and analyst commentary that retail traders are reacting to.
     Read enough distinct sources to form a credible count.
  2. Tally how many distinct discussion items (posts, threads, articles) are
     bullish, how many are bearish, and how many are neutral. Judge a
     qualitative buzz_level — "low" when discussion is sparse, "elevated" when
     there is notable but not extreme activity, "high" when the ticker is
     dominating retail chatter.
  3. Call `classify_retail_sentiment` with those four values: bullish,
     bearish, neutral (integer counts), and buzz_level. Use the returned
     sentiment_score, direction, bull_pct, bear_pct, and signals verbatim —
     do not invent or override the computed numbers.
  4. Extract the key narratives and themes driving the discussion (e.g.
     earnings catalyst, short squeeze talk, macro headwinds, product news).
     Capture up to five distinct narratives as short strings.
  5. If a financial connector (EODHD) is available, optionally fetch an
     aggregated sentiment score and analyst consensus rating for a cross-check.
     Leave aggregated_sentiment and analyst_gap null if the connector is not
     available or the data is not returned — never invent these values.
  6. Cite concrete threads, posts, or articles as evidence items. Each
     evidence item must include the title, url, source, and classification
     (bullish/bearish/neutral). Add published_at when available.
  7. Write a short narrative synthesis (2-4 sentences) that captures the
     overall mood, the dominant themes, and any notable divergence between
     retail enthusiasm and fundamental signals.
  8. Call `emit_dashboard` exactly once with a complete RetailSentimentData
     object in `payload`. This finalizes the run."""


_RETAIL_SENTIMENT_PAYLOAD_SHAPE = """\
# RetailSentimentData payload shape

`emit_dashboard`'s `payload` is one JSON object with these keys:
  - `subject`: string — the ticker or subject for this dashboard run.
  - `sentiment_score`: float in [-1.0, 1.0] — from the classifier output;
    do not invent.
  - `direction`: one of "bullish"/"bearish"/"neutral" — from the classifier.
  - `momentum`: float or null — history-derived velocity; the engine fills
    this from prior runs; leave null in the emit.
  - `trend_label`: string or null — history-derived label (e.g. "rising");
    the engine fills this; leave null in the emit.
  - `buzz_level`: one of "low"/"elevated"/"high" — your qualitative judgment
    from step 2.
  - `buzz_note`: string — a one-sentence note explaining the buzz_level read.
  - `bull_pct`: float in [0.0, 100.0] — from the classifier; do not invent.
  - `bear_pct`: float in [0.0, 100.0] — from the classifier; do not invent.
  - `narratives`: list of strings — key themes driving the discussion (up to
    five short strings from step 4).
  - `signals`: list of {name, severity, note} — from the classifier's
    returned signals; severity is one of "info"/"caution"/"alert".
  - `evidence`: list of {title, url, source, classification, published_at}
    — concrete threads/articles cited in step 6; classification is one of
    "bullish"/"bearish"/"neutral"; published_at is ISO-8601 or null.
  - `narrative`: string — the synthesis paragraph from step 7.
  - `aggregated_sentiment`: float or null — connector-sourced aggregated
    sentiment score; null if no financial connector or data unavailable.
  - `analyst_gap`: float or null — difference between analyst consensus and
    retail sentiment score; null if no financial connector or data unavailable.
  - `captured_at`: ISO-8601 timestamp string or null — set to the current
    timestamp when emitting."""


# Per-dashboard prompt content. ``build_system_prompt`` looks the slug up
# here and fails loud when a dashboard has no spec. New dashboards register
# their workflow, payload-shape block, and indicator-sourcing hint here.
DASHBOARD_PROMPT_SPECS: dict[str, DashboardPromptSpec] = {
    "retail_sentiment": DashboardPromptSpec(
        workflow=_RETAIL_SENTIMENT_WORKFLOW,
        payload_shape=_RETAIL_SENTIMENT_PAYLOAD_SHAPE,
        indicator_hint=(
            "an aggregated sentiment score and analyst consensus rating "
            "for the subject ticker as a cross-check against retail discussion."
        ),
    ),
}
