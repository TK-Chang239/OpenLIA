from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


def _coerce_numeric_list(raw: Any) -> list[float] | None:
    """Best-effort coercion of a heterogeneous list to ``list[float]``.

    Returns ``None`` if the input is not a list-like at all so callers can
    fall through to other normalization paths."""
    if not isinstance(raw, list):
        return None
    out: list[float] = []
    for item in raw:
        if isinstance(item, int | float) and not isinstance(item, bool):
            out.append(float(item))
        elif isinstance(item, dict) and "y" in item:
            try:
                out.append(float(item["y"]))
            except (TypeError, ValueError):
                out.append(0.0)
        else:
            try:
                out.append(float(item))
            except (TypeError, ValueError):
                out.append(0.0)
    return out


class _Series(_Strict):
    """Shared base for chart series with ``data → values`` back-compat.

    The LLM prompt historically asked for ``data: [n, n, n]`` for every chart
    family. The packer used to splat ``**payload`` straight into the block,
    so the frontend (which expects ``values``) silently rendered empty bars.
    These validators map both shapes to the canonical ``values`` form."""

    @model_validator(mode="before")
    @classmethod
    def _coerce_data_to_values(cls, raw: Any) -> Any:
        if not isinstance(raw, dict):
            return raw
        if "values" in raw and raw["values"] is not None:
            return raw
        if "data" in raw and raw["data"] is not None:
            coerced = _coerce_numeric_list(raw["data"])
            if coerced is not None:
                raw = dict(raw)
                raw["values"] = coerced
                raw.pop("data", None)
        return raw


class BarSeries(_Series):
    name: str
    values: list[float] = Field(default_factory=list)


class LineSeries(_Series):
    name: str
    values: list[float] = Field(default_factory=list)


class AreaSeries(_Series):
    name: str
    values: list[float] = Field(default_factory=list)


class ScatterPoint(_Strict):
    x: float
    y: float


class ScatterSeries(_Strict):
    """Scatter is genuinely 2D so it keeps point-pair shape; ``data`` and
    ``points`` are both accepted as aliases for the canonical key."""

    name: str
    points: list[ScatterPoint] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _coerce_data_to_points(cls, raw: Any) -> Any:
        if not isinstance(raw, dict):
            return raw
        if "points" in raw and raw["points"] is not None:
            return raw
        if "data" in raw and isinstance(raw["data"], list):
            raw = dict(raw)
            raw["points"] = raw.pop("data")
        return raw


Align = Literal["left", "center", "right"]
RowStyle = Literal["default", "subtotal", "total", "header_group"]
FormatRule = Literal[
    "negative",
    "positive",
    "directional",
    "bold",
    "muted",
    "tag-beat",
    "tag-miss",
    "tag-info",
]
ChartHeight = Literal["small", "medium", "tall"]
DeltaDirection = Literal["up", "down", "flat"]
Tone = Literal["positive", "negative", "neutral", "warn"]


class Tag(_Strict):
    """Inline chip used by metrics, timeline events, and quote attribution."""

    label: str
    tone: Tone = "neutral"


class Metric(_Strict):
    label: str
    value: str
    delta: str | None = None
    delta_direction: DeltaDirection | None = None
    context: str | None = None
    tag: Tag | None = None
    highlight: bool = False
    # IDs of entries in ReportSchema.citations supporting this metric's
    # value/delta. Empty list = uncited; the Phase 5d validator emits a
    # warning for value-bearing slots that ship without sources.
    source_ids: list[str] = Field(default_factory=list)


class ChartOptions(_Strict):
    height: ChartHeight = "medium"
    show_legend: bool = True
    show_grid: bool = True


class TableHeader(_Strict):
    key: str
    label: str
    align: Align = "left"
    sortable: bool = False
    sparkline: bool = False


class CellFormat(_Strict):
    rule: FormatRule


class TextBlock(_Strict):
    type: Literal["text"]
    content: str


class TableBlock(_Strict):
    type: Literal["table"]
    title: str
    headers: Annotated[list[TableHeader], Field(min_length=1)]
    rows: Annotated[list[dict[str, Any]], Field(min_length=1)]
    cell_format: dict[str, CellFormat] = Field(default_factory=dict)
    footnotes: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    options: dict[str, Any] = Field(default_factory=dict)


class MetricCardsBlock(_Strict):
    type: Literal["metric_cards"]
    metrics: Annotated[list[Metric], Field(min_length=1)]


class KeyFindingBlock(_Strict):
    type: Literal["key_finding"]
    content: str
    source_ids: list[str] = Field(default_factory=list)


class RatingBadgeBlock(_Strict):
    type: Literal["rating_badge"]
    rating: str
    previous_rating: str | None = None
    change_date: str | None = None


class PullQuoteBlock(_Strict):
    """Editorial pull-quote callout with accent left-border.

    Use sparingly: the punchline of the section, not a generic blockquote."""

    type: Literal["pull_quote"]
    text: str
    attribution: str | None = None
    source: str | None = None
    timestamp: str | None = None
    source_ids: list[str] = Field(default_factory=list)


class CalloutItem(_Strict):
    eyebrow: str | None = None
    title: str
    description: str


class CalloutGridBlock(_Strict):
    """N-card callout grid (2-4 columns). Generic for thesis pillars,
    drivers, themes, options, frameworks."""

    type: Literal["callout_grid"]
    columns: int = Field(ge=2, le=4, default=3)
    items: Annotated[list[CalloutItem], Field(min_length=2)]


class TimelineEvent(_Strict):
    when: str
    what: str
    impact: str | None = None
    impact_tag: Tag | None = None
    highlight: bool = False


class TimelineBlock(_Strict):
    """Time-ordered events with optional tone-tagged impact line.
    Generic for catalysts, milestones, history, agendas."""

    type: Literal["timeline"]
    title: str | None = None
    events: Annotated[list[TimelineEvent], Field(min_length=1)]


class BulletListBlock(_Strict):
    type: Literal["bullet_list"]
    items: Annotated[list[str], Field(min_length=1)]
    tone: Literal["default", "positive", "negative"] = "default"


class ComparisonColumn(_Strict):
    title: str
    tone: Tone = "neutral"
    items: Annotated[list[str], Field(min_length=1)]


class ComparisonSplitBlock(_Strict):
    """Two-column tone-tagged comparison. Risks (up/down), pros/cons,
    bull/bear, before/after."""

    type: Literal["comparison_split"]
    left: ComparisonColumn
    right: ComparisonColumn


class QuoteBlock(_Strict):
    """Attributed quote with optional speaker/role/tag/timestamp.
    Inline ``==marks==`` in `text` render as highlight spans.

    Distinct from PullQuoteBlock (editorial) — QuoteBlock is for
    earnings-call transcripts, expert interviews, news quotes."""

    type: Literal["quote"]
    text: str
    speaker: str | None = None
    role: str | None = None
    tag: Tag | None = None
    timestamp: str | None = None
    source_ids: list[str] = Field(default_factory=list)


def _backfill_categories_from_data(raw: Any) -> Any:
    """Pull x-axis labels off ``series[0].data: [{x, y}]`` if the block has
    no top-level ``categories`` — the legacy line/area writer shape."""
    if not isinstance(raw, dict):
        return raw
    if raw.get("categories"):
        return raw
    series = raw.get("series") or []
    if not series or not isinstance(series[0], dict):
        return raw
    data = series[0].get("data")
    if not isinstance(data, list) or not data:
        return raw
    if not all(isinstance(d, dict) and "x" in d for d in data):
        return raw
    raw = dict(raw)
    raw["categories"] = [str(d["x"]) for d in data]
    return raw


class LineChartBlock(_Strict):
    type: Literal["line_chart"]
    title: str
    categories: list[str] = Field(default_factory=list)
    series: Annotated[list[LineSeries], Field(min_length=1)]
    x_label: str | None = None
    y_label: str | None = None
    source_ids: list[str] = Field(default_factory=list)
    options: ChartOptions = Field(default_factory=ChartOptions)

    @model_validator(mode="before")
    @classmethod
    def _backfill_categories(cls, raw: Any) -> Any:
        return _backfill_categories_from_data(raw)


class BarChartBlock(_Strict):
    type: Literal["bar_chart"]
    title: str
    categories: Annotated[list[str], Field(min_length=1)]
    series: Annotated[list[BarSeries], Field(min_length=1)]
    orientation: Literal["vertical", "horizontal"] = "vertical"
    stacked: bool = False
    source_ids: list[str] = Field(default_factory=list)
    options: ChartOptions = Field(default_factory=ChartOptions)


class AreaChartBlock(_Strict):
    type: Literal["area_chart"]
    title: str
    categories: list[str] = Field(default_factory=list)
    series: Annotated[list[AreaSeries], Field(min_length=1)]
    stacked: bool = False
    source_ids: list[str] = Field(default_factory=list)
    options: ChartOptions = Field(default_factory=ChartOptions)

    @model_validator(mode="before")
    @classmethod
    def _backfill_categories(cls, raw: Any) -> Any:
        return _backfill_categories_from_data(raw)


class PieSegment(_Strict):
    label: str
    value: float


class PieChartBlock(_Strict):
    type: Literal["pie_chart"]
    title: str
    segments: Annotated[list[PieSegment], Field(min_length=1)]
    donut: bool = False
    source_ids: list[str] = Field(default_factory=list)
    options: ChartOptions = Field(default_factory=ChartOptions)


class CandleRow(_Strict):
    date: str
    open: float
    high: float
    low: float
    close: float


class VolumeRow(_Strict):
    date: str
    value: float


class CandlestickBlock(_Strict):
    type: Literal["candlestick_chart"]
    title: str
    data: Annotated[list[CandleRow], Field(min_length=1)]
    volume: list[VolumeRow] | None = None
    source_ids: list[str] = Field(default_factory=list)
    options: ChartOptions = Field(default_factory=ChartOptions)


class WaterfallItem(_Strict):
    label: str
    value: float
    type: Literal["total", "increase", "decrease"]


class WaterfallBlock(_Strict):
    type: Literal["waterfall_chart"]
    title: str
    items: Annotated[list[WaterfallItem], Field(min_length=2)]
    source_ids: list[str] = Field(default_factory=list)
    options: ChartOptions = Field(default_factory=ChartOptions)


class ScatterBlock(_Strict):
    type: Literal["scatter_plot"]
    title: str
    series: Annotated[list[ScatterSeries], Field(min_length=1)]
    x_label: str | None = None
    y_label: str | None = None
    source_ids: list[str] = Field(default_factory=list)
    options: ChartOptions = Field(default_factory=ChartOptions)


class HeatmapBlock(_Strict):
    type: Literal["heatmap"]
    title: str
    x_labels: Annotated[list[str], Field(min_length=1)]
    y_labels: Annotated[list[str], Field(min_length=1)]
    values: Annotated[list[list[float]], Field(min_length=1)]
    source_ids: list[str] = Field(default_factory=list)
    options: ChartOptions = Field(default_factory=ChartOptions)


class TreemapNode(_Strict):
    name: str
    value: float
    children: list[TreemapNode] | None = None


class TreemapBlock(_Strict):
    type: Literal["treemap"]
    title: str
    data: Annotated[list[TreemapNode], Field(min_length=1)]
    source_ids: list[str] = Field(default_factory=list)
    options: ChartOptions = Field(default_factory=ChartOptions)


class ComboSeries(_Strict):
    name: str
    values: Annotated[list[float], Field(min_length=1)]


class ComboChartBlock(_Strict):
    type: Literal["combo_chart"]
    title: str
    categories: Annotated[list[str], Field(min_length=1)]
    bar_series: Annotated[list[ComboSeries], Field(min_length=1)]
    line_series: Annotated[list[ComboSeries], Field(min_length=1)]
    y_left_label: str | None = None
    y_right_label: str | None = None
    source_ids: list[str] = Field(default_factory=list)
    options: ChartOptions = Field(default_factory=ChartOptions)


LeafBlock = (
    TextBlock
    | TableBlock
    | MetricCardsBlock
    | KeyFindingBlock
    | RatingBadgeBlock
    | PullQuoteBlock
    | CalloutGridBlock
    | TimelineBlock
    | BulletListBlock
    | ComparisonSplitBlock
    | QuoteBlock
    | LineChartBlock
    | BarChartBlock
    | AreaChartBlock
    | PieChartBlock
    | CandlestickBlock
    | WaterfallBlock
    | ScatterBlock
    | HeatmapBlock
    | TreemapBlock
    | ComboChartBlock
)


class GroupBlock(_Strict):
    type: Literal["group"]
    columns: int = Field(ge=1, le=4)
    blocks: Annotated[list[LeafBlock], Field(min_length=1)]


Block = Annotated[
    LeafBlock | GroupBlock,
    Field(discriminator="type"),
]


class Section(_Strict):
    id: str
    title: str
    blocks: list[Block]


class Cover(_Strict):
    title: str
    subtitle: str
    eyebrow: str | None = None
    ticker: str | None = None
    tagline: str
    tldr: list[str] = Field(default_factory=list)
    tldr_label: str | None = None
    key_metrics: list[Metric] = Field(default_factory=list)


class PageFurniture(_Strict):
    header: dict[str, str]
    footer: dict[str, str]
    disclaimer: str


class Verdict(_Strict):
    rating: str
    previous_rating: str | None = None
    target: str | None = None
    upside: str | None = None
    as_of: str | None = None


class SparklinePoint(_Strict):
    x: float
    y: float


class Sparkline(_Strict):
    label: str
    points: Annotated[list[SparklinePoint], Field(min_length=2)]


class Rail(_Strict):
    """Sticky right-rail summary. Renderer falls back to 2-column when
    omitted. ``Rail.related`` is renderer-derived (cross-report query),
    not authored — kept off the schema deliberately."""

    verdict: Verdict | None = None
    quick_stats: list[Metric] = Field(default_factory=list)
    sparkline: Sparkline | None = None


class Citation(_Strict):
    id: str
    title: str | None = None
    source: str | None = None
    url: str | None = None
    date: str | None = None


class MetaStats(_Strict):
    """Server-authoritative stats about the report itself (not the subject).
    Rendered in the left sidebar below the table of contents so the reader
    can gauge thoroughness and freshness at a glance."""

    sources_count: int = 0
    sections_count: int = 0
    model_id: str | None = None
    tokens_used: int | None = None
    web_search_queries: int | None = None
    est_read_minutes: int = 0


class ReportSchema(_Strict):
    schema_version: Literal["2.0"]
    department: str
    generated_at: datetime
    page_furniture: PageFurniture | None = None
    cover: Cover
    sections: list[Section]
    rail: Rail | None = None
    citations: list[Citation] = Field(default_factory=list)
    meta_stats: MetaStats | None = None
    # WavedReportRunner v2 diagnostics: per-section SUCCESS/DEGRADED/EXHAUSTED
    # states, wave timings, auto-repair fix counts, omitted blocks, cross-
    # section findings. Populated by ReportTelemetry.snapshot(). NULL for
    # v1 reports and any pre-telemetry rows.
    telemetry: dict[str, Any] | None = None


TreemapNode.model_rebuild()
