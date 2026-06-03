"""Lean schemas for the Morning Briefing engine.

Forked from the Earnings Update v2 engine. The schema surface stays
small: a chart spec, a citation log entry, the run request, and the run
result. Citations live in a server-side ledger keyed by ``source_id``
and the model cites them inline with standard Markdown footnote syntax
(``[^web_3]``).

Morning Briefing deltas vs. EU v2:
  - The earnings anchor is replaced by a briefing anchor.
    ``RunRequest`` carries ``enabled_connectors`` (which tool groups to
    build) and ``briefing_context`` (which briefing this run writes:
    its run date, schedule label, and time/timezone). ``instructions``
    (free-form analyst methodology injected into the system prompt) is
    supported, same as EU.
  - No revision schemas — the engine has no revise flow.

The ``TemplateSpec`` itself is reused verbatim from v2.3 — same Pydantic
model, same built-ins. The engine only changes how it consumes the
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
    "BriefingContext",
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
]


# Chart types the renderer understands. Enforced server-side, not in
# the LLM prompt — invalid types come back as a descriptive tool error
# the model can act on.
ChartType = Literal["line", "bar", "column", "area", "pie", "scatter", "table"]

# Status of an EU v2 run.
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
    """Which data sources the LLM may use this run.

    ``provider_ids`` are the registry provider ids enabled for routing
    (``"eodhd"`` -> curated EODHD financial + calendar tools; any other
    -> dispatcher-routed, added in a later task). ``web_search`` is the
    model-native web search (not a registry connector).
    """

    provider_ids: frozenset[str] = frozenset()
    web_search: bool = False

    @property
    def eodhd(self) -> bool:
        return "eodhd" in self.provider_ids


class BriefingContext(BaseModel):
    """Briefing metadata handed to a run.

    Identifies which recurring market briefing this run writes: its
    ``run_date`` (always), an optional human ``schedule_label`` (e.g.
    "Pre-market briefing"), and optional ``time_label`` / ``timezone``
    for when the briefing fires. Injected into the system prompt so the
    model knows which briefing it is writing before it calls any tool.
    """

    run_date: str = Field(..., min_length=1)
    schedule_label: str | None = None
    time_label: str | None = None
    timezone: str | None = None


class RunRequest(BaseModel):
    """Input to a Morning Briefing run.

    Forked from the Earnings Update v2 ``RunRequest``. Differences: the
    earnings anchor is replaced by a briefing anchor. Two anchor fields —
    ``enabled_connectors`` (which tool groups to build) and
    ``briefing_context`` (which briefing this run writes). Free-form
    ``instructions`` are supported and injected into the system prompt.

    ``subject`` is the briefing label (e.g.
    ``"Morning Briefing - 2026-06-02"``), not a ticker. ``provider_kind``
    and ``model`` resolve through the existing capability map at runner
    construction.

    ``reasoning_effort`` is the user-selected extended-thinking knob.
    ``None`` (the default) maps to "off" — no reasoning param is sent
    to the adapter. The engine applies the chosen effort on every model
    turn since it is a single free-running loop with no stage notion.
    Adapters whose model does not support thinking silently ignore it.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    dashboard_slug: str = Field(..., min_length=1)
    subject: str = Field(..., min_length=1)
    template: TemplateSpec | None = None
    language: Language = Language.EN
    length: ReportLength = ReportLength.NORMAL
    provider_kind: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    reasoning_effort: ReasoningEffort | None = None
    enabled_connectors: EnabledConnectors = Field(default_factory=EnabledConnectors)
    briefing_context: BriefingContext | None = None
    # Free-form analyst methodology/guidance injected into the system prompt.
    instructions: str | None = None


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
    """Output of an EU v2 run.

    Populates ``sections``, ``charts``, and ``citations`` from the
    ledger. ``cover`` is populated when the model called ``set_cover`` during
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
    # JSON-ready serialized dashboard payload (e.g. DebtCycleData). None
    # until the model calls emit_dashboard; set when the run finalizes
    # via a dashboard emit.
    payload: dict[str, Any] | None = None
