"""Data contracts for the v2.3 equity-research subagent pipeline.

Source: `planning/2026-05-22-report-subagent-design.md` (companion artifact
`/Users/tkchang/Downloads/report_schemas.py`), with OpenLIA adaptations:

1. `Language` carried on `ReportThesis` so writers render in the report's language.
2. `BundleFact.value` accepts `float | str | BundleSeries` (time-series).
3. `ResearchBundle.tickers: list[str]` — multi-ticker reports are first-class.
4. `OutlineSection.section_type` links the planner to existing sector templates.
5. `ValuationPlan` lives on `ReportThesis` (planned at synthesis, executed by COMPUTE
   if needed before WRITE).
6. `ReportType` enum carried on `Outline` (initiation / update / morning_brief).
7. Computed facts may reference *bundle* fact ids whose values were filled by
   COMPUTE; the validator runs after the bundle is complete.
8. Canonical figure rendering is language-aware (caller's responsibility; the
   `display` string is the *final* rendering for the report's language).

Placeholder conventions (used inside written prose, resolved at ASSEMBLE):
    {{CITE:<fact_id>}}    -> inline footnote marker
    {{FIG:<chart_id>}}    -> "Figure N" + chart placement anchor
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

# ---------------------------------------------------------------------------
# 0. ENUMS
# ---------------------------------------------------------------------------


class Language(StrEnum):
    """Supported report languages. Mirrors user_prefs.report_language."""

    EN = "en"
    ZH_TW = "zh-TW"


class ReportType(StrEnum):
    """High-level report shape. Drives default sections and valuation plan."""

    INITIATION = "initiation"
    UPDATE = "update"
    MORNING_BRIEF = "morning_brief"
    EARNINGS_REVIEW = "earnings_review"


class RunStatus(StrEnum):
    """CLARIFY makes the run suspendable. WAITING_ON_USER means ReportState is
    checkpointed and the runner returned questions to the client."""

    RUNNING = "running"
    WAITING_ON_USER = "waiting_on_user"
    COMPLETE = "complete"
    FAILED = "failed"


class SourceType(StrEnum):
    DATA_PROVIDER = "data_provider"  # EODHD / FMP — quantitative
    WEB = "web"  # qualitative / narrative
    FILING = "filing"  # 10-K, 10-Q, 8-K, etc.
    COMPUTED = "computed"  # derived from other facts


class ChartType(StrEnum):
    """Supported by python-docx high-level chart API. Candlestick/dual-axis
    require a direct OOXML path and are out of scope for first cut."""

    COLUMN = "column"
    BAR = "bar"
    LINE = "line"
    AREA = "area"
    PIE = "pie"
    SCATTER = "scatter"


class ValuationMethod(StrEnum):
    DCF = "dcf"
    COMPS = "comps"
    SENSITIVITY = "sensitivity"


class IssueSeverity(StrEnum):
    HIGH = "high"  # routes the section back for a targeted rewrite
    LOW = "low"  # surfaced, not blocking


class IssueKind(StrEnum):
    UNCITED_NUMBER = "uncited_number"
    DANGLING_CITE = "dangling_cite"
    VALUE_MISMATCH = "value_mismatch"
    CROSS_SECTION_CONTRADICTION = "cross_section_contradiction"
    REDUNDANCY = "redundancy"
    CHART_TEXT_MISMATCH = "chart_text_mismatch"
    BROKEN_FIG_REF = "broken_fig_ref"


# ---------------------------------------------------------------------------
# 1. PROVENANCE — born in RESEARCH, carried as data thereafter
# ---------------------------------------------------------------------------


class DataProviderSource(BaseModel):
    type: Literal[SourceType.DATA_PROVIDER] = SourceType.DATA_PROVIDER
    provider: str  # "EODHD", "FMP"
    endpoint: str  # e.g. "fundamentals/income_statement"
    statement: str | None = None
    period: str  # "TTM", "2025-Q4", "FY2025"
    retrieved_at: datetime


class WebSource(BaseModel):
    type: Literal[SourceType.WEB] = SourceType.WEB
    url: str
    title: str | None = None
    publisher: str | None = None
    snippet: str = Field(..., description="Short verbatim support so VERIFY can value-match.")
    retrieved_at: datetime


class FilingSource(BaseModel):
    type: Literal[SourceType.FILING] = SourceType.FILING
    company: str
    form_type: str  # "10-K", "10-Q", "8-K"
    fiscal_period: str  # "FY2025"
    page: int | None = None
    url: str | None = None
    retrieved_at: datetime


class ComputedSource(BaseModel):
    """A fact we calculated. Cites its INPUTS, not a phantom external source."""

    type: Literal[SourceType.COMPUTED] = SourceType.COMPUTED
    method: str  # e.g. "EV / EBITDA"
    derived_from: list[str] = Field(
        ...,
        min_length=1,
        description="fact_ids of the inputs that fed this calculation.",
    )


Provenance = DataProviderSource | WebSource | FilingSource | ComputedSource


# ---------------------------------------------------------------------------
# 2. RESEARCH BUNDLE — single source of truth for every number
# ---------------------------------------------------------------------------


class BundleSeriesPoint(BaseModel):
    """One observation in a time-series fact. Period strings follow the same
    convention as DataProviderSource.period (e.g. "2025-Q4", "FY2025")."""

    period: str
    value: float


class BundleSeries(BaseModel):
    """Time-series value for a fact. Charts plot series.points; writers cite
    the parent fact's id (the chart shows the detail)."""

    points: list[BundleSeriesPoint] = Field(..., min_length=1)
    unit: str | None = None


class BundleFact(BaseModel):
    """One fact, with provenance. Value may be scalar (float / str) or a
    time-series — equity-research charts often need the latter."""

    id: str = Field(..., description="Stable ID writers reference, e.g. 'rev_ttm_growth'.")
    label: str  # human-readable, for the canonical table
    value: float | str | BundleSeries  # scalar OR time-series
    unit: str | None = None  # "percent", "USD_millions", "x", None
    ticker: str | None = None  # which subject this fact is about (None = report-wide)
    source: Provenance = Field(..., discriminator="type")

    @property
    def is_quantitative(self) -> bool:
        return isinstance(self.value, (int, float, BundleSeries))


class ResearchBundle(BaseModel):
    """Output of RESEARCH (+ COMPUTE). Every fact carries provenance already."""

    tickers: list[str] = Field(..., min_length=1)
    facts: dict[str, BundleFact] = Field(default_factory=dict)

    def add(self, fact: BundleFact) -> None:
        if fact.id in self.facts:
            raise ValueError(f"Duplicate fact id: {fact.id}")
        self.facts[fact.id] = fact

    def get(self, fact_id: str) -> BundleFact:
        return self.facts[fact_id]

    @model_validator(mode="after")
    def _check_derived_chains(self) -> ResearchBundle:
        for fid, fact in self.facts.items():
            if isinstance(fact.source, ComputedSource):
                missing = [d for d in fact.source.derived_from if d not in self.facts]
                if missing:
                    raise ValueError(f"Fact '{fid}' derives from missing facts: {missing}")
        return self


# ---------------------------------------------------------------------------
# 3. CHARTS — planned at SYNTHESIZE around a claim; rendered NATIVELY in docx
# ---------------------------------------------------------------------------


class ChartSeries(BaseModel):
    name: str
    value_fact_ids: list[str] = Field(..., min_length=1)


class ChartSpec(BaseModel):
    id: str = Field(..., description="Referenced in prose via {{FIG:<id>}}.")
    section_id: str
    claim: str = Field(..., description="The point this chart is meant to make.")
    chart_type: ChartType
    title: str
    category_labels: list[str]
    series: list[ChartSeries] = Field(..., min_length=1)
    x_axis_label: str | None = None
    y_axis_label: str | None = None

    def referenced_fact_ids(self) -> set[str]:
        return {fid for s in self.series for fid in s.value_fact_ids}


# ---------------------------------------------------------------------------
# 4. COMPUTE — valuation tools (DCF, comps, sensitivity)
# ---------------------------------------------------------------------------


class DCFInputs(BaseModel):
    revenue_base_fact_id: str
    revenue_growth_path: list[float] = Field(..., min_length=1)
    margin_path: list[float] = Field(..., min_length=1)
    wacc: float
    terminal_growth: float
    tax_rate: float
    grounding_fact_ids: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def _paths_align(self) -> DCFInputs:
        if len(self.revenue_growth_path) != len(self.margin_path):
            raise ValueError("growth_path and margin_path must cover the same horizon.")
        return self


class CompPeer(BaseModel):
    ticker: str
    metric_fact_ids: dict[str, str] = Field(
        ...,
        description="metric name -> fact_id, e.g. {'ev_ebitda': 'peer_nvda_ev_ebitda'}.",
    )


class CompsInputs(BaseModel):
    subject_ticker: str
    peers: list[CompPeer] = Field(..., min_length=1)
    multiples: list[str] = Field(..., min_length=1)
    subject_metric_fact_ids: dict[str, str] = Field(default_factory=dict)


class SensitivityInputs(BaseModel):
    base: DCFInputs
    row_driver: Literal["wacc", "terminal_growth"]
    col_driver: Literal["wacc", "terminal_growth"]
    row_values: list[float] = Field(..., min_length=2)
    col_values: list[float] = Field(..., min_length=2)

    @model_validator(mode="after")
    def _distinct_drivers(self) -> SensitivityInputs:
        if self.row_driver == self.col_driver:
            raise ValueError("Sensitivity axes must vary different drivers.")
        return self


class DCFResult(BaseModel):
    enterprise_value: float
    equity_value: float
    fair_value_per_share: float
    implied_upside: float | None = None


class CompsResult(BaseModel):
    implied_value_by_multiple: dict[str, float]
    peer_table: list[dict[str, float]]


class SensitivityResult(BaseModel):
    """Locked: ONE structured fact holding the grid, not N facts. Feeds a
    heatmap ChartSpec as a single object."""

    row_driver: str
    col_driver: str
    row_values: list[float]
    col_values: list[float]
    grid: list[list[float]]


ValuationInputs = DCFInputs | CompsInputs | SensitivityInputs
ValuationResult = DCFResult | CompsResult | SensitivityResult


class ValuationPlan(BaseModel):
    """Emitted by PLAN/SYNTHESIZE: which methods this report needs. Lives on
    `ReportThesis` so the COMPUTE re-run (if VERIFY routes back) sees the
    canonical plan."""

    methods: list[ValuationMethod] = Field(default_factory=list)


def dcf_result_to_facts(result: DCFResult, inputs: DCFInputs) -> list[BundleFact]:
    """Decompose a DCF result into computed BundleFacts. Each cites its inputs
    via ComputedSource.derived_from, so {{CITE:dcf_fair_value}} renders an
    auditable 'Author calculation: DCF' footnote with a real input chain."""
    derived = [inputs.revenue_base_fact_id, *inputs.grounding_fact_ids]

    def src(method: str) -> ComputedSource:
        return ComputedSource(method=method, derived_from=derived)

    return [
        BundleFact(
            id="dcf_enterprise_value",
            label="DCF enterprise value",
            value=result.enterprise_value,
            unit="USD_millions",
            source=src("DCF (enterprise value)"),
        ),
        BundleFact(
            id="dcf_fair_value",
            label="DCF fair value per share",
            value=result.fair_value_per_share,
            unit="USD",
            source=src("DCF (per share)"),
        ),
    ]


# ---------------------------------------------------------------------------
# 5. CLARIFY — conditional front gate
# ---------------------------------------------------------------------------


MAX_CLARIFY_QUESTIONS = 3


class ClarifyQuestion(BaseModel):
    id: str
    question: str
    why_blocking: str = Field(
        ...,
        description="Why a wrong guess here would misdirect the pipeline.",
    )
    default: str = Field(
        ...,
        description="Stated fallback that flows into PLAN/thesis if unanswered.",
    )


class ClarifyProceed(BaseModel):
    """Prompt is sufficient. Go straight to PLAN."""

    outcome: Literal["proceed"] = "proceed"
    assumptions: list[str] = Field(default_factory=list)


class ClarifyNeedsInput(BaseModel):
    """Prompt has blocking ambiguity. Suspend and ask."""

    outcome: Literal["needs_input"] = "needs_input"
    questions: list[ClarifyQuestion] = Field(..., min_length=1, max_length=MAX_CLARIFY_QUESTIONS)


ClarifyResult = ClarifyProceed | ClarifyNeedsInput


class ClarifyAnswers(BaseModel):
    """User reply when the run was suspended. Missing ids fall back to defaults."""

    answers: dict[str, str] = Field(default_factory=dict)

    def resolve(self, questions: list[ClarifyQuestion]) -> dict[str, str]:
        return {q.id: self.answers.get(q.id, q.default) for q in questions}


# ---------------------------------------------------------------------------
# 6. OUTLINE + THESIS — the coherence anchor (PLAN -> SYNTHESIZE)
# ---------------------------------------------------------------------------


class DataNeed(BaseModel):
    """PLAN emits these; they become RESEARCH's targeted work queue."""

    description: str  # "gross margin trend, last 8 quarters"
    expected_fact_ids: list[str] = Field(default_factory=list)


class OutlineSection(BaseModel):
    id: str
    title: str
    section_type: str | None = Field(
        None,
        description="Links to a sector template / framework key for default content.",
    )
    data_needs: list[DataNeed] = Field(default_factory=list)


class Outline(BaseModel):
    """Output of PLAN."""

    tickers: list[str] = Field(..., min_length=1)
    report_type: ReportType
    sections: list[OutlineSection]


class SectionMandate(BaseModel):
    """Per-section instruction emitted by SYNTHESIZE. Carries the anti-redundancy
    boundary and the chart assignments for the section."""

    section_id: str
    covers: str = Field(..., description="What this section IS about.")
    does_not_cover: str = Field(..., description="Explicit non-overlap boundary.")
    chart_ids: list[str] = Field(default_factory=list)
    relevant_fact_ids: list[str] = Field(
        default_factory=list,
        description="The bundle slice this writer is allowed to use.",
    )


class CanonicalFigure(BaseModel):
    fact_id: str
    display: str = Field(
        ...,
        description="The ONE agreed rendering for the report's language, e.g. '14.2%'.",
    )


class ReportThesis(BaseModel):
    """Output of SYNTHESIZE. Prepended to EVERY write call — the shared anchor
    that makes parallel section writing cohere instead of drift."""

    language: Language
    central_argument: str
    key_takeaways: list[str]
    valuation_stance: str
    valuation_plan: ValuationPlan = Field(default_factory=ValuationPlan)
    canonical_figures: list[CanonicalFigure]
    mandates: list[SectionMandate]
    charts: list[ChartSpec]

    @model_validator(mode="after")
    def _charts_reference_assigned_sections(self) -> ReportThesis:
        section_ids = {m.section_id for m in self.mandates}
        for c in self.charts:
            if c.section_id not in section_ids:
                raise ValueError(f"Chart '{c.id}' targets unknown section '{c.section_id}'.")
        return self


# ---------------------------------------------------------------------------
# 7. WRITTEN OUTPUT — prose with placeholders, not resolved citations
# ---------------------------------------------------------------------------


CITE_RE = re.compile(r"\{\{CITE:([a-zA-Z0-9_]+)\}\}")
FIG_RE = re.compile(r"\{\{FIG:([a-zA-Z0-9_]+)\}\}")


class WrittenSection(BaseModel):
    """Output of one WRITE call. Body contains {{CITE:}} and {{FIG:}} tokens."""

    section_id: str
    title: str
    body: str

    def cited_fact_ids(self) -> list[str]:
        return CITE_RE.findall(self.body)

    def figure_ids(self) -> list[str]:
        return FIG_RE.findall(self.body)


# ---------------------------------------------------------------------------
# 8. VERIFY — what the critic emits; the runner gates on it
# ---------------------------------------------------------------------------


class VerifyIssue(BaseModel):
    section_id: str | None
    kind: IssueKind
    severity: IssueSeverity
    detail: str


class VerifyResult(BaseModel):
    issues: list[VerifyIssue] = Field(default_factory=list)

    @property
    def must_rewrite(self) -> bool:
        return any(i.severity == IssueSeverity.HIGH for i in self.issues)


# ---------------------------------------------------------------------------
# 9. PLACEHOLDER RESOLUTION — owned by ASSEMBLE (deterministic)
# ---------------------------------------------------------------------------


class ResolvedReport(BaseModel):
    """What ASSEMBLE produces before handing to the docx writer."""

    section_bodies: dict[str, str]
    footnotes: list[str]
    figure_labels: dict[str, int]


def render_citation(fact: BundleFact) -> str:
    """Render a single footnote line from provenance. Format is owned here, so
    it is consistent everywhere."""
    s = fact.source
    if isinstance(s, DataProviderSource):
        stmt = f", {s.statement}" if s.statement else ""
        return f"{s.provider}{stmt} ({s.endpoint}), {s.period}."
    if isinstance(s, WebSource):
        pub = f"{s.publisher}. " if s.publisher else ""
        title = s.title or s.url
        return f"{pub}{title}. {s.url}"
    if isinstance(s, FilingSource):
        page = f", p. {s.page}" if s.page else ""
        return f"{s.company} {s.form_type} ({s.fiscal_period}){page}."
    if isinstance(s, ComputedSource):
        return f"Author calculation: {s.method}."
    raise TypeError(f"Unknown source type: {type(s)}")


def resolve(
    sections: list[WrittenSection],
    bundle: ResearchBundle,
    charts: list[ChartSpec],
    section_order: list[str],
) -> ResolvedReport:
    """Deterministic resolution of {{CITE:}} and {{FIG:}} placeholders.

    - Footnotes are numbered in document order, deduped by fact_id.
    - Figures are numbered in document order. Writers never hardcode numbers,
      so parallel writing cannot collide.
    - Dangling references raise — better to fail loud than ship a broken report.
    """
    section_by_id = {s.section_id: s for s in sections}
    chart_ids = {c.id for c in charts}

    figure_labels: dict[str, int] = {}
    fig_counter = 0
    for sid in section_order:
        body = section_by_id[sid].body
        for chart_id in FIG_RE.findall(body):
            if chart_id not in chart_ids:
                raise ValueError(f"Figure ref '{chart_id}' has no ChartSpec.")
            if chart_id not in figure_labels:
                fig_counter += 1
                figure_labels[chart_id] = fig_counter

    footnotes: list[str] = []
    footnote_index: dict[str, int] = {}
    resolved_bodies: dict[str, str] = {}

    for sid in section_order:
        body = section_by_id[sid].body

        def _cite_sub(m: re.Match) -> str:
            fact_id = m.group(1)
            if fact_id not in bundle.facts:
                raise ValueError(f"Dangling citation: '{fact_id}' not in bundle.")
            if fact_id not in footnote_index:
                footnote_index[fact_id] = len(footnotes) + 1
                footnotes.append(render_citation(bundle.get(fact_id)))
            return f"[^{footnote_index[fact_id]}]"

        def _fig_sub(m: re.Match) -> str:
            chart_id = m.group(1)
            return f"Figure {figure_labels[chart_id]}"

        body = CITE_RE.sub(_cite_sub, body)
        body = FIG_RE.sub(_fig_sub, body)
        resolved_bodies[sid] = body

    return ResolvedReport(
        section_bodies=resolved_bodies,
        footnotes=footnotes,
        figure_labels=figure_labels,
    )
