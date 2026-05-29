"""Lean schemas for the Earnings Update v2 engine.

Forked from report_v3. EU v2 keeps the schema surface small: a chart
spec, a citation log entry, the run request, and the run result.
Citations live in a server-side ledger keyed by ``source_id`` and the
model cites them inline with standard Markdown footnote syntax
(``[^web_3]``).

EU v2 deltas vs. v3:
  - ``RunRequest`` drops ``attachments`` / ``instructions`` (out of
    scope) and gains ``enabled_connectors`` (which tool groups to
    build) and ``trigger_context`` (the earnings event covered).
  - No revision schemas — EU v2 has no revise flow.

The ``TemplateSpec`` itself is reused verbatim from v2.3 — same Pydantic
model, same built-ins. EU v2 only changes how the engine consumes the
template, not what a template is.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ...types import ReasoningEffort
from ..report_v2_3.schemas import Language, ReportLength
from ..report_v2_3.templates.spec import SectionSpec, TemplateSpec

__all__ = [
    "ChartDataPoint",
    "ChartSpec",
    "ChartType",
    "CitationLogEntry",
    "CoverMetric",
    "CoverSpec",
    "EnabledConnectors",
    "Language",
    "ReportLength",
    "RunRequest",
    "RunResult",
    "RunStatus",
    "SectionSpec",
    "TemplateSpec",
    "TriggerContext",
]


# Chart types the renderer understands. Enforced server-side, not in
# the LLM prompt — invalid types come back as a descriptive tool error
# the model can act on.
ChartType = Literal["line", "bar", "column", "area", "pie", "scatter", "table"]

# Status of a v3 run. Phase 0 only exercises ``placeholder``; later
# phases add the real lifecycle states.
RunStatus = Literal["placeholder", "running", "completed", "failed"]


class ChartDataPoint(BaseModel):
    """One data point in a chart series.

    Permissive on the value type — the model may emit numeric strings
    that we coerce. The renderer normalizes ``label`` vs ``x``.
    """

    model_config = {"extra": "allow"}

    label: str | None = None
    x: str | float | int | None = None
    y: float | int | str | None = None
    value: float | int | str | None = None


class ChartSpec(BaseModel):
    """Spec the model emits via ``emit_chart``.

    Lean Pydantic with permissive coercion. The renderer's actual
    capability surface is what gates validation; this schema only
    enforces the minimum the renderer needs to lay something out.

    ``source_ids`` resolve against the run's citation ledger at emit
    time. ``chart_id`` is the model-chosen handle used to reference
    the chart from section markdown via ``{{chart:<chart_id>}}``.
    """

    model_config = {"extra": "allow"}

    chart_id: str = Field(..., min_length=1, pattern=r"^[a-z0-9_]+$")
    chart_type: ChartType
    title: str = Field(..., min_length=1)
    data: list[ChartDataPoint] = Field(..., min_length=1)
    axes: dict[str, str] = Field(default_factory=dict)
    source_ids: list[str] = Field(default_factory=list)


class CitationLogEntry(BaseModel):
    """One entry in the per-run citation ledger.

    Every tool call appends one entry; the ledger assigns the stable
    ``source_id`` (``web_1``, ``eodhd_3``, ``dcf_1``) the model cites
    in section markdown. ``provenance`` is loosely typed here because
    the underlying v2.3 ``WebSource`` / ``DataProviderSource`` /
    ``ComputedSource`` discriminated union is heavier than the ledger
    needs — Phase 1 will tighten this if necessary.
    """

    source_id: str = Field(..., min_length=1)
    tool_name: str = Field(..., min_length=1)
    arguments: dict[str, Any] = Field(default_factory=dict)
    result_summary: str = ""
    provenance: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime
    input_tokens: int = 0
    output_tokens: int = 0
    wall_time_ms: int = 0


class EnabledConnectors(BaseModel):
    """Which connector tool groups the LLM may call this run.

    Per-user global toggles resolved from ``eu_v2_settings``. None are
    required — all-False yields an output-tools-only catalog and the
    model writes from the prompt and trigger context alone.
    """

    financial: bool = True
    earnings_calendar: bool = True
    web_search: bool = False


class TriggerContext(BaseModel):
    """Earnings event metadata handed to a run.

    For scheduled runs this is populated from the matched
    ``eu_v2_earnings_schedule`` row; for on-demand runs the route fills
    in what it can (ticker always; estimates when the calendar
    connector is enabled). Injected into the system prompt so the model
    knows which release it is covering before it calls any tool.
    """

    ticker: str = Field(..., min_length=1)
    company_name: str | None = None
    fiscal_period: str | None = None
    report_date: str | None = None
    release_timing: str | None = None
    eps_estimate: str | None = None
    revenue_estimate: str | None = None


class RunRequest(BaseModel):
    """Input to an Earnings Update v2 run.

    Forked from report_v3's RunRequest. Differences: no ``attachments``
    / ``instructions`` (out of scope for EU v2), and two added fields —
    ``enabled_connectors`` (which tool groups to build) and
    ``trigger_context`` (the earnings event being covered).

    ``subject`` is either a ticker (``MSFT.US``) or a free-form earnings
    topic; the template's ``ticker_anchored`` flag decides how to
    interpret it. ``provider_kind`` and ``model`` resolve through the
    existing capability map at runner construction.

    ``reasoning_effort`` is the user-selected extended-thinking knob.
    ``None`` (the default) maps to "off" — no reasoning param is sent
    to the adapter. EU v2 applies the chosen effort on every model turn
    since the engine is a single free-running loop with no stage notion.
    Adapters whose model does not support thinking silently ignore it.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    subject: str = Field(..., min_length=1)
    template: TemplateSpec
    language: Language = Language.EN
    length: ReportLength = ReportLength.NORMAL
    provider_kind: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    reasoning_effort: ReasoningEffort | None = None
    enabled_connectors: EnabledConnectors = Field(default_factory=EnabledConnectors)
    trigger_context: TriggerContext | None = None


class CoverMetric(BaseModel):
    """One headline metric card on the report cover.

    Values are strings (not floats) so the model can ship pre-formatted
    figures with units like ``"$1.2B"``, ``"24.7%"``, or ``"3.1x"``
    without the engine re-doing the formatting. ``change`` carries an
    optional period-over-period delta (``"+18% YoY"`` / ``"(0.45)"``)
    and ``tone`` lets the model nudge the renderer toward green/red
    typography when the delta is directional.
    """

    label: str = Field(..., min_length=1)
    value: str = Field(..., min_length=1)
    change: str | None = None
    tone: Literal["positive", "negative", "neutral"] | None = None


class CoverSpec(BaseModel):
    """Cover hero content the model emits via ``set_cover``.

    All fields are optional — an unpopulated cover renders with just
    the subject + eyebrow (template label + date) and the renderer
    suppresses the empty rows. The model is encouraged to call
    ``set_cover`` once near the end of the run with the headline
    thesis, 3-5 TLDR bullets, a handful of key metrics, and the
    investment rating; revisions can call ``set_cover`` again to
    overwrite (last write wins).
    """

    subtitle: str | None = None
    tagline: str | None = None
    tldr: list[str] = Field(default_factory=list)
    key_metrics: list[CoverMetric] = Field(default_factory=list)
    rating: str | None = None
    upside_pct: float | None = None


class RunResult(BaseModel):
    """Output of a v3 run.

    Phase 0 returns a placeholder; subsequent phases populate
    ``sections``, ``charts``, and ``citations`` from the ledger.
    ``cover`` is populated when the model called ``set_cover`` during
    the run; otherwise it stays None and the cover renders bare.
    """

    status: RunStatus
    subject: str
    template_id: str
    message: str = ""
    sections: list[dict[str, Any]] = Field(default_factory=list)
    charts: list[ChartSpec] = Field(default_factory=list)
    citations: list[CitationLogEntry] = Field(default_factory=list)
    cover: CoverSpec | None = None
