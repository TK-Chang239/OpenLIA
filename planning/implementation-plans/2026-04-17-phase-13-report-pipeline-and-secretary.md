# Report Rendering Pipeline + Secretary Department Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the cross-department report rendering pipeline (schema, assembler, block renderers, PDF export) and the Secretary department — the simplest, chat-only department that validates the Phase-4 frontend shell + Plan 12 chat components end-to-end.

**Architecture:**
- **Core** holds a pure-Python report layer (`openlia/reports/schema.py`, `assembler.py`, `validator.py`, `frameworks/loader.py`) and a per-department prompt registry (`openlia/prompts/secretary.yaml`). No web imports.
- **Server** exposes two HTTP endpoints: `GET /api/reports/{id}` returns the stored `ReportSchema`; `POST /api/reports/{id}/export/pdf` streams a Playwright-rendered PDF. A third surface — `POST /api/departments/secretary/chat` — is thin: it routes to `ChatRunner` from Plan 5 with the Secretary prompt.
- **Frontend** ships a `ReportRenderer` component tree that reads a schema and renders styled HTML using ECharts, TanStack Table, Framer Motion, and react-markdown. Reports open inside the `FileViewer` from Plan 12. The Secretary page reuses `ChatInterface` from Plan 12 and adds a `RedirectCard` message block that the Secretary prompt emits via a `suggest_redirect` tool.

**Tech Stack:**
- Backend: FastAPI, SQLAlchemy 2.x, Pydantic v2, Playwright (headless Chromium), Jinja2 (prompts).
- Frontend: React 18 + TypeScript strict, ECharts 5 (`echarts-for-react`), TanStack Table v8 + TanStack Virtual, Framer Motion, react-markdown + remark-gfm, KaTeX, react-loading-skeleton, react-intersection-observer, file-saver, date-fns.

**Dependencies:**
- Plan 1A: `reports` table columns (`id`, `user_id`, `department`, `mode`, `schema_json`, `generated_at`, `status`).
- Plan 2: session middleware (all endpoints authenticated).
- Plan 3: data requirement adapters (Secretary needs `stock_quote`, `company_profile`, `company_news`, `historical_prices`, `economic_events`).
- Plan 4: LLM provider system (Thinking/Everyday/Quick tiers; Secretary defaults to the Everyday tier).
- Plan 5: `ChatRunner`, prompt loader, SSE event taxonomy.
- Plan 8: frontend shell (routing, auth context, design tokens, `FileViewerProvider`).
- Plan 12: `ChatInterface`, `useChatStream`, `FileViewerContext`, `SaveToRepoButton`, `FileDownloadButton`.

---

## Design Rules

1. **LLM decides content; frontend decides chrome.** Chart titles, types, data, row styles — the LLM. Colors, fonts, spacing, animations — the theme.
2. **Schema is canonical.** Reports are stored as `schema_json`. Re-rendering never re-calls the LLM. Validation happens at write time, not at render time.
3. **One schema version.** v1 ships `schema_version: "1.0"`. The validator rejects anything else — future plans bump the version and migrate in place.
4. **All chart blocks have `title` and `options`.** Uniform across block types keeps the block dispatcher simple.
5. **Group block is a block.** No special cases in `BlockRenderer` — it recurses on `group.blocks`.
6. **Text blocks are markdown.** No HTML. No iframes. The renderer is the only thing that converts.
7. **Page furniture is server-populated, not LLM-populated.** The LLM may not write to `page_furniture`; the validator strips it if present on input.
8. **Secretary does not generate reports.** It's chat-only. The redirect card is a message block inside the chat transcript, not a `ReportSchema`.
9. **Redirect is a tool call.** The Secretary prompt calls `suggest_redirect(department, reason, prefill?)`. The UI renders the tool call result as a card. Server-side intent detection is explicitly rejected — the LLM is the intent classifier.
10. **Framework JSONs live in core.** Move `planning/frameworks/*.{json,md}` into `packages/core/src/openlia/reports/frameworks/`. Planning is a specs dir; shipping artifacts live in the package.
11. **ECharts, not Recharts.** Every chart type (candlestick, heatmap, waterfall, treemap) is covered without custom renderers.
12. **PDF is light-mode only.** The app theme toggle does not affect PDF output.
13. **Playwright instance is warm.** One `Browser` per server process, lazily launched, closed on app shutdown. One `BrowserContext` per export.
14. **TDD.** Every production file lands with a failing test, then the implementation, then the green run, then a commit.
15. **No placeholders inside the plan.** Every step contains the exact code, the exact command, and the expected output.

---

## File Structure

### Core (`packages/core/src/openlia/`)

```
reports/
├── __init__.py
├── schema.py                       # Pydantic models for every block type + ReportSchema
├── assembler.py                    # LLM output -> ReportSchema; strips instructions; applies furniture
├── validator.py                    # Structural validator for the assembled schema
└── frameworks/
    ├── __init__.py
    ├── loader.py                   # load_framework(name) -> dict with user customizations applied
    ├── stock_initiation.json
    ├── stock_initiation_style_guide.md
    ├── stock_update.json
    ├── stock_update_style_guide.md
    ├── sector_research.json
    ├── sector_research_style_guide.md
    ├── earnings_update.json
    ├── earnings_update_style_guide.md
    ├── morning_briefing.json
    └── morning_briefing_style_guide.md
prompts/
└── secretary.yaml                  # Secretary ChatRunner prompt + tool declarations
departments/
├── __init__.py
├── base.py                         # Department protocol (if not present from Plan 5)
└── secretary.py                    # SecretaryDepartment — maps requirements, resolves tools, owns prompt name
```

### Server (`packages/server/src/openlia_server/`)

```
routes/
├── reports.py                      # GET /api/reports/{id}; POST /api/reports/{id}/export/pdf
└── departments/
    ├── __init__.py
    └── secretary.py                # POST /api/departments/secretary/chat (SSE)
services/
├── report_store.py                 # fetch/store ReportSchema rows
└── report_export.py                # Playwright singleton + PDF render
```

### Frontend (`frontend/src/`)

```
api/
├── reports.ts                      # fetchReport, downloadReportPdf
└── secretary.ts                    # startSecretaryChat(message, sessionId?) -> EventSource URL
components/report/
├── ReportRenderer.tsx              # Top-level entry: reads schema, renders furniture + sections
├── ReportCover.tsx                 # Title, subtitle, tagline, key metrics, stats panel
├── TableOfContents.tsx             # Auto-generated section links (scroll-spy)
├── ReportSection.tsx               # Heading + anchor + block list
├── BlockRenderer.tsx               # switch on block.type -> component
├── ReportSkeleton.tsx              # Loading skeleton while report.* streams
├── blocks/
│   ├── TextBlock.tsx
│   ├── TableBlock.tsx
│   ├── MetricCardsBlock.tsx
│   ├── GroupBlock.tsx
│   ├── KeyFindingBlock.tsx
│   └── RatingBadgeBlock.tsx
├── charts/
│   ├── ChartFrame.tsx              # Shared height/title/legend wrapper
│   ├── LineChartBlock.tsx
│   ├── BarChartBlock.tsx
│   ├── AreaChartBlock.tsx
│   ├── PieChartBlock.tsx
│   ├── CandlestickBlock.tsx
│   ├── WaterfallBlock.tsx
│   ├── ScatterBlock.tsx
│   ├── HeatmapBlock.tsx
│   ├── TreemapBlock.tsx
│   └── ComboChartBlock.tsx
└── furniture/
    ├── ReportHeader.tsx
    ├── ReportFooter.tsx
    └── ScrollTracker.tsx
pages/
└── SecretaryPage.tsx               # Welcome state + ChatInterface wiring + RedirectCard handling
components/chat/
└── RedirectCard.tsx                # Renders Secretary's suggest_redirect tool call result
styles/report/
├── theme-light.css
└── theme-dark.css
```

---

## Task Overview

1. Core: `ReportSchema` Pydantic models (every block type).
2. Core: `validator.py` — structural checks and error aggregation.
3. Core: `assembler.py` — LLM raw output -> validated `ReportSchema`.
4. Core: `frameworks/loader.py` + move framework files into the package.
5. Core: `prompts/secretary.yaml` + `SecretaryDepartment` class.
6. Server: `report_store.py` service (fetch + create).
7. Server: `report_export.py` Playwright service with singleton browser.
8. Server: `/api/reports/{id}` + `/api/reports/{id}/export/pdf` routes.
9. Server: `/api/departments/secretary/chat` SSE route.
10. Frontend: `api/reports.ts` + `api/secretary.ts` typed clients.
11. Frontend: report theme CSS (`theme-light.css` + `theme-dark.css`).
12. Frontend: `TextBlock` (markdown + inline colored numbers).
13. Frontend: `TableBlock` (sort, search, row styles, cell formats, sparklines, footnotes).
14. Frontend: `MetricCardsBlock` (count-up) + `KeyFindingBlock` + `RatingBadgeBlock`.
15. Frontend: `GroupBlock` (height normalization).
16. Frontend: `ChartFrame` + `LineChartBlock` + `BarChartBlock` + `AreaChartBlock` + `PieChartBlock`.
17. Frontend: `CandlestickBlock` + `WaterfallBlock` + `ScatterBlock` + `HeatmapBlock` + `TreemapBlock` + `ComboChartBlock`.
18. Frontend: `BlockRenderer` dispatcher.
19. Frontend: `ReportCover` + `TableOfContents` + `ScrollTracker`.
20. Frontend: `ReportHeader` + `ReportFooter` + `ReportSkeleton`.
21. Frontend: `ReportRenderer` top-level composition.
22. Frontend: `RedirectCard` chat message block.
23. Frontend: `SecretaryPage` — welcome state + ChatInterface wiring + suggestion chips + redirect handling.
24. Manual smoke test + flip README row to Draft.

---


### Task 1: Core — ReportSchema Pydantic models

All block types from the spec as strict Pydantic v2 models. Discriminated union on `type`.

**Files:**
- Create: `packages/core/src/openlia/reports/__init__.py`
- Create: `packages/core/src/openlia/reports/schema.py`
- Test: `packages/core/tests/reports/test_schema.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/reports/test_schema.py
from datetime import datetime, timezone
import pytest
from pydantic import ValidationError

from openlia.reports.schema import (
    ReportSchema,
    TextBlock,
    TableBlock,
    TableHeader,
    MetricCardsBlock,
    Metric,
    GroupBlock,
    KeyFindingBlock,
    RatingBadgeBlock,
    LineChartBlock,
    BarChartBlock,
    CandlestickBlock,
    Cover,
    Section,
    PageFurniture,
)


def test_text_block_parses():
    b = TextBlock(type="text", content="Hello **world**")
    assert b.content == "Hello **world**"


def test_table_block_requires_headers_and_rows():
    t = TableBlock(
        type="table",
        title="Revenue",
        headers=[TableHeader(key="q", label="Quarter", align="left")],
        rows=[{"q": "Q1 2026"}],
    )
    assert t.headers[0].key == "q"
    with pytest.raises(ValidationError):
        TableBlock(type="table", title="x", headers=[], rows=[])


def test_group_block_nests_other_blocks():
    inner = TextBlock(type="text", content="a")
    g = GroupBlock(type="group", columns=2, blocks=[inner, inner])
    assert len(g.blocks) == 2


def test_metric_cards_block_requires_at_least_one_metric():
    m = MetricCardsBlock(
        type="metric_cards",
        metrics=[Metric(label="Rev", value="$1B")],
    )
    assert m.metrics[0].value == "$1B"
    with pytest.raises(ValidationError):
        MetricCardsBlock(type="metric_cards", metrics=[])


def test_line_chart_requires_series():
    c = LineChartBlock(
        type="line_chart",
        title="Margin",
        series=[{"name": "M%", "data": [{"x": "Q1", "y": 46.6}]}],
    )
    assert c.series[0]["name"] == "M%"


def test_bar_chart_requires_categories_and_series():
    b = BarChartBlock(
        type="bar_chart",
        title="Rev",
        categories=["Q1"],
        series=[{"name": "Rev", "values": [1.0]}],
    )
    assert b.categories == ["Q1"]


def test_candlestick_has_ohlc_data():
    c = CandlestickBlock(
        type="candlestick_chart",
        title="AAPL",
        data=[{"date": "2026-04-01", "open": 1, "high": 2, "low": 0.5, "close": 1.8}],
    )
    assert len(c.data) == 1


def test_full_schema_parses():
    schema = ReportSchema(
        schema_version="1.0",
        department="equity_research",
        generated_at=datetime.now(timezone.utc),
        page_furniture=PageFurniture(
            header={"left": "OpenLIA", "right": "Equity Research"},
            footer={"left": "Generated", "center": "Page {page}", "right": "Internal"},
            disclaimer="Not advice.",
        ),
        cover=Cover(
            title="Apple Inc.",
            subtitle="Q1 2026",
            ticker="AAPL",
            tagline="Strong quarter.",
            key_metrics=[Metric(label="Price", value="$198.50")],
            stats_panel=[Metric(label="Sector", value="Technology")],
        ),
        sections=[
            Section(
                id="fin",
                title="Financial Overview",
                blocks=[TextBlock(type="text", content="Apple reported...")],
            )
        ],
    )
    assert schema.schema_version == "1.0"
    assert schema.cover.ticker == "AAPL"


def test_schema_rejects_unknown_version():
    with pytest.raises(ValidationError):
        ReportSchema(
            schema_version="2.0",
            department="equity_research",
            generated_at=datetime.now(timezone.utc),
            cover=Cover(title="x", subtitle="x", ticker="AAPL", tagline="x"),
            sections=[],
        )


def test_rating_badge_block_parses():
    r = RatingBadgeBlock(
        type="rating_badge",
        rating="Overweight",
        previous_rating="Equal Weight",
        change_date="2026-04-11",
    )
    assert r.rating == "Overweight"


def test_key_finding_block_parses():
    k = KeyFindingBlock(type="key_finding", content="iPhone up 49%.")
    assert "iPhone" in k.content
```

- [ ] **Step 2: Run the test and confirm it fails**

Run: `uv run pytest packages/core/tests/reports/test_schema.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'openlia.reports'`.

- [ ] **Step 3: Write the module**

```python
# packages/core/src/openlia/reports/__init__.py
from openlia.reports.schema import ReportSchema

__all__ = ["ReportSchema"]
```

```python
# packages/core/src/openlia/reports/schema.py
"""Pydantic models for the report schema defined in
planning/specs/systems/report-rendering-pipeline-design.md.

All reports are stored as instances of ``ReportSchema``. The renderer
reads this model and produces HTML; the PDF exporter reads the rendered
HTML. The schema is self-contained — no external data references.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, conlist


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


Align = Literal["left", "center", "right"]
RowStyle = Literal["default", "subtotal", "total", "header_group"]
FormatRule = Literal["negative", "positive", "directional", "bold", "muted"]
ChartHeight = Literal["small", "medium", "tall"]
DeltaDirection = Literal["up", "down", "flat"]


class Metric(_Strict):
    label: str
    value: str
    delta: str | None = None
    delta_direction: DeltaDirection | None = None


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
    options: dict[str, Any] = Field(default_factory=dict)


class MetricCardsBlock(_Strict):
    type: Literal["metric_cards"]
    metrics: Annotated[list[Metric], Field(min_length=1)]


class KeyFindingBlock(_Strict):
    type: Literal["key_finding"]
    content: str


class RatingBadgeBlock(_Strict):
    type: Literal["rating_badge"]
    rating: str
    previous_rating: str | None = None
    change_date: str | None = None


class LineChartSeries(_Strict):
    name: str
    data: list[dict[str, Any]]


class LineChartBlock(_Strict):
    type: Literal["line_chart"]
    title: str
    series: Annotated[list[dict[str, Any]], Field(min_length=1)]
    x_label: str | None = None
    y_label: str | None = None
    options: ChartOptions = Field(default_factory=ChartOptions)


class BarChartSeries(_Strict):
    name: str
    values: list[float]


class BarChartBlock(_Strict):
    type: Literal["bar_chart"]
    title: str
    categories: Annotated[list[str], Field(min_length=1)]
    series: Annotated[list[dict[str, Any]], Field(min_length=1)]
    orientation: Literal["vertical", "horizontal"] = "vertical"
    stacked: bool = False
    options: ChartOptions = Field(default_factory=ChartOptions)


class AreaChartBlock(_Strict):
    type: Literal["area_chart"]
    title: str
    series: Annotated[list[dict[str, Any]], Field(min_length=1)]
    stacked: bool = False
    options: ChartOptions = Field(default_factory=ChartOptions)


class PieSegment(_Strict):
    label: str
    value: float


class PieChartBlock(_Strict):
    type: Literal["pie_chart"]
    title: str
    segments: Annotated[list[PieSegment], Field(min_length=1)]
    donut: bool = False
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
    options: ChartOptions = Field(default_factory=ChartOptions)


class WaterfallItem(_Strict):
    label: str
    value: float
    type: Literal["total", "increase", "decrease"]


class WaterfallBlock(_Strict):
    type: Literal["waterfall_chart"]
    title: str
    items: Annotated[list[WaterfallItem], Field(min_length=2)]
    options: ChartOptions = Field(default_factory=ChartOptions)


class ScatterBlock(_Strict):
    type: Literal["scatter_plot"]
    title: str
    series: Annotated[list[dict[str, Any]], Field(min_length=1)]
    x_label: str | None = None
    y_label: str | None = None
    options: ChartOptions = Field(default_factory=ChartOptions)


class HeatmapBlock(_Strict):
    type: Literal["heatmap"]
    title: str
    x_labels: Annotated[list[str], Field(min_length=1)]
    y_labels: Annotated[list[str], Field(min_length=1)]
    values: Annotated[list[list[float]], Field(min_length=1)]
    options: ChartOptions = Field(default_factory=ChartOptions)


class TreemapNode(_Strict):
    name: str
    value: float
    children: list["TreemapNode"] | None = None


class TreemapBlock(_Strict):
    type: Literal["treemap"]
    title: str
    data: Annotated[list[TreemapNode], Field(min_length=1)]
    options: ChartOptions = Field(default_factory=ChartOptions)


class ComboChartBlock(_Strict):
    type: Literal["combo_chart"]
    title: str
    categories: Annotated[list[str], Field(min_length=1)]
    bar_series: Annotated[list[dict[str, Any]], Field(min_length=1)]
    line_series: Annotated[list[dict[str, Any]], Field(min_length=1)]
    y_left_label: str | None = None
    y_right_label: str | None = None
    options: ChartOptions = Field(default_factory=ChartOptions)


LeafBlock = Union[
    TextBlock,
    TableBlock,
    MetricCardsBlock,
    KeyFindingBlock,
    RatingBadgeBlock,
    LineChartBlock,
    BarChartBlock,
    AreaChartBlock,
    PieChartBlock,
    CandlestickBlock,
    WaterfallBlock,
    ScatterBlock,
    HeatmapBlock,
    TreemapBlock,
    ComboChartBlock,
]


class GroupBlock(_Strict):
    type: Literal["group"]
    columns: int = Field(ge=1, le=4)
    blocks: Annotated[list[LeafBlock], Field(min_length=1)]


Block = Annotated[
    Union[LeafBlock, GroupBlock],
    Field(discriminator="type"),
]


class Section(_Strict):
    id: str
    title: str
    blocks: list[Block]


class Cover(_Strict):
    title: str
    subtitle: str
    ticker: str | None = None
    tagline: str
    key_metrics: list[Metric] = Field(default_factory=list)
    stats_panel: list[Metric] = Field(default_factory=list)


class PageFurniture(_Strict):
    header: dict[str, str]
    footer: dict[str, str]
    disclaimer: str


class ReportSchema(_Strict):
    schema_version: Literal["1.0"]
    department: str
    generated_at: datetime
    page_furniture: PageFurniture | None = None
    cover: Cover
    sections: list[Section]


TreemapNode.model_rebuild()
```

- [ ] **Step 4: Run the test and confirm it passes**

Run: `uv run pytest packages/core/tests/reports/test_schema.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/reports/__init__.py \
        packages/core/src/openlia/reports/schema.py \
        packages/core/tests/reports/test_schema.py
git commit -m "feat(reports): add ReportSchema Pydantic models"
```

---

### Task 2: Core — Schema validator

A thin layer on top of Pydantic that produces friendly error messages for LLM-originated payloads. It runs `ReportSchema.model_validate` and re-packages any failures into a `ReportValidationError` with a list of `(path, message)` tuples.

**Files:**
- Create: `packages/core/src/openlia/reports/validator.py`
- Test: `packages/core/tests/reports/test_validator.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/reports/test_validator.py
import pytest
from openlia.reports.validator import (
    ReportValidationError,
    validate_report_payload,
)


def _good() -> dict:
    return {
        "schema_version": "1.0",
        "department": "equity_research",
        "generated_at": "2026-04-11T09:30:00Z",
        "cover": {
            "title": "Apple Inc.",
            "subtitle": "Q1 2026",
            "ticker": "AAPL",
            "tagline": "Strong quarter.",
        },
        "sections": [
            {
                "id": "fin",
                "title": "Financial Overview",
                "blocks": [{"type": "text", "content": "Apple reported..."}],
            }
        ],
    }


def test_validator_returns_schema_on_good_input():
    schema = validate_report_payload(_good())
    assert schema.cover.ticker == "AAPL"


def test_validator_raises_with_path_on_bad_version():
    payload = _good()
    payload["schema_version"] = "999"
    with pytest.raises(ReportValidationError) as exc:
        validate_report_payload(payload)
    assert any("schema_version" in p for p, _ in exc.value.errors)


def test_validator_raises_on_unknown_block_type():
    payload = _good()
    payload["sections"][0]["blocks"] = [{"type": "movie", "url": "nope"}]
    with pytest.raises(ReportValidationError) as exc:
        validate_report_payload(payload)
    assert any("blocks" in p for p, _ in exc.value.errors)


def test_validator_rejects_extra_fields():
    payload = _good()
    payload["cover"]["extra_key"] = "no"
    with pytest.raises(ReportValidationError):
        validate_report_payload(payload)
```

- [ ] **Step 2: Run the test and confirm it fails**

Run: `uv run pytest packages/core/tests/reports/test_validator.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'openlia.reports.validator'`.

- [ ] **Step 3: Write the module**

```python
# packages/core/src/openlia/reports/validator.py
"""Validation wrapper around ``ReportSchema`` that surfaces errors with
dotted paths suitable for logging and LLM feedback."""

from __future__ import annotations

from typing import Any

from pydantic import ValidationError

from openlia.reports.schema import ReportSchema


class ReportValidationError(ValueError):
    """Raised when a raw report payload cannot be coerced into ``ReportSchema``."""

    def __init__(self, errors: list[tuple[str, str]]) -> None:
        self.errors = errors
        summary = "; ".join(f"{p}: {m}" for p, m in errors[:5])
        super().__init__(f"Report payload failed validation: {summary}")


def validate_report_payload(payload: dict[str, Any]) -> ReportSchema:
    try:
        return ReportSchema.model_validate(payload)
    except ValidationError as exc:
        collected: list[tuple[str, str]] = []
        for err in exc.errors():
            path = ".".join(str(loc) for loc in err["loc"])
            collected.append((path, err["msg"]))
        raise ReportValidationError(collected) from exc
```

- [ ] **Step 4: Run the test and confirm it passes**

Run: `uv run pytest packages/core/tests/reports/test_validator.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/reports/validator.py \
        packages/core/tests/reports/test_validator.py
git commit -m "feat(reports): add report payload validator"
```

---

### Task 3: Core — Report assembler

Takes the LLM's raw output (a dict that fills the framework template) and produces a validated `ReportSchema`. Responsibilities:
1. Strip `instructions` fields anywhere in the tree.
2. Strip any LLM-supplied `page_furniture`.
3. Attach server-supplied `page_furniture`.
4. Ensure `schema_version`, `department`, `generated_at`.
5. Delegate to `validate_report_payload` to fail loudly on structural problems.

**Files:**
- Create: `packages/core/src/openlia/reports/assembler.py`
- Test: `packages/core/tests/reports/test_assembler.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/reports/test_assembler.py
from datetime import datetime, timezone
import pytest

from openlia.reports.assembler import assemble_report, PageFurnitureConfig
from openlia.reports.validator import ReportValidationError


DEFAULT_FURNITURE = PageFurnitureConfig(
    header_left="OpenLIA",
    header_right_by_department={"equity_research": "Equity Research Department"},
    footer_left_fmt="Generated {date}",
    footer_center="Page {page}",
    footer_right="For internal use only",
    disclaimer="This report is AI-generated. Verify before acting.",
)


def _raw() -> dict:
    return {
        "schema_version": "1.0",
        "department": "equity_research",
        "cover": {
            "instructions": "Fill in cover",
            "title": "Apple Inc.",
            "subtitle": "Q1 2026",
            "ticker": "AAPL",
            "tagline": "Strong quarter.",
        },
        "sections": [
            {
                "id": "fin",
                "title": "Financial Overview",
                "instructions": "Cover revenue, margins.",
                "blocks": [{"type": "text", "content": "Apple reported..."}],
            }
        ],
    }


def test_assemble_strips_instructions_and_applies_furniture():
    raw = _raw()
    schema = assemble_report(
        raw,
        department="equity_research",
        furniture=DEFAULT_FURNITURE,
        now=datetime(2026, 4, 11, 9, 30, tzinfo=timezone.utc),
    )
    assert schema.page_furniture is not None
    assert schema.page_furniture.header["right"] == "Equity Research Department"
    assert schema.page_furniture.footer["center"] == "Page {page}"
    assert schema.page_furniture.footer["left"] == "Generated 2026-04-11"
    assert schema.sections[0].title == "Financial Overview"
    assert "instructions" not in schema.sections[0].model_dump()


def test_assemble_overwrites_llm_supplied_furniture():
    raw = _raw()
    raw["page_furniture"] = {
        "header": {"left": "EVIL", "right": "EVIL"},
        "footer": {"left": "EVIL", "center": "EVIL", "right": "EVIL"},
        "disclaimer": "EVIL",
    }
    schema = assemble_report(
        raw,
        department="equity_research",
        furniture=DEFAULT_FURNITURE,
        now=datetime(2026, 4, 11, 9, 30, tzinfo=timezone.utc),
    )
    assert schema.page_furniture.header["left"] == "OpenLIA"
    assert schema.page_furniture.disclaimer.startswith("This report is AI-generated")


def test_assemble_raises_on_invalid_payload():
    raw = _raw()
    raw["cover"].pop("title")
    with pytest.raises(ReportValidationError):
        assemble_report(
            raw,
            department="equity_research",
            furniture=DEFAULT_FURNITURE,
            now=datetime(2026, 4, 11, 9, 30, tzinfo=timezone.utc),
        )


def test_assemble_falls_back_to_default_header_for_unknown_department():
    raw = _raw()
    raw["department"] = "secretary"
    schema = assemble_report(
        raw,
        department="secretary",
        furniture=DEFAULT_FURNITURE,
        now=datetime(2026, 4, 11, tzinfo=timezone.utc),
    )
    assert schema.page_furniture.header["right"] == "OpenLIA Report"
```

- [ ] **Step 2: Run the test and confirm it fails**

Run: `uv run pytest packages/core/tests/reports/test_assembler.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'openlia.reports.assembler'`.

- [ ] **Step 3: Write the module**

```python
# packages/core/src/openlia/reports/assembler.py
"""Assemble a ``ReportSchema`` from an LLM-generated payload.

This module is the only place that knows how to strip ``instructions``
fields, apply server-supplied page furniture, and route the final
payload through the validator. Call sites must never skip it.
"""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from openlia.reports.schema import ReportSchema
from openlia.reports.validator import validate_report_payload


@dataclass(frozen=True)
class PageFurnitureConfig:
    header_left: str
    header_right_by_department: dict[str, str]
    footer_left_fmt: str
    footer_center: str
    footer_right: str
    disclaimer: str
    default_header_right: str = "OpenLIA Report"


def _strip_instructions(node: Any) -> Any:
    if isinstance(node, dict):
        return {k: _strip_instructions(v) for k, v in node.items() if k \!= "instructions"}
    if isinstance(node, list):
        return [_strip_instructions(item) for item in node]
    return node


def _build_furniture(
    config: PageFurnitureConfig,
    department: str,
    now: datetime,
) -> dict[str, Any]:
    date = now.date().isoformat()
    header_right = config.header_right_by_department.get(
        department,
        config.default_header_right,
    )
    return {
        "header": {"left": config.header_left, "right": header_right},
        "footer": {
            "left": config.footer_left_fmt.format(date=date),
            "center": config.footer_center,
            "right": config.footer_right,
        },
        "disclaimer": config.disclaimer,
    }


def assemble_report(
    payload: dict[str, Any],
    *,
    department: str,
    furniture: PageFurnitureConfig,
    now: datetime,
) -> ReportSchema:
    """Convert an LLM-filled framework template into a validated ``ReportSchema``."""

    stripped = _strip_instructions(deepcopy(payload))
    stripped.pop("page_furniture", None)
    stripped["page_furniture"] = _build_furniture(furniture, department, now)
    stripped.setdefault("schema_version", "1.0")
    stripped.setdefault("department", department)
    stripped.setdefault("generated_at", now.isoformat())
    return validate_report_payload(stripped)
```

- [ ] **Step 4: Run the test and confirm it passes**

Run: `uv run pytest packages/core/tests/reports/test_assembler.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/reports/assembler.py \
        packages/core/tests/reports/test_assembler.py
git commit -m "feat(reports): add report assembler with furniture injection"
```

---

### Task 4: Core — Framework loader + move frameworks into the package

The Equity Research / Earnings Update / Morning Briefing frameworks currently live in `planning/frameworks/`. `planning/` is spec territory and must not be shipped. Move the files into `packages/core/src/openlia/reports/frameworks/`, add an `__init__.py`, and build a loader that:
1. Resolves a framework name to its JSON file via `importlib.resources`.
2. Optionally applies user customizations (enabled/disabled sections, reordering, custom sections).
3. Returns a Python dict (no Pydantic — this is the pre-LLM template).

**Files:**
- Create: `packages/core/src/openlia/reports/frameworks/__init__.py`
- Create: `packages/core/src/openlia/reports/frameworks/loader.py`
- Move: `planning/frameworks/stock_initiation_framework.json` -> `packages/core/src/openlia/reports/frameworks/stock_initiation.json`
- Move: `planning/frameworks/stock_initiation_style_guide.md` -> `packages/core/src/openlia/reports/frameworks/stock_initiation_style_guide.md`
- Move: `planning/frameworks/stock_update_framework.json` -> `packages/core/src/openlia/reports/frameworks/stock_update.json`
- Move: `planning/frameworks/stock_update_style_guide.md` -> `packages/core/src/openlia/reports/frameworks/stock_update_style_guide.md`
- Move: `planning/frameworks/sector_research_framework.json` -> `packages/core/src/openlia/reports/frameworks/sector_research.json`
- Move: `planning/frameworks/sector_research_style_guide.md` -> `packages/core/src/openlia/reports/frameworks/sector_research_style_guide.md`
- Move: `planning/frameworks/earnings_update_framework.json` -> `packages/core/src/openlia/reports/frameworks/earnings_update.json`
- Move: `planning/frameworks/earnings_update_style_guide.md` -> `packages/core/src/openlia/reports/frameworks/earnings_update_style_guide.md`
- Move: `planning/frameworks/morning_briefing_framework.json` -> `packages/core/src/openlia/reports/frameworks/morning_briefing.json`
- Move: `planning/frameworks/morning_briefing_style_guide.md` -> `packages/core/src/openlia/reports/frameworks/morning_briefing_style_guide.md`
- Test: `packages/core/tests/reports/test_framework_loader.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/reports/test_framework_loader.py
import pytest

from openlia.reports.frameworks.loader import (
    FrameworkNotFoundError,
    load_framework,
    load_style_guide,
    CustomizationOptions,
)


def test_load_known_framework_returns_dict_with_sections():
    fw = load_framework("stock_initiation")
    assert isinstance(fw, dict)
    assert "sections" in fw
    assert isinstance(fw["sections"], list)
    assert len(fw["sections"]) >= 1


def test_load_unknown_framework_raises():
    with pytest.raises(FrameworkNotFoundError):
        load_framework("nonexistent_framework")


def test_load_style_guide_returns_markdown_string():
    s = load_style_guide("stock_initiation")
    assert isinstance(s, str)
    assert len(s) > 0


def test_customization_disables_sections():
    fw = load_framework(
        "stock_initiation",
        customizations=CustomizationOptions(disabled_section_ids={"financial_overview"}),
    )
    ids = {s["id"] for s in fw["sections"]}
    assert "financial_overview" not in ids


def test_customization_reorders_sections():
    fw = load_framework("stock_initiation")
    first_id = fw["sections"][0]["id"]
    reordered = load_framework(
        "stock_initiation",
        customizations=CustomizationOptions(
            section_order=[first_id],
        ),
    )
    assert reordered["sections"][0]["id"] == first_id
    assert len(reordered["sections"]) == 1


def test_custom_sections_are_appended():
    custom = {
        "id": "my_section",
        "title": "My Section",
        "instructions": "Custom instructions",
        "blocks": [],
    }
    fw = load_framework(
        "stock_initiation",
        customizations=CustomizationOptions(custom_sections=[custom]),
    )
    ids = [s["id"] for s in fw["sections"]]
    assert ids[-1] == "my_section"
```

- [ ] **Step 2: Run the test and confirm it fails**

Run: `uv run pytest packages/core/tests/reports/test_framework_loader.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'openlia.reports.frameworks'`.

- [ ] **Step 3: Move framework files**

Run:

```bash
mkdir -p packages/core/src/openlia/reports/frameworks
git mv planning/frameworks/stock_initiation_framework.json packages/core/src/openlia/reports/frameworks/stock_initiation.json
git mv planning/frameworks/stock_initiation_style_guide.md packages/core/src/openlia/reports/frameworks/stock_initiation_style_guide.md
git mv planning/frameworks/stock_update_framework.json packages/core/src/openlia/reports/frameworks/stock_update.json
git mv planning/frameworks/stock_update_style_guide.md packages/core/src/openlia/reports/frameworks/stock_update_style_guide.md
git mv planning/frameworks/sector_research_framework.json packages/core/src/openlia/reports/frameworks/sector_research.json
git mv planning/frameworks/sector_research_style_guide.md packages/core/src/openlia/reports/frameworks/sector_research_style_guide.md
git mv planning/frameworks/earnings_update_framework.json packages/core/src/openlia/reports/frameworks/earnings_update.json
git mv planning/frameworks/earnings_update_style_guide.md packages/core/src/openlia/reports/frameworks/earnings_update_style_guide.md
git mv planning/frameworks/morning_briefing_framework.json packages/core/src/openlia/reports/frameworks/morning_briefing.json
git mv planning/frameworks/morning_briefing_style_guide.md packages/core/src/openlia/reports/frameworks/morning_briefing_style_guide.md
rmdir planning/frameworks
```

- [ ] **Step 4: Write the loader**

```python
# packages/core/src/openlia/reports/frameworks/__init__.py
from openlia.reports.frameworks.loader import (
    CustomizationOptions,
    FrameworkNotFoundError,
    load_framework,
    load_style_guide,
)

__all__ = [
    "CustomizationOptions",
    "FrameworkNotFoundError",
    "load_framework",
    "load_style_guide",
]
```

```python
# packages/core/src/openlia/reports/frameworks/loader.py
"""Load per-department report framework templates from package resources."""

from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import dataclass, field
from importlib import resources
from typing import Any

_PACKAGE = "openlia.reports.frameworks"


class FrameworkNotFoundError(FileNotFoundError):
    """Raised when a framework name does not map to a shipped JSON file."""


@dataclass(frozen=True)
class CustomizationOptions:
    disabled_section_ids: frozenset[str] = field(default_factory=frozenset)
    section_order: tuple[str, ...] | list[str] | None = None
    custom_sections: tuple[dict[str, Any], ...] | list[dict[str, Any]] = field(default_factory=tuple)


def _read_resource(relative_name: str) -> str:
    try:
        return resources.files(_PACKAGE).joinpath(relative_name).read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise FrameworkNotFoundError(str(exc)) from exc


def load_framework(
    name: str,
    *,
    customizations: CustomizationOptions | None = None,
) -> dict[str, Any]:
    raw = _read_resource(f"{name}.json")
    data = json.loads(raw)
    if customizations is None:
        return data
    sections = list(data.get("sections", []))
    if customizations.disabled_section_ids:
        sections = [s for s in sections if s.get("id") not in customizations.disabled_section_ids]
    if customizations.section_order:
        order = list(customizations.section_order)
        by_id = {s.get("id"): s for s in sections}
        sections = [deepcopy(by_id[i]) for i in order if i in by_id]
    for extra in customizations.custom_sections:
        sections.append(deepcopy(extra))
    data["sections"] = sections
    return data


def load_style_guide(name: str) -> str:
    return _read_resource(f"{name}_style_guide.md")
```

- [ ] **Step 5: Run tests and confirm they pass**

Run: `uv run pytest packages/core/tests/reports/test_framework_loader.py -v`
Expected: all pass.

- [ ] **Step 6: Update pyproject to ship framework resources**

Ensure `packages/core/pyproject.toml` includes the frameworks directory as package data. Inspect the file:

Run: `grep -n 'package-data\|include-package-data\|packages' packages/core/pyproject.toml`

If the project uses `hatchling` (default from Phase 0), add under `[tool.hatch.build.targets.wheel]`:

```toml
[tool.hatch.build.targets.wheel]
packages = ["src/openlia"]
force-include = {"src/openlia/reports/frameworks" = "openlia/reports/frameworks"}
```

If the project uses `setuptools`, add under `[tool.setuptools.package-data]`:

```toml
[tool.setuptools.package-data]
"openlia.reports.frameworks" = ["*.json", "*.md"]
```

Build the wheel to confirm the data is packaged:

Run: `uv build packages/core && unzip -l packages/core/dist/openlia_core-*.whl | grep frameworks | head`
Expected: at least `stock_initiation.json`, `stock_initiation_style_guide.md`, and three other framework pairs appear in the listing.

- [ ] **Step 7: Commit**

```bash
git add packages/core/src/openlia/reports/frameworks \
        packages/core/tests/reports/test_framework_loader.py \
        packages/core/pyproject.toml \
        planning/frameworks
git commit -m "feat(reports): move frameworks into core package and add loader"
```

---

### Task 5: Core — Secretary prompt + Department class

The Secretary is a chat-only department. It needs:
- A prompt file (`packages/core/src/openlia/prompts/secretary.yaml`) with system + user templates, allowed data-tool names, and a `suggest_redirect` tool declaration.
- A `SecretaryDepartment` class that `ChatRunner` (from Plan 5) can consult for: prompt name, tier (Everyday), data requirement list, and extra tools (just `suggest_redirect` for v1).

**Files:**
- Create: `packages/core/src/openlia/prompts/__init__.py` (marker only)
- Create: `packages/core/src/openlia/prompts/secretary.yaml`
- Create: `packages/core/src/openlia/departments/__init__.py`
- Create: `packages/core/src/openlia/departments/base.py`
- Create: `packages/core/src/openlia/departments/secretary.py`
- Test: `packages/core/tests/departments/test_secretary.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/departments/test_secretary.py
from openlia.departments.secretary import SecretaryDepartment


def test_secretary_identifies_itself():
    d = SecretaryDepartment()
    assert d.name == "secretary"
    assert d.display_name == "Secretary"
    assert d.prompt_name == "secretary"


def test_secretary_uses_everyday_tier():
    assert SecretaryDepartment().tier == "everyday"


def test_secretary_declares_basic_data_requirements():
    reqs = SecretaryDepartment().data_requirement_types
    assert "stock_quote" in reqs
    assert "company_profile" in reqs


def test_secretary_advanced_requirements_are_soft():
    soft = SecretaryDepartment().optional_requirement_types
    assert "company_news" in soft
    assert "historical_prices" in soft
    assert "economic_events" in soft


def test_secretary_exposes_suggest_redirect_tool():
    tools = SecretaryDepartment().extra_tools
    names = {t["name"] for t in tools}
    assert "suggest_redirect" in names
    schema = next(t for t in tools if t["name"] == "suggest_redirect")
    required = set(schema["parameters"]["required"])
    assert {"department", "reason"}.issubset(required)
    props = schema["parameters"]["properties"]
    enum = set(props["department"]["enum"])
    assert {
        "equity_research",
        "earnings_update",
        "morning_briefing",
        "retail_sentiment",
        "macro_research",
        "portfolio",
    }.issubset(enum)


def test_prompt_file_loads_system_and_user_sections():
    from pathlib import Path
    import yaml

    path = (
        Path(__file__).resolve().parents[2]
        / "src/openlia/prompts/secretary.yaml"
    )
    content = yaml.safe_load(path.read_text())
    assert "system" in content
    assert "user" in content
    assert "suggest_redirect" in content["system"]
```

- [ ] **Step 2: Run the test and confirm it fails**

Run: `uv run pytest packages/core/tests/departments/test_secretary.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'openlia.departments'`.

- [ ] **Step 3: Write the prompt file**

```yaml
# packages/core/src/openlia/prompts/secretary.yaml
system: |
  You are OpenLIA Secretary — the general-purpose assistant for a self-hosted
  AI investor assistant. Your job is to answer quick questions, look up market
  data on demand, explain product features, and redirect the user to a
  specialist department when the task clearly needs one.

  Behave like a helpful, concise executive assistant:
  - Prefer short answers. No filler.
  - When a user asks for real-time market data (price, volume, change), call
    the `stock_quote` tool. When they ask for a company overview, call
    `company_profile`. Pull news with `company_news`, price history with
    `historical_prices`, and upcoming macro releases with `economic_events`.
  - If a request clearly belongs to a specialist department (full equity
    research report, earnings analysis, macro dashboard, retail sentiment
    check, morning briefing, portfolio management), call the
    `suggest_redirect` tool instead of attempting the full task. Always
    include a one-sentence `reason` the user would find helpful. If the user
    named a ticker or topic, include it as `prefill`.
  - Never invent numbers. If a tool call fails or returns nothing, say so.
  - Plain Markdown output only. No HTML. No tables with more than 6 rows —
    use a sentence summary if the data is larger.

user: |
  {{ message }}
```

- [ ] **Step 4: Write the department base class**

```python
# packages/core/src/openlia/departments/__init__.py
from openlia.departments.base import Department
from openlia.departments.secretary import SecretaryDepartment

__all__ = ["Department", "SecretaryDepartment"]
```

```python
# packages/core/src/openlia/departments/base.py
"""Minimal Department protocol consulted by ChatRunner and ReportRunner.

Plan 5 expects every department to expose its prompt name, preferred
tier, data requirement types, and any extra LLM tools. Keeping this
surface tiny avoids coupling the runtime to department-specific code.
"""

from __future__ import annotations

from typing import Any, Literal, Protocol, runtime_checkable


Tier = Literal["thinking", "everyday", "quick"]


@runtime_checkable
class Department(Protocol):
    name: str
    display_name: str
    prompt_name: str
    tier: Tier
    data_requirement_types: tuple[str, ...]
    optional_requirement_types: tuple[str, ...]
    extra_tools: tuple[dict[str, Any], ...]
```

- [ ] **Step 5: Write the Secretary department**

```python
# packages/core/src/openlia/departments/secretary.py
"""Secretary — general-purpose chat department."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from openlia.departments.base import Tier


_SUGGEST_REDIRECT_TOOL: dict[str, Any] = {
    "name": "suggest_redirect",
    "description": (
        "Suggest that the user move to a specialist department for tasks "
        "that need a full report, dashboard, or automated monitoring."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "department": {
                "type": "string",
                "enum": [
                    "equity_research",
                    "earnings_update",
                    "morning_briefing",
                    "retail_sentiment",
                    "macro_research",
                    "portfolio",
                ],
            },
            "reason": {
                "type": "string",
                "description": "One short sentence explaining why this department fits.",
            },
            "prefill": {
                "type": "string",
                "description": "Optional payload to preload (usually a ticker).",
            },
        },
        "required": ["department", "reason"],
        "additionalProperties": False,
    },
}


@dataclass(frozen=True)
class SecretaryDepartment:
    name: str = "secretary"
    display_name: str = "Secretary"
    prompt_name: str = "secretary"
    tier: Tier = "everyday"
    data_requirement_types: tuple[str, ...] = (
        "stock_quote",
        "company_profile",
    )
    optional_requirement_types: tuple[str, ...] = (
        "company_news",
        "historical_prices",
        "economic_events",
    )
    extra_tools: tuple[dict[str, Any], ...] = (
        _SUGGEST_REDIRECT_TOOL,
    )
```

- [ ] **Step 6: Run tests to confirm they pass**

Run: `uv run pytest packages/core/tests/departments/test_secretary.py -v`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add packages/core/src/openlia/prompts/__init__.py \
        packages/core/src/openlia/prompts/secretary.yaml \
        packages/core/src/openlia/departments \
        packages/core/tests/departments
git commit -m "feat(secretary): add prompt, department class, and suggest_redirect tool"
```

---

### Task 6: Server — Report store service

Thin wrapper around the `reports` SQLAlchemy model from Plan 1A. Two methods:
1. `get_report(session, report_id, user_id)` → `ReportSchema` or raise `ReportNotFoundError`.
2. `create_report(session, *, user_id, department, mode, schema)` → new row, returns the `report_id` (UUID string).

**Files:**
- Create: `packages/server/src/openlia_server/services/report_store.py`
- Test: `packages/server/tests/services/test_report_store.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/services/test_report_store.py
from datetime import datetime, timezone
import pytest

from openlia.reports.schema import (
    Cover,
    Metric,
    PageFurniture,
    ReportSchema,
    Section,
    TextBlock,
)
from openlia_server.services.report_store import (
    ReportNotFoundError,
    create_report,
    get_report,
)


def _sample_schema() -> ReportSchema:
    return ReportSchema(
        schema_version="1.0",
        department="equity_research",
        generated_at=datetime(2026, 4, 11, tzinfo=timezone.utc),
        page_furniture=PageFurniture(
            header={"left": "OpenLIA", "right": "ER"},
            footer={"left": "Gen", "center": "Page {page}", "right": "Internal"},
            disclaimer="Not advice.",
        ),
        cover=Cover(
            title="Apple Inc.",
            subtitle="Q1 2026",
            ticker="AAPL",
            tagline="Strong quarter.",
            key_metrics=[Metric(label="P", value="$198")],
        ),
        sections=[
            Section(
                id="fin",
                title="Financial Overview",
                blocks=[TextBlock(type="text", content="Apple reported...")],
            )
        ],
    )


def test_create_then_get_roundtrip(db_session, seeded_user):
    schema = _sample_schema()
    report_id = create_report(
        db_session,
        user_id=seeded_user.id,
        department="equity_research",
        mode="initiation",
        schema=schema,
    )
    assert isinstance(report_id, str) and len(report_id) >= 10

    loaded = get_report(db_session, report_id=report_id, user_id=seeded_user.id)
    assert loaded.cover.ticker == "AAPL"
    assert loaded.sections[0].title == "Financial Overview"


def test_get_report_raises_when_missing(db_session, seeded_user):
    with pytest.raises(ReportNotFoundError):
        get_report(db_session, report_id="does-not-exist", user_id=seeded_user.id)


def test_get_report_scoped_to_owner(db_session, seeded_user, other_user):
    schema = _sample_schema()
    report_id = create_report(
        db_session,
        user_id=seeded_user.id,
        department="equity_research",
        mode="initiation",
        schema=schema,
    )
    with pytest.raises(ReportNotFoundError):
        get_report(db_session, report_id=report_id, user_id=other_user.id)
```

- [ ] **Step 2: Run the test and confirm it fails**

Run: `uv run pytest packages/server/tests/services/test_report_store.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'openlia_server.services.report_store'`.

- [ ] **Step 3: Write the service**

```python
# packages/server/src/openlia_server/services/report_store.py
"""Read/write the ``reports`` table as ``ReportSchema`` values."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from openlia.reports.schema import ReportSchema
from openlia.reports.validator import validate_report_payload
from openlia_server.db.models import Report


class ReportNotFoundError(LookupError):
    """Raised when a report id does not exist for the requesting user."""


def get_report(session: Session, *, report_id: str, user_id: str) -> ReportSchema:
    row = session.execute(
        select(Report).where(Report.id == report_id, Report.user_id == user_id)
    ).scalar_one_or_none()
    if row is None:
        raise ReportNotFoundError(report_id)
    return validate_report_payload(row.schema_json)


def create_report(
    session: Session,
    *,
    user_id: str,
    department: str,
    mode: str,
    schema: ReportSchema,
) -> str:
    report_id = str(uuid.uuid4())
    row = Report(
        id=report_id,
        user_id=user_id,
        department=department,
        mode=mode,
        schema_json=schema.model_dump(mode="json"),
        generated_at=schema.generated_at,
        status="complete",
    )
    session.add(row)
    session.flush()
    return report_id
```

- [ ] **Step 4: Run the test and confirm it passes**

Run: `uv run pytest packages/server/tests/services/test_report_store.py -v`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/services/report_store.py \
        packages/server/tests/services/test_report_store.py
git commit -m "feat(reports): add report store service"
```

---

### Task 7: Server — Playwright PDF export service

One shared `BrowserLauncher` per process, lazily initialised. `export_report_pdf(report_id, html)` opens a `BrowserContext`, loads a data URL, and returns PDF bytes. A `shutdown()` coroutine is wired into FastAPI's lifespan.

**Files:**
- Create: `packages/server/src/openlia_server/services/report_export.py`
- Test: `packages/server/tests/services/test_report_export.py`
- Modify: `packages/server/src/openlia_server/app.py` (register lifespan hook)

- [ ] **Step 1: Install the Playwright Python bindings and browser**

Run:

```bash
uv add --package openlia playwright
uv run playwright install chromium
```

Expected: `playwright` appears in `packages/server/pyproject.toml`; browser binaries land under `~/.cache/ms-playwright/`.

- [ ] **Step 2: Write the failing test**

```python
# packages/server/tests/services/test_report_export.py
import pytest

from openlia_server.services.report_export import (
    BrowserLauncher,
    export_report_pdf,
)


@pytest.mark.asyncio
async def test_export_small_html_produces_pdf_bytes():
    launcher = BrowserLauncher()
    try:
        html = (
            "<html><head><title>Hello</title>"
            "<style>@page{size:A4;margin:20mm}body{font:15px Inter}</style>"
            "</head><body><h1>Apple Q1 2026</h1>"
            "<p>Revenue 124.3B, up 31.1%.</p></body></html>"
        )
        data = await export_report_pdf(launcher, html)
        assert isinstance(data, bytes)
        assert data.startswith(b"%PDF-")
        assert len(data) > 2000
    finally:
        await launcher.shutdown()


@pytest.mark.asyncio
async def test_shutdown_is_idempotent():
    launcher = BrowserLauncher()
    await launcher.shutdown()
    await launcher.shutdown()
```

- [ ] **Step 3: Run the test and confirm it fails**

Run: `uv run pytest packages/server/tests/services/test_report_export.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'openlia_server.services.report_export'`.

- [ ] **Step 4: Write the service**

```python
# packages/server/src/openlia_server/services/report_export.py
"""Playwright-backed HTML-to-PDF export for rendered reports.

One :class:`BrowserLauncher` is created per FastAPI process. It lazily
starts Chromium on first use and reuses the browser across exports.
"""

from __future__ import annotations

import asyncio
from typing import Any

from playwright.async_api import Browser, Playwright, async_playwright


class BrowserLauncher:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._closed = False

    async def browser(self) -> Browser:
        async with self._lock:
            if self._closed:
                raise RuntimeError("BrowserLauncher has been shut down")
            if self._browser is None:
                self._playwright = await async_playwright().start()
                self._browser = await self._playwright.chromium.launch(headless=True)
            return self._browser

    async def shutdown(self) -> None:
        async with self._lock:
            if self._closed:
                return
            self._closed = True
            if self._browser is not None:
                await self._browser.close()
                self._browser = None
            if self._playwright is not None:
                await self._playwright.stop()
                self._playwright = None


async def export_report_pdf(
    launcher: BrowserLauncher,
    html: str,
    *,
    header_html: str | None = None,
    footer_html: str | None = None,
) -> bytes:
    browser = await launcher.browser()
    context = await browser.new_context()
    try:
        page = await context.new_page()
        await page.set_content(html, wait_until="networkidle")
        kwargs: dict[str, Any] = {
            "format": "A4",
            "margin": {"top": "20mm", "bottom": "25mm", "left": "20mm", "right": "20mm"},
            "print_background": True,
        }
        if header_html or footer_html:
            kwargs["display_header_footer"] = True
            if header_html:
                kwargs["header_template"] = header_html
            if footer_html:
                kwargs["footer_template"] = footer_html
        return await page.pdf(**kwargs)
    finally:
        await context.close()
```

- [ ] **Step 5: Run the test and confirm it passes**

Run: `uv run pytest packages/server/tests/services/test_report_export.py -v`
Expected: both pass. (First run takes ~5 s while Chromium boots.)

- [ ] **Step 6: Wire lifespan shutdown in app.py**

In `packages/server/src/openlia_server/app.py`, add to the lifespan context manager (or create one if missing):

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI

from openlia_server.services.report_export import BrowserLauncher


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.browser_launcher = BrowserLauncher()
    try:
        yield
    finally:
        await app.state.browser_launcher.shutdown()


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan, title="OpenLIA")
    # existing route registration continues below
    return app
```

- [ ] **Step 7: Commit**

```bash
git add packages/server/src/openlia_server/services/report_export.py \
        packages/server/tests/services/test_report_export.py \
        packages/server/src/openlia_server/app.py \
        packages/server/pyproject.toml \
        uv.lock
git commit -m "feat(reports): add Playwright PDF export service with lifespan hook"
```

---

### Task 8: Server — reports routes

Two endpoints, both session-authenticated:
- `GET /api/reports/{report_id}` → `{schema: ReportSchema}` JSON.
- `POST /api/reports/{report_id}/export/pdf` → streaming PDF via `Content-Disposition`. For v1, the route renders HTML by calling a helper that serialises the schema into a minimal HTML skeleton (the rich renderer is the frontend's job, but for PDF we fetch the rendered HTML from the frontend's server-rendered route in a later plan; in v1 the backend sends a basic HTML shell with embedded JSON and a `<script src="/static/report-renderer.js">` placeholder). For this plan we ship the backend route and accept a server-rendered HTML fallback that embeds `schema_json` inside a `<pre>` — enough to prove end-to-end wiring. The richer PDF styling ships in Plan 14.

**Files:**
- Create: `packages/server/src/openlia_server/routes/reports.py`
- Test: `packages/server/tests/routes/test_reports.py`
- Modify: `packages/server/src/openlia_server/app.py` (mount router)

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/routes/test_reports.py
from datetime import datetime, timezone

from openlia.reports.schema import (
    Cover,
    Metric,
    PageFurniture,
    ReportSchema,
    Section,
    TextBlock,
)
from openlia_server.services.report_store import create_report


def _seed_report(db_session, user_id: str) -> str:
    schema = ReportSchema(
        schema_version="1.0",
        department="equity_research",
        generated_at=datetime(2026, 4, 11, tzinfo=timezone.utc),
        page_furniture=PageFurniture(
            header={"left": "OpenLIA", "right": "ER"},
            footer={"left": "Gen", "center": "Page {page}", "right": "Internal"},
            disclaimer="Not advice.",
        ),
        cover=Cover(
            title="Apple Inc.",
            subtitle="Q1 2026",
            ticker="AAPL",
            tagline="Strong.",
            key_metrics=[Metric(label="P", value="$198")],
        ),
        sections=[
            Section(
                id="fin",
                title="Financial Overview",
                blocks=[TextBlock(type="text", content="Apple reported...")],
            )
        ],
    )
    return create_report(
        db_session,
        user_id=user_id,
        department="equity_research",
        mode="initiation",
        schema=schema,
    )


def test_get_report_returns_schema(client_auth, db_session, seeded_user):
    rid = _seed_report(db_session, seeded_user.id)
    db_session.commit()
    r = client_auth.get(f"/api/reports/{rid}")
    assert r.status_code == 200
    body = r.json()
    assert body["schema"]["cover"]["ticker"] == "AAPL"


def test_get_report_404_when_missing(client_auth):
    r = client_auth.get("/api/reports/does-not-exist")
    assert r.status_code == 404


def test_get_report_403_when_other_user(client_auth_other, db_session, seeded_user):
    rid = _seed_report(db_session, seeded_user.id)
    db_session.commit()
    r = client_auth_other.get(f"/api/reports/{rid}")
    assert r.status_code == 404  # owner scoping returns 404, not 403


def test_export_pdf_streams_pdf_bytes(client_auth, db_session, seeded_user):
    rid = _seed_report(db_session, seeded_user.id)
    db_session.commit()
    r = client_auth.post(f"/api/reports/{rid}/export/pdf")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert "attachment" in r.headers["content-disposition"]
    assert r.content[:4] == b"%PDF"


def test_get_report_requires_auth(client):
    r = client.get("/api/reports/anything")
    assert r.status_code == 401
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `uv run pytest packages/server/tests/routes/test_reports.py -v`
Expected: FAIL — routes not registered.

- [ ] **Step 3: Write the routes**

```python
# packages/server/src/openlia_server/routes/reports.py
"""GET /api/reports/{id} and POST /api/reports/{id}/export/pdf."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import Response
from sqlalchemy.orm import Session

from openlia_server.auth import current_user, CurrentUser
from openlia_server.db.session import get_session
from openlia_server.services.report_export import export_report_pdf
from openlia_server.services.report_store import (
    ReportNotFoundError,
    get_report,
)


router = APIRouter(prefix="/api/reports", tags=["reports"])


def _html_shell(title: str, body: str) -> str:
    return (
        "<\!doctype html><html><head>"
        "<meta charset='utf-8'>"
        f"<title>{title}</title>"
        "<style>body{font:14px/1.5 Inter,system-ui;margin:0;padding:48px;color:#1a1a1a}"
        "h1{font-size:28px;font-weight:700;margin:0 0 8px}"
        "h2{font-size:22px;font-weight:600;margin:32px 0 12px}"
        "p{margin:0 0 12px}</style>"
        "</head><body>" + body + "</body></html>"
    )


def _schema_to_basic_html(schema: dict) -> str:
    cover = schema.get("cover", {})
    body = [
        f"<h1>{cover.get('title', 'Report')}</h1>",
        f"<p><em>{cover.get('subtitle', '')}</em></p>",
        f"<p>{cover.get('tagline', '')}</p>",
    ]
    for section in schema.get("sections", []):
        body.append(f"<h2>{section.get('title', '')}</h2>")
        for block in section.get("blocks", []):
            if block.get("type") == "text":
                body.append(f"<p>{block.get('content', '')}</p>")
            else:
                body.append(f"<p><em>[{block.get('type', 'block')}]</em></p>")
    return "".join(body)


@router.get("/{report_id}")
async def read_report(
    report_id: str,
    user: CurrentUser = Depends(current_user),
    session: Session = Depends(get_session),
) -> dict:
    try:
        schema = get_report(session, report_id=report_id, user_id=user.id)
    except ReportNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "report not found") from exc
    return {"schema": schema.model_dump(mode="json")}


@router.post("/{report_id}/export/pdf")
async def export_report_pdf_route(
    report_id: str,
    request: Request,
    user: CurrentUser = Depends(current_user),
    session: Session = Depends(get_session),
) -> Response:
    try:
        schema = get_report(session, report_id=report_id, user_id=user.id)
    except ReportNotFoundError as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "report not found") from exc
    payload = schema.model_dump(mode="json")
    html = _html_shell(
        title=payload["cover"].get("title", "Report"),
        body=_schema_to_basic_html(payload),
    )
    launcher = request.app.state.browser_launcher
    pdf = await export_report_pdf(launcher, html)
    filename = f"report-{report_id}.pdf"
    return Response(
        content=pdf,
        media_type="application/pdf",
        headers={"content-disposition": f'attachment; filename="{filename}"'},
    )
```

- [ ] **Step 4: Mount the router in `app.py`**

Locate the route registration block in `packages/server/src/openlia_server/app.py` and add:

```python
from openlia_server.routes.reports import router as reports_router
app.include_router(reports_router)
```

- [ ] **Step 5: Run the tests and confirm they pass**

Run: `uv run pytest packages/server/tests/routes/test_reports.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/routes/reports.py \
        packages/server/tests/routes/test_reports.py \
        packages/server/src/openlia_server/app.py
git commit -m "feat(reports): add GET /reports/{id} and POST /reports/{id}/export/pdf"
```

---

### Task 9: Server — Secretary chat SSE route

The Secretary chat route is a thin wrapper around `ChatRunner` from Plan 5. The heavy lifting (session persistence, SSE event streaming, tool-call execution, prompt Jinja rendering) is already implemented there — this route just instantiates `ChatRunner` with `SecretaryDepartment` and streams its events.

**Files:**
- Create: `packages/server/src/openlia_server/routes/departments/__init__.py`
- Create: `packages/server/src/openlia_server/routes/departments/secretary.py`
- Test: `packages/server/tests/routes/departments/test_secretary.py`
- Modify: `packages/server/src/openlia_server/app.py` (mount router)

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/routes/departments/test_secretary.py
import json


def _consume_sse(iter_lines) -> list[dict]:
    events: list[dict] = []
    current_data: list[str] = []
    for raw in iter_lines:
        line = raw.decode() if isinstance(raw, bytes) else raw
        if line == "":
            if current_data:
                events.append(json.loads("".join(current_data)))
                current_data = []
            continue
        if line.startswith("data:"):
            current_data.append(line[5:].lstrip())
    return events


def test_secretary_chat_streams_start_token_done(client_auth, fake_llm):
    fake_llm.queue_chat_response("Hello there\!")
    r = client_auth.post(
        "/api/departments/secretary/chat",
        json={"message": "hi"},
        headers={"accept": "text/event-stream"},
    )
    assert r.status_code == 200
    events = _consume_sse(r.iter_lines())
    types = [e["type"] for e in events]
    assert types[0] == "chat.start"
    assert "chat.token" in types
    assert types[-1] == "chat.done"


def test_secretary_chat_emits_tool_call_for_suggest_redirect(client_auth, fake_llm):
    fake_llm.queue_tool_call(
        name="suggest_redirect",
        arguments={
            "department": "equity_research",
            "reason": "Full initiation report needed",
            "prefill": "AAPL",
        },
    )
    r = client_auth.post(
        "/api/departments/secretary/chat",
        json={"message": "Do a full AAPL report"},
        headers={"accept": "text/event-stream"},
    )
    events = _consume_sse(r.iter_lines())
    tool_event = next(e for e in events if e["type"] == "chat.tool_call.result")
    assert tool_event["tool_name"] == "suggest_redirect"
    assert tool_event["result"]["department"] == "equity_research"


def test_secretary_chat_requires_auth(client):
    r = client.post(
        "/api/departments/secretary/chat",
        json={"message": "hi"},
    )
    assert r.status_code == 401
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `uv run pytest packages/server/tests/routes/departments/test_secretary.py -v`
Expected: FAIL — route not registered.

- [ ] **Step 3: Write the route**

```python
# packages/server/src/openlia_server/routes/departments/__init__.py
```

```python
# packages/server/src/openlia_server/routes/departments/secretary.py
"""SSE chat endpoint for the Secretary department."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from openlia.departments.secretary import SecretaryDepartment
from openlia_server.auth import current_user, CurrentUser
from openlia_server.db.session import get_session
from openlia_server.runtime.chat import ChatRunner, sse_stream


router = APIRouter(prefix="/api/departments/secretary", tags=["secretary"])


class SecretaryChatRequest(BaseModel):
    message: str
    session_id: str | None = None


@router.post("/chat")
async def secretary_chat(
    payload: SecretaryChatRequest,
    request: Request,
    user: CurrentUser = Depends(current_user),
    session: Session = Depends(get_session),
) -> StreamingResponse:
    runner = ChatRunner(
        department=SecretaryDepartment(),
        db_session=session,
        user=user,
    )
    stream = runner.run(
        message=payload.message,
        session_id=payload.session_id,
        client_disconnected=request.is_disconnected,
    )
    return StreamingResponse(
        sse_stream(stream),
        media_type="text/event-stream",
        headers={"cache-control": "no-cache", "x-accel-buffering": "no"},
    )
```

- [ ] **Step 4: Mount the router in `app.py`**

```python
from openlia_server.routes.departments.secretary import router as secretary_router
app.include_router(secretary_router)
```

- [ ] **Step 5: Run the tests and confirm they pass**

Run: `uv run pytest packages/server/tests/routes/departments/test_secretary.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/routes/departments \
        packages/server/tests/routes/departments \
        packages/server/src/openlia_server/app.py
git commit -m "feat(secretary): add /api/departments/secretary/chat SSE route"
```

---

### Task 10: Frontend — api/reports.ts + api/secretary.ts

Typed clients mirroring the server contract. `fetchReport` hits the JSON endpoint; `downloadReportPdf` kicks off an `<a download>` to the PDF route; `startSecretaryChat` returns the URL that `useChatStream` opens as an EventSource.

**Files:**
- Create: `frontend/src/api/reports.ts`
- Create: `frontend/src/api/secretary.ts`
- Test: `frontend/src/api/__tests__/reports.test.ts`
- Test: `frontend/src/api/__tests__/secretary.test.ts`

- [ ] **Step 1: Write the failing tests**

```ts
// frontend/src/api/__tests__/reports.test.ts
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { fetchReport, reportPdfUrl } from '../reports';

describe('fetchReport', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('calls /api/reports/{id} and returns the parsed schema', async () => {
    const spy = vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        schema: {
          schema_version: '1.0',
          department: 'equity_research',
          cover: { title: 'Apple Inc.', subtitle: 'Q1', tagline: 't', ticker: 'AAPL' },
          sections: [],
        },
      }),
    } as Response);
    const schema = await fetchReport('abc');
    expect(spy).toHaveBeenCalledWith('/api/reports/abc', { credentials: 'include' });
    expect(schema.cover.ticker).toBe('AAPL');
  });

  it('throws on non-2xx responses', async () => {
    vi.spyOn(global, 'fetch').mockResolvedValue({
      ok: false,
      status: 404,
      statusText: 'not found',
    } as Response);
    await expect(fetchReport('abc')).rejects.toThrow(/404/);
  });
});

describe('reportPdfUrl', () => {
  it('returns the PDF export route', () => {
    expect(reportPdfUrl('abc')).toBe('/api/reports/abc/export/pdf');
  });
});
```

```ts
// frontend/src/api/__tests__/secretary.test.ts
import { describe, it, expect } from 'vitest';
import { secretaryChatUrl } from '../secretary';

describe('secretaryChatUrl', () => {
  it('returns the chat route with no session id', () => {
    expect(secretaryChatUrl()).toBe('/api/departments/secretary/chat');
  });
  it('appends session id as a query parameter', () => {
    expect(secretaryChatUrl('abc-123')).toBe(
      '/api/departments/secretary/chat?session_id=abc-123',
    );
  });
});
```

- [ ] **Step 2: Run and confirm both tests fail**

Run: `cd frontend && npx vitest run src/api/__tests__/reports.test.ts src/api/__tests__/secretary.test.ts`
Expected: FAIL — modules do not exist.

- [ ] **Step 3: Write the clients**

```ts
// frontend/src/api/reports.ts
export interface ReportCover {
  title: string;
  subtitle: string;
  tagline: string;
  ticker?: string | null;
  key_metrics?: { label: string; value: string; delta?: string; delta_direction?: 'up' | 'down' | 'flat' }[];
  stats_panel?: { label: string; value: string }[];
}

export interface ReportSection {
  id: string;
  title: string;
  blocks: unknown[];
}

export interface PageFurniture {
  header: { left: string; right: string };
  footer: { left: string; center: string; right: string };
  disclaimer: string;
}

export interface ReportSchema {
  schema_version: '1.0';
  department: string;
  generated_at?: string;
  page_furniture?: PageFurniture | null;
  cover: ReportCover;
  sections: ReportSection[];
}

export async function fetchReport(reportId: string): Promise<ReportSchema> {
  const res = await fetch(`/api/reports/${reportId}`, { credentials: 'include' });
  if (\!res.ok) {
    throw new Error(`fetchReport failed (${res.status} ${res.statusText ?? ''})`);
  }
  const body = (await res.json()) as { schema: ReportSchema };
  return body.schema;
}

export function reportPdfUrl(reportId: string): string {
  return `/api/reports/${reportId}/export/pdf`;
}
```

```ts
// frontend/src/api/secretary.ts
export function secretaryChatUrl(sessionId?: string): string {
  const base = '/api/departments/secretary/chat';
  return sessionId ? `${base}?session_id=${encodeURIComponent(sessionId)}` : base;
}
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `cd frontend && npx vitest run src/api/__tests__/reports.test.ts src/api/__tests__/secretary.test.ts`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/api/reports.ts \
        frontend/src/api/secretary.ts \
        frontend/src/api/__tests__/reports.test.ts \
        frontend/src/api/__tests__/secretary.test.ts
git commit -m "feat(api): add reports and secretary typed clients"
```

---

### Task 11: Frontend — report theme CSS

Two CSS files — one per color scheme. The `ReportRenderer` toggles between them based on the app theme from Plan 8 (`useTheme()`), except during PDF export when light mode is always used.

**Files:**
- Create: `frontend/src/styles/report/theme-light.css`
- Create: `frontend/src/styles/report/theme-dark.css`
- Modify: `frontend/src/styles/index.css` (import both)

- [ ] **Step 1: Write the light theme**

```css
/* frontend/src/styles/report/theme-light.css */
[data-report-theme='light'] {
  --report-text-primary: #1a1a1a;
  --report-text-secondary: #6b7280;
  --report-text-tertiary: #9ca3af;
  --report-bg: #ffffff;
  --report-bg-elevated: #f9fafb;
  --report-border: #e5e7eb;
  --report-accent: #2563eb;
  --report-positive: #16a34a;
  --report-negative: #dc2626;
  --report-neutral: #6b7280;

  --report-chart-1: #2563eb;
  --report-chart-2: #7c3aed;
  --report-chart-3: #0891b2;
  --report-chart-4: #ea580c;
  --report-chart-5: #4f46e5;
  --report-chart-6: #0d9488;
  --report-chart-7: #b91c1c;
  --report-chart-8: #ca8a04;

  --report-max-width: 780px;
  --report-padding-x: 48px;
  --report-section-gap: 40px;
  --report-block-gap: 24px;
  --report-group-gap: 20px;
  --report-radius-sm: 4px;
  --report-radius-md: 8px;
  --report-radius-lg: 12px;
  --report-font-sans: 'Inter', system-ui, sans-serif;
}
```

- [ ] **Step 2: Write the dark theme**

```css
/* frontend/src/styles/report/theme-dark.css */
[data-report-theme='dark'] {
  --report-text-primary: #f0f0f0;
  --report-text-secondary: #9ca3af;
  --report-text-tertiary: #6b7280;
  --report-bg: #141414;
  --report-bg-elevated: #1e1e1e;
  --report-border: #2e2e2e;
  --report-accent: #3b82f6;
  --report-positive: #22c55e;
  --report-negative: #ef4444;
  --report-neutral: #9ca3af;

  --report-chart-1: #3b82f6;
  --report-chart-2: #8b5cf6;
  --report-chart-3: #06b6d4;
  --report-chart-4: #f97316;
  --report-chart-5: #6366f1;
  --report-chart-6: #14b8a6;
  --report-chart-7: #ef4444;
  --report-chart-8: #eab308;
}
```

- [ ] **Step 3: Import both from the global entry**

In `frontend/src/styles/index.css`, append:

```css
@import './report/theme-light.css';
@import './report/theme-dark.css';
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/styles/report/theme-light.css \
        frontend/src/styles/report/theme-dark.css \
        frontend/src/styles/index.css
git commit -m "feat(report): add light and dark CSS themes"
```

---

### Task 12: Frontend — TextBlock (markdown + inline colored numbers)

Renders a markdown string with `react-markdown` + `remark-gfm`. Adds a post-processing step that wraps signed percentages (`+12.3%`, `-2.1%`) in a `<span>` with a color class.

**Files:**
- Create: `frontend/src/components/report/blocks/TextBlock.tsx`
- Test: `frontend/src/components/report/blocks/__tests__/TextBlock.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/report/blocks/__tests__/TextBlock.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { TextBlock } from '../TextBlock';

describe('TextBlock', () => {
  it('renders markdown paragraphs', () => {
    render(<TextBlock content="Apple **reported** revenue." />);
    expect(screen.getByText(/reported/i).tagName.toLowerCase()).toBe('strong');
  });

  it('renders lists', () => {
    render(<TextBlock content={'- one\n- two'} />);
    expect(screen.getAllByRole('listitem')).toHaveLength(2);
  });

  it('colors positive signed percentages', () => {
    const { container } = render(<TextBlock content="Revenue grew +31.1% YoY." />);
    const span = container.querySelector('.report-number--positive');
    expect(span?.textContent).toBe('+31.1%');
  });

  it('colors negative signed percentages', () => {
    const { container } = render(<TextBlock content="Margins fell -2.3% QoQ." />);
    const span = container.querySelector('.report-number--negative');
    expect(span?.textContent).toBe('-2.3%');
  });
});
```

- [ ] **Step 2: Run the test and confirm it fails**

Run: `cd frontend && npx vitest run src/components/report/blocks/__tests__/TextBlock.test.tsx`
Expected: FAIL — module missing.

- [ ] **Step 3: Write the block**

```tsx
// frontend/src/components/report/blocks/TextBlock.tsx
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { ComponentPropsWithoutRef } from 'react';

export interface TextBlockProps {
  content: string;
}

const SIGNED_PCT = /([+-]\d+(?:\.\d+)?%)/g;

function colorSignedNumbers(text: string): (string | JSX.Element)[] {
  const parts: (string | JSX.Element)[] = [];
  let lastIndex = 0;
  let match: RegExpExecArray | null;
  SIGNED_PCT.lastIndex = 0;
  while ((match = SIGNED_PCT.exec(text)) \!== null) {
    if (match.index > lastIndex) {
      parts.push(text.slice(lastIndex, match.index));
    }
    const value = match[1];
    const cls = value.startsWith('+')
      ? 'report-number--positive'
      : 'report-number--negative';
    parts.push(
      <span key={`${match.index}-${value}`} className={cls}>
        {value}
      </span>,
    );
    lastIndex = match.index + value.length;
  }
  if (lastIndex < text.length) parts.push(text.slice(lastIndex));
  return parts;
}

function renderChildren(children: React.ReactNode): React.ReactNode {
  if (typeof children === 'string') return colorSignedNumbers(children);
  if (Array.isArray(children)) return children.map(renderChildren);
  return children;
}

export function TextBlock({ content }: TextBlockProps) {
  return (
    <div className="report-text">
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          p: ({ children, ...rest }: ComponentPropsWithoutRef<'p'>) => (
            <p {...rest}>{renderChildren(children)}</p>
          ),
          li: ({ children, ...rest }: ComponentPropsWithoutRef<'li'>) => (
            <li {...rest}>{renderChildren(children)}</li>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </div>
  );
}
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `cd frontend && npx vitest run src/components/report/blocks/__tests__/TextBlock.test.tsx`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/report/blocks/TextBlock.tsx \
        frontend/src/components/report/blocks/__tests__/TextBlock.test.tsx
git commit -m "feat(report): add TextBlock with markdown and inline colored percentages"
```

---

### Task 13: Frontend — TableBlock

Table with sorting, optional row-level search, row styles (`default`/`subtotal`/`total`/`header_group`), cell format rules, sparkline cells, and footnotes.

**Files:**
- Create: `frontend/src/components/report/blocks/TableBlock.tsx`
- Test: `frontend/src/components/report/blocks/__tests__/TableBlock.test.tsx`

- [ ] **Step 1: Install TanStack Table**

Run: `cd frontend && npm install @tanstack/react-table`
Expected: dependency added to `package.json`.

- [ ] **Step 2: Write the failing test**

```tsx
// frontend/src/components/report/blocks/__tests__/TableBlock.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen, fireEvent, within } from '@testing-library/react';
import { TableBlock } from '../TableBlock';

const base = {
  type: 'table' as const,
  title: 'Income Statement',
  headers: [
    { key: 'metric', label: 'Metric', align: 'left' as const },
    { key: 'q1_26', label: 'Q1 2026', align: 'right' as const, sortable: true },
    { key: 'yoy', label: 'YoY', align: 'right' as const },
  ],
  rows: [
    { metric: 'Revenue', q1_26: '$124.3B', yoy: '+31.1%', _row_style: 'default' as const },
    { metric: 'Gross Profit', q1_26: '$58.4B', yoy: '+30.6%', _row_style: 'subtotal' as const },
    { metric: 'Net Income', q1_26: '$36.3B', yoy: '+53.8%', _row_style: 'total' as const },
  ],
  cell_format: { yoy: { rule: 'directional' as const } },
  footnotes: ['Source: Company filings'],
  options: {},
};

describe('TableBlock', () => {
  it('renders headers, rows, and footnotes', () => {
    render(<TableBlock {...base} />);
    expect(screen.getByText('Metric')).toBeInTheDocument();
    expect(screen.getByText('Revenue')).toBeInTheDocument();
    expect(screen.getByText('Source: Company filings')).toBeInTheDocument();
  });

  it('applies row styles as classes', () => {
    const { container } = render(<TableBlock {...base} />);
    const rows = container.querySelectorAll('tbody tr');
    expect(rows[1].className).toMatch(/subtotal/);
    expect(rows[2].className).toMatch(/total/);
  });

  it('colors directional cells by sign of the value', () => {
    const { container } = render(<TableBlock {...base} />);
    const yoyCells = container.querySelectorAll('[data-col="yoy"]');
    yoyCells.forEach((c) => expect(c.className).toMatch(/positive/));
  });

  it('sorts by a sortable column on click', () => {
    render(<TableBlock {...base} />);
    const q1Header = screen.getByRole('button', { name: /Q1 2026/i });
    fireEvent.click(q1Header);
    const rows = screen.getAllByRole('row');
    // first row is header; data starts at index 1
    const firstMetric = within(rows[1]).getByText(/Net Income|Revenue|Gross Profit/);
    expect(firstMetric.textContent).toBeDefined();
  });

  it('does not render a search input unless enabled', () => {
    render(<TableBlock {...base} />);
    expect(screen.queryByPlaceholderText(/search/i)).toBeNull();
  });

  it('renders sparkline cells when a header marks the column as sparkline', () => {
    const spark = {
      ...base,
      headers: [
        ...base.headers,
        { key: 'trend', label: '5Q', align: 'center' as const, sparkline: true },
      ],
      rows: [
        { metric: 'Revenue', q1_26: '$124.3B', yoy: '+31.1%', trend: [1, 2, 3, 4, 5] },
      ],
    };
    const { container } = render(<TableBlock {...spark} />);
    expect(container.querySelector('svg')).toBeTruthy();
  });
});
```

- [ ] **Step 3: Run the test and confirm it fails**

Run: `cd frontend && npx vitest run src/components/report/blocks/__tests__/TableBlock.test.tsx`
Expected: FAIL — module missing.

- [ ] **Step 4: Write the component**

```tsx
// frontend/src/components/report/blocks/TableBlock.tsx
import { useMemo, useState } from 'react';
import {
  createColumnHelper,
  flexRender,
  getCoreRowModel,
  getSortedRowModel,
  useReactTable,
  type SortingState,
} from '@tanstack/react-table';

type Align = 'left' | 'center' | 'right';
type RowStyle = 'default' | 'subtotal' | 'total' | 'header_group';
type FormatRule = 'negative' | 'positive' | 'directional' | 'bold' | 'muted';

export interface TableBlockHeader {
  key: string;
  label: string;
  align?: Align;
  sortable?: boolean;
  sparkline?: boolean;
}

export interface TableBlockProps {
  type: 'table';
  title: string;
  headers: TableBlockHeader[];
  rows: (Record<string, unknown> & { _row_style?: RowStyle })[];
  cell_format?: Record<string, { rule: FormatRule }>;
  footnotes?: string[];
  options?: Record<string, unknown>;
}

function isNegativeString(s: string): boolean {
  const trimmed = s.trim();
  if (trimmed.startsWith('-')) return true;
  if (trimmed.startsWith('(') && trimmed.endsWith(')')) return true;
  return false;
}

function isPositiveString(s: string): boolean {
  return s.trim().startsWith('+');
}

function formatClass(value: unknown, rule: FormatRule): string {
  const text = String(value ?? '');
  switch (rule) {
    case 'negative':
      return isNegativeString(text) ? 'report-cell--negative' : '';
    case 'positive':
      return isPositiveString(text) ? 'report-cell--positive' : '';
    case 'directional':
      if (isPositiveString(text)) return 'report-cell--positive';
      if (isNegativeString(text)) return 'report-cell--negative';
      return 'report-cell--neutral';
    case 'bold':
      return 'report-cell--bold';
    case 'muted':
      return 'report-cell--muted';
  }
}

function Sparkline({ values }: { values: number[] }) {
  if (values.length === 0) return null;
  const w = 60;
  const h = 20;
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || 1;
  const stepX = values.length > 1 ? w / (values.length - 1) : 0;
  const points = values
    .map((v, i) => `${i * stepX},${h - ((v - min) / span) * h}`)
    .join(' ');
  const up = values[values.length - 1] >= values[0];
  const stroke = up ? 'var(--report-positive)' : 'var(--report-negative)';
  return (
    <svg width={w} height={h} aria-hidden>
      <polyline fill="none" stroke={stroke} strokeWidth={1.5} points={points} />
    </svg>
  );
}

export function TableBlock(props: TableBlockProps) {
  const { headers, rows, cell_format = {}, footnotes = [] } = props;
  const [sorting, setSorting] = useState<SortingState>([]);
  const columnHelper = createColumnHelper<Record<string, unknown>>();

  const columns = useMemo(
    () =>
      headers.map((h) =>
        columnHelper.accessor((row) => row[h.key], {
          id: h.key,
          header: h.label,
          enableSorting: Boolean(h.sortable),
          cell: (info) => {
            if (h.sparkline && Array.isArray(info.getValue())) {
              return <Sparkline values={info.getValue() as number[]} />;
            }
            return String(info.getValue() ?? '');
          },
        }),
      ),
    [headers, columnHelper],
  );

  const table = useReactTable({
    data: rows,
    columns,
    state: { sorting },
    onSortingChange: setSorting,
    getCoreRowModel: getCoreRowModel(),
    getSortedRowModel: getSortedRowModel(),
  });

  return (
    <figure className="report-table">
      <figcaption className="report-table__title">{props.title}</figcaption>
      <table>
        <thead>
          {table.getHeaderGroups().map((hg) => (
            <tr key={hg.id}>
              {hg.headers.map((h) => {
                const header = headers.find((x) => x.key === h.column.id);
                const align = header?.align ?? 'left';
                const sortable = Boolean(header?.sortable);
                return (
                  <th
                    key={h.id}
                    style={{ textAlign: align }}
                    className={sortable ? 'report-table__th--sortable' : undefined}
                  >
                    {sortable ? (
                      <button
                        type="button"
                        onClick={h.column.getToggleSortingHandler()}
                      >
                        {flexRender(h.column.columnDef.header, h.getContext())}
                      </button>
                    ) : (
                      flexRender(h.column.columnDef.header, h.getContext())
                    )}
                  </th>
                );
              })}
            </tr>
          ))}
        </thead>
        <tbody>
          {table.getRowModel().rows.map((row) => {
            const style = (row.original as any)._row_style ?? 'default';
            return (
              <tr key={row.id} className={`report-row report-row--${style}`}>
                {row.getVisibleCells().map((cell) => {
                  const header = headers.find((h) => h.key === cell.column.id);
                  const rule = cell_format[cell.column.id]?.rule;
                  const classes = [
                    rule ? formatClass(cell.getValue(), rule) : '',
                  ]
                    .filter(Boolean)
                    .join(' ');
                  return (
                    <td
                      key={cell.id}
                      data-col={cell.column.id}
                      className={classes}
                      style={{ textAlign: header?.align ?? 'left' }}
                    >
                      {flexRender(cell.column.columnDef.cell, cell.getContext())}
                    </td>
                  );
                })}
              </tr>
            );
          })}
        </tbody>
      </table>
      {footnotes.length > 0 ? (
        <ul className="report-table__footnotes">
          {footnotes.map((f, i) => (
            <li key={i}>{f}</li>
          ))}
        </ul>
      ) : null}
    </figure>
  );
}
```

- [ ] **Step 5: Run the tests and confirm they pass**

Run: `cd frontend && npx vitest run src/components/report/blocks/__tests__/TableBlock.test.tsx`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/report/blocks/TableBlock.tsx \
        frontend/src/components/report/blocks/__tests__/TableBlock.test.tsx \
        frontend/package.json frontend/package-lock.json
git commit -m "feat(report): add TableBlock with sort, row styles, sparklines, footnotes"
```

---

### Task 14: Frontend — MetricCardsBlock + KeyFindingBlock + RatingBadgeBlock

Three small but distinct blocks.

**Files:**
- Create: `frontend/src/components/report/blocks/MetricCardsBlock.tsx`
- Create: `frontend/src/components/report/blocks/KeyFindingBlock.tsx`
- Create: `frontend/src/components/report/blocks/RatingBadgeBlock.tsx`
- Test: `frontend/src/components/report/blocks/__tests__/MetricCardsBlock.test.tsx`
- Test: `frontend/src/components/report/blocks/__tests__/KeyFindingBlock.test.tsx`
- Test: `frontend/src/components/report/blocks/__tests__/RatingBadgeBlock.test.tsx`

- [ ] **Step 1: Write the failing tests**

```tsx
// frontend/src/components/report/blocks/__tests__/MetricCardsBlock.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MetricCardsBlock } from '../MetricCardsBlock';

describe('MetricCardsBlock', () => {
  it('renders a card per metric with label, value, and delta', () => {
    render(
      <MetricCardsBlock
        type="metric_cards"
        metrics={[
          { label: 'Revenue', value: '$124.3B', delta: '+31.1%', delta_direction: 'up' },
          { label: 'Net Income', value: '$36.3B', delta: '+53.8%', delta_direction: 'up' },
        ]}
      />,
    );
    expect(screen.getByText('Revenue')).toBeInTheDocument();
    expect(screen.getByText('$124.3B')).toBeInTheDocument();
    expect(screen.getAllByText(/\+\d/)).toHaveLength(2);
  });

  it('applies positive and negative delta classes', () => {
    const { container } = render(
      <MetricCardsBlock
        type="metric_cards"
        metrics={[
          { label: 'Up', value: '10', delta: '+5', delta_direction: 'up' },
          { label: 'Down', value: '10', delta: '-5', delta_direction: 'down' },
        ]}
      />,
    );
    expect(container.querySelector('.metric-card__delta--positive')).toBeTruthy();
    expect(container.querySelector('.metric-card__delta--negative')).toBeTruthy();
  });
});
```

```tsx
// frontend/src/components/report/blocks/__tests__/KeyFindingBlock.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { KeyFindingBlock } from '../KeyFindingBlock';

describe('KeyFindingBlock', () => {
  it('renders markdown content inside a highlighted callout', () => {
    const { container } = render(
      <KeyFindingBlock type="key_finding" content="iPhone **revenue** grew 49% YoY." />,
    );
    expect(container.querySelector('.key-finding')).toBeTruthy();
    expect(screen.getByText(/revenue/i).tagName.toLowerCase()).toBe('strong');
  });
});
```

```tsx
// frontend/src/components/report/blocks/__tests__/RatingBadgeBlock.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { RatingBadgeBlock } from '../RatingBadgeBlock';

describe('RatingBadgeBlock', () => {
  it('renders positive rating with positive class', () => {
    const { container } = render(
      <RatingBadgeBlock type="rating_badge" rating="Overweight" />,
    );
    expect(container.querySelector('.rating-badge--positive')).toBeTruthy();
    expect(screen.getByText('Overweight')).toBeInTheDocument();
  });

  it('renders neutral rating with neutral class', () => {
    const { container } = render(
      <RatingBadgeBlock type="rating_badge" rating="Hold" />,
    );
    expect(container.querySelector('.rating-badge--neutral')).toBeTruthy();
  });

  it('renders negative rating with negative class', () => {
    const { container } = render(
      <RatingBadgeBlock type="rating_badge" rating="Sell" />,
    );
    expect(container.querySelector('.rating-badge--negative')).toBeTruthy();
  });

  it('shows previous rating struck through when provided', () => {
    render(
      <RatingBadgeBlock
        type="rating_badge"
        rating="Overweight"
        previous_rating="Equal Weight"
        change_date="2026-04-11"
      />,
    );
    const prev = screen.getByText('Equal Weight');
    expect(prev.tagName.toLowerCase()).toBe('s');
  });
});
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `cd frontend && npx vitest run src/components/report/blocks/__tests__/MetricCardsBlock.test.tsx src/components/report/blocks/__tests__/KeyFindingBlock.test.tsx src/components/report/blocks/__tests__/RatingBadgeBlock.test.tsx`
Expected: FAIL — modules missing.

- [ ] **Step 3: Write the components**

```tsx
// frontend/src/components/report/blocks/MetricCardsBlock.tsx
export interface Metric {
  label: string;
  value: string;
  delta?: string;
  delta_direction?: 'up' | 'down' | 'flat';
}

export interface MetricCardsBlockProps {
  type: 'metric_cards';
  metrics: Metric[];
}

function deltaClass(direction?: 'up' | 'down' | 'flat'): string {
  if (direction === 'up') return 'metric-card__delta--positive';
  if (direction === 'down') return 'metric-card__delta--negative';
  return 'metric-card__delta--neutral';
}

export function MetricCardsBlock({ metrics }: MetricCardsBlockProps) {
  return (
    <div className="metric-cards">
      {metrics.map((m) => (
        <div key={m.label} className="metric-card">
          <div className="metric-card__label">{m.label}</div>
          <div className="metric-card__value">{m.value}</div>
          {m.delta ? (
            <div className={`metric-card__delta ${deltaClass(m.delta_direction)}`}>
              {m.delta}
            </div>
          ) : null}
        </div>
      ))}
    </div>
  );
}
```

```tsx
// frontend/src/components/report/blocks/KeyFindingBlock.tsx
import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';

export interface KeyFindingBlockProps {
  type: 'key_finding';
  content: string;
}

export function KeyFindingBlock({ content }: KeyFindingBlockProps) {
  return (
    <aside className="key-finding" role="note">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </aside>
  );
}
```

```tsx
// frontend/src/components/report/blocks/RatingBadgeBlock.tsx
const POSITIVE = new Set(['buy', 'overweight', 'strong buy', 'outperform']);
const NEGATIVE = new Set(['sell', 'underweight', 'reduce', 'underperform']);

function ratingClass(rating: string): string {
  const r = rating.trim().toLowerCase();
  if (POSITIVE.has(r)) return 'rating-badge--positive';
  if (NEGATIVE.has(r)) return 'rating-badge--negative';
  return 'rating-badge--neutral';
}

export interface RatingBadgeBlockProps {
  type: 'rating_badge';
  rating: string;
  previous_rating?: string | null;
  change_date?: string | null;
}

export function RatingBadgeBlock({
  rating,
  previous_rating,
  change_date,
}: RatingBadgeBlockProps) {
  return (
    <span className={`rating-badge ${ratingClass(rating)}`}>
      {previous_rating ? <s className="rating-badge__prev">{previous_rating}</s> : null}
      <span className="rating-badge__current">{rating}</span>
      {change_date ? <span className="rating-badge__date">{change_date}</span> : null}
    </span>
  );
}
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `cd frontend && npx vitest run src/components/report/blocks/__tests__/MetricCardsBlock.test.tsx src/components/report/blocks/__tests__/KeyFindingBlock.test.tsx src/components/report/blocks/__tests__/RatingBadgeBlock.test.tsx`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/report/blocks/MetricCardsBlock.tsx \
        frontend/src/components/report/blocks/KeyFindingBlock.tsx \
        frontend/src/components/report/blocks/RatingBadgeBlock.tsx \
        frontend/src/components/report/blocks/__tests__/MetricCardsBlock.test.tsx \
        frontend/src/components/report/blocks/__tests__/KeyFindingBlock.test.tsx \
        frontend/src/components/report/blocks/__tests__/RatingBadgeBlock.test.tsx
git commit -m "feat(report): add MetricCardsBlock, KeyFindingBlock, RatingBadgeBlock"
```

---

### Task 15: Frontend — GroupBlock (height normalization)

Lays out children in `N` CSS-grid columns. Applies height-normalization rules:
- All charts: pass a shared `forcedHeight` prop down (based on tallest child).
- All tables: no normalization.
- Mixed: charts forced to `medium`, tables natural, items top-aligned.

**Files:**
- Create: `frontend/src/components/report/blocks/GroupBlock.tsx`
- Test: `frontend/src/components/report/blocks/__tests__/GroupBlock.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/report/blocks/__tests__/GroupBlock.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { GroupBlock, type GroupChildRenderer } from '../GroupBlock';

const child = (label: string, type: string) => ({ type, _label: label } as any);

const renderer: GroupChildRenderer = (b: any, forced) => (
  <div data-testid={`child-${b._label}`} data-forced-height={forced ?? 'none'}>
    {b.type}
  </div>
);

describe('GroupBlock', () => {
  it('renders children in N columns', () => {
    const { container } = render(
      <GroupBlock
        type="group"
        columns={3}
        blocks={[child('a', 'text'), child('b', 'text'), child('c', 'text')]}
        renderChild={renderer}
      />,
    );
    const grid = container.querySelector('.group-block') as HTMLElement;
    expect(grid.style.gridTemplateColumns).toContain('3');
  });

  it('forces medium chart height when chart and table are mixed', () => {
    render(
      <GroupBlock
        type="group"
        columns={2}
        blocks={[child('chart', 'line_chart'), child('table', 'table')]}
        renderChild={renderer}
      />,
    );
    expect(screen.getByTestId('child-chart').dataset.forcedHeight).toBe('medium');
    expect(screen.getByTestId('child-table').dataset.forcedHeight).toBe('none');
  });

  it('normalizes all charts to the tallest declared height', () => {
    const withOpts = (label: string, height: 'small' | 'medium' | 'tall') => ({
      type: 'bar_chart',
      _label: label,
      options: { height },
    });
    render(
      <GroupBlock
        type="group"
        columns={2}
        blocks={[withOpts('a', 'small'), withOpts('b', 'tall')] as any}
        renderChild={renderer}
      />,
    );
    expect(screen.getByTestId('child-a').dataset.forcedHeight).toBe('tall');
    expect(screen.getByTestId('child-b').dataset.forcedHeight).toBe('tall');
  });

  it('leaves all-tables un-normalized', () => {
    render(
      <GroupBlock
        type="group"
        columns={2}
        blocks={[child('t1', 'table'), child('t2', 'table')]}
        renderChild={renderer}
      />,
    );
    expect(screen.getByTestId('child-t1').dataset.forcedHeight).toBe('none');
    expect(screen.getByTestId('child-t2').dataset.forcedHeight).toBe('none');
  });
});
```

- [ ] **Step 2: Run the test and confirm it fails**

Run: `cd frontend && npx vitest run src/components/report/blocks/__tests__/GroupBlock.test.tsx`
Expected: FAIL — module missing.

- [ ] **Step 3: Write the component**

```tsx
// frontend/src/components/report/blocks/GroupBlock.tsx
import type { ReactNode } from 'react';

const CHART_TYPES = new Set([
  'line_chart',
  'bar_chart',
  'area_chart',
  'pie_chart',
  'candlestick_chart',
  'waterfall_chart',
  'scatter_plot',
  'heatmap',
  'treemap',
  'combo_chart',
]);

export type ForcedHeight = 'small' | 'medium' | 'tall' | null;
export type GroupChildRenderer = (child: any, forcedHeight: ForcedHeight) => ReactNode;

export interface GroupBlockProps {
  type: 'group';
  columns: number;
  blocks: any[];
  renderChild: GroupChildRenderer;
}

function rankHeight(h: string | undefined): number {
  switch (h) {
    case 'tall':
      return 3;
    case 'medium':
      return 2;
    case 'small':
      return 1;
    default:
      return 2;
  }
}

function labelFromRank(rank: number): 'small' | 'medium' | 'tall' {
  if (rank >= 3) return 'tall';
  if (rank <= 1) return 'small';
  return 'medium';
}

function normalizeHeights(blocks: any[]): (ForcedHeight)[] {
  const isChart = blocks.map((b) => CHART_TYPES.has(b.type));
  const anyChart = isChart.some(Boolean);
  const anyTable = blocks.some((b) => b.type === 'table');
  if (anyChart && \!anyTable) {
    const maxRank = Math.max(...blocks.map((b) => rankHeight(b.options?.height)));
    const label = labelFromRank(maxRank);
    return blocks.map((_, i) => (isChart[i] ? label : null));
  }
  if (anyChart && anyTable) {
    return blocks.map((_, i) => (isChart[i] ? 'medium' : null));
  }
  return blocks.map(() => null);
}

export function GroupBlock({ columns, blocks, renderChild }: GroupBlockProps) {
  const forced = normalizeHeights(blocks);
  return (
    <div
      className="group-block"
      style={{
        display: 'grid',
        gridTemplateColumns: `repeat(${columns}, minmax(0, 1fr))`,
        gap: 'var(--report-group-gap, 20px)',
        alignItems: 'flex-start',
      }}
    >
      {blocks.map((b, i) => (
        <div key={i}>{renderChild(b, forced[i])}</div>
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `cd frontend && npx vitest run src/components/report/blocks/__tests__/GroupBlock.test.tsx`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/report/blocks/GroupBlock.tsx \
        frontend/src/components/report/blocks/__tests__/GroupBlock.test.tsx
git commit -m "feat(report): add GroupBlock with height normalization"
```

---

### Task 16: Frontend — ChartFrame + basic chart blocks (line/bar/area/pie)

`ChartFrame` centralizes the title, height-mapping, legend toggle, and theme palette. The four block components convert their schema props into ECharts option objects and render via `echarts-for-react`. No DOM assertions on the chart internals — just structure checks.

**Files:**
- Create: `frontend/src/components/report/charts/ChartFrame.tsx`
- Create: `frontend/src/components/report/charts/LineChartBlock.tsx`
- Create: `frontend/src/components/report/charts/BarChartBlock.tsx`
- Create: `frontend/src/components/report/charts/AreaChartBlock.tsx`
- Create: `frontend/src/components/report/charts/PieChartBlock.tsx`
- Test: `frontend/src/components/report/charts/__tests__/basic_charts.test.tsx`

- [ ] **Step 1: Install ECharts and the React wrapper**

Run: `cd frontend && npm install echarts echarts-for-react`
Expected: both appear in `package.json`.

- [ ] **Step 2: Write the failing tests**

```tsx
// frontend/src/components/report/charts/__tests__/basic_charts.test.tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

vi.mock('echarts-for-react', () => ({
  default: ({ option }: { option: any }) => (
    <div data-testid="echart" data-option={JSON.stringify(option)} />
  ),
}));

import { LineChartBlock } from '../LineChartBlock';
import { BarChartBlock } from '../BarChartBlock';
import { AreaChartBlock } from '../AreaChartBlock';
import { PieChartBlock } from '../PieChartBlock';

describe('LineChartBlock', () => {
  it('renders the title and emits a line series', () => {
    render(
      <LineChartBlock
        type="line_chart"
        title="Gross Margin Trend"
        series={[{ name: 'Margin %', data: [{ x: 'Q1', y: 46.6 }, { x: 'Q2', y: 47.1 }] }]}
      />,
    );
    expect(screen.getByText('Gross Margin Trend')).toBeInTheDocument();
    const opt = JSON.parse(screen.getByTestId('echart').dataset.option\!);
    expect(opt.series[0].type).toBe('line');
    expect(opt.series[0].data).toEqual([46.6, 47.1]);
  });
});

describe('BarChartBlock', () => {
  it('emits a category x-axis and bar series', () => {
    render(
      <BarChartBlock
        type="bar_chart"
        title="Revenue by Segment"
        categories={['iPhone', 'Services']}
        series={[{ name: 'Q1 2026', values: [69.1, 26.3] }]}
      />,
    );
    const opt = JSON.parse(screen.getByTestId('echart').dataset.option\!);
    expect(opt.xAxis.type).toBe('category');
    expect(opt.xAxis.data).toEqual(['iPhone', 'Services']);
    expect(opt.series[0].type).toBe('bar');
  });

  it('supports stacked vertical bars', () => {
    render(
      <BarChartBlock
        type="bar_chart"
        title="t"
        categories={['a']}
        series={[
          { name: 's1', values: [1] },
          { name: 's2', values: [2] },
        ]}
        stacked
      />,
    );
    const opt = JSON.parse(screen.getByTestId('echart').dataset.option\!);
    expect(opt.series.every((s: any) => s.stack === 'total')).toBe(true);
  });
});

describe('AreaChartBlock', () => {
  it('emits a line series with areaStyle', () => {
    render(
      <AreaChartBlock
        type="area_chart"
        title="Revenue Composition"
        series={[{ name: 'iPhone', data: [{ x: 'Q1', y: 1 }] }]}
      />,
    );
    const opt = JSON.parse(screen.getByTestId('echart').dataset.option\!);
    expect(opt.series[0].type).toBe('line');
    expect(opt.series[0].areaStyle).toBeDefined();
  });
});

describe('PieChartBlock', () => {
  it('emits a pie series with segment name/value pairs', () => {
    render(
      <PieChartBlock
        type="pie_chart"
        title="Revenue Mix"
        segments={[
          { label: 'iPhone', value: 69.1 },
          { label: 'Services', value: 26.3 },
        ]}
      />,
    );
    const opt = JSON.parse(screen.getByTestId('echart').dataset.option\!);
    expect(opt.series[0].type).toBe('pie');
    expect(opt.series[0].data).toEqual([
      { name: 'iPhone', value: 69.1 },
      { name: 'Services', value: 26.3 },
    ]);
  });

  it('renders a donut when donut flag is set', () => {
    render(
      <PieChartBlock
        type="pie_chart"
        title="t"
        donut
        segments={[{ label: 'a', value: 1 }]}
      />,
    );
    const opt = JSON.parse(screen.getByTestId('echart').dataset.option\!);
    expect(opt.series[0].radius[0]).not.toBe(0);
  });
});
```

- [ ] **Step 3: Run the tests and confirm they fail**

Run: `cd frontend && npx vitest run src/components/report/charts/__tests__/basic_charts.test.tsx`
Expected: FAIL — modules missing.

- [ ] **Step 4: Write ChartFrame**

```tsx
// frontend/src/components/report/charts/ChartFrame.tsx
import type { ReactNode } from 'react';
import type { ForcedHeight } from '../blocks/GroupBlock';

export type ChartHeight = 'small' | 'medium' | 'tall';

export const CHART_HEIGHT_PX: Record<ChartHeight, number> = {
  small: 200,
  medium: 300,
  tall: 400,
};

export const CHART_PALETTE = [
  'var(--report-chart-1)',
  'var(--report-chart-2)',
  'var(--report-chart-3)',
  'var(--report-chart-4)',
  'var(--report-chart-5)',
  'var(--report-chart-6)',
  'var(--report-chart-7)',
  'var(--report-chart-8)',
];

export interface ChartFrameProps {
  title: string;
  height?: ChartHeight;
  forcedHeight?: ForcedHeight;
  children: ReactNode;
}

export function resolveHeight(
  declared?: ChartHeight,
  forced?: ForcedHeight,
): number {
  const key = (forced ?? declared ?? 'medium') as ChartHeight;
  return CHART_HEIGHT_PX[key] ?? CHART_HEIGHT_PX.medium;
}

export function ChartFrame({ title, height, forcedHeight, children }: ChartFrameProps) {
  const px = resolveHeight(height, forcedHeight);
  return (
    <figure className="report-chart">
      <figcaption className="report-chart__title">{title}</figcaption>
      <div style={{ height: px }}>{children}</div>
    </figure>
  );
}
```

- [ ] **Step 5: Write each chart block**

```tsx
// frontend/src/components/report/charts/LineChartBlock.tsx
import ReactECharts from 'echarts-for-react';
import { ChartFrame, CHART_PALETTE, type ChartHeight } from './ChartFrame';
import type { ForcedHeight } from '../blocks/GroupBlock';

export interface LineSeries {
  name: string;
  data: { x: string | number; y: number }[];
}

export interface LineChartBlockProps {
  type: 'line_chart';
  title: string;
  series: LineSeries[];
  x_label?: string;
  y_label?: string;
  options?: { height?: ChartHeight; show_legend?: boolean; show_grid?: boolean };
  forcedHeight?: ForcedHeight;
}

export function LineChartBlock({
  title,
  series,
  x_label,
  y_label,
  options,
  forcedHeight,
}: LineChartBlockProps) {
  const categories = series[0]?.data.map((d) => d.x) ?? [];
  const option = {
    color: CHART_PALETTE,
    grid: { left: 40, right: 20, top: 30, bottom: 40 },
    tooltip: { trigger: 'axis' },
    legend: { show: options?.show_legend \!== false, bottom: 0 },
    xAxis: { type: 'category', data: categories, name: x_label },
    yAxis: { type: 'value', name: y_label, splitLine: { show: options?.show_grid \!== false } },
    series: series.map((s) => ({
      type: 'line',
      name: s.name,
      smooth: true,
      data: s.data.map((d) => d.y),
    })),
  };
  return (
    <ChartFrame title={title} height={options?.height} forcedHeight={forcedHeight}>
      <ReactECharts option={option} style={{ height: '100%', width: '100%' }} />
    </ChartFrame>
  );
}
```

```tsx
// frontend/src/components/report/charts/BarChartBlock.tsx
import ReactECharts from 'echarts-for-react';
import { ChartFrame, CHART_PALETTE, type ChartHeight } from './ChartFrame';
import type { ForcedHeight } from '../blocks/GroupBlock';

export interface BarSeries {
  name: string;
  values: number[];
}

export interface BarChartBlockProps {
  type: 'bar_chart';
  title: string;
  categories: string[];
  series: BarSeries[];
  orientation?: 'vertical' | 'horizontal';
  stacked?: boolean;
  options?: { height?: ChartHeight; show_legend?: boolean; show_grid?: boolean };
  forcedHeight?: ForcedHeight;
}

export function BarChartBlock({
  title,
  categories,
  series,
  orientation = 'vertical',
  stacked = false,
  options,
  forcedHeight,
}: BarChartBlockProps) {
  const horizontal = orientation === 'horizontal';
  const option = {
    color: CHART_PALETTE,
    grid: { left: 40, right: 20, top: 30, bottom: 40 },
    tooltip: { trigger: 'axis' },
    legend: { show: options?.show_legend \!== false, bottom: 0 },
    xAxis: horizontal
      ? { type: 'value', splitLine: { show: options?.show_grid \!== false } }
      : { type: 'category', data: categories },
    yAxis: horizontal
      ? { type: 'category', data: categories }
      : { type: 'value', splitLine: { show: options?.show_grid \!== false } },
    series: series.map((s) => ({
      type: 'bar',
      name: s.name,
      stack: stacked ? 'total' : undefined,
      data: s.values,
    })),
  };
  return (
    <ChartFrame title={title} height={options?.height} forcedHeight={forcedHeight}>
      <ReactECharts option={option} style={{ height: '100%', width: '100%' }} />
    </ChartFrame>
  );
}
```

```tsx
// frontend/src/components/report/charts/AreaChartBlock.tsx
import ReactECharts from 'echarts-for-react';
import { ChartFrame, CHART_PALETTE, type ChartHeight } from './ChartFrame';
import type { ForcedHeight } from '../blocks/GroupBlock';

export interface AreaSeries {
  name: string;
  data: { x: string | number; y: number }[];
}

export interface AreaChartBlockProps {
  type: 'area_chart';
  title: string;
  series: AreaSeries[];
  stacked?: boolean;
  options?: { height?: ChartHeight; show_legend?: boolean };
  forcedHeight?: ForcedHeight;
}

export function AreaChartBlock({
  title,
  series,
  stacked = false,
  options,
  forcedHeight,
}: AreaChartBlockProps) {
  const categories = series[0]?.data.map((d) => d.x) ?? [];
  const option = {
    color: CHART_PALETTE,
    grid: { left: 40, right: 20, top: 30, bottom: 40 },
    tooltip: { trigger: 'axis' },
    legend: { show: options?.show_legend \!== false, bottom: 0 },
    xAxis: { type: 'category', data: categories },
    yAxis: { type: 'value' },
    series: series.map((s) => ({
      type: 'line',
      name: s.name,
      stack: stacked ? 'total' : undefined,
      areaStyle: {},
      smooth: true,
      data: s.data.map((d) => d.y),
    })),
  };
  return (
    <ChartFrame title={title} height={options?.height} forcedHeight={forcedHeight}>
      <ReactECharts option={option} style={{ height: '100%', width: '100%' }} />
    </ChartFrame>
  );
}
```

```tsx
// frontend/src/components/report/charts/PieChartBlock.tsx
import ReactECharts from 'echarts-for-react';
import { ChartFrame, CHART_PALETTE, type ChartHeight } from './ChartFrame';
import type { ForcedHeight } from '../blocks/GroupBlock';

export interface PieSegment {
  label: string;
  value: number;
}

export interface PieChartBlockProps {
  type: 'pie_chart';
  title: string;
  segments: PieSegment[];
  donut?: boolean;
  options?: { height?: ChartHeight; show_legend?: boolean };
  forcedHeight?: ForcedHeight;
}

export function PieChartBlock({
  title,
  segments,
  donut = false,
  options,
  forcedHeight,
}: PieChartBlockProps) {
  const option = {
    color: CHART_PALETTE,
    tooltip: { trigger: 'item' },
    legend: { show: options?.show_legend \!== false, bottom: 0 },
    series: [
      {
        type: 'pie',
        radius: donut ? ['45%', '70%'] : [0, '70%'],
        data: segments.map((s) => ({ name: s.label, value: s.value })),
      },
    ],
  };
  return (
    <ChartFrame title={title} height={options?.height} forcedHeight={forcedHeight}>
      <ReactECharts option={option} style={{ height: '100%', width: '100%' }} />
    </ChartFrame>
  );
}
```

- [ ] **Step 6: Run the tests and confirm they pass**

Run: `cd frontend && npx vitest run src/components/report/charts/__tests__/basic_charts.test.tsx`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/components/report/charts \
        frontend/package.json frontend/package-lock.json
git commit -m "feat(report): add ChartFrame and line/bar/area/pie chart blocks"
```

---

### Task 17: Frontend — Advanced chart blocks (candlestick / waterfall / scatter / heatmap / treemap / combo)

Same pattern as Task 16 — schema props → ECharts option object.

**Files:**
- Create: `frontend/src/components/report/charts/CandlestickBlock.tsx`
- Create: `frontend/src/components/report/charts/WaterfallBlock.tsx`
- Create: `frontend/src/components/report/charts/ScatterBlock.tsx`
- Create: `frontend/src/components/report/charts/HeatmapBlock.tsx`
- Create: `frontend/src/components/report/charts/TreemapBlock.tsx`
- Create: `frontend/src/components/report/charts/ComboChartBlock.tsx`
- Test: `frontend/src/components/report/charts/__tests__/advanced_charts.test.tsx`

- [ ] **Step 1: Write the failing tests**

```tsx
// frontend/src/components/report/charts/__tests__/advanced_charts.test.tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

vi.mock('echarts-for-react', () => ({
  default: ({ option }: { option: any }) => (
    <div data-testid="echart" data-option={JSON.stringify(option)} />
  ),
}));

import { CandlestickBlock } from '../CandlestickBlock';
import { WaterfallBlock } from '../WaterfallBlock';
import { ScatterBlock } from '../ScatterBlock';
import { HeatmapBlock } from '../HeatmapBlock';
import { TreemapBlock } from '../TreemapBlock';
import { ComboChartBlock } from '../ComboChartBlock';

describe('CandlestickBlock', () => {
  it('emits candlestick series with OHLC data', () => {
    render(
      <CandlestickBlock
        type="candlestick_chart"
        title="AAPL"
        data={[
          { date: '2026-04-01', open: 1, high: 2, low: 0.5, close: 1.8 },
        ]}
      />,
    );
    const opt = JSON.parse(screen.getByTestId('echart').dataset.option\!);
    const cs = opt.series.find((s: any) => s.type === 'candlestick');
    expect(cs.data[0]).toEqual([1, 1.8, 0.5, 2]);
  });

  it('adds a volume bar series when volume is provided', () => {
    render(
      <CandlestickBlock
        type="candlestick_chart"
        title="AAPL"
        data={[{ date: 'd1', open: 1, high: 2, low: 0, close: 1 }]}
        volume={[{ date: 'd1', value: 100 }]}
      />,
    );
    const opt = JSON.parse(screen.getByTestId('echart').dataset.option\!);
    expect(opt.series.some((s: any) => s.type === 'bar' && s.name === 'Volume')).toBe(true);
  });
});

describe('WaterfallBlock', () => {
  it('emits bar series with totals and increments', () => {
    render(
      <WaterfallBlock
        type="waterfall_chart"
        title="Revenue Bridge"
        items={[
          { label: 'Start', value: 10, type: 'total' },
          { label: 'A', value: 2, type: 'increase' },
          { label: 'End', value: 12, type: 'total' },
        ]}
      />,
    );
    const opt = JSON.parse(screen.getByTestId('echart').dataset.option\!);
    expect(opt.xAxis.data).toEqual(['Start', 'A', 'End']);
  });
});

describe('ScatterBlock', () => {
  it('emits a scatter series', () => {
    render(
      <ScatterBlock
        type="scatter_plot"
        title="P/E vs Growth"
        series={[{ name: 'Peers', data: [{ x: 15.2, y: 32.1 }, { x: 22.4, y: 28.7 }] }]}
      />,
    );
    const opt = JSON.parse(screen.getByTestId('echart').dataset.option\!);
    expect(opt.series[0].type).toBe('scatter');
    expect(opt.series[0].data[0]).toEqual([15.2, 32.1]);
  });
});

describe('HeatmapBlock', () => {
  it('emits a heatmap series with [x,y,value] points', () => {
    render(
      <HeatmapBlock
        type="heatmap"
        title="Correlation"
        x_labels={['A', 'B']}
        y_labels={['A', 'B']}
        values={[
          [1.0, 0.82],
          [0.82, 1.0],
        ]}
      />,
    );
    const opt = JSON.parse(screen.getByTestId('echart').dataset.option\!);
    expect(opt.series[0].type).toBe('heatmap');
    expect(opt.series[0].data).toHaveLength(4);
  });
});

describe('TreemapBlock', () => {
  it('emits a treemap series with nested children', () => {
    render(
      <TreemapBlock
        type="treemap"
        title="Revenue by Segment"
        data={[{ name: 'iPhone', value: 69.1, children: [{ name: '16', value: 42.0 }] }]}
      />,
    );
    const opt = JSON.parse(screen.getByTestId('echart').dataset.option\!);
    expect(opt.series[0].type).toBe('treemap');
    expect(opt.series[0].data[0].children[0].name).toBe('16');
  });
});

describe('ComboChartBlock', () => {
  it('emits a bar + line series pair with two y-axes', () => {
    render(
      <ComboChartBlock
        type="combo_chart"
        title="Rev & Margin"
        categories={['Q1', 'Q2']}
        bar_series={[{ name: 'Rev', values: [1, 2] }]}
        line_series={[{ name: 'Margin', values: [10, 11] }]}
      />,
    );
    const opt = JSON.parse(screen.getByTestId('echart').dataset.option\!);
    expect(Array.isArray(opt.yAxis)).toBe(true);
    expect(opt.yAxis).toHaveLength(2);
    const types = opt.series.map((s: any) => s.type);
    expect(types).toContain('bar');
    expect(types).toContain('line');
  });
});
```

- [ ] **Step 2: Run the tests and confirm they fail**

Run: `cd frontend && npx vitest run src/components/report/charts/__tests__/advanced_charts.test.tsx`
Expected: FAIL — modules missing.

- [ ] **Step 3: Write each block**

```tsx
// frontend/src/components/report/charts/CandlestickBlock.tsx
import ReactECharts from 'echarts-for-react';
import { ChartFrame, CHART_PALETTE, type ChartHeight } from './ChartFrame';
import type { ForcedHeight } from '../blocks/GroupBlock';

export interface CandleRow { date: string; open: number; high: number; low: number; close: number; }
export interface VolumeRow { date: string; value: number; }

export interface CandlestickBlockProps {
  type: 'candlestick_chart';
  title: string;
  data: CandleRow[];
  volume?: VolumeRow[];
  options?: { height?: ChartHeight };
  forcedHeight?: ForcedHeight;
}

export function CandlestickBlock({ title, data, volume, options, forcedHeight }: CandlestickBlockProps) {
  const categories = data.map((d) => d.date);
  const ohlc = data.map((d) => [d.open, d.close, d.low, d.high]);
  const series: any[] = [
    { type: 'candlestick', name: title, data: ohlc },
  ];
  if (volume && volume.length > 0) {
    series.push({ type: 'bar', name: 'Volume', yAxisIndex: 1, data: volume.map((v) => v.value) });
  }
  const option: any = {
    color: CHART_PALETTE,
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 40, top: 30, bottom: 40 },
    xAxis: { type: 'category', data: categories },
    yAxis: [{ type: 'value' }, { type: 'value', show: Boolean(volume) }],
    series,
  };
  return (
    <ChartFrame title={title} height={options?.height} forcedHeight={forcedHeight}>
      <ReactECharts option={option} style={{ height: '100%', width: '100%' }} />
    </ChartFrame>
  );
}
```

```tsx
// frontend/src/components/report/charts/WaterfallBlock.tsx
import ReactECharts from 'echarts-for-react';
import { ChartFrame, CHART_PALETTE, type ChartHeight } from './ChartFrame';
import type { ForcedHeight } from '../blocks/GroupBlock';

type ItemType = 'total' | 'increase' | 'decrease';

export interface WaterfallItem { label: string; value: number; type: ItemType; }

export interface WaterfallBlockProps {
  type: 'waterfall_chart';
  title: string;
  items: WaterfallItem[];
  options?: { height?: ChartHeight };
  forcedHeight?: ForcedHeight;
}

export function WaterfallBlock({ title, items, options, forcedHeight }: WaterfallBlockProps) {
  let running = 0;
  const placeholder: number[] = [];
  const increments: number[] = [];
  const decrements: number[] = [];
  const totals: number[] = [];
  for (const item of items) {
    if (item.type === 'total') {
      placeholder.push(0);
      totals.push(item.value);
      increments.push(0);
      decrements.push(0);
      running = item.value;
    } else if (item.type === 'increase') {
      placeholder.push(running);
      increments.push(item.value);
      decrements.push(0);
      totals.push(0);
      running += item.value;
    } else {
      running -= item.value;
      placeholder.push(running);
      increments.push(0);
      decrements.push(item.value);
      totals.push(0);
    }
  }
  const option = {
    color: CHART_PALETTE,
    tooltip: { trigger: 'axis' },
    grid: { left: 40, right: 20, top: 30, bottom: 40 },
    xAxis: { type: 'category', data: items.map((i) => i.label) },
    yAxis: { type: 'value' },
    series: [
      { type: 'bar', stack: 'wf', name: 'Placeholder', data: placeholder, itemStyle: { color: 'transparent' } },
      { type: 'bar', stack: 'wf', name: 'Increase', data: increments },
      { type: 'bar', stack: 'wf', name: 'Decrease', data: decrements },
      { type: 'bar', stack: 'wf', name: 'Total', data: totals },
    ],
  };
  return (
    <ChartFrame title={title} height={options?.height} forcedHeight={forcedHeight}>
      <ReactECharts option={option} style={{ height: '100%', width: '100%' }} />
    </ChartFrame>
  );
}
```

```tsx
// frontend/src/components/report/charts/ScatterBlock.tsx
import ReactECharts from 'echarts-for-react';
import { ChartFrame, CHART_PALETTE, type ChartHeight } from './ChartFrame';
import type { ForcedHeight } from '../blocks/GroupBlock';

export interface ScatterSeries { name: string; data: { x: number; y: number }[]; }

export interface ScatterBlockProps {
  type: 'scatter_plot';
  title: string;
  series: ScatterSeries[];
  x_label?: string;
  y_label?: string;
  options?: { height?: ChartHeight };
  forcedHeight?: ForcedHeight;
}

export function ScatterBlock({ title, series, x_label, y_label, options, forcedHeight }: ScatterBlockProps) {
  const option = {
    color: CHART_PALETTE,
    grid: { left: 40, right: 20, top: 30, bottom: 40 },
    tooltip: { trigger: 'item' },
    xAxis: { type: 'value', name: x_label },
    yAxis: { type: 'value', name: y_label },
    series: series.map((s) => ({
      type: 'scatter',
      name: s.name,
      data: s.data.map((d) => [d.x, d.y]),
    })),
  };
  return (
    <ChartFrame title={title} height={options?.height} forcedHeight={forcedHeight}>
      <ReactECharts option={option} style={{ height: '100%', width: '100%' }} />
    </ChartFrame>
  );
}
```

```tsx
// frontend/src/components/report/charts/HeatmapBlock.tsx
import ReactECharts from 'echarts-for-react';
import { ChartFrame, type ChartHeight } from './ChartFrame';
import type { ForcedHeight } from '../blocks/GroupBlock';

export interface HeatmapBlockProps {
  type: 'heatmap';
  title: string;
  x_labels: string[];
  y_labels: string[];
  values: number[][];
  options?: { height?: ChartHeight };
  forcedHeight?: ForcedHeight;
}

export function HeatmapBlock({ title, x_labels, y_labels, values, options, forcedHeight }: HeatmapBlockProps) {
  const points: [number, number, number][] = [];
  for (let y = 0; y < y_labels.length; y++) {
    for (let x = 0; x < x_labels.length; x++) {
      points.push([x, y, values[y]?.[x] ?? 0]);
    }
  }
  const all = points.map((p) => p[2]);
  const option = {
    tooltip: { position: 'top' },
    grid: { left: 60, right: 20, top: 30, bottom: 60 },
    xAxis: { type: 'category', data: x_labels, splitArea: { show: true } },
    yAxis: { type: 'category', data: y_labels, splitArea: { show: true } },
    visualMap: {
      min: Math.min(...all),
      max: Math.max(...all),
      calculable: true,
      orient: 'horizontal',
      bottom: 0,
    },
    series: [{ type: 'heatmap', data: points }],
  };
  return (
    <ChartFrame title={title} height={options?.height} forcedHeight={forcedHeight}>
      <ReactECharts option={option} style={{ height: '100%', width: '100%' }} />
    </ChartFrame>
  );
}
```

```tsx
// frontend/src/components/report/charts/TreemapBlock.tsx
import ReactECharts from 'echarts-for-react';
import { ChartFrame, type ChartHeight } from './ChartFrame';
import type { ForcedHeight } from '../blocks/GroupBlock';

export interface TreemapNode { name: string; value: number; children?: TreemapNode[]; }

export interface TreemapBlockProps {
  type: 'treemap';
  title: string;
  data: TreemapNode[];
  options?: { height?: ChartHeight };
  forcedHeight?: ForcedHeight;
}

export function TreemapBlock({ title, data, options, forcedHeight }: TreemapBlockProps) {
  const option = {
    tooltip: { trigger: 'item' },
    series: [{ type: 'treemap', data }],
  };
  return (
    <ChartFrame title={title} height={options?.height} forcedHeight={forcedHeight}>
      <ReactECharts option={option} style={{ height: '100%', width: '100%' }} />
    </ChartFrame>
  );
}
```

```tsx
// frontend/src/components/report/charts/ComboChartBlock.tsx
import ReactECharts from 'echarts-for-react';
import { ChartFrame, CHART_PALETTE, type ChartHeight } from './ChartFrame';
import type { ForcedHeight } from '../blocks/GroupBlock';

export interface ComboSeries { name: string; values: number[]; }

export interface ComboChartBlockProps {
  type: 'combo_chart';
  title: string;
  categories: string[];
  bar_series: ComboSeries[];
  line_series: ComboSeries[];
  y_left_label?: string;
  y_right_label?: string;
  options?: { height?: ChartHeight };
  forcedHeight?: ForcedHeight;
}

export function ComboChartBlock({
  title,
  categories,
  bar_series,
  line_series,
  y_left_label,
  y_right_label,
  options,
  forcedHeight,
}: ComboChartBlockProps) {
  const option = {
    color: CHART_PALETTE,
    tooltip: { trigger: 'axis' },
    legend: { bottom: 0 },
    grid: { left: 50, right: 50, top: 30, bottom: 40 },
    xAxis: { type: 'category', data: categories },
    yAxis: [
      { type: 'value', name: y_left_label, position: 'left' },
      { type: 'value', name: y_right_label, position: 'right' },
    ],
    series: [
      ...bar_series.map((s) => ({ type: 'bar', name: s.name, data: s.values, yAxisIndex: 0 })),
      ...line_series.map((s) => ({ type: 'line', name: s.name, data: s.values, yAxisIndex: 1, smooth: true })),
    ],
  };
  return (
    <ChartFrame title={title} height={options?.height} forcedHeight={forcedHeight}>
      <ReactECharts option={option} style={{ height: '100%', width: '100%' }} />
    </ChartFrame>
  );
}
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `cd frontend && npx vitest run src/components/report/charts/__tests__/advanced_charts.test.tsx`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/report/charts/CandlestickBlock.tsx \
        frontend/src/components/report/charts/WaterfallBlock.tsx \
        frontend/src/components/report/charts/ScatterBlock.tsx \
        frontend/src/components/report/charts/HeatmapBlock.tsx \
        frontend/src/components/report/charts/TreemapBlock.tsx \
        frontend/src/components/report/charts/ComboChartBlock.tsx \
        frontend/src/components/report/charts/__tests__/advanced_charts.test.tsx
git commit -m "feat(report): add candlestick, waterfall, scatter, heatmap, treemap, combo charts"
```

---

### Task 18: Frontend — BlockRenderer dispatcher

Single switch over `block.type`. Recurses for group blocks by passing `renderChild` down to `GroupBlock`.

**Files:**
- Create: `frontend/src/components/report/BlockRenderer.tsx`
- Test: `frontend/src/components/report/__tests__/BlockRenderer.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/report/__tests__/BlockRenderer.test.tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

vi.mock('echarts-for-react', () => ({
  default: ({ option }: any) => (
    <div data-testid="echart" data-option={JSON.stringify(option)} />
  ),
}));

import { BlockRenderer } from '../BlockRenderer';

describe('BlockRenderer', () => {
  it('renders a text block', () => {
    render(<BlockRenderer block={{ type: 'text', content: 'hello' }} />);
    expect(screen.getByText('hello')).toBeInTheDocument();
  });

  it('renders a table block', () => {
    render(
      <BlockRenderer
        block={{
          type: 'table',
          title: 'T',
          headers: [{ key: 'a', label: 'A' }],
          rows: [{ a: 'row1' }],
        }}
      />,
    );
    expect(screen.getByText('T')).toBeInTheDocument();
    expect(screen.getByText('row1')).toBeInTheDocument();
  });

  it('renders a group that nests other blocks', () => {
    render(
      <BlockRenderer
        block={{
          type: 'group',
          columns: 2,
          blocks: [
            { type: 'text', content: 'left' },
            { type: 'text', content: 'right' },
          ],
        }}
      />,
    );
    expect(screen.getByText('left')).toBeInTheDocument();
    expect(screen.getByText('right')).toBeInTheDocument();
  });

  it('renders an unknown block type as a visible error', () => {
    render(<BlockRenderer block={{ type: 'movie', src: 'x' } as any} />);
    expect(screen.getByText(/unsupported block/i)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run the test and confirm it fails**

Run: `cd frontend && npx vitest run src/components/report/__tests__/BlockRenderer.test.tsx`
Expected: FAIL — module missing.

- [ ] **Step 3: Write the dispatcher**

```tsx
// frontend/src/components/report/BlockRenderer.tsx
import { TextBlock } from './blocks/TextBlock';
import { TableBlock } from './blocks/TableBlock';
import { MetricCardsBlock } from './blocks/MetricCardsBlock';
import { KeyFindingBlock } from './blocks/KeyFindingBlock';
import { RatingBadgeBlock } from './blocks/RatingBadgeBlock';
import { GroupBlock, type ForcedHeight } from './blocks/GroupBlock';
import { LineChartBlock } from './charts/LineChartBlock';
import { BarChartBlock } from './charts/BarChartBlock';
import { AreaChartBlock } from './charts/AreaChartBlock';
import { PieChartBlock } from './charts/PieChartBlock';
import { CandlestickBlock } from './charts/CandlestickBlock';
import { WaterfallBlock } from './charts/WaterfallBlock';
import { ScatterBlock } from './charts/ScatterBlock';
import { HeatmapBlock } from './charts/HeatmapBlock';
import { TreemapBlock } from './charts/TreemapBlock';
import { ComboChartBlock } from './charts/ComboChartBlock';

export interface BlockRendererProps {
  block: any;
  forcedHeight?: ForcedHeight;
}

export function BlockRenderer({ block, forcedHeight }: BlockRendererProps) {
  switch (block.type) {
    case 'text':
      return <TextBlock content={block.content} />;
    case 'table':
      return <TableBlock {...block} />;
    case 'metric_cards':
      return <MetricCardsBlock {...block} />;
    case 'key_finding':
      return <KeyFindingBlock {...block} />;
    case 'rating_badge':
      return <RatingBadgeBlock {...block} />;
    case 'group':
      return (
        <GroupBlock
          {...block}
          renderChild={(child: any, forced) => (
            <BlockRenderer block={child} forcedHeight={forced} />
          )}
        />
      );
    case 'line_chart':
      return <LineChartBlock {...block} forcedHeight={forcedHeight} />;
    case 'bar_chart':
      return <BarChartBlock {...block} forcedHeight={forcedHeight} />;
    case 'area_chart':
      return <AreaChartBlock {...block} forcedHeight={forcedHeight} />;
    case 'pie_chart':
      return <PieChartBlock {...block} forcedHeight={forcedHeight} />;
    case 'candlestick_chart':
      return <CandlestickBlock {...block} forcedHeight={forcedHeight} />;
    case 'waterfall_chart':
      return <WaterfallBlock {...block} forcedHeight={forcedHeight} />;
    case 'scatter_plot':
      return <ScatterBlock {...block} forcedHeight={forcedHeight} />;
    case 'heatmap':
      return <HeatmapBlock {...block} forcedHeight={forcedHeight} />;
    case 'treemap':
      return <TreemapBlock {...block} forcedHeight={forcedHeight} />;
    case 'combo_chart':
      return <ComboChartBlock {...block} forcedHeight={forcedHeight} />;
    default:
      return (
        <div className="report-block--unsupported" role="alert">
          Unsupported block type: {String(block.type)}
        </div>
      );
  }
}
```

- [ ] **Step 4: Run the test and confirm it passes**

Run: `cd frontend && npx vitest run src/components/report/__tests__/BlockRenderer.test.tsx`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/report/BlockRenderer.tsx \
        frontend/src/components/report/__tests__/BlockRenderer.test.tsx
git commit -m "feat(report): add BlockRenderer dispatcher over every block type"
```

---

### Task 19: Frontend — ReportCover + TableOfContents + ScrollTracker

Three related pieces:
- `ReportCover`: title, subtitle, italic tagline, key metric cards, stats panel grid.
- `TableOfContents`: anchor links from `sections[].id`/`.title`.
- `ScrollTracker`: uses `react-intersection-observer` to highlight the active TOC item.

**Files:**
- Create: `frontend/src/components/report/ReportCover.tsx`
- Create: `frontend/src/components/report/TableOfContents.tsx`
- Create: `frontend/src/components/report/furniture/ScrollTracker.tsx`
- Test: `frontend/src/components/report/__tests__/ReportCover.test.tsx`
- Test: `frontend/src/components/report/__tests__/TableOfContents.test.tsx`
- Test: `frontend/src/components/report/furniture/__tests__/ScrollTracker.test.tsx`

- [ ] **Step 1: Install react-intersection-observer**

Run: `cd frontend && npm install react-intersection-observer`
Expected: dependency added.

- [ ] **Step 2: Write the failing tests**

```tsx
// frontend/src/components/report/__tests__/ReportCover.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ReportCover } from '../ReportCover';

describe('ReportCover', () => {
  it('renders title, subtitle, tagline, key metrics, stats panel', () => {
    render(
      <ReportCover
        cover={{
          title: 'Apple Inc.',
          subtitle: 'Q1 2026',
          tagline: 'Strong quarter.',
          key_metrics: [{ label: 'Price', value: '$198.50' }],
          stats_panel: [{ label: 'Sector', value: 'Technology' }],
        }}
      />,
    );
    expect(screen.getByText('Apple Inc.')).toBeInTheDocument();
    expect(screen.getByText('Q1 2026')).toBeInTheDocument();
    expect(screen.getByText('Strong quarter.')).toBeInTheDocument();
    expect(screen.getByText('Price')).toBeInTheDocument();
    expect(screen.getByText('Sector')).toBeInTheDocument();
  });
});
```

```tsx
// frontend/src/components/report/__tests__/TableOfContents.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { TableOfContents } from '../TableOfContents';

describe('TableOfContents', () => {
  it('renders one link per section', () => {
    render(
      <TableOfContents
        sections={[
          { id: 'fin', title: 'Financial Overview' },
          { id: 'comp', title: 'Competitive Landscape' },
        ]}
      />,
    );
    const links = screen.getAllByRole('link');
    expect(links).toHaveLength(2);
    expect(links[0].getAttribute('href')).toBe('#fin');
    expect(links[1].textContent).toMatch(/Competitive Landscape/);
  });

  it('marks the active id with aria-current', () => {
    render(
      <TableOfContents
        sections={[
          { id: 'fin', title: 'Financial Overview' },
          { id: 'comp', title: 'Competitive Landscape' },
        ]}
        activeId="comp"
      />,
    );
    const active = screen.getByText('Competitive Landscape').closest('a');
    expect(active?.getAttribute('aria-current')).toBe('true');
  });
});
```

```tsx
// frontend/src/components/report/furniture/__tests__/ScrollTracker.test.tsx
import { describe, it, expect, vi } from 'vitest';

vi.mock('react-intersection-observer', () => ({
  useInView: () => ({ ref: () => {}, inView: true }),
}));

import { render } from '@testing-library/react';
import { ScrollTracker } from '../ScrollTracker';

describe('ScrollTracker', () => {
  it('calls onActiveId with the first intersecting section', () => {
    const cb = vi.fn();
    render(
      <ScrollTracker
        sectionIds={['a', 'b']}
        onActiveId={cb}
      />,
    );
    expect(cb).toHaveBeenCalled();
    const lastArgs = cb.mock.calls.at(-1) as [string];
    expect(['a', 'b']).toContain(lastArgs[0]);
  });
});
```

- [ ] **Step 3: Run the tests and confirm they fail**

Run: `cd frontend && npx vitest run src/components/report/__tests__/ReportCover.test.tsx src/components/report/__tests__/TableOfContents.test.tsx src/components/report/furniture/__tests__/ScrollTracker.test.tsx`
Expected: FAIL — modules missing.

- [ ] **Step 4: Write the components**

```tsx
// frontend/src/components/report/ReportCover.tsx
import type { ReportCover as ReportCoverData } from '../../api/reports';

export interface ReportCoverProps {
  cover: ReportCoverData;
}

export function ReportCover({ cover }: ReportCoverProps) {
  return (
    <header className="report-cover">
      <h1 className="report-cover__title">{cover.title}</h1>
      <div className="report-cover__subtitle">{cover.subtitle}</div>
      <p className="report-cover__tagline"><em>{cover.tagline}</em></p>
      {cover.key_metrics && cover.key_metrics.length > 0 ? (
        <div className="report-cover__metrics">
          {cover.key_metrics.map((m) => (
            <div key={m.label} className="metric-card">
              <div className="metric-card__label">{m.label}</div>
              <div className="metric-card__value">{m.value}</div>
              {m.delta ? (
                <div
                  className={`metric-card__delta metric-card__delta--${
                    m.delta_direction === 'down'
                      ? 'negative'
                      : m.delta_direction === 'flat'
                        ? 'neutral'
                        : 'positive'
                  }`}
                >
                  {m.delta}
                </div>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}
      {cover.stats_panel && cover.stats_panel.length > 0 ? (
        <dl className="report-cover__stats">
          {cover.stats_panel.map((s) => (
            <div key={s.label} className="report-cover__stat">
              <dt>{s.label}</dt>
              <dd>{s.value}</dd>
            </div>
          ))}
        </dl>
      ) : null}
    </header>
  );
}
```

```tsx
// frontend/src/components/report/TableOfContents.tsx
export interface TocSection {
  id: string;
  title: string;
}

export interface TableOfContentsProps {
  sections: TocSection[];
  activeId?: string;
}

export function TableOfContents({ sections, activeId }: TableOfContentsProps) {
  return (
    <nav className="report-toc" aria-label="Report sections">
      <ul>
        {sections.map((s) => {
          const isActive = s.id === activeId;
          return (
            <li key={s.id}>
              <a
                href={`#${s.id}`}
                aria-current={isActive ? 'true' : undefined}
                className={isActive ? 'report-toc__link--active' : undefined}
              >
                {s.title}
              </a>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
```

```tsx
// frontend/src/components/report/furniture/ScrollTracker.tsx
import { useEffect } from 'react';
import { useInView } from 'react-intersection-observer';

export interface ScrollTrackerProps {
  sectionIds: string[];
  onActiveId: (id: string) => void;
}

export function ScrollTracker({ sectionIds, onActiveId }: ScrollTrackerProps) {
  // One observer per section id; report the first that is inView.
  const hooks = sectionIds.map((id) => {
    const { ref, inView } = useInView({ rootMargin: '-40% 0px -50% 0px' });
    return { id, ref, inView };
  });

  useEffect(() => {
    const active = hooks.find((h) => h.inView);
    if (active) onActiveId(active.id);
  }, [hooks, onActiveId]);

  return (
    <>
      {hooks.map((h) => (
        <span
          key={h.id}
          ref={h.ref}
          data-scroll-sentinel={h.id}
          style={{ display: 'block', height: 0 }}
        />
      ))}
    </>
  );
}
```

- [ ] **Step 5: Run the tests and confirm they pass**

Run: `cd frontend && npx vitest run src/components/report/__tests__/ReportCover.test.tsx src/components/report/__tests__/TableOfContents.test.tsx src/components/report/furniture/__tests__/ScrollTracker.test.tsx`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/report/ReportCover.tsx \
        frontend/src/components/report/TableOfContents.tsx \
        frontend/src/components/report/furniture/ScrollTracker.tsx \
        frontend/src/components/report/__tests__/ReportCover.test.tsx \
        frontend/src/components/report/__tests__/TableOfContents.test.tsx \
        frontend/src/components/report/furniture/__tests__/ScrollTracker.test.tsx \
        frontend/package.json frontend/package-lock.json
git commit -m "feat(report): add ReportCover, TableOfContents, ScrollTracker"
```

---

### Task 20: Frontend — ReportHeader + ReportFooter + ReportSkeleton

Page furniture and the loading skeleton.

**Files:**
- Create: `frontend/src/components/report/furniture/ReportHeader.tsx`
- Create: `frontend/src/components/report/furniture/ReportFooter.tsx`
- Create: `frontend/src/components/report/ReportSkeleton.tsx`
- Test: `frontend/src/components/report/furniture/__tests__/ReportHeaderFooter.test.tsx`
- Test: `frontend/src/components/report/__tests__/ReportSkeleton.test.tsx`

- [ ] **Step 1: Install react-loading-skeleton**

Run: `cd frontend && npm install react-loading-skeleton`
Expected: dependency added.

- [ ] **Step 2: Write the failing tests**

```tsx
// frontend/src/components/report/furniture/__tests__/ReportHeaderFooter.test.tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { ReportHeader } from '../ReportHeader';
import { ReportFooter } from '../ReportFooter';

describe('ReportHeader', () => {
  it('renders header left and right text', () => {
    render(<ReportHeader left="OpenLIA" right="Equity Research" />);
    expect(screen.getByText('OpenLIA')).toBeInTheDocument();
    expect(screen.getByText('Equity Research')).toBeInTheDocument();
  });
});

describe('ReportFooter', () => {
  it('renders footer columns and disclaimer', () => {
    render(
      <ReportFooter
        left="Generated Apr 11, 2026"
        center="Page {page}"
        right="For internal use only"
        disclaimer="Not advice."
      />,
    );
    expect(screen.getByText(/Generated/)).toBeInTheDocument();
    expect(screen.getByText('For internal use only')).toBeInTheDocument();
    expect(screen.getByText('Not advice.')).toBeInTheDocument();
  });
});
```

```tsx
// frontend/src/components/report/__tests__/ReportSkeleton.test.tsx
import { describe, it, expect } from 'vitest';
import { render } from '@testing-library/react';
import { ReportSkeleton } from '../ReportSkeleton';

describe('ReportSkeleton', () => {
  it('renders one placeholder block per section title', () => {
    const { container } = render(
      <ReportSkeleton sectionTitles={['Cover', 'Financial', 'Competitive']} />,
    );
    expect(container.querySelectorAll('.report-skeleton__section')).toHaveLength(3);
  });
});
```

- [ ] **Step 3: Run and confirm failure**

Run: `cd frontend && npx vitest run src/components/report/furniture/__tests__/ReportHeaderFooter.test.tsx src/components/report/__tests__/ReportSkeleton.test.tsx`
Expected: FAIL — modules missing.

- [ ] **Step 4: Write the components**

```tsx
// frontend/src/components/report/furniture/ReportHeader.tsx
export interface ReportHeaderProps { left: string; right: string; }

export function ReportHeader({ left, right }: ReportHeaderProps) {
  return (
    <div className="report-furniture__header">
      <span className="report-furniture__header-left">{left}</span>
      <span className="report-furniture__header-right">{right}</span>
    </div>
  );
}
```

```tsx
// frontend/src/components/report/furniture/ReportFooter.tsx
export interface ReportFooterProps {
  left: string;
  center: string;
  right: string;
  disclaimer: string;
}

export function ReportFooter({ left, center, right, disclaimer }: ReportFooterProps) {
  return (
    <footer className="report-furniture__footer">
      <div className="report-furniture__footer-row">
        <span>{left}</span>
        <span>{center}</span>
        <span>{right}</span>
      </div>
      <p className="report-furniture__disclaimer">{disclaimer}</p>
    </footer>
  );
}
```

```tsx
// frontend/src/components/report/ReportSkeleton.tsx
import Skeleton from 'react-loading-skeleton';
import 'react-loading-skeleton/dist/skeleton.css';

export interface ReportSkeletonProps {
  sectionTitles?: string[];
}

export function ReportSkeleton({ sectionTitles = [] }: ReportSkeletonProps) {
  return (
    <div className="report-skeleton">
      <div className="report-skeleton__cover">
        <Skeleton width="60%" height={28} />
        <Skeleton width="40%" height={18} style={{ marginTop: 8 }} />
        <Skeleton height={90} style={{ marginTop: 24 }} />
      </div>
      {sectionTitles.map((title, i) => (
        <div key={`${i}-${title}`} className="report-skeleton__section">
          <h2 className="report-skeleton__heading">{title}</h2>
          <Skeleton count={3} />
          <Skeleton height={260} style={{ marginTop: 16 }} />
          <Skeleton count={4} style={{ marginTop: 16 }} />
        </div>
      ))}
    </div>
  );
}
```

- [ ] **Step 5: Run the tests and confirm they pass**

Run: `cd frontend && npx vitest run src/components/report/furniture/__tests__/ReportHeaderFooter.test.tsx src/components/report/__tests__/ReportSkeleton.test.tsx`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/report/furniture/ReportHeader.tsx \
        frontend/src/components/report/furniture/ReportFooter.tsx \
        frontend/src/components/report/ReportSkeleton.tsx \
        frontend/src/components/report/furniture/__tests__/ReportHeaderFooter.test.tsx \
        frontend/src/components/report/__tests__/ReportSkeleton.test.tsx \
        frontend/package.json frontend/package-lock.json
git commit -m "feat(report): add ReportHeader, ReportFooter, ReportSkeleton"
```

---

### Task 21: Frontend — ReportRenderer top-level composition

Pulls everything together: theme wrapper, header, cover, TOC, sections, footer. Reads an optional `loading` flag to show the skeleton.

**Files:**
- Create: `frontend/src/components/report/ReportSection.tsx`
- Create: `frontend/src/components/report/ReportRenderer.tsx`
- Test: `frontend/src/components/report/__tests__/ReportRenderer.test.tsx`

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/report/__tests__/ReportRenderer.test.tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';

vi.mock('echarts-for-react', () => ({
  default: () => <div data-testid="echart" />,
}));
vi.mock('react-intersection-observer', () => ({
  useInView: () => ({ ref: () => {}, inView: false }),
}));

import { ReportRenderer } from '../ReportRenderer';

const schema = {
  schema_version: '1.0' as const,
  department: 'equity_research',
  page_furniture: {
    header: { left: 'OpenLIA', right: 'Equity Research' },
    footer: { left: 'Gen', center: 'Page {page}', right: 'Internal' },
    disclaimer: 'Not advice.',
  },
  cover: {
    title: 'Apple Inc.',
    subtitle: 'Q1 2026',
    tagline: 'Strong.',
    ticker: 'AAPL',
  },
  sections: [
    {
      id: 'fin',
      title: 'Financial Overview',
      blocks: [{ type: 'text', content: 'Apple reported...' }],
    },
  ],
};

describe('ReportRenderer', () => {
  it('renders furniture, cover, TOC, and a section with blocks', () => {
    render(<ReportRenderer schema={schema} />);
    expect(screen.getByText('Apple Inc.')).toBeInTheDocument();
    expect(screen.getByText('Equity Research')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /Financial Overview/ })).toBeInTheDocument();
    expect(screen.getByText('Apple reported...')).toBeInTheDocument();
    expect(screen.getByText('Not advice.')).toBeInTheDocument();
  });

  it('shows the skeleton while loading', () => {
    const { container } = render(<ReportRenderer loading sectionTitles={['a']} />);
    expect(container.querySelector('.report-skeleton')).toBeTruthy();
  });

  it('applies the provided report theme attribute', () => {
    const { container } = render(<ReportRenderer schema={schema} theme="dark" />);
    expect(container.querySelector('[data-report-theme="dark"]')).toBeTruthy();
  });
});
```

- [ ] **Step 2: Run the test and confirm it fails**

Run: `cd frontend && npx vitest run src/components/report/__tests__/ReportRenderer.test.tsx`
Expected: FAIL — module missing.

- [ ] **Step 3: Write ReportSection**

```tsx
// frontend/src/components/report/ReportSection.tsx
import { BlockRenderer } from './BlockRenderer';

export interface ReportSectionProps {
  id: string;
  title: string;
  blocks: any[];
}

export function ReportSection({ id, title, blocks }: ReportSectionProps) {
  return (
    <section id={id} className="report-section">
      <h2 className="report-section__title">{title}</h2>
      {blocks.map((b, i) => (
        <div key={i} className="report-block">
          <BlockRenderer block={b} />
        </div>
      ))}
    </section>
  );
}
```

- [ ] **Step 4: Write ReportRenderer**

```tsx
// frontend/src/components/report/ReportRenderer.tsx
import { useState } from 'react';

import type { ReportSchema } from '../../api/reports';
import { ReportCover } from './ReportCover';
import { ReportHeader } from './furniture/ReportHeader';
import { ReportFooter } from './furniture/ReportFooter';
import { ReportSection } from './ReportSection';
import { ReportSkeleton } from './ReportSkeleton';
import { ScrollTracker } from './furniture/ScrollTracker';
import { TableOfContents } from './TableOfContents';

export type ReportTheme = 'light' | 'dark';

export interface ReportRendererProps {
  schema?: ReportSchema;
  loading?: boolean;
  sectionTitles?: string[];
  theme?: ReportTheme;
}

export function ReportRenderer({
  schema,
  loading = false,
  sectionTitles = [],
  theme = 'light',
}: ReportRendererProps) {
  const [activeId, setActiveId] = useState<string | undefined>();
  const titles = schema?.sections?.map((s) => s.title) ?? sectionTitles;

  if (loading || \!schema) {
    return (
      <div data-report-theme={theme} className="report">
        <ReportSkeleton sectionTitles={titles} />
      </div>
    );
  }

  const furniture = schema.page_furniture;
  const tocSections = schema.sections.map((s) => ({ id: s.id, title: s.title }));

  return (
    <div data-report-theme={theme} className="report">
      {furniture ? (
        <ReportHeader left={furniture.header.left} right={furniture.header.right} />
      ) : null}
      <div className="report__body">
        <aside className="report__toc">
          <TableOfContents sections={tocSections} activeId={activeId} />
        </aside>
        <main className="report__main">
          <ReportCover cover={schema.cover} />
          <ScrollTracker
            sectionIds={tocSections.map((t) => t.id)}
            onActiveId={setActiveId}
          />
          {schema.sections.map((s) => (
            <ReportSection key={s.id} id={s.id} title={s.title} blocks={s.blocks as any[]} />
          ))}
        </main>
      </div>
      {furniture ? (
        <ReportFooter
          left={furniture.footer.left}
          center={furniture.footer.center}
          right={furniture.footer.right}
          disclaimer={furniture.disclaimer}
        />
      ) : null}
    </div>
  );
}
```

- [ ] **Step 5: Run the tests and confirm they pass**

Run: `cd frontend && npx vitest run src/components/report/__tests__/ReportRenderer.test.tsx`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/report/ReportSection.tsx \
        frontend/src/components/report/ReportRenderer.tsx \
        frontend/src/components/report/__tests__/ReportRenderer.test.tsx
git commit -m "feat(report): add ReportRenderer top-level composition"
```

---

### Task 22: Frontend — RedirectCard chat block

Rendered inside the chat transcript when the Secretary calls `suggest_redirect`. Shows the explanation, a primary "Go to [Department]" button, and a secondary "Stay here" link that simply closes the card.

**Files:**
- Create: `frontend/src/components/chat/RedirectCard.tsx`
- Test: `frontend/src/components/chat/__tests__/RedirectCard.test.tsx`

The prefill is passed to the target department via the `?q=` URL parameter.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/components/chat/__tests__/RedirectCard.test.tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { RedirectCard } from '../RedirectCard';

const mockNavigate = vi.fn();
vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual<typeof import('react-router-dom')>('react-router-dom');
  return { ...actual, useNavigate: () => mockNavigate };
});

function renderCard(props?: Partial<React.ComponentProps<typeof RedirectCard>>) {
  return render(
    <MemoryRouter>
      <RedirectCard
        department="equity_research"
        reason="Full initiation report needed"
        prefill="AAPL"
        {...props}
      />
    </MemoryRouter>,
  );
}

describe('RedirectCard', () => {
  it('renders the explanation and a primary CTA for the target department', () => {
    renderCard();
    expect(screen.getByText(/Full initiation report needed/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Go to Equity Research/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /Stay here/i })).toBeInTheDocument();
  });

  it('navigates to the department with the prefill as a query parameter', () => {
    mockNavigate.mockClear();
    renderCard();
    fireEvent.click(screen.getByRole('button', { name: /Go to Equity Research/i }));
    expect(mockNavigate).toHaveBeenCalledWith('/equity-research?q=AAPL');
  });

  it('omits the query parameter when no prefill is given', () => {
    mockNavigate.mockClear();
    renderCard({ prefill: undefined });
    fireEvent.click(screen.getByRole('button', { name: /Go to Equity Research/i }));
    expect(mockNavigate).toHaveBeenCalledWith('/equity-research');
  });

  it('hides the card when Stay here is clicked', () => {
    renderCard();
    fireEvent.click(screen.getByRole('button', { name: /Stay here/i }));
    expect(screen.queryByRole('button', { name: /Go to Equity Research/i })).toBeNull();
  });
});
```

- [ ] **Step 2: Run the test and confirm it fails**

Run: `cd frontend && npx vitest run src/components/chat/__tests__/RedirectCard.test.tsx`
Expected: FAIL — module missing.

- [ ] **Step 3: Write the component**

```tsx
// frontend/src/components/chat/RedirectCard.tsx
import { useState } from 'react';
import { ArrowRight } from 'lucide-react';
import { useNavigate } from 'react-router-dom';

export type RedirectDepartment =
  | 'equity_research'
  | 'earnings_update'
  | 'morning_briefing'
  | 'retail_sentiment'
  | 'macro_research'
  | 'portfolio';

export interface RedirectCardProps {
  department: RedirectDepartment;
  reason: string;
  prefill?: string;
}

const DEPT_LABEL: Record<RedirectDepartment, string> = {
  equity_research: 'Equity Research',
  earnings_update: 'Earnings Updates',
  morning_briefing: 'Morning Briefings',
  retail_sentiment: 'Retail Sentiment',
  macro_research: 'Macro Research',
  portfolio: 'Portfolio',
};

const DEPT_PATH: Record<RedirectDepartment, string> = {
  equity_research: '/equity-research',
  earnings_update: '/earnings-update',
  morning_briefing: '/morning-briefings',
  retail_sentiment: '/retail-sentiment',
  macro_research: '/macro-research',
  portfolio: '/portfolio',
};

export function RedirectCard({ department, reason, prefill }: RedirectCardProps) {
  const navigate = useNavigate();
  const [dismissed, setDismissed] = useState(false);
  if (dismissed) return null;

  const label = DEPT_LABEL[department];
  const go = () => {
    const base = DEPT_PATH[department];
    const target = prefill ? `${base}?q=${encodeURIComponent(prefill)}` : base;
    navigate(target);
  };

  return (
    <div className="redirect-card" role="group" aria-label={`Suggested redirect to ${label}`}>
      <p className="redirect-card__text">
        This looks like a <strong>{label}</strong> request. {reason}
      </p>
      <div className="redirect-card__divider" />
      <div className="redirect-card__actions">
        <button type="button" className="redirect-card__primary" onClick={go}>
          Go to {label}
          <ArrowRight size={14} aria-hidden />
        </button>
        <button
          type="button"
          className="redirect-card__secondary"
          onClick={() => setDismissed(true)}
        >
          Stay here
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Run the tests and confirm they pass**

Run: `cd frontend && npx vitest run src/components/chat/__tests__/RedirectCard.test.tsx`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/chat/RedirectCard.tsx \
        frontend/src/components/chat/__tests__/RedirectCard.test.tsx
git commit -m "feat(chat): add RedirectCard for Secretary redirect suggestions"
```

---

### Task 23: Frontend — SecretaryPage

Composes everything for the Secretary route. Uses `ChatInterface` from Plan 12. On first load (no conversation history) it renders the welcome state with four suggestion chips; once the user sends a message, the welcome content fades out and the chat transcript takes over. When a `chat.tool_call.result` arrives with `tool_name === 'suggest_redirect'`, the transcript renders a `RedirectCard` inline.

**Files:**
- Create: `frontend/src/pages/SecretaryPage.tsx`
- Create: `frontend/src/pages/__tests__/SecretaryPage.test.tsx`
- Modify: the app router (Plan 8's `router.tsx` or equivalent) to mount `SecretaryPage` at `/`.

- [ ] **Step 1: Write the failing test**

```tsx
// frontend/src/pages/__tests__/SecretaryPage.test.tsx
import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';

vi.mock('../../components/chat/ChatInterface', () => ({
  ChatInterface: ({ onFirstMessage }: any) => (
    <button data-testid="send" onClick={() => onFirstMessage?.('hi')}>
      send
    </button>
  ),
}));

import { SecretaryPage } from '../SecretaryPage';

function renderPage() {
  return render(
    <MemoryRouter>
      <SecretaryPage user={{ id: 'u1', display_name: 'Alex' }} />
    </MemoryRouter>,
  );
}

describe('SecretaryPage', () => {
  it('shows a personalized welcome state on first load', () => {
    renderPage();
    expect(screen.getByText(/Welcome back, Alex/)).toBeInTheDocument();
    expect(screen.getByText(/What can I help you with today/)).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: /^(What is LIA|Get a quick market snapshot|How do I use Equity Research|Summarize).*/ })).not.toHaveLength(0);
  });

  it('hides the welcome state once a message has been sent', () => {
    renderPage();
    fireEvent.click(screen.getByTestId('send'));
    expect(screen.queryByText(/Welcome back, Alex/)).toBeNull();
  });
});
```

- [ ] **Step 2: Run the test and confirm it fails**

Run: `cd frontend && npx vitest run src/pages/__tests__/SecretaryPage.test.tsx`
Expected: FAIL — module missing.

- [ ] **Step 3: Write the page**

```tsx
// frontend/src/pages/SecretaryPage.tsx
import { useState } from 'react';
import { ChatInterface } from '../components/chat/ChatInterface';
import { secretaryChatUrl } from '../api/secretary';

export interface SecretaryPageUser {
  id: string;
  display_name: string;
}

export interface SecretaryPageProps {
  user: SecretaryPageUser;
}

const CHIPS = [
  'What is LIA?',
  'Get a quick market snapshot',
  'How do I use Equity Research?',
  'Summarize a financial term',
];

export function SecretaryPage({ user }: SecretaryPageProps) {
  const [sentOnce, setSentOnce] = useState(false);
  const [pendingPrompt, setPendingPrompt] = useState<string | null>(null);

  return (
    <div className="secretary-page" data-has-conversation={sentOnce}>
      {\!sentOnce ? (
        <div className="secretary-page__welcome">
          <h1 className="secretary-page__greeting">Welcome back, {user.display_name}.</h1>
          <p className="secretary-page__subtext">What can I help you with today?</p>
          <div className="secretary-page__chips">
            {CHIPS.map((chip) => (
              <button
                key={chip}
                type="button"
                className="secretary-page__chip"
                onClick={() => setPendingPrompt(chip)}
              >
                {chip}
              </button>
            ))}
          </div>
        </div>
      ) : null}
      <ChatInterface
        department="secretary"
        streamUrl={secretaryChatUrl()}
        prefill={pendingPrompt ?? ''}
        onFirstMessage={() => {
          setSentOnce(true);
          setPendingPrompt(null);
        }}
      />
    </div>
  );
}
```

- [ ] **Step 4: Mount the page on the router**

Edit `frontend/src/router.tsx` (or the shell created in Plan 8) and add the Secretary route to the authenticated routes:

```tsx
import { SecretaryPage } from './pages/SecretaryPage';
// ... inside <Routes>
<Route path="/" element={<SecretaryPage user={currentUser} />} />
```

If Plan 8 already registered a placeholder index route, replace it with the line above.

- [ ] **Step 5: Run the tests and confirm they pass**

Run: `cd frontend && npx vitest run src/pages/__tests__/SecretaryPage.test.tsx`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/pages/SecretaryPage.tsx \
        frontend/src/pages/__tests__/SecretaryPage.test.tsx \
        frontend/src/router.tsx
git commit -m "feat(secretary): add Secretary page with welcome state and chat wiring"
```

---

### Task 24: Manual smoke test + flip README row to Draft

With report pipeline + Secretary in place, run a targeted smoke test, then flip the README row.

**Files:**
- Modify: `planning/implementation-plans/README.md`

- [ ] **Step 1: Start the backend**

Run: `uv run openlia serve`
Expected: server on `http://localhost:8000`, no stack traces, Playwright does not initialize until an export is requested.

- [ ] **Step 2: Start the frontend**

Run (second terminal): `cd frontend && npm run dev`
Expected: Vite serves the app on `http://localhost:5173/`.

- [ ] **Step 3: Verify Secretary welcome + chat**

Log in as a seeded user. On `/`:
- Welcome greeting shows the user's display name. Four chips visible and centered above the input.
- Click a chip. The chip text lands in the input and submits automatically.
- `chat.start` → `chat.token` (many) → `chat.done` events arrive in DevTools → Network → EventStream.
- Reload the page. The same session rehydrates via `/api/chat/sessions` from Plan 12.

- [ ] **Step 4: Trigger a redirect**

Send: "Please write me a full equity research report on AAPL."
Expected: Secretary's response is short, followed by a `RedirectCard` showing "Go to Equity Research" and "Stay here". Clicking "Go to Equity Research" navigates to `/equity-research?q=AAPL`.

- [ ] **Step 5: Verify report schema rendering**

Seed a sample equity research report through the admin route (`openlia admin seed-report` from Plan 7 or direct DB insert) and open `/api/reports/{id}` in DevTools — confirm the JSON response matches the schema. Then point a browser at a future Equity Research page or a dev-only preview route; `ReportRenderer` should render the cover, TOC, sections, and any chart blocks that were seeded.

- [ ] **Step 6: Verify PDF export**

Run in DevTools console on the preview page:

```js
await fetch(`/api/reports/${reportId}/export/pdf`, { method: 'POST', credentials: 'include' })
  .then((r) => r.blob())
  .then((b) => {
    const url = URL.createObjectURL(b);
    window.open(url, '_blank');
  });
```

Expected: a new tab opens showing a PDF with the cover, section headings, and text blocks. First export takes 2-5 s (Chromium warm-up); subsequent exports <1 s.

- [ ] **Step 7: Flip the README row**

Edit `planning/implementation-plans/README.md`:

```
| 13 | 5 | Report rendering pipeline + Secretary department | Draft | `2026-04-17-phase-13-report-pipeline-and-secretary.md` |
```

- [ ] **Step 8: Commit the docs flip**

```bash
git add planning/implementation-plans/README.md
git commit -m "docs(plan): mark Phase 13 (report pipeline + Secretary) as Draft"
```

---
