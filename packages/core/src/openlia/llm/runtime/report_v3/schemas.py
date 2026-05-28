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

from pydantic import BaseModel, Field

from ...types import ReasoningEffort
from ..report_v2_3.schemas import Language, ReportLength
from ..report_v2_3.templates.spec import SectionSpec, TemplateSpec

__all__ = [
    "ChartDataPoint",
    "ChartSpec",
    "ChartType",
    "CitationLogEntry",
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
    """

    subject: str = Field(..., min_length=1)
    template: TemplateSpec
    language: Language = Language.EN
    length: ReportLength = ReportLength.NORMAL
    provider_kind: str = Field(..., min_length=1)
    model: str = Field(..., min_length=1)
    reasoning_effort: ReasoningEffort | None = None


class RunResult(BaseModel):
    """Output of a v3 run.

    Phase 0 returns a placeholder; subsequent phases populate
    ``sections``, ``charts``, and ``citations`` from the ledger.
    """

    status: RunStatus
    subject: str
    template_id: str
    message: str = ""
    sections: list[dict[str, Any]] = Field(default_factory=list)
    charts: list[ChartSpec] = Field(default_factory=list)
    citations: list[CitationLogEntry] = Field(default_factory=list)
