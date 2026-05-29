"""Lean schemas for the v3 equity-research engine.

v3 deliberately keeps the schema surface small: a chart spec, a citation
log entry, the run request, and the run result. Everything else (facts,
provenance graphs, marker grammars) is gone — citations live in a
server-side ledger keyed by ``source_id`` and the model cites them
inline with standard Markdown footnote syntax (``[^web_3]``).

The ``TemplateSpec`` itself is reused verbatim from v2.3 — same Pydantic
model, same built-ins. v3 only changes how the engine consumes the
template, not what a template is.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

from ...types import ReasoningEffort
from ..messages import Attachment
from ..report_v2_3.schemas import Language, ReportLength
from ..report_v2_3.templates.spec import SectionSpec, TemplateSpec

__all__ = [
    "ChartDataPoint",
    "ChartSpec",
    "ChartType",
    "CitationLogEntry",
    "CoverMetric",
    "CoverSpec",
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


class RunRequest(BaseModel):
    """Input to a v3 run.

    ``subject`` is either a ticker (``RKLB.US``) or a free-form topic;
    the template's ``ticker_anchored`` flag decides how to interpret
    it. ``provider_kind`` and ``model`` resolve through the existing
    capability map at runner construction so v3 inherits the same
    provider rules as the rest of the codebase.

    ``reasoning_effort`` is the user-selected extended-thinking knob.
    ``None`` (the default) maps to "off" — no reasoning param is sent
    to the adapter. v3 applies the chosen effort on every model turn
    (unlike v2.3 which scopes it to specific stages) since v3 is a
    single free-running loop with no stage notion. Adapters whose
    model does not support thinking silently ignore the field.

    ``attachments`` are user-uploaded source documents (filings, decks)
    the runner materializes into multimodal content blocks on the first
    turn so the model can read them. Empty for runs with no uploads.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    subject: str = Field(..., min_length=1)
    template: TemplateSpec
    language: Language = Language.EN
    length: ReportLength = ReportLength.NORMAL
    provider_kind: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    reasoning_effort: ReasoningEffort | None = None
    attachments: list[Attachment] = Field(default_factory=list)


class PriorSection(BaseModel):
    """Snapshot of one section as it stood before a revision started.

    Fed into ``ReviseContext`` so the engine can render the prior
    report verbatim into the model's context window. ``markdown`` is
    the raw text with un-rewritten ``[^source_id]`` markers so the
    ledger seeded from the same revision can still resolve them.
    """

    section_id: str
    title: str
    markdown: str


class PriorCitation(BaseModel):
    """Snapshot of one citation row from the report before a revision.

    The revision engine seeds its ledger with these so prior sections'
    ``[^source_id]`` markers still resolve and new web_search calls
    append rather than collide.
    """

    source_id: str
    tool_name: str
    provenance: dict[str, Any] = Field(default_factory=dict)


class ReviseContext(BaseModel):
    """Inputs that turn an ordinary v3 run into a revision pass.

    The runner pre-loads the workspace with the prior sections +
    charts so the in-flight ``RunResult`` always reflects the full
    report (touched + untouched), seeds the ledger with prior
    citations so existing markers resolve, and switches to revision
    prompts. ``request`` is the free-form user instruction (e.g.
    "rewrite the bull case to lead with EBITDA margin expansion").
    """

    revision_request: str = Field(..., min_length=1)
    prior_sections: list[PriorSection] = Field(default_factory=list)
    prior_charts: list[ChartSpec] = Field(default_factory=list)
    prior_citations: list[PriorCitation] = Field(default_factory=list)


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
