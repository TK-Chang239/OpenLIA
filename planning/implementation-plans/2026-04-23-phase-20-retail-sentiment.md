# Retail Sentiment Department Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Audit 2026-04-23 normalizations (apply before executing this plan):**
> - All IDs are UUID strings (`String(36)`) generated via `str(uuid.uuid4())`. No prefixed short-hex ids.
> - Backend imports: `User` from `openlia_server.db.models.auth`; `RsUserConfig`, `RsSnapshot` from `openlia_server.db.models.dashboard` (shipped Plan 1B). `RsClassificationLog` lives in a new models file once this plan ships Task 3.
> - Auth via `build_require_auth(...)` router factories; no bare `require_user` helper.
> - Runtime imports: `from openlia.llm.runtime.messages import ChatRequest, ToolSchema`, `from openlia.llm.runtime.events import to_wire`. RS does **not** use `ReportRequest` or `ReportRunner` (no markdown reports generated).
> - HTTP: backend routers use **bare prefixes** (`/departments/retail_sentiment/...`). Frontend hits `/api/departments/retail_sentiment/...` — the Vite proxy strips `/api`.
> - Scheduler: one schedule per `(job_type, user_id)`. RS adds a new `JobType.RS_SNAPSHOT` enum value in Task 9. No concurrent schedules per user.
> - `String(36)` ids on every new FK and PK. Use `uuid.uuid4()` everywhere.

**Goal:** Ship the Retail Sentiment (RS) department — a 12-metric, 3-tab sentiment-monitoring dashboard that periodically ingests social posts + news headlines + financial-provider sentiment data, classifies raw items via batch LLM NLP, computes a reliability-weighted composite across sources, detects 7-day volume spikes, and renders an Overview / Evidence / Insights dashboard with configurable per-user thresholds and cron-scheduled automatic snapshots.

**Architecture:**
- **Core** gets a `RetailSentimentDepartment` class (no `valid_modes` — RS is a dashboard department, not a report-producer), a `retail_sentiment/classifier.py` batch NLP wrapper over the Quick-tier LLM runtime, a `retail_sentiment/metrics.py` Pandas engine computing all 12 metrics, a `retail_sentiment/reliability.py` source-weighting matrix, a `retail_sentiment/spike_detector.py` 7-day volume spike detector, and updates `prompts/retail_sentiment.yaml` to add a **batch** prompt (the existing prompt is single-post — it stays as a fallback).
- **Server** adds one new table — `rs_classification_log` (LLM classification audit trail) — a new `JobType.RS_SNAPSHOT` enum value + `RetailSentimentExecutor` + scheduler-wiring registration, a `services/rs_config.py` CRUD layer over `RsUserConfig`, a `services/rs_snapshot.py` read/write layer over `RsSnapshot`, a `services/rs_runner.py` pipeline orchestrator that fetches → classifies in batches → computes metrics → writes snapshot, and a `routes/departments/retail_sentiment.py` surface with 8 endpoints (dashboard/history/config/run/schedule/stock/spikes).
- **Frontend** replaces `frontend/src/pages/departments/RetailSentiment.tsx` (currently a `PagePlaceholder`) with a full page composition. Three tabs: `OverviewTab`, `PerStockTab`, `SpikesTab`. Sub-components render the 12 metric cards, trend charts, reliability badges, schedule editor, and settings drawer.

**Tech Stack:**
- Backend: FastAPI, SQLAlchemy 2.x, Pydantic v2, Alembic, APScheduler 4.x (hot-reload), Pandas (metrics), NumPy (stats).
- Frontend: React 18 + TypeScript strict, Framer Motion, Recharts (trend charts + sparklines), Radix UI primitives (`Dialog`, `Popover`, `Tabs`, `ToggleGroup`), Zod, Vitest + React Testing Library.
- Shared: Jinja2 + YAML prompts (`retail_sentiment.yaml` extended to add a `batch_classify` template).

**Dependencies:**
- Plan 1A: `users`, `watchlists`, `watchlist_items` tables; `SessionLocal`.
- Plan 1B: `RsUserConfig`, `RsSnapshot`, `JobRun`, `UserNotification` tables. `rs_classification_log` is **not** in Plan 1B — this plan adds it via Alembic (see Task 3).
- Plan 2: session middleware; all endpoints authenticated.
- Plan 3: data adapter dispatcher; `social_sentiment`, `company_news`, `stock_quote`, `historical_prices` adapters. Optional: `options_data`, `short_interest`, `institutional_holdings`.
- Plan 4: LLM provider system; `DEPARTMENT_DEFAULT_TIERS["retail_sentiment"] == QUICK`.
- Plan 5: `PromptLoader` (Jinja2 YAML), LLM runtime adapter invocation. No `ReportRunner` (no markdown reports).
- Plan 6: `SchedulerService`, `BaseExecutor`, `job_runs` insertion, `user_notifications` fan-out. **New** `JobType.RS_SNAPSHOT` added here (this plan owns the enum extension).
- Plan 8: frontend shell (routing, auth context, design tokens).
- Plan 12: `SaveToRepo`, `FileViewer` are **not** used (RS is a dashboard — no saveable artifacts).

**Unblocks:** no downstream plan consumers — RS is a leaf department. (Plan 16 Morning Briefing could optionally cite RS snapshots as a section input; that follow-up is deferred.)

---

## Design Rules

1. **RS is a dashboard department.** No chat interface, no markdown reports, no `chat_sessions` rows, no `reports` rows. Users see metric cards, trend charts, an evidence feed, and a narrative synthesis paragraph produced by a Quick-tier LLM call on the active signal set. Nothing persists to `reports`.
2. **Snapshots are global, per-ticker.** The `rs_snapshots` table is shared across all users. Each snapshot row captures one ticker's 12-metric state at `captured_at`. Users' watchlists are layered at read-time via the shared `watchlists` / `watchlist_items` tables (Plan 1A). This keeps LLM classification costs at O(tickers) rather than O(users × tickers).
3. **User config is per-user.** `RsUserConfig` holds tab state, metric-level thresholds, refresh interval, and filter presets. Thresholds (divergence z-score, buzz multiplier, momentum window, etc.) feed the signal detector at read-time — they do **not** re-trigger a snapshot recompute.
4. **NLP classification is batched by ticker.** Items for the same ticker are bundled (default batch size 30) and sent in a single LLM call. Response must be a JSON array matching the input length. On schema violation, retry once; on second failure fall back to neutral classification and log the error.
5. **Every LLM classification call is audited.** Each batch writes exactly one `rs_classification_log` row with `batch_id`, `ticker`, `model_ref`, `item_count`, `prompt_tokens`, `completion_tokens`, `latency_ms`, and `error` (nullable). This gives cost attribution and enables retrospective accuracy sampling.
6. **Cross-source reliability is a fixed weighting matrix.** Sources: `financial_provider`, `social_media`, `cross_platform`. Default weights `0.40 / 0.35 / 0.25`. User can override via `RsUserConfig.metric_settings["cross_source_weights"]`. Weights always renormalized to sum to 1 at read-time.
7. **Spike detection runs on every snapshot.** The `spike_detector` compares the latest snapshot's buzz volume against a 7-day rolling mean + stddev. A spike fires when `buzz > mean + 2 * stddev`. Spikes are surfaced through `GET /spikes` and through the `SpikesTab` UI; there is no separate spike table — spikes are computed on-the-fly from historical `rs_snapshots` rows.
8. **Tier is fixed at `quick`.** All NLP classification uses the user's Quick-tier model. Narrative synthesis (single LLM call per snapshot) also uses Quick — no `everyday` escalation. Per `DEPARTMENT_DEFAULT_TIERS["retail_sentiment"] = QUICK` (added in Plan 4; if not present this plan asserts it via Task 1).
9. **Graceful degradation when advanced data is missing.** Options, short interest, institutional holdings are optional. When a provider capability is missing, the corresponding metric is omitted from the snapshot (`snapshot_data` has no key for it). The frontend renders disabled cards labeled "Requires <capability>." Basic metrics (1, 2, 3, 4, 5, 6, 7, 10, 12) must always compute if `company_news` + `social_sentiment` are configured.
10. **Scheduled runs write to `user_notifications` via Plan 6.** `RetailSentimentExecutor` fans out notifications per user watching the ticker(s) that fired a signal. This is the only per-user channel — the snapshot itself is global.
11. **On-demand runs bypass the scheduler.** `POST /run` synchronously kicks off the same pipeline the executor uses, blocks until complete (no SSE — RS is polling-based per the spec), and returns the snapshot IDs.
12. **Schedule constraint: one `RS_SNAPSHOT` per user.** The scheduler-level lock is `(JobType.RS_SNAPSHOT, user_id)`. The schedule's `label` can carry a user-facing name; `days_of_week` selects run days.
13. **All IDs are `String(36)` UUIDs.** Generate with `str(uuid.uuid4())`.
14. **TDD everywhere.** Failing test → implementation → green run → commit per step.
15. **No placeholders.** Real code, real commands, real expected output in every step.

---

## File Structure

### Core (`packages/core/src/openlia/`)

```
prompts/
└── retail_sentiment.yaml                # MODIFY — append batch_classify + synthesis sections
departments/
└── retail_sentiment.py                  # NEW — RetailSentimentDepartment class
retail_sentiment/
├── __init__.py                          # NEW — package marker + re-exports
├── schemas.py                           # NEW — Pydantic DTOs (ClassifiedItem, MetricSnapshot, Signal, SpikeEvent)
├── classifier.py                        # NEW — batch NLP classification wrapper
├── metrics.py                           # NEW — 12-metric Pandas engine
├── reliability.py                       # NEW — cross-source weighting matrix
└── spike_detector.py                    # NEW — 7-day volume spike detector
```

### Server (`packages/server/src/openlia_server/`)

```
db/
├── models/
│   └── dashboard.py                     # MODIFY — append RsClassificationLog
└── migrations/versions/
    └── 2026_04_23_1900_rs_classification_log.py    # NEW
scheduler/
├── registry.py                          # MODIFY — add JobType.RS_SNAPSHOT
├── executors/
│   └── rs.py                            # NEW — RetailSentimentExecutor
└── wiring.py                            # MODIFY — register RetailSentimentExecutor
services/
├── rs_config.py                         # NEW — RsUserConfig CRUD
├── rs_snapshot.py                       # NEW — RsSnapshot read/write + history queries
└── rs_runner.py                         # NEW — pipeline orchestrator
routes/departments/
└── retail_sentiment.py                  # NEW — dashboard/history/config/run/schedule/stocks/spikes
```

### Frontend (`frontend/src/`)

```
api/
└── retail-sentiment.ts                  # NEW — typed client
pages/departments/
└── RetailSentiment.tsx                  # REPLACE placeholder with composition
components/retail-sentiment/
├── OverviewTab.tsx                      # NEW — overall + per-stock scores + market mood
├── PerStockTab.tsx                      # NEW — per-ticker deep-dive view
├── SpikesTab.tsx                        # NEW — detected spike list
├── MetricCard.tsx                       # NEW — single metric card (value + trend + reliability)
├── SentimentGauge.tsx                   # NEW — SVG gauge arc for sentiment score
├── TrendChart.tsx                       # NEW — Recharts line chart wrapper
├── ReliabilityBadge.tsx                 # NEW — source count pill
├── SignalAlert.tsx                      # NEW — red/amber/green alert card
├── ScheduleEditor.tsx                   # NEW — cron schedule modal
└── SettingsDrawer.tsx                   # NEW — thresholds + cross-source weights drawer
hooks/
├── useRsDashboard.ts                    # NEW — SWR fetch of /dashboard
├── useRsHistory.ts                      # NEW — SWR fetch of /dashboard/history
├── useRsConfig.ts                       # NEW — SWR fetch + mutate /config
├── useRsSpikes.ts                       # NEW — SWR fetch of /spikes
└── useRsSchedule.ts                     # NEW — SWR fetch + mutate /schedule
lib/retail-sentiment/
└── metric-catalog.ts                    # NEW — metric IDs, labels, units, reliability refs
```

---

## Task Overview

1. Core — `RetailSentimentDepartment` class.
2. Core — `retail_sentiment/schemas.py` Pydantic DTOs.
3. Core — Append batch + synthesis prompts to `retail_sentiment.yaml`.
4. Core — `retail_sentiment/classifier.py` (batch NLP wrapper).
5. Core — `retail_sentiment/reliability.py` (source weighting).
6. Core — `retail_sentiment/metrics.py` (all 12 metrics — one test per metric).
7. Core — `retail_sentiment/spike_detector.py` (7-day spike detection).
8. Server — `RsClassificationLog` model + Alembic migration.
9. Server — Add `JobType.RS_SNAPSHOT` + registry mapping.
10. Server — `services/rs_config.py` CRUD.
11. Server — `services/rs_snapshot.py` read/write + history.
12. Server — `services/rs_runner.py` pipeline orchestrator.
13. Server — `RetailSentimentExecutor` + scheduler wiring.
14. Server — Routes: `/dashboard` + `/dashboard/history`.
15. Server — Routes: `/config` GET/PUT.
16. Server — Routes: `/run` POST.
17. Server — Routes: `/schedule` GET/PUT.
18. Server — Routes: `/stocks/{ticker}/sentiment` GET.
19. Server — Routes: `/spikes` GET.
20. Frontend — Typed client (`api/retail-sentiment.ts`).
21. Frontend — Hooks (`useRsDashboard`, `useRsHistory`, `useRsConfig`, `useRsSpikes`, `useRsSchedule`).
22. Frontend — `MetricCard` + `SentimentGauge` + `ReliabilityBadge`.
23. Frontend — `OverviewTab`.
24. Frontend — `PerStockTab` + `TrendChart`.
25. Frontend — `SpikesTab`.
26. Frontend — `ScheduleEditor` + `SettingsDrawer` + `SignalAlert`.
27. Frontend — `RetailSentiment.tsx` page composition.
28. Manual smoke test + flip README row to Draft.

---

### Task 1: Core — `RetailSentimentDepartment` class

The department advertises: name, display name, prompt name, tier, basic + optional data requirement lists. Dashboard departments do not expose `valid_modes`.

**Files:**
- Create: `packages/core/src/openlia/departments/retail_sentiment.py`
- Modify: `packages/core/src/openlia/departments/__init__.py` (export `RetailSentimentDepartment`)
- Test: `packages/core/tests/departments/test_retail_sentiment.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/departments/test_retail_sentiment.py
from openlia.departments.retail_sentiment import RetailSentimentDepartment


def test_rs_identifies_itself():
    d = RetailSentimentDepartment()
    assert d.name == "retail_sentiment"
    assert d.display_name == "Retail Sentiment"
    assert d.prompt_name == "retail_sentiment"


def test_rs_tier_is_quick():
    assert RetailSentimentDepartment().tier == "quick"


def test_rs_basic_data_requirements():
    reqs = RetailSentimentDepartment().data_requirement_types
    for name in ("social_sentiment", "company_news", "stock_quote"):
        assert name in reqs


def test_rs_optional_data_requirements():
    soft = RetailSentimentDepartment().optional_requirement_types
    for name in (
        "historical_prices",
        "options_data",
        "short_interest",
        "institutional_holdings",
    ):
        assert name in soft


def test_rs_is_dashboard_department():
    d = RetailSentimentDepartment()
    assert d.department_type == "dashboard"
    assert not hasattr(d, "valid_modes") or d.valid_modes == ()


def test_rs_has_no_extra_tools():
    assert RetailSentimentDepartment().extra_tools == ()
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `uv run pytest packages/core/tests/departments/test_retail_sentiment.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'openlia.departments.retail_sentiment'`.

- [ ] **Step 3: Write the department class**

```python
# packages/core/src/openlia/departments/retail_sentiment.py
"""Retail Sentiment department — dashboard, no report generation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from openlia.departments.base import Tier


@dataclass(frozen=True)
class RetailSentimentDepartment:
    name: str = "retail_sentiment"
    display_name: str = "Retail Sentiment"
    prompt_name: str = "retail_sentiment"
    department_type: str = "dashboard"
    tier: Tier = "quick"
    data_requirement_types: tuple[str, ...] = (
        "social_sentiment",
        "company_news",
        "stock_quote",
    )
    optional_requirement_types: tuple[str, ...] = (
        "historical_prices",
        "options_data",
        "short_interest",
        "institutional_holdings",
    )
    extra_tools: tuple[dict[str, Any], ...] = ()
    valid_modes: tuple[str, ...] = ()
```

- [ ] **Step 4: Export the class**

In `packages/core/src/openlia/departments/__init__.py`, add:

```python
from openlia.departments.retail_sentiment import RetailSentimentDepartment

__all__ = [*__all__, "RetailSentimentDepartment"]
```

- [ ] **Step 5: Run the test to confirm it passes**

Run: `uv run pytest packages/core/tests/departments/test_retail_sentiment.py -v`
Expected: PASS (6 tests).

- [ ] **Step 6: Commit**

```bash
git add packages/core/src/openlia/departments/retail_sentiment.py \
        packages/core/src/openlia/departments/__init__.py \
        packages/core/tests/departments/test_retail_sentiment.py
git commit -m "feat(core): add RetailSentimentDepartment dashboard class"
```

---

### Task 2: Core — `retail_sentiment/schemas.py` Pydantic DTOs

Shared Pydantic models used by classifier, metrics, runner, and routes.

**Files:**
- Create: `packages/core/src/openlia/retail_sentiment/__init__.py`
- Create: `packages/core/src/openlia/retail_sentiment/schemas.py`
- Test: `packages/core/tests/retail_sentiment/__init__.py` (empty)
- Test: `packages/core/tests/retail_sentiment/test_schemas.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/retail_sentiment/test_schemas.py
from datetime import datetime, UTC

import pytest
from pydantic import ValidationError

from openlia.retail_sentiment.schemas import (
    ClassificationLabel,
    ClassifiedItem,
    MetricSnapshot,
    RawSocialPost,
    SignalAlert,
    SpikeEvent,
)


def test_classification_label_values():
    for v in ("bullish", "bearish", "neutral"):
        assert ClassificationLabel(v).value == v


def test_classified_item_requires_matching_id():
    item = ClassifiedItem(
        id="post_1",
        classification="bullish",
        confidence=0.8,
        key_phrases=["strong guidance"],
    )
    assert item.id == "post_1"
    assert 0 <= item.confidence <= 1


def test_classified_item_confidence_bounds():
    with pytest.raises(ValidationError):
        ClassifiedItem(id="x", classification="bullish", confidence=1.5, key_phrases=[])


def test_raw_social_post_round_trip():
    p = RawSocialPost(
        id="t_1",
        ticker="AAPL",
        source="x_twitter",
        text="Loving $AAPL here",
        engagement={"likes": 120, "retweets": 10, "replies": 3},
        created_at=datetime.now(UTC),
    )
    assert p.engagement["likes"] == 120


def test_metric_snapshot_all_12_metrics():
    s = MetricSnapshot(
        ticker="AAPL",
        captured_at=datetime.now(UTC),
        sentiment_score=0.42,
        buzz_volume=1.8,
        sentiment_momentum=0.05,
        bull_bear_ratio=0.62,
        buzz_sentiment_divergence=1.2,
        social_velocity=0.3,
        cross_source_agreement=0.66,
        put_call_ratio=None,
        short_interest_pressure=None,
        narrative_concentration=0.45,
        institutional_retail_gap=None,
        event_sensitivity=1.7,
        source_breakdown={"financial_provider": 0.5, "social_media": 0.4, "cross_platform": 0.1},
    )
    assert -1 <= s.sentiment_score <= 1
    assert s.buzz_volume >= 0


def test_signal_alert_severity_enum():
    a = SignalAlert(
        ticker="AAPL",
        metric_id="buzz_sentiment_divergence",
        severity="panic",
        message="Divergence z=2.5 — high buzz with negative tone",
        value=2.5,
    )
    assert a.severity in {"panic", "stealth_recovery", "caution", "info"}


def test_spike_event_fields():
    e = SpikeEvent(
        ticker="AAPL",
        detected_at=datetime.now(UTC),
        buzz=2500,
        baseline_mean=800,
        baseline_stddev=200,
        z_score=8.5,
    )
    assert e.z_score > 2
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `uv run pytest packages/core/tests/retail_sentiment/test_schemas.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the schemas**

```python
# packages/core/src/openlia/retail_sentiment/__init__.py
"""Retail Sentiment core package — classification, metrics, reliability, spikes."""

from openlia.retail_sentiment.schemas import (
    ClassificationLabel,
    ClassifiedItem,
    MetricSnapshot,
    RawSocialPost,
    SignalAlert,
    SpikeEvent,
)

__all__ = [
    "ClassificationLabel",
    "ClassifiedItem",
    "MetricSnapshot",
    "RawSocialPost",
    "SignalAlert",
    "SpikeEvent",
]
```

```python
# packages/core/src/openlia/retail_sentiment/schemas.py
"""Pydantic DTOs shared across classifier, metrics, runner, routes."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ClassificationLabel(StrEnum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class RawSocialPost(BaseModel):
    """A single raw social post or news article prior to classification."""

    model_config = ConfigDict(frozen=True)

    id: str
    ticker: str
    source: str
    text: str
    engagement: dict[str, int] = Field(default_factory=dict)
    created_at: datetime


class ClassifiedItem(BaseModel):
    """Result of a single NLP classification for one post."""

    model_config = ConfigDict(frozen=True)

    id: str
    classification: ClassificationLabel
    confidence: float = Field(ge=0.0, le=1.0)
    key_phrases: list[str] = Field(default_factory=list)


class MetricSnapshot(BaseModel):
    """All 12 metrics for a single ticker at a point in time."""

    model_config = ConfigDict(frozen=True)

    ticker: str
    captured_at: datetime

    # 12 metrics — optional ones are None when the required data source is missing.
    sentiment_score: float  # Metric 1
    buzz_volume: float  # Metric 2 (ratio vs 30d MA)
    sentiment_momentum: float  # Metric 3
    bull_bear_ratio: float  # Metric 4 (0..1)
    buzz_sentiment_divergence: float  # Metric 5 (z-score difference)
    social_velocity: float  # Metric 6 (pct change day-over-day)
    cross_source_agreement: float  # Metric 7 (0..1)
    put_call_ratio: float | None = None  # Metric 8
    short_interest_pressure: float | None = None  # Metric 9
    narrative_concentration: float | None = None  # Metric 10
    institutional_retail_gap: float | None = None  # Metric 11
    event_sensitivity: float | None = None  # Metric 12
    source_breakdown: dict[str, float] = Field(default_factory=dict)


SignalSeverity = Literal["panic", "stealth_recovery", "caution", "info"]


class SignalAlert(BaseModel):
    """An active signal fired by the metric engine at snapshot time."""

    model_config = ConfigDict(frozen=True)

    ticker: str
    metric_id: str
    severity: SignalSeverity
    message: str
    value: float


class SpikeEvent(BaseModel):
    """A 7-day volume spike detection result."""

    model_config = ConfigDict(frozen=True)

    ticker: str
    detected_at: datetime
    buzz: float
    baseline_mean: float
    baseline_stddev: float
    z_score: float
```

- [ ] **Step 4: Run the test to confirm it passes**

Run: `uv run pytest packages/core/tests/retail_sentiment/test_schemas.py -v`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/retail_sentiment/__init__.py \
        packages/core/src/openlia/retail_sentiment/schemas.py \
        packages/core/tests/retail_sentiment/__init__.py \
        packages/core/tests/retail_sentiment/test_schemas.py
git commit -m "feat(core): add retail_sentiment Pydantic schemas"
```

---

### Task 3: Core — Append batch + synthesis prompts to `retail_sentiment.yaml`

The existing prompt is single-post `batch.classify_sentiment`. Add a batch template that accepts a list and produces a JSON array, plus a `synthesis.narrative` template for the Insights-tab paragraph.

**Files:**
- Modify: `packages/core/src/openlia/prompts/retail_sentiment.yaml`
- Test: `packages/core/tests/prompts/test_retail_sentiment_prompt.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/prompts/test_retail_sentiment_prompt.py
from pathlib import Path

import pytest

from openlia.llm.runtime.prompts import PromptLoader


@pytest.fixture
def loader() -> PromptLoader:
    root = Path(__file__).resolve().parents[2] / "src" / "openlia" / "prompts"
    return PromptLoader(root=root)


def test_batch_classify_system_prompt_exists(loader: PromptLoader) -> None:
    text = loader.render(
        "retail_sentiment",
        "batch.classify_batch.system",
        {},
    )
    assert "json array" in text.lower() or "array" in text.lower()
    assert "bullish" in text.lower()
    assert "bearish" in text.lower()
    assert "neutral" in text.lower()


def test_batch_classify_user_prompt_embeds_items(loader: PromptLoader) -> None:
    items = [
        {"id": "p1", "source": "x_twitter", "text": "Love this stock", "engagement": {"likes": 10}},
        {"id": "p2", "source": "x_twitter", "text": "Going to zero", "engagement": {"likes": 3}},
    ]
    text = loader.render(
        "retail_sentiment",
        "batch.classify_batch.user",
        {"ticker": "AAPL", "items": items},
    )
    assert "AAPL" in text
    assert "p1" in text
    assert "p2" in text


def test_synthesis_narrative_mentions_signal_set(loader: PromptLoader) -> None:
    text = loader.render(
        "retail_sentiment",
        "synthesis.narrative.system",
        {},
    )
    assert "signal" in text.lower()
    assert "narrative" in text.lower()


def test_synthesis_narrative_user_embeds_signals(loader: PromptLoader) -> None:
    signals = [
        {"metric_id": "buzz_sentiment_divergence", "severity": "panic", "value": 2.5},
        {"metric_id": "sentiment_momentum", "severity": "info", "value": -0.08},
    ]
    text = loader.render(
        "retail_sentiment",
        "synthesis.narrative.user",
        {"ticker": "AAPL", "signals": signals},
    )
    assert "AAPL" in text
    assert "buzz_sentiment_divergence" in text
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `uv run pytest packages/core/tests/prompts/test_retail_sentiment_prompt.py -v`
Expected: FAIL (keys `batch.classify_batch.*` and `synthesis.narrative.*` not found).

- [ ] **Step 3: Extend the YAML prompt**

Append (do not replace existing `batch.classify_sentiment`) these sections to
`packages/core/src/openlia/prompts/retail_sentiment.yaml`:

```yaml
batch:
  classify_batch:
    system: |
      You classify a batch of social-media posts and news headlines about a single
      ticker. Output a strict JSON array with one object per input item, in the
      exact order the input items were provided. Each object has:

        {"id": "<string>", "classification": "bullish|bearish|neutral",
         "confidence": <float 0..1>, "key_phrases": ["<string>", ...]}

      Classification must be one of: bullish, bearish, neutral.
      Do not include any prose outside the JSON array.

      {% include "shared/output_discipline.yaml.j2" %}
    user: |
      Ticker: {{ ticker }}

      Classify each of the following {{ items|length }} items. Output a JSON
      array of {{ items|length }} objects in the same order.

      {% for it in items %}
      - id: {{ it.id }}
        source: {{ it.source }}
        text: |
          {{ it.text }}
        engagement: {{ it.engagement | tojson }}
      {% endfor %}

synthesis:
  narrative:
    system: |
      You are a retail-sentiment analyst. Given the set of active signals for
      a single ticker, produce a brief 2-3 sentence narrative synthesis that
      ties the signals together. Be factual, avoid hedging, and do not give
      investment advice. Use plain English. Output plain text only — no JSON,
      no markdown headers.
    user: |
      Ticker: {{ ticker }}

      Active signals:
      {% for s in signals %}
      - metric={{ s.metric_id }}, severity={{ s.severity }}, value={{ s.value }}
      {% endfor %}

      Write a 2-3 sentence synthesis that ties these signals together and
      explains what a reasonable reader should focus on next.
```

- [ ] **Step 4: Run the test to confirm it passes**

Run: `uv run pytest packages/core/tests/prompts/test_retail_sentiment_prompt.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/prompts/retail_sentiment.yaml \
        packages/core/tests/prompts/test_retail_sentiment_prompt.py
git commit -m "feat(core): add batch + synthesis prompts to retail_sentiment.yaml"
```

---

### Task 4: Core — `retail_sentiment/classifier.py` (batch NLP wrapper)

`BatchClassifier.classify(posts, ticker, quick_llm)` bundles `posts` in batches of 30 (configurable), renders the batch prompt, invokes the Quick-tier LLM, parses the JSON array, validates each element, retries once on validation error, and falls back to neutral on a second failure. Returns `list[ClassifiedItem]` in input order.

**Files:**
- Create: `packages/core/src/openlia/retail_sentiment/classifier.py`
- Test: `packages/core/tests/retail_sentiment/test_classifier.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/retail_sentiment/test_classifier.py
from datetime import UTC, datetime

import pytest

from openlia.retail_sentiment.classifier import BatchClassifier, ClassifierResult
from openlia.retail_sentiment.schemas import ClassificationLabel, RawSocialPost


class _FakeLLM:
    """Fake Quick-tier LLM that returns pre-canned responses per invocation."""

    def __init__(self, responses: list[str]) -> None:
        self.responses = list(responses)
        self.calls: list[dict] = []

    async def complete(self, *, system: str, user: str, **_kwargs) -> dict:
        self.calls.append({"system": system, "user": user})
        return {
            "text": self.responses.pop(0),
            "prompt_tokens": 100,
            "completion_tokens": 50,
            "latency_ms": 42,
        }


def _post(idx: int, text: str = "hello") -> RawSocialPost:
    return RawSocialPost(
        id=f"p{idx}",
        ticker="AAPL",
        source="x_twitter",
        text=text,
        engagement={"likes": idx},
        created_at=datetime.now(UTC),
    )


@pytest.mark.asyncio
async def test_classify_empty_posts_returns_empty() -> None:
    clf = BatchClassifier(llm=_FakeLLM([]), batch_size=30)
    result = await clf.classify(posts=[], ticker="AAPL")
    assert result.items == []
    assert result.batches_called == 0


@pytest.mark.asyncio
async def test_classify_single_batch_valid_response() -> None:
    posts = [_post(1), _post(2)]
    llm = _FakeLLM([
        '[{"id":"p1","classification":"bullish","confidence":0.8,"key_phrases":["love"]},'
        '{"id":"p2","classification":"bearish","confidence":0.9,"key_phrases":["zero"]}]'
    ])
    clf = BatchClassifier(llm=llm, batch_size=30)
    result = await clf.classify(posts=posts, ticker="AAPL")
    assert len(result.items) == 2
    assert result.items[0].classification == ClassificationLabel.BULLISH
    assert result.items[1].classification == ClassificationLabel.BEARISH
    assert result.batches_called == 1


@pytest.mark.asyncio
async def test_classify_splits_into_multiple_batches() -> None:
    posts = [_post(i) for i in range(35)]
    llm = _FakeLLM([
        "[" + ",".join(
            f'{{"id":"p{i}","classification":"neutral","confidence":0.5,"key_phrases":[]}}'
            for i in range(30)
        ) + "]",
        "[" + ",".join(
            f'{{"id":"p{i}","classification":"neutral","confidence":0.5,"key_phrases":[]}}'
            for i in range(30, 35)
        ) + "]",
    ])
    clf = BatchClassifier(llm=llm, batch_size=30)
    result = await clf.classify(posts=posts, ticker="AAPL")
    assert len(result.items) == 35
    assert result.batches_called == 2


@pytest.mark.asyncio
async def test_classify_retries_once_on_invalid_json() -> None:
    posts = [_post(1)]
    llm = _FakeLLM([
        "not valid json at all",
        '[{"id":"p1","classification":"bullish","confidence":0.7,"key_phrases":[]}]',
    ])
    clf = BatchClassifier(llm=llm, batch_size=30)
    result = await clf.classify(posts=posts, ticker="AAPL")
    assert len(result.items) == 1
    assert result.items[0].classification == ClassificationLabel.BULLISH
    assert result.retries == 1


@pytest.mark.asyncio
async def test_classify_falls_back_to_neutral_on_second_failure() -> None:
    posts = [_post(1), _post(2)]
    llm = _FakeLLM(["garbage 1", "still garbage"])
    clf = BatchClassifier(llm=llm, batch_size=30)
    result = await clf.classify(posts=posts, ticker="AAPL")
    assert len(result.items) == 2
    assert all(i.classification == ClassificationLabel.NEUTRAL for i in result.items)
    assert result.fallback_count == 2


@pytest.mark.asyncio
async def test_classify_preserves_input_order() -> None:
    posts = [_post(i) for i in (5, 1, 9, 3)]
    llm = _FakeLLM([
        '[{"id":"p5","classification":"bullish","confidence":1.0,"key_phrases":[]},'
        '{"id":"p1","classification":"bearish","confidence":1.0,"key_phrases":[]},'
        '{"id":"p9","classification":"neutral","confidence":1.0,"key_phrases":[]},'
        '{"id":"p3","classification":"bullish","confidence":1.0,"key_phrases":[]}]'
    ])
    clf = BatchClassifier(llm=llm, batch_size=30)
    result = await clf.classify(posts=posts, ticker="AAPL")
    assert [i.id for i in result.items] == ["p5", "p1", "p9", "p3"]


@pytest.mark.asyncio
async def test_classifier_records_token_usage() -> None:
    posts = [_post(1)]
    llm = _FakeLLM(['[{"id":"p1","classification":"bullish","confidence":0.5,"key_phrases":[]}]'])
    clf = BatchClassifier(llm=llm, batch_size=30)
    result = await clf.classify(posts=posts, ticker="AAPL")
    assert result.prompt_tokens == 100
    assert result.completion_tokens == 50
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `uv run pytest packages/core/tests/retail_sentiment/test_classifier.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the classifier**

```python
# packages/core/src/openlia/retail_sentiment/classifier.py
"""Batch NLP classifier — bundles posts, invokes Quick-tier LLM, parses responses."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from pydantic import ValidationError

from openlia.llm.runtime.prompts import PromptLoader
from openlia.retail_sentiment.schemas import (
    ClassificationLabel,
    ClassifiedItem,
    RawSocialPost,
)

logger = logging.getLogger(__name__)


class QuickLLM(Protocol):
    async def complete(self, *, system: str, user: str, **kwargs: Any) -> dict[str, Any]: ...


@dataclass(frozen=True)
class ClassifierResult:
    items: list[ClassifiedItem]
    batches_called: int = 0
    retries: int = 0
    fallback_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    latency_ms_total: int = 0


@dataclass
class BatchClassifier:
    llm: QuickLLM
    batch_size: int = 30
    prompt_loader: PromptLoader | None = None

    def __post_init__(self) -> None:
        if self.prompt_loader is None:
            root = Path(__file__).resolve().parents[1] / "prompts"
            self.prompt_loader = PromptLoader(root=root)

    async def classify(self, *, posts: list[RawSocialPost], ticker: str) -> ClassifierResult:
        if not posts:
            return ClassifierResult(items=[])

        all_items: list[ClassifiedItem] = []
        batches = 0
        retries = 0
        fallbacks = 0
        prompt_toks = 0
        completion_toks = 0
        latency = 0

        for start in range(0, len(posts), self.batch_size):
            chunk = posts[start : start + self.batch_size]
            assert self.prompt_loader is not None
            system = self.prompt_loader.render(
                "retail_sentiment", "batch.classify_batch.system", {}
            )
            user = self.prompt_loader.render(
                "retail_sentiment",
                "batch.classify_batch.user",
                {
                    "ticker": ticker,
                    "items": [
                        {
                            "id": p.id,
                            "source": p.source,
                            "text": p.text,
                            "engagement": p.engagement,
                        }
                        for p in chunk
                    ],
                },
            )

            parsed, used_retry, used_fallback, tok_in, tok_out, lat = (
                await self._invoke_with_retry(system=system, user=user, chunk=chunk)
            )
            batches += 1
            retries += int(used_retry)
            fallbacks += used_fallback
            prompt_toks += tok_in
            completion_toks += tok_out
            latency += lat
            all_items.extend(parsed)

        return ClassifierResult(
            items=all_items,
            batches_called=batches,
            retries=retries,
            fallback_count=fallbacks,
            prompt_tokens=prompt_toks,
            completion_tokens=completion_toks,
            latency_ms_total=latency,
        )

    async def _invoke_with_retry(
        self, *, system: str, user: str, chunk: list[RawSocialPost]
    ) -> tuple[list[ClassifiedItem], bool, int, int, int, int]:
        tok_in = 0
        tok_out = 0
        lat = 0
        used_retry = False
        for attempt in (1, 2):
            response = await self.llm.complete(system=system, user=user)
            tok_in += int(response.get("prompt_tokens", 0))
            tok_out += int(response.get("completion_tokens", 0))
            lat += int(response.get("latency_ms", 0))
            try:
                parsed = self._parse(response["text"], chunk=chunk)
                return parsed, used_retry, 0, tok_in, tok_out, lat
            except (ValueError, ValidationError, KeyError) as exc:
                logger.warning("rs classifier parse failed attempt=%d err=%s", attempt, exc)
                used_retry = attempt == 1
                continue
        # Both attempts failed — fall back to neutral for every item.
        fallback = [
            ClassifiedItem(
                id=p.id, classification=ClassificationLabel.NEUTRAL, confidence=0.0, key_phrases=[]
            )
            for p in chunk
        ]
        return fallback, used_retry, len(chunk), tok_in, tok_out, lat

    @staticmethod
    def _parse(text: str, *, chunk: list[RawSocialPost]) -> list[ClassifiedItem]:
        payload = json.loads(text)
        if not isinstance(payload, list):
            raise ValueError("expected JSON array")
        if len(payload) != len(chunk):
            raise ValueError(f"expected {len(chunk)} items, got {len(payload)}")
        by_id = {p.id: p for p in chunk}
        out: list[ClassifiedItem] = []
        for obj in payload:
            item = ClassifiedItem(
                id=obj["id"],
                classification=ClassificationLabel(obj["classification"]),
                confidence=float(obj["confidence"]),
                key_phrases=list(obj.get("key_phrases", [])),
            )
            if item.id not in by_id:
                raise ValueError(f"unexpected id {item.id!r}")
            out.append(item)
        # Preserve the input order rather than the LLM's output order.
        ordered = {o.id: o for o in out}
        return [ordered[p.id] for p in chunk]
```

- [ ] **Step 4: Run the test to confirm it passes**

Run: `uv run pytest packages/core/tests/retail_sentiment/test_classifier.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/retail_sentiment/classifier.py \
        packages/core/tests/retail_sentiment/test_classifier.py
git commit -m "feat(core): add BatchClassifier for retail sentiment NLP"
```

---

### Task 5: Core — `retail_sentiment/reliability.py` (cross-source weighting)

A small module that normalizes weights and computes the reliability-weighted composite sentiment from per-source sentiment readings.

**Files:**
- Create: `packages/core/src/openlia/retail_sentiment/reliability.py`
- Test: `packages/core/tests/retail_sentiment/test_reliability.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/retail_sentiment/test_reliability.py
import math

import pytest

from openlia.retail_sentiment.reliability import (
    DEFAULT_SOURCE_WEIGHTS,
    ReliabilityMatrix,
    cross_source_agreement,
)


def test_default_weights_sum_to_one():
    total = sum(DEFAULT_SOURCE_WEIGHTS.values())
    assert math.isclose(total, 1.0, abs_tol=1e-9)


def test_default_weights_have_expected_keys():
    assert set(DEFAULT_SOURCE_WEIGHTS.keys()) == {
        "financial_provider",
        "social_media",
        "cross_platform",
    }


def test_reliability_normalizes_custom_weights():
    m = ReliabilityMatrix(weights={"financial_provider": 2.0, "social_media": 2.0})
    total = sum(m.weights.values())
    assert math.isclose(total, 1.0, abs_tol=1e-9)
    assert math.isclose(m.weights["financial_provider"], 0.5, abs_tol=1e-9)


def test_reliability_weighted_score_simple():
    m = ReliabilityMatrix(weights=DEFAULT_SOURCE_WEIGHTS)
    score = m.weighted_score({
        "financial_provider": 0.5,
        "social_media": -0.2,
        "cross_platform": 0.1,
    })
    expected = 0.5 * 0.40 + (-0.2) * 0.35 + 0.1 * 0.25
    assert math.isclose(score, expected, abs_tol=1e-9)


def test_weighted_score_omits_missing_sources():
    m = ReliabilityMatrix(weights=DEFAULT_SOURCE_WEIGHTS)
    # Only 2 sources present — weights of present ones are re-normalized.
    score = m.weighted_score({"financial_provider": 0.5, "social_media": -0.2})
    denom = 0.40 + 0.35
    expected = (0.5 * 0.40 + (-0.2) * 0.35) / denom
    assert math.isclose(score, expected, abs_tol=1e-9)


def test_cross_source_agreement_all_agree_returns_one():
    assert cross_source_agreement({"a": 0.1, "b": 0.2, "c": 0.05}) == 1.0


def test_cross_source_agreement_split():
    agree = cross_source_agreement({"a": 0.3, "b": -0.3})
    assert 0.0 <= agree <= 1.0
    # Two sources, opposite signs = 0.5 (majority = 1 of 2).
    assert agree == pytest.approx(0.5)


def test_cross_source_agreement_empty_returns_zero():
    assert cross_source_agreement({}) == 0.0


def test_cross_source_agreement_ignores_zero_sentiment():
    # Near-zero values are treated as "no opinion" and excluded.
    agree = cross_source_agreement({"a": 0.3, "b": 0.0001, "c": 0.2})
    assert agree == 1.0
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `uv run pytest packages/core/tests/retail_sentiment/test_reliability.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the module**

```python
# packages/core/src/openlia/retail_sentiment/reliability.py
"""Cross-source reliability weighting for retail sentiment."""

from __future__ import annotations

from dataclasses import dataclass, field

DEFAULT_SOURCE_WEIGHTS: dict[str, float] = {
    "financial_provider": 0.40,
    "social_media": 0.35,
    "cross_platform": 0.25,
}

_ZERO_EPSILON = 1e-3


@dataclass
class ReliabilityMatrix:
    """Normalized per-source weights for composite sentiment."""

    weights: dict[str, float] = field(default_factory=lambda: dict(DEFAULT_SOURCE_WEIGHTS))

    def __post_init__(self) -> None:
        total = sum(self.weights.values())
        if total <= 0:
            raise ValueError("reliability weights must sum to > 0")
        self.weights = {k: v / total for k, v in self.weights.items()}

    def weighted_score(self, per_source: dict[str, float]) -> float:
        """Compute the weighted average of per-source sentiment, renormalizing."""

        numerator = 0.0
        denom = 0.0
        for source, value in per_source.items():
            w = self.weights.get(source, 0.0)
            if w <= 0:
                continue
            numerator += value * w
            denom += w
        if denom == 0:
            return 0.0
        return numerator / denom


def cross_source_agreement(per_source: dict[str, float]) -> float:
    """Return share of non-neutral sources whose sign matches the majority sign."""

    opinionated = {k: v for k, v in per_source.items() if abs(v) >= _ZERO_EPSILON}
    if not opinionated:
        return 0.0
    positives = sum(1 for v in opinionated.values() if v > 0)
    negatives = sum(1 for v in opinionated.values() if v < 0)
    majority = max(positives, negatives)
    return majority / len(opinionated)
```

- [ ] **Step 4: Run the test to confirm it passes**

Run: `uv run pytest packages/core/tests/retail_sentiment/test_reliability.py -v`
Expected: PASS (9 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/retail_sentiment/reliability.py \
        packages/core/tests/retail_sentiment/test_reliability.py
git commit -m "feat(core): add reliability matrix + cross-source agreement"
```

---

### Task 6: Core — `retail_sentiment/metrics.py` (12-metric Pandas engine)

One function per metric. Each metric takes a Pandas DataFrame of classified items + historical sentiment + auxiliary data, and returns a float (or None if required inputs are missing). `compute_snapshot()` composes all 12 into a `MetricSnapshot`.

**Metric names (cite spec `retail-sentiment-dashboard-design.md §Metric Definitions`):**
1. `sentiment_score` — `(positive - negative) / total`
2. `buzz_volume` — `count_today / mean(count_last_30d)`
3. `sentiment_momentum` — `SMA(sentiment, N)_today - SMA(sentiment, N)_yesterday`
4. `bull_bear_ratio` — `bullish / (bullish + bearish)`
5. `buzz_sentiment_divergence` — `zscore(buzz_30d) - zscore(sentiment_30d)`
6. `social_velocity` — `(buzz_today - buzz_yesterday) / buzz_yesterday`
7. `cross_source_agreement` — from reliability module
8. `put_call_ratio` — `put_volume / call_volume` (optional — None if no options data)
9. `short_interest_pressure` — `short_interest / float` paired with days-to-cover (optional)
10. `narrative_concentration` — `sum(top_3_word_weights) / sum(all_word_weights)` (optional)
11. `institutional_retail_gap` — `analyst_consensus_normalized - retail_sentiment_score` (optional)
12. `event_sensitivity` — `stddev(sentiment_change on event_days) / stddev(sentiment_change on quiet_days)` over 60d (optional; requires ≥30 days history)

**Engagement weighting:** helper `engagement_weight(post)` returns a weight ∈ [1, 5] derived from likes + retweets (log-scaled). Sentiment score and bull/bear ratio use this weight.

**Files:**
- Create: `packages/core/src/openlia/retail_sentiment/metrics.py`
- Test: `packages/core/tests/retail_sentiment/test_metrics.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/retail_sentiment/test_metrics.py
from datetime import UTC, datetime, timedelta
import math

import pandas as pd
import pytest

from openlia.retail_sentiment.metrics import (
    bull_bear_ratio,
    buzz_sentiment_divergence,
    buzz_volume,
    compute_snapshot,
    engagement_weight,
    event_sensitivity,
    institutional_retail_gap,
    narrative_concentration,
    put_call_ratio,
    sentiment_momentum,
    sentiment_score,
    short_interest_pressure,
    social_velocity,
)
from openlia.retail_sentiment.schemas import ClassificationLabel, ClassifiedItem


def _items(n_bull: int, n_bear: int, n_neutral: int = 0) -> list[ClassifiedItem]:
    out: list[ClassifiedItem] = []
    i = 0
    for _ in range(n_bull):
        out.append(ClassifiedItem(id=f"i{i}", classification=ClassificationLabel.BULLISH, confidence=1.0, key_phrases=[]))
        i += 1
    for _ in range(n_bear):
        out.append(ClassifiedItem(id=f"i{i}", classification=ClassificationLabel.BEARISH, confidence=1.0, key_phrases=[]))
        i += 1
    for _ in range(n_neutral):
        out.append(ClassifiedItem(id=f"i{i}", classification=ClassificationLabel.NEUTRAL, confidence=1.0, key_phrases=[]))
        i += 1
    return out


# --- Metric 1: Sentiment Score ---
def test_sentiment_score_balanced_returns_zero():
    assert sentiment_score(_items(5, 5)) == 0.0


def test_sentiment_score_all_bullish_returns_one():
    assert sentiment_score(_items(10, 0)) == 1.0


def test_sentiment_score_all_bearish_returns_neg_one():
    assert sentiment_score(_items(0, 10)) == -1.0


def test_sentiment_score_empty_returns_zero():
    assert sentiment_score([]) == 0.0


# --- Metric 2: Buzz Volume ---
def test_buzz_volume_today_vs_30d_mean():
    # Today has 100 mentions; 30d mean is 50. Ratio = 2.0
    assert buzz_volume(today=100, history=[50] * 30) == pytest.approx(2.0)


def test_buzz_volume_zero_history_returns_one():
    # No baseline — buzz is "normal".
    assert buzz_volume(today=100, history=[]) == 1.0


# --- Metric 3: Sentiment Momentum ---
def test_sentiment_momentum_improving():
    history = [0.1, 0.1, 0.1, 0.1, 0.1, 0.3, 0.3, 0.3, 0.3, 0.3]  # last 5 higher
    assert sentiment_momentum(history=history, window=5) == pytest.approx(0.2)


def test_sentiment_momentum_flat_returns_zero():
    assert sentiment_momentum(history=[0.2] * 10, window=5) == pytest.approx(0.0)


def test_sentiment_momentum_insufficient_history_returns_zero():
    assert sentiment_momentum(history=[0.1, 0.2], window=5) == 0.0


# --- Metric 4: Bull/Bear Ratio ---
def test_bull_bear_ratio_mostly_bullish():
    assert bull_bear_ratio(_items(8, 2)) == pytest.approx(0.8)


def test_bull_bear_ratio_neutral_excluded():
    assert bull_bear_ratio(_items(3, 2, n_neutral=100)) == pytest.approx(0.6)


def test_bull_bear_ratio_all_neutral_returns_nan_guard():
    assert bull_bear_ratio(_items(0, 0, n_neutral=5)) == 0.5


# --- Metric 5: Buzz-Sentiment Divergence ---
def test_buzz_sentiment_divergence_panic_signal():
    buzz_hist = [100.0] * 30
    sent_hist = [0.3] * 30
    d = buzz_sentiment_divergence(
        buzz_today=300.0, sentiment_today=-0.3,
        buzz_history=buzz_hist, sentiment_history=sent_hist,
    )
    # Buzz z >> 0, sentiment z << 0 → divergence >> 2
    assert d > 2.0


def test_buzz_sentiment_divergence_normal_near_zero():
    import random
    random.seed(0)
    buzz_hist = [100.0 + random.gauss(0, 5) for _ in range(30)]
    sent_hist = [0.2 + random.gauss(0, 0.05) for _ in range(30)]
    d = buzz_sentiment_divergence(
        buzz_today=100.0, sentiment_today=0.2,
        buzz_history=buzz_hist, sentiment_history=sent_hist,
    )
    assert abs(d) < 1.0


# --- Metric 6: Social Velocity ---
def test_social_velocity_positive_change():
    assert social_velocity(buzz_today=150, buzz_yesterday=100) == pytest.approx(0.5)


def test_social_velocity_zero_yesterday_returns_zero():
    assert social_velocity(buzz_today=100, buzz_yesterday=0) == 0.0


# --- Metric 8: Put/Call Ratio ---
def test_put_call_ratio_basic():
    assert put_call_ratio(put_volume=1000, call_volume=2000) == pytest.approx(0.5)


def test_put_call_ratio_zero_call_returns_none():
    assert put_call_ratio(put_volume=1000, call_volume=0) is None


# --- Metric 9: Short Interest Pressure ---
def test_short_interest_pressure_pct_and_days_to_cover():
    r = short_interest_pressure(
        short_interest=10_000_000, float_shares=100_000_000, avg_daily_volume=1_000_000
    )
    assert r is not None
    assert r["short_pct"] == pytest.approx(0.10)
    assert r["days_to_cover"] == pytest.approx(10.0)


def test_short_interest_pressure_missing_inputs_returns_none():
    assert short_interest_pressure(short_interest=None, float_shares=None, avg_daily_volume=None) is None


# --- Metric 10: Narrative Concentration ---
def test_narrative_concentration_top3_fraction():
    weights = {"growth": 40, "ai": 30, "margin": 20, "competition": 5, "regulation": 5}
    c = narrative_concentration(word_weights=weights)
    assert c == pytest.approx(0.90)


def test_narrative_concentration_empty_returns_none():
    assert narrative_concentration(word_weights={}) is None


# --- Metric 11: Institutional-Retail Gap ---
def test_institutional_retail_gap_positive():
    gap = institutional_retail_gap(
        analyst_ratings={"strong_buy": 10, "buy": 5, "hold": 3, "sell": 0, "strong_sell": 0},
        retail_sentiment=0.1,
    )
    assert gap is not None
    assert gap > 0  # analysts very bullish, retail lukewarm


def test_institutional_retail_gap_no_analysts_returns_none():
    assert institutional_retail_gap(analyst_ratings={}, retail_sentiment=0.2) is None


# --- Metric 12: Event Sensitivity ---
def test_event_sensitivity_requires_30d_history():
    # Only 10 days → None
    daily = pd.DataFrame({
        "date": [datetime(2026, 4, d, tzinfo=UTC) for d in range(1, 11)],
        "sentiment": [0.1] * 10,
        "has_event": [False] * 10,
    })
    assert event_sensitivity(daily=daily) is None


def test_event_sensitivity_high_on_reactive_crowd():
    # 60-day panel. Sentiment swings wildly on event days, stable on quiet days.
    rows = []
    for i in range(60):
        is_event = i % 10 == 0
        rows.append({
            "date": datetime(2026, 1, 1, tzinfo=UTC) + timedelta(days=i),
            "sentiment": (0.5 if is_event else 0.01) * (1 if i % 2 == 0 else -1),
            "has_event": is_event,
        })
    daily = pd.DataFrame(rows)
    s = event_sensitivity(daily=daily)
    assert s is not None
    assert s > 3.0


# --- Helper: engagement_weight ---
def test_engagement_weight_minimum_is_one():
    assert engagement_weight({}) == 1.0


def test_engagement_weight_scales_with_likes():
    low = engagement_weight({"likes": 5})
    high = engagement_weight({"likes": 5000})
    assert high > low
    assert 1.0 <= low <= 5.0
    assert 1.0 <= high <= 5.0


# --- Integration: compute_snapshot ---
def test_compute_snapshot_basic_returns_all_metrics():
    classified = _items(6, 4, n_neutral=2)
    snap = compute_snapshot(
        ticker="AAPL",
        captured_at=datetime.now(UTC),
        classified=classified,
        per_source_sentiment={
            "financial_provider": 0.2,
            "social_media": 0.25,
            "cross_platform": 0.15,
        },
        buzz_today=100,
        buzz_history=[80] * 30,
        sentiment_history=[0.15] * 30,
        buzz_yesterday=95,
        word_weights={"growth": 50, "ai": 30, "competition": 10, "regs": 5, "supply": 5},
        analyst_ratings={"buy": 10, "hold": 3},
        options={"put_volume": 500, "call_volume": 1000},
        short_data={"short_interest": 5_000_000, "float_shares": 100_000_000, "avg_daily_volume": 500_000},
        event_panel=None,
    )
    assert snap.ticker == "AAPL"
    assert -1 <= snap.sentiment_score <= 1
    assert snap.buzz_volume >= 0
    assert snap.bull_bear_ratio == pytest.approx(0.6)
    assert snap.put_call_ratio == pytest.approx(0.5)
    assert snap.cross_source_agreement == 1.0
    # Optional metric with no history.
    assert snap.event_sensitivity is None


def test_compute_snapshot_omits_optional_when_inputs_missing():
    snap = compute_snapshot(
        ticker="TSLA",
        captured_at=datetime.now(UTC),
        classified=_items(5, 5),
        per_source_sentiment={"social_media": 0.0},
        buzz_today=50,
        buzz_history=[50] * 30,
        sentiment_history=[0.0] * 30,
        buzz_yesterday=50,
        word_weights=None,
        analyst_ratings=None,
        options=None,
        short_data=None,
        event_panel=None,
    )
    assert snap.put_call_ratio is None
    assert snap.short_interest_pressure is None
    assert snap.institutional_retail_gap is None
    assert snap.narrative_concentration is None
    assert snap.event_sensitivity is None
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `uv run pytest packages/core/tests/retail_sentiment/test_metrics.py -v`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Write the metrics engine**

```python
# packages/core/src/openlia/retail_sentiment/metrics.py
"""Pandas-based engine computing all 12 retail-sentiment metrics."""

from __future__ import annotations

import math
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

from openlia.retail_sentiment.reliability import (
    DEFAULT_SOURCE_WEIGHTS,
    ReliabilityMatrix,
    cross_source_agreement,
)
from openlia.retail_sentiment.schemas import (
    ClassificationLabel,
    ClassifiedItem,
    MetricSnapshot,
)


# ----- Metric 1 -----
def sentiment_score(items: list[ClassifiedItem]) -> float:
    if not items:
        return 0.0
    pos = sum(1 for i in items if i.classification is ClassificationLabel.BULLISH)
    neg = sum(1 for i in items if i.classification is ClassificationLabel.BEARISH)
    total = len(items)
    return (pos - neg) / total


# ----- Metric 2 -----
def buzz_volume(*, today: float, history: list[float]) -> float:
    if not history:
        return 1.0
    mean = float(np.mean(history))
    if mean == 0:
        return 1.0
    return today / mean


# ----- Metric 3 -----
def sentiment_momentum(*, history: list[float], window: int = 5) -> float:
    if len(history) < window + 1:
        return 0.0
    series = pd.Series(history)
    sma = series.rolling(window=window).mean()
    return float(sma.iloc[-1] - sma.iloc[-2])


# ----- Metric 4 -----
def bull_bear_ratio(items: list[ClassifiedItem]) -> float:
    bulls = sum(1 for i in items if i.classification is ClassificationLabel.BULLISH)
    bears = sum(1 for i in items if i.classification is ClassificationLabel.BEARISH)
    denom = bulls + bears
    if denom == 0:
        return 0.5
    return bulls / denom


# ----- Metric 5 -----
def buzz_sentiment_divergence(
    *,
    buzz_today: float,
    sentiment_today: float,
    buzz_history: list[float],
    sentiment_history: list[float],
) -> float:
    if len(buzz_history) < 2 or len(sentiment_history) < 2:
        return 0.0
    bz = np.asarray(buzz_history, dtype=float)
    sh = np.asarray(sentiment_history, dtype=float)
    bz_std = bz.std() or 1.0
    sh_std = sh.std() or 1.0
    z_buzz = (buzz_today - bz.mean()) / bz_std
    z_sent = (sentiment_today - sh.mean()) / sh_std
    return float(z_buzz - z_sent)


# ----- Metric 6 -----
def social_velocity(*, buzz_today: float, buzz_yesterday: float) -> float:
    if buzz_yesterday <= 0:
        return 0.0
    return (buzz_today - buzz_yesterday) / buzz_yesterday


# ----- Metric 8 -----
def put_call_ratio(*, put_volume: float | None, call_volume: float | None) -> float | None:
    if put_volume is None or call_volume is None or call_volume == 0:
        return None
    return put_volume / call_volume


# ----- Metric 9 -----
def short_interest_pressure(
    *,
    short_interest: float | None,
    float_shares: float | None,
    avg_daily_volume: float | None,
) -> dict[str, float] | None:
    if not short_interest or not float_shares or not avg_daily_volume:
        return None
    return {
        "short_pct": short_interest / float_shares,
        "days_to_cover": short_interest / avg_daily_volume,
    }


# ----- Metric 10 -----
def narrative_concentration(*, word_weights: dict[str, float] | None) -> float | None:
    if not word_weights:
        return None
    top3 = sorted(word_weights.values(), reverse=True)[:3]
    total = sum(word_weights.values())
    if total == 0:
        return None
    return sum(top3) / total


# ----- Metric 11 -----
_RATING_SCALE = {
    "strong_buy": 1.0,
    "buy": 0.5,
    "hold": 0.0,
    "sell": -0.5,
    "strong_sell": -1.0,
}


def institutional_retail_gap(
    *, analyst_ratings: dict[str, int] | None, retail_sentiment: float
) -> float | None:
    if not analyst_ratings:
        return None
    weighted = 0.0
    total = 0
    for label, count in analyst_ratings.items():
        if label not in _RATING_SCALE or count <= 0:
            continue
        weighted += _RATING_SCALE[label] * count
        total += count
    if total == 0:
        return None
    analyst_norm = weighted / total
    return analyst_norm - retail_sentiment


# ----- Metric 12 -----
def event_sensitivity(*, daily: pd.DataFrame | None) -> float | None:
    if daily is None or len(daily) < 30:
        return None
    panel = daily.sort_values("date").copy()
    panel["sentiment_change"] = panel["sentiment"].diff()
    event_std = panel.loc[panel["has_event"], "sentiment_change"].dropna().std()
    quiet_std = panel.loc[~panel["has_event"], "sentiment_change"].dropna().std()
    if not quiet_std or math.isnan(quiet_std) or quiet_std == 0:
        return None
    if not event_std or math.isnan(event_std):
        return None
    return float(event_std / quiet_std)


# ----- Helper: engagement weight -----
def engagement_weight(engagement: dict[str, int]) -> float:
    likes = int(engagement.get("likes", 0))
    rts = int(engagement.get("retweets", 0))
    raw = max(1, likes + rts * 2)
    # log10 scaled into [1, 5]
    weight = 1.0 + min(4.0, math.log10(raw))
    return round(weight, 4)


# ----- Composition -----
def compute_snapshot(
    *,
    ticker: str,
    captured_at: datetime,
    classified: list[ClassifiedItem],
    per_source_sentiment: dict[str, float],
    buzz_today: float,
    buzz_history: list[float],
    sentiment_history: list[float],
    buzz_yesterday: float,
    word_weights: dict[str, float] | None,
    analyst_ratings: dict[str, int] | None,
    options: dict[str, float] | None,
    short_data: dict[str, float] | None,
    event_panel: pd.DataFrame | None,
    reliability: ReliabilityMatrix | None = None,
) -> MetricSnapshot:
    matrix = reliability or ReliabilityMatrix(weights=dict(DEFAULT_SOURCE_WEIGHTS))
    composite = matrix.weighted_score(per_source_sentiment)
    local_score = sentiment_score(classified)
    # When classification items are present, they override the composite contribution
    # of the social_media source by blending 50/50 with the provider reading.
    combined = composite if not classified else (composite + local_score) / 2

    short_pct = None
    short_days = None
    if short_data:
        sip = short_interest_pressure(
            short_interest=short_data.get("short_interest"),
            float_shares=short_data.get("float_shares"),
            avg_daily_volume=short_data.get("avg_daily_volume"),
        )
        if sip:
            short_pct = sip["short_pct"]
            short_days = sip["days_to_cover"]

    return MetricSnapshot(
        ticker=ticker,
        captured_at=captured_at,
        sentiment_score=combined,
        buzz_volume=buzz_volume(today=buzz_today, history=buzz_history),
        sentiment_momentum=sentiment_momentum(history=sentiment_history, window=5),
        bull_bear_ratio=bull_bear_ratio(classified),
        buzz_sentiment_divergence=buzz_sentiment_divergence(
            buzz_today=buzz_today,
            sentiment_today=local_score,
            buzz_history=buzz_history,
            sentiment_history=sentiment_history,
        ),
        social_velocity=social_velocity(buzz_today=buzz_today, buzz_yesterday=buzz_yesterday),
        cross_source_agreement=cross_source_agreement(per_source_sentiment),
        put_call_ratio=put_call_ratio(
            put_volume=(options or {}).get("put_volume"),
            call_volume=(options or {}).get("call_volume"),
        ),
        short_interest_pressure=short_pct,
        narrative_concentration=narrative_concentration(word_weights=word_weights),
        institutional_retail_gap=institutional_retail_gap(
            analyst_ratings=analyst_ratings, retail_sentiment=combined
        ),
        event_sensitivity=event_sensitivity(daily=event_panel),
        source_breakdown={k: v for k, v in per_source_sentiment.items()},
    )


__all__ = [
    "sentiment_score",
    "buzz_volume",
    "sentiment_momentum",
    "bull_bear_ratio",
    "buzz_sentiment_divergence",
    "social_velocity",
    "put_call_ratio",
    "short_interest_pressure",
    "narrative_concentration",
    "institutional_retail_gap",
    "event_sensitivity",
    "engagement_weight",
    "compute_snapshot",
]
```

- [ ] **Step 4: Run the test to confirm it passes**

Run: `uv run pytest packages/core/tests/retail_sentiment/test_metrics.py -v`
Expected: PASS (~30 tests, one per metric + composition).

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/retail_sentiment/metrics.py \
        packages/core/tests/retail_sentiment/test_metrics.py
git commit -m "feat(core): add retail_sentiment metrics engine (12 metrics)"
```

---

### Task 7: Core — `retail_sentiment/spike_detector.py`

Detects 7-day volume spikes from a list of historical buzz readings: spike when `buzz_today > mean(last_7) + 2 * stddev(last_7)`. Returns `SpikeEvent | None`. Helper `detect_spikes_batch(snapshots_by_ticker)` iterates per ticker.

**Files:**
- Create: `packages/core/src/openlia/retail_sentiment/spike_detector.py`
- Test: `packages/core/tests/retail_sentiment/test_spike_detector.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/retail_sentiment/test_spike_detector.py
from datetime import UTC, datetime, timedelta

import pytest

from openlia.retail_sentiment.spike_detector import (
    detect_spike,
    detect_spikes_batch,
)


def _now() -> datetime:
    return datetime(2026, 4, 23, 21, 0, tzinfo=UTC)


def test_detect_spike_flat_history_no_spike():
    ev = detect_spike(ticker="AAPL", buzz_today=100, history=[100] * 7, detected_at=_now())
    assert ev is None


def test_detect_spike_3sigma_returns_event():
    history = [100, 95, 105, 100, 98, 102, 99]
    ev = detect_spike(ticker="AAPL", buzz_today=500, history=history, detected_at=_now())
    assert ev is not None
    assert ev.ticker == "AAPL"
    assert ev.z_score > 2.0
    assert ev.buzz == 500


def test_detect_spike_requires_seven_days_history():
    ev = detect_spike(ticker="AAPL", buzz_today=1000, history=[100] * 3, detected_at=_now())
    assert ev is None


def test_detect_spike_mild_increase_no_event():
    history = [100, 95, 105, 100, 98, 102, 99]
    ev = detect_spike(ticker="AAPL", buzz_today=110, history=history, detected_at=_now())
    assert ev is None  # well within 2 sigma


def test_detect_spikes_batch_filters_non_spikers():
    buckets = {
        "AAPL": {"today": 500, "history": [100] * 7},
        "TSLA": {"today": 95, "history": [100] * 7},
        "GME": {"today": 2000, "history": [200] * 7},
    }
    events = detect_spikes_batch(buckets=buckets, detected_at=_now())
    tickers = {e.ticker for e in events}
    assert tickers == {"AAPL", "GME"}
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `uv run pytest packages/core/tests/retail_sentiment/test_spike_detector.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Write the detector**

```python
# packages/core/src/openlia/retail_sentiment/spike_detector.py
"""7-day volume spike detector."""

from __future__ import annotations

from datetime import datetime

import numpy as np

from openlia.retail_sentiment.schemas import SpikeEvent

_SPIKE_Z_THRESHOLD = 2.0
_MIN_HISTORY = 7


def detect_spike(
    *,
    ticker: str,
    buzz_today: float,
    history: list[float],
    detected_at: datetime,
) -> SpikeEvent | None:
    if len(history) < _MIN_HISTORY:
        return None
    arr = np.asarray(history[-_MIN_HISTORY:], dtype=float)
    mean = float(arr.mean())
    stddev = float(arr.std())
    if stddev == 0:
        return None
    z = (buzz_today - mean) / stddev
    if z < _SPIKE_Z_THRESHOLD:
        return None
    return SpikeEvent(
        ticker=ticker,
        detected_at=detected_at,
        buzz=buzz_today,
        baseline_mean=mean,
        baseline_stddev=stddev,
        z_score=z,
    )


def detect_spikes_batch(
    *, buckets: dict[str, dict[str, object]], detected_at: datetime
) -> list[SpikeEvent]:
    events: list[SpikeEvent] = []
    for ticker, data in buckets.items():
        ev = detect_spike(
            ticker=ticker,
            buzz_today=float(data["today"]),  # type: ignore[arg-type]
            history=list(data["history"]),  # type: ignore[arg-type]
            detected_at=detected_at,
        )
        if ev:
            events.append(ev)
    return events
```

- [ ] **Step 4: Run the test to confirm it passes**

Run: `uv run pytest packages/core/tests/retail_sentiment/test_spike_detector.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/core/src/openlia/retail_sentiment/spike_detector.py \
        packages/core/tests/retail_sentiment/test_spike_detector.py
git commit -m "feat(core): add 7-day volume spike detector"
```

---

### Task 8: Server — `RsClassificationLog` model + Alembic migration

`RsUserConfig` and `RsSnapshot` are already shipped (Plan 1B — see `packages/server/src/openlia_server/db/models/dashboard.py` lines 153–194). This task **adds** the audit table.

**Files:**
- Modify: `packages/server/src/openlia_server/db/models/dashboard.py` (append `RsClassificationLog`)
- Modify: `packages/server/src/openlia_server/db/models/__init__.py` (export new class)
- Create: `packages/server/src/openlia_server/db/migrations/versions/2026_04_23_1900_rs_classification_log.py`
- Test: `packages/server/tests/db/test_rs_classification_log.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/db/test_rs_classification_log.py
from datetime import UTC, datetime

import pytest
from sqlalchemy import inspect
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from openlia_server.db.models.dashboard import RsClassificationLog


def test_classification_log_columns(create_tables) -> None:
    cols = {c["name"] for c in inspect(RsClassificationLog).columns}
    for expected in {
        "id",
        "batch_id",
        "ticker",
        "model_ref",
        "item_count",
        "prompt_tokens",
        "completion_tokens",
        "latency_ms",
        "error",
        "created_at",
    }:
        assert expected in cols, f"missing column {expected}"


def test_classification_log_insert_basic(create_tables, db_session: Session) -> None:
    row = RsClassificationLog(
        id="log_1",
        batch_id="b_1",
        ticker="AAPL",
        model_ref="openai:gpt-4o-mini",
        item_count=15,
        prompt_tokens=500,
        completion_tokens=300,
        latency_ms=1200,
        error=None,
    )
    db_session.add(row)
    db_session.commit()
    fetched = db_session.query(RsClassificationLog).filter_by(id="log_1").one()
    assert fetched.ticker == "AAPL"
    assert fetched.item_count == 15
    assert fetched.error is None


def test_classification_log_error_field_nullable(create_tables, db_session: Session) -> None:
    row = RsClassificationLog(
        id="log_2",
        batch_id="b_2",
        ticker="TSLA",
        model_ref="openai:gpt-4o-mini",
        item_count=0,
        prompt_tokens=100,
        completion_tokens=0,
        latency_ms=50,
        error="schema_validation_failed",
    )
    db_session.add(row)
    db_session.commit()
    assert row.error == "schema_validation_failed"


def test_migration_upgrade_downgrade_roundtrip(tmp_path) -> None:
    """Applying then reversing the migration leaves the schema clean."""
    import subprocess
    db = tmp_path / "t.db"
    env = {"OPENLIA_DB_PATH": str(db), "PATH": __import__("os").environ["PATH"]}
    subprocess.run(["uv", "run", "alembic", "upgrade", "head"], check=True, env=env)
    subprocess.run(
        ["uv", "run", "alembic", "downgrade", "2026_04_22_2200_repo_items_and_drop_legacy_report_cols"],
        check=True, env=env,
    )
    subprocess.run(["uv", "run", "alembic", "upgrade", "head"], check=True, env=env)
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `uv run pytest packages/server/tests/db/test_rs_classification_log.py -v`
Expected: FAIL with `ImportError` on `RsClassificationLog`.

- [ ] **Step 3: Append the model**

In `packages/server/src/openlia_server/db/models/dashboard.py`, **after** the `RsSnapshot` class and **before** `# ---------- Formula engine ----------`, append:

```python
class RsClassificationLog(Base):
    """Audit row for every batch NLP classification call."""

    __tablename__ = "rs_classification_log"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    batch_id: Mapped[str] = mapped_column(String(36), nullable=False)
    ticker: Mapped[str] = mapped_column(String(16), nullable=False)
    model_ref: Mapped[str] = mapped_column(String(128), nullable=False)
    item_count: Mapped[int] = mapped_column(Integer, nullable=False)
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    latency_ms: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        nullable=False,
        server_default=func.now(),
    )

    __table_args__ = (
        Index("ix_rs_classification_log_ticker_created", "ticker", "created_at"),
        Index("ix_rs_classification_log_batch", "batch_id"),
    )
```

- [ ] **Step 4: Export the model**

In `packages/server/src/openlia_server/db/models/__init__.py`, make sure `RsClassificationLog` is re-exported alongside `RsUserConfig` / `RsSnapshot`.

- [ ] **Step 5: Write the Alembic migration**

```python
# packages/server/src/openlia_server/db/migrations/versions/2026_04_23_1900_rs_classification_log.py
"""Add rs_classification_log audit table.

Revision ID: 2026_04_23_1900_rs_classification_log
Revises: 2026_04_22_2200_repo_items_and_drop_legacy_report_cols
Create Date: 2026-04-23 19:00:00
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

from openlia_server.db.utcdatetime import UTCDateTime

revision = "2026_04_23_1900_rs_classification_log"
down_revision = "2026_04_22_2200_repo_items_and_drop_legacy_report_cols"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rs_classification_log",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("batch_id", sa.String(36), nullable=False),
        sa.Column("ticker", sa.String(16), nullable=False),
        sa.Column("model_ref", sa.String(128), nullable=False),
        sa.Column("item_count", sa.Integer, nullable=False),
        sa.Column("prompt_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer, nullable=False, server_default="0"),
        sa.Column("error", sa.String(256), nullable=True),
        sa.Column("created_at", UTCDateTime(), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_rs_classification_log_ticker_created",
        "rs_classification_log",
        ["ticker", "created_at"],
    )
    op.create_index(
        "ix_rs_classification_log_batch",
        "rs_classification_log",
        ["batch_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_rs_classification_log_batch", table_name="rs_classification_log")
    op.drop_index("ix_rs_classification_log_ticker_created", table_name="rs_classification_log")
    op.drop_table("rs_classification_log")
```

- [ ] **Step 6: Run the test to confirm it passes**

Run: `uv run pytest packages/server/tests/db/test_rs_classification_log.py -v`
Expected: PASS (3 tests, including migration round-trip).

- [ ] **Step 7: Commit**

```bash
git add packages/server/src/openlia_server/db/models/dashboard.py \
        packages/server/src/openlia_server/db/models/__init__.py \
        packages/server/src/openlia_server/db/migrations/versions/2026_04_23_1900_rs_classification_log.py \
        packages/server/tests/db/test_rs_classification_log.py
git commit -m "feat(server): add rs_classification_log table + migration"
```

---

### Task 9: Server — Add `JobType.RS_SNAPSHOT` + registry mapping

Plan 6 shipped four job types: `MB_BRIEFING`, `EU_SCAN`, `MR_ASSESSMENT`, `SYSTEM_MAINTENANCE`. RS adds a fifth. Because the enum is a `StrEnum` backed by a string key, adding a new member is an additive change — no existing job keys change semantics.

**Files:**
- Modify: `packages/server/src/openlia_server/scheduler/registry.py`
- Test: `packages/server/tests/scheduler/test_registry_rs.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/scheduler/test_registry_rs.py
import pytest

from openlia_server.scheduler.registry import (
    JobType,
    department_for_job_type,
    job_key,
    parse_job_key,
)


def test_rs_snapshot_enum_value():
    assert JobType.RS_SNAPSHOT.value == "rs_snapshot"


def test_rs_snapshot_maps_to_retail_sentiment_department():
    assert department_for_job_type(JobType.RS_SNAPSHOT) == "retail_sentiment"


def test_rs_snapshot_requires_user_id_for_key():
    with pytest.raises(ValueError):
        job_key(JobType.RS_SNAPSHOT, None)
    assert job_key(JobType.RS_SNAPSHOT, "user_abc") == "rs_snapshot:user_abc"


def test_parse_job_key_rs_snapshot():
    jt, uid = parse_job_key("rs_snapshot:u123")
    assert jt is JobType.RS_SNAPSHOT
    assert uid == "u123"
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `uv run pytest packages/server/tests/scheduler/test_registry_rs.py -v`
Expected: FAIL (`JobType` has no attribute `RS_SNAPSHOT`).

- [ ] **Step 3: Extend the enum**

In `packages/server/src/openlia_server/scheduler/registry.py`:

```python
class JobType(StrEnum):
    MB_BRIEFING = "mb_briefing"
    EU_SCAN = "eu_scan"
    MR_ASSESSMENT = "mr_assessment"
    RS_SNAPSHOT = "rs_snapshot"             # NEW
    SYSTEM_MAINTENANCE = "system_maintenance"
```

And extend `_DEPARTMENT_BY_JOB`:

```python
_DEPARTMENT_BY_JOB: dict[JobType, str] = {
    JobType.MB_BRIEFING: "morning_briefing",
    JobType.EU_SCAN: "earnings_update",
    JobType.MR_ASSESSMENT: "macro_research",
    JobType.RS_SNAPSHOT: "retail_sentiment",   # NEW
}
```

- [ ] **Step 4: Run the test to confirm it passes**

Run: `uv run pytest packages/server/tests/scheduler/test_registry_rs.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Also re-run the full scheduler test suite** to catch regressions.

Run: `uv run pytest packages/server/tests/scheduler/ -v`
Expected: all existing tests still PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/scheduler/registry.py \
        packages/server/tests/scheduler/test_registry_rs.py
git commit -m "feat(scheduler): add JobType.RS_SNAPSHOT for retail sentiment"
```

---

### Task 10: Server — `services/rs_config.py` CRUD

Per-user `RsUserConfig` loader with sensible defaults. `get_or_create(user_id)` lazy-creates a row on first read with the spec's defaults.

**Files:**
- Create: `packages/server/src/openlia_server/services/rs_config.py`
- Test: `packages/server/tests/services/test_rs_config.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/services/test_rs_config.py
import pytest
from sqlalchemy.orm import Session

from openlia_server.db.models.auth import User
from openlia_server.db.models.dashboard import RsUserConfig
from openlia_server.services.rs_config import (
    RsConfigPatch,
    get_or_create_config,
    update_config,
)


def _mk_user(db: Session, uid: str = "u_rs_1") -> User:
    u = User(id=uid, email=f"{uid}@x", display_name="RS User", password_hash="x", is_admin=False)
    db.add(u)
    db.commit()
    return u


def test_get_or_create_creates_default_row(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    cfg = get_or_create_config(db_session, user_id="u_rs_1")
    assert cfg.user_id == "u_rs_1"
    assert cfg.active_tab == "overview"
    assert cfg.refresh_interval_minutes == 60
    assert "divergence_threshold" in cfg.metric_settings
    assert cfg.metric_settings["divergence_threshold"] == 2.0


def test_get_or_create_returns_existing(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    first = get_or_create_config(db_session, user_id="u_rs_1")
    first.refresh_interval_minutes = 30
    db_session.commit()
    second = get_or_create_config(db_session, user_id="u_rs_1")
    assert second.refresh_interval_minutes == 30


def test_update_config_partial_patch(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    get_or_create_config(db_session, user_id="u_rs_1")
    patched = update_config(
        db_session,
        user_id="u_rs_1",
        patch=RsConfigPatch(
            refresh_interval_minutes=30,
            metric_settings={"buzz_spike_multiplier": 2.0},
        ),
    )
    assert patched.refresh_interval_minutes == 30
    # Settings merge rather than overwrite.
    assert patched.metric_settings["buzz_spike_multiplier"] == 2.0
    assert patched.metric_settings["divergence_threshold"] == 2.0


def test_update_config_missing_user_raises(create_tables, db_session: Session) -> None:
    with pytest.raises(LookupError):
        update_config(db_session, user_id="nope", patch=RsConfigPatch(refresh_interval_minutes=30))
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `uv run pytest packages/server/tests/services/test_rs_config.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Write the service**

```python
# packages/server/src/openlia_server/services/rs_config.py
"""RsUserConfig CRUD + defaults."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from sqlalchemy.orm import Session

from openlia_server.db.models.dashboard import RsUserConfig

_DEFAULT_METRIC_SETTINGS: dict[str, Any] = {
    "divergence_threshold": 2.0,
    "buzz_spike_multiplier": 1.5,
    "momentum_window_days": 5,
    "short_interest_squeeze_threshold": 0.10,
    "institutional_gap_significance": 0.5,
    "put_call_bullish_threshold": 0.7,
    "put_call_bearish_threshold": 1.0,
    "narrative_concentration_fragile_threshold": 0.60,
    "event_sensitivity_reactive_threshold": 3.0,
    "cross_source_weights": {
        "financial_provider": 0.40,
        "social_media": 0.35,
        "cross_platform": 0.25,
    },
    "batch_size": 30,
}


@dataclass(frozen=True)
class RsConfigPatch:
    active_tab: str | None = None
    refresh_interval_minutes: int | None = None
    metric_settings: dict[str, Any] | None = None
    filter_presets: list[Any] | None = None


def get_or_create_config(db: Session, *, user_id: str) -> RsUserConfig:
    cfg = db.query(RsUserConfig).filter_by(user_id=user_id).one_or_none()
    if cfg is None:
        cfg = RsUserConfig(
            id=str(uuid.uuid4()),
            user_id=user_id,
            active_tab="overview",
            metric_settings=dict(_DEFAULT_METRIC_SETTINGS),
            filter_presets=[],
            refresh_interval_minutes=60,
        )
        db.add(cfg)
        db.commit()
        db.refresh(cfg)
    return cfg


def update_config(db: Session, *, user_id: str, patch: RsConfigPatch) -> RsUserConfig:
    cfg = db.query(RsUserConfig).filter_by(user_id=user_id).one_or_none()
    if cfg is None:
        raise LookupError(f"no RsUserConfig row for user_id={user_id}")
    if patch.active_tab is not None:
        cfg.active_tab = patch.active_tab
    if patch.refresh_interval_minutes is not None:
        cfg.refresh_interval_minutes = patch.refresh_interval_minutes
    if patch.metric_settings is not None:
        merged = dict(cfg.metric_settings)
        merged.update(patch.metric_settings)
        cfg.metric_settings = merged
    if patch.filter_presets is not None:
        cfg.filter_presets = list(patch.filter_presets)
    db.commit()
    db.refresh(cfg)
    return cfg
```

- [ ] **Step 4: Run the test to confirm it passes**

Run: `uv run pytest packages/server/tests/services/test_rs_config.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/services/rs_config.py \
        packages/server/tests/services/test_rs_config.py
git commit -m "feat(server): add rs_config service (get_or_create + update)"
```

---

### Task 11: Server — `services/rs_snapshot.py` read/write + history

`write_snapshot(ticker, snapshot)` inserts an `RsSnapshot` row. `latest_for_tickers(tickers)` returns the most-recent row per ticker. `history(ticker, days)` returns all rows within a window, ordered ascending by `captured_at`.

**Files:**
- Create: `packages/server/src/openlia_server/services/rs_snapshot.py`
- Test: `packages/server/tests/services/test_rs_snapshot.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/services/test_rs_snapshot.py
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.orm import Session

from openlia_server.db.models.dashboard import RsSnapshot
from openlia_server.services.rs_snapshot import (
    history,
    latest_for_tickers,
    write_snapshot,
)


def test_write_snapshot_inserts_row(create_tables, db_session: Session) -> None:
    row = write_snapshot(
        db_session,
        ticker="AAPL",
        captured_at=datetime.now(UTC),
        snapshot_data={"sentiment_score": 0.4, "buzz_volume": 1.1},
        source_breakdown={"financial_provider": 0.4, "social_media": 0.4, "cross_platform": 0.2},
    )
    assert row.id
    assert row.ticker == "AAPL"
    assert row.snapshot_data["sentiment_score"] == 0.4


def test_latest_for_tickers_returns_newest_per_ticker(create_tables, db_session: Session) -> None:
    base = datetime.now(UTC)
    write_snapshot(db_session, ticker="AAPL", captured_at=base - timedelta(hours=2),
                   snapshot_data={"sentiment_score": 0.1}, source_breakdown=None)
    write_snapshot(db_session, ticker="AAPL", captured_at=base,
                   snapshot_data={"sentiment_score": 0.5}, source_breakdown=None)
    write_snapshot(db_session, ticker="TSLA", captured_at=base,
                   snapshot_data={"sentiment_score": -0.2}, source_breakdown=None)
    out = latest_for_tickers(db_session, tickers=["AAPL", "TSLA", "NVDA"])
    assert set(out.keys()) == {"AAPL", "TSLA"}  # NVDA has no rows
    assert out["AAPL"].snapshot_data["sentiment_score"] == 0.5


def test_history_respects_days_window(create_tables, db_session: Session) -> None:
    now = datetime.now(UTC)
    for offset in (-40, -15, -5, -1):
        write_snapshot(db_session, ticker="AAPL", captured_at=now + timedelta(days=offset),
                       snapshot_data={"sentiment_score": 0.0}, source_breakdown=None)
    rows = history(db_session, ticker="AAPL", days=30)
    assert len(rows) == 3  # -15, -5, -1
    # Ascending order.
    assert rows[0].captured_at < rows[-1].captured_at


def test_history_empty_returns_empty_list(create_tables, db_session: Session) -> None:
    assert history(db_session, ticker="AAPL", days=30) == []
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `uv run pytest packages/server/tests/services/test_rs_snapshot.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Write the service**

```python
# packages/server/src/openlia_server/services/rs_snapshot.py
"""Read/write helpers for rs_snapshots."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import desc, func, select
from sqlalchemy.orm import Session

from openlia_server.db.models.dashboard import RsSnapshot


def write_snapshot(
    db: Session,
    *,
    ticker: str,
    captured_at: datetime,
    snapshot_data: dict[str, Any],
    source_breakdown: dict[str, Any] | None,
) -> RsSnapshot:
    row = RsSnapshot(
        id=str(uuid.uuid4()),
        ticker=ticker,
        captured_at=captured_at,
        snapshot_data=snapshot_data,
        source_breakdown=source_breakdown,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def latest_for_tickers(db: Session, *, tickers: list[str]) -> dict[str, RsSnapshot]:
    if not tickers:
        return {}
    subq = (
        select(RsSnapshot.ticker, func.max(RsSnapshot.captured_at).label("max_at"))
        .where(RsSnapshot.ticker.in_(tickers))
        .group_by(RsSnapshot.ticker)
        .subquery()
    )
    rows = (
        db.query(RsSnapshot)
        .join(
            subq,
            (RsSnapshot.ticker == subq.c.ticker) & (RsSnapshot.captured_at == subq.c.max_at),
        )
        .all()
    )
    return {r.ticker: r for r in rows}


def history(db: Session, *, ticker: str, days: int) -> list[RsSnapshot]:
    cutoff = datetime.now(UTC) - timedelta(days=days)
    rows = (
        db.query(RsSnapshot)
        .filter(RsSnapshot.ticker == ticker, RsSnapshot.captured_at >= cutoff)
        .order_by(RsSnapshot.captured_at.asc())
        .all()
    )
    return rows
```

- [ ] **Step 4: Run the test to confirm it passes**

Run: `uv run pytest packages/server/tests/services/test_rs_snapshot.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/services/rs_snapshot.py \
        packages/server/tests/services/test_rs_snapshot.py
git commit -m "feat(server): add rs_snapshot service (write + latest + history)"
```

---

### Task 12: Server — `services/rs_runner.py` pipeline orchestrator

`RsRunner.run_snapshot_for_tickers(tickers, *, user_id)` executes the end-to-end pipeline:
1. For each ticker, fetch social posts + news via `social_sentiment`/`company_news` adapters (Plan 3).
2. Fetch auxiliary data (options, short interest, institutional) where available.
3. Call `BatchClassifier.classify(posts, ticker)` — log to `rs_classification_log`.
4. Fetch per-ticker history window (`rs_snapshots` — last 30 days).
5. Call `compute_snapshot(...)`.
6. Call `detect_spike(...)` using `rs_snapshots` last-7-days buzz.
7. Write `RsSnapshot` row.
8. Return `list[RsSnapshot]` IDs + spike events.

**Files:**
- Create: `packages/server/src/openlia_server/services/rs_runner.py`
- Test: `packages/server/tests/services/test_rs_runner.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/services/test_rs_runner.py
from datetime import UTC, datetime
from typing import Any

import pytest
from sqlalchemy.orm import Session

from openlia_server.db.models.auth import User
from openlia_server.db.models.dashboard import (
    RsClassificationLog,
    RsSnapshot,
    RsUserConfig,
)
from openlia_server.services.rs_config import get_or_create_config
from openlia_server.services.rs_runner import RsRunner, RsRunResult


class _FakeDataAdapter:
    """Captures adapter calls and returns canned data."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    def fetch(self, *, requirement: str, ticker: str) -> Any:
        self.calls.append((requirement, ticker))
        if requirement == "social_sentiment":
            return [
                {"id": "p1", "ticker": ticker, "text": "love it", "source": "x_twitter",
                 "engagement": {"likes": 10}, "created_at": datetime.now(UTC)},
                {"id": "p2", "ticker": ticker, "text": "worried", "source": "x_twitter",
                 "engagement": {"likes": 2}, "created_at": datetime.now(UTC)},
            ]
        if requirement == "company_news":
            return [{"id": "n1", "ticker": ticker, "text": "beat earnings",
                     "source": "eodhd", "engagement": {}, "created_at": datetime.now(UTC)}]
        if requirement == "stock_quote":
            return {"price": 180.5, "change": 0.01}
        return None


class _FakeClassifier:
    def __init__(self, model_ref: str = "openai:gpt-4o-mini") -> None:
        self.model_ref = model_ref
        self.calls: list[dict] = []

    async def classify(self, *, posts, ticker):
        from openlia.retail_sentiment.classifier import ClassifierResult
        from openlia.retail_sentiment.schemas import ClassificationLabel, ClassifiedItem
        self.calls.append({"ticker": ticker, "n": len(posts)})
        items = []
        for idx, p in enumerate(posts):
            lbl = ClassificationLabel.BULLISH if idx % 2 == 0 else ClassificationLabel.BEARISH
            items.append(ClassifiedItem(id=p.id, classification=lbl, confidence=0.8, key_phrases=[]))
        return ClassifierResult(
            items=items, batches_called=1, prompt_tokens=123, completion_tokens=45, latency_ms_total=100,
        )


def _mk_user(db: Session, uid: str = "u_rs_run_1") -> User:
    u = User(id=uid, email=f"{uid}@x", display_name="Runner",
             password_hash="x", is_admin=False)
    db.add(u)
    db.commit()
    return u


@pytest.mark.asyncio
async def test_runner_writes_snapshot_and_log(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    get_or_create_config(db_session, user_id="u_rs_run_1")
    adapter = _FakeDataAdapter()
    classifier = _FakeClassifier()
    runner = RsRunner(
        session_factory=lambda: db_session,
        adapter=adapter,
        classifier=classifier,
    )
    result = await runner.run_snapshot_for_tickers(
        tickers=["AAPL"], user_id="u_rs_run_1"
    )
    assert isinstance(result, RsRunResult)
    assert len(result.snapshot_ids) == 1
    # RsSnapshot row exists.
    rows = db_session.query(RsSnapshot).filter_by(ticker="AAPL").all()
    assert len(rows) == 1
    # Audit row exists.
    logs = db_session.query(RsClassificationLog).filter_by(ticker="AAPL").all()
    assert len(logs) == 1
    assert logs[0].item_count > 0
    assert logs[0].prompt_tokens == 123


@pytest.mark.asyncio
async def test_runner_handles_empty_posts_gracefully(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    get_or_create_config(db_session, user_id="u_rs_run_1")

    class _EmptyAdapter(_FakeDataAdapter):
        def fetch(self, *, requirement, ticker):
            return [] if requirement in ("social_sentiment", "company_news") else None

    classifier = _FakeClassifier()
    runner = RsRunner(
        session_factory=lambda: db_session,
        adapter=_EmptyAdapter(),
        classifier=classifier,
    )
    result = await runner.run_snapshot_for_tickers(tickers=["AAPL"], user_id="u_rs_run_1")
    assert len(result.snapshot_ids) == 1  # still writes a row (with neutral score)
    rows = db_session.query(RsSnapshot).filter_by(ticker="AAPL").all()
    assert rows[0].snapshot_data.get("sentiment_score") == 0.0


@pytest.mark.asyncio
async def test_runner_runs_multiple_tickers(create_tables, db_session: Session) -> None:
    _mk_user(db_session)
    get_or_create_config(db_session, user_id="u_rs_run_1")
    adapter = _FakeDataAdapter()
    classifier = _FakeClassifier()
    runner = RsRunner(
        session_factory=lambda: db_session,
        adapter=adapter,
        classifier=classifier,
    )
    result = await runner.run_snapshot_for_tickers(
        tickers=["AAPL", "TSLA", "NVDA"], user_id="u_rs_run_1"
    )
    assert len(result.snapshot_ids) == 3
    tickers_written = {
        r.ticker for r in db_session.query(RsSnapshot).all()
    }
    assert tickers_written == {"AAPL", "TSLA", "NVDA"}
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `uv run pytest packages/server/tests/services/test_rs_runner.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Write the runner**

```python
# packages/server/src/openlia_server/services/rs_runner.py
"""End-to-end pipeline for one retail-sentiment snapshot cycle."""

from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Callable, Protocol

from sqlalchemy.orm import Session

from openlia.retail_sentiment.classifier import ClassifierResult
from openlia.retail_sentiment.metrics import compute_snapshot
from openlia.retail_sentiment.reliability import (
    DEFAULT_SOURCE_WEIGHTS,
    ReliabilityMatrix,
)
from openlia.retail_sentiment.schemas import (
    RawSocialPost,
    SpikeEvent,
)
from openlia.retail_sentiment.spike_detector import detect_spike
from openlia_server.db.models.dashboard import RsClassificationLog, RsSnapshot
from openlia_server.services.rs_config import get_or_create_config
from openlia_server.services.rs_snapshot import history as snapshot_history
from openlia_server.services.rs_snapshot import write_snapshot

logger = logging.getLogger(__name__)


class _Classifier(Protocol):
    model_ref: str

    async def classify(self, *, posts: list[RawSocialPost], ticker: str) -> ClassifierResult: ...


class _Adapter(Protocol):
    def fetch(self, *, requirement: str, ticker: str) -> Any: ...


@dataclass
class RsRunResult:
    snapshot_ids: list[str] = field(default_factory=list)
    spike_events: list[SpikeEvent] = field(default_factory=list)


@dataclass
class RsRunner:
    session_factory: Callable[[], Session]
    adapter: _Adapter
    classifier: _Classifier

    async def run_snapshot_for_tickers(
        self, *, tickers: list[str], user_id: str
    ) -> RsRunResult:
        db = self.session_factory()
        cfg = get_or_create_config(db, user_id=user_id)
        weights = cfg.metric_settings.get("cross_source_weights") or DEFAULT_SOURCE_WEIGHTS
        matrix = ReliabilityMatrix(weights=dict(weights))

        ids: list[str] = []
        spikes: list[SpikeEvent] = []

        for ticker in tickers:
            raw_social = self.adapter.fetch(requirement="social_sentiment", ticker=ticker) or []
            raw_news = self.adapter.fetch(requirement="company_news", ticker=ticker) or []
            quote = self.adapter.fetch(requirement="stock_quote", ticker=ticker) or {}
            options = self.adapter.fetch(requirement="options_data", ticker=ticker)
            short = self.adapter.fetch(requirement="short_interest", ticker=ticker)
            inst = self.adapter.fetch(requirement="institutional_holdings", ticker=ticker)

            posts: list[RawSocialPost] = []
            for raw in list(raw_social) + list(raw_news):
                posts.append(
                    RawSocialPost(
                        id=raw["id"],
                        ticker=ticker,
                        source=raw.get("source", "unknown"),
                        text=raw.get("text", ""),
                        engagement=raw.get("engagement", {}),
                        created_at=raw.get("created_at", datetime.now(UTC)),
                    )
                )

            result = await self.classifier.classify(posts=posts, ticker=ticker)

            # Audit row.
            db.add(
                RsClassificationLog(
                    id=str(uuid.uuid4()),
                    batch_id=str(uuid.uuid4()),
                    ticker=ticker,
                    model_ref=getattr(self.classifier, "model_ref", "unknown"),
                    item_count=len(result.items),
                    prompt_tokens=result.prompt_tokens,
                    completion_tokens=result.completion_tokens,
                    latency_ms=result.latency_ms_total,
                    error=None,
                )
            )
            db.commit()

            # History.
            prior_rows = snapshot_history(db, ticker=ticker, days=30)
            buzz_history = [float(r.snapshot_data.get("buzz_today") or 0) for r in prior_rows]
            sentiment_history = [float(r.snapshot_data.get("sentiment_score") or 0) for r in prior_rows]
            buzz_yesterday = buzz_history[-1] if buzz_history else 0.0

            per_source = {
                "social_media": self._naive_avg(result.items),
            }
            # In real deployments financial_provider supplies its own pre-computed reading.
            provider_sentiment = None
            if isinstance(quote, dict) and "sentiment_score" in quote:
                provider_sentiment = quote["sentiment_score"]
                per_source["financial_provider"] = float(provider_sentiment)

            snap = compute_snapshot(
                ticker=ticker,
                captured_at=datetime.now(UTC),
                classified=result.items,
                per_source_sentiment=per_source,
                buzz_today=len(posts),
                buzz_history=buzz_history,
                sentiment_history=sentiment_history,
                buzz_yesterday=buzz_yesterday,
                word_weights=None,
                analyst_ratings=(inst or {}).get("analyst_ratings") if inst else None,
                options=options,
                short_data=short,
                event_panel=None,
                reliability=matrix,
            )

            spike = detect_spike(
                ticker=ticker,
                buzz_today=len(posts),
                history=buzz_history[-7:],
                detected_at=datetime.now(UTC),
            )
            if spike:
                spikes.append(spike)

            row = write_snapshot(
                db,
                ticker=ticker,
                captured_at=snap.captured_at,
                snapshot_data={
                    **snap.model_dump(mode="json"),
                    "buzz_today": len(posts),
                },
                source_breakdown=snap.source_breakdown,
            )
            ids.append(row.id)

        return RsRunResult(snapshot_ids=ids, spike_events=spikes)

    @staticmethod
    def _naive_avg(items) -> float:
        if not items:
            return 0.0
        from openlia.retail_sentiment.schemas import ClassificationLabel
        bulls = sum(1 for i in items if i.classification is ClassificationLabel.BULLISH)
        bears = sum(1 for i in items if i.classification is ClassificationLabel.BEARISH)
        return (bulls - bears) / len(items)
```

- [ ] **Step 4: Run the test to confirm it passes**

Run: `uv run pytest packages/server/tests/services/test_rs_runner.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/services/rs_runner.py \
        packages/server/tests/services/test_rs_runner.py
git commit -m "feat(server): add RsRunner pipeline orchestrator"
```

---

### Task 13: Server — `RetailSentimentExecutor` + scheduler wiring

Scheduler executor implementing the Plan 6 `BaseExecutor` pattern. Reads user's watchlist, delegates to `RsRunner`, writes `job_runs` row, fans out notifications.

**Files:**
- Create: `packages/server/src/openlia_server/scheduler/executors/rs.py`
- Modify: `packages/server/src/openlia_server/scheduler/wiring.py`
- Test: `packages/server/tests/scheduler/test_rs_executor.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/scheduler/test_rs_executor.py
from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from openlia_server.db.models.auth import User
from openlia_server.db.models.content import Watchlist, WatchlistItem
from openlia_server.db.models.dashboard import RsSnapshot
from openlia_server.db.models.scheduler import JobRun
from openlia_server.scheduler.executors.rs import RetailSentimentExecutor
from openlia_server.scheduler.registry import JobType


class _StubRunner:
    async def run_snapshot_for_tickers(self, *, tickers, user_id):
        from openlia_server.services.rs_runner import RsRunResult
        return RsRunResult(snapshot_ids=[f"snap_{t}" for t in tickers], spike_events=[])


def _mk_user_with_watchlist(db: Session, uid: str, tickers: list[str]) -> None:
    u = User(id=uid, email=f"{uid}@x", display_name=uid, password_hash="x", is_admin=False)
    db.add(u)
    wl = Watchlist(id=f"wl_{uid}", user_id=uid, name="RS")
    db.add(wl)
    for t in tickers:
        db.add(WatchlistItem(id=f"wli_{uid}_{t}", watchlist_id=wl.id, ticker=t))
    db.commit()


@pytest.mark.asyncio
async def test_executor_runs_pipeline_for_user_watchlist(create_tables, db_session: Session) -> None:
    _mk_user_with_watchlist(db_session, "u_rs_e_1", ["AAPL", "TSLA"])
    exe = RetailSentimentExecutor(
        session_factory=lambda: db_session,
        runner=_StubRunner(),
    )
    await exe.execute(user_id="u_rs_e_1", triggered_at=datetime.now(UTC))
    # Job run recorded.
    jobs = db_session.query(JobRun).filter_by(job_type=JobType.RS_SNAPSHOT.value).all()
    assert len(jobs) == 1
    assert jobs[0].status == "completed"


@pytest.mark.asyncio
async def test_executor_handles_empty_watchlist(create_tables, db_session: Session) -> None:
    _mk_user_with_watchlist(db_session, "u_rs_e_2", [])
    exe = RetailSentimentExecutor(
        session_factory=lambda: db_session,
        runner=_StubRunner(),
    )
    await exe.execute(user_id="u_rs_e_2", triggered_at=datetime.now(UTC))
    jobs = db_session.query(JobRun).filter_by(job_type=JobType.RS_SNAPSHOT.value).all()
    assert len(jobs) == 1
    assert jobs[0].status == "completed"
    # No snapshots written because no tickers.
    assert db_session.query(RsSnapshot).count() == 0


@pytest.mark.asyncio
async def test_executor_records_failure(create_tables, db_session: Session) -> None:
    class _BoomRunner:
        async def run_snapshot_for_tickers(self, *, tickers, user_id):
            raise RuntimeError("boom")

    _mk_user_with_watchlist(db_session, "u_rs_e_3", ["AAPL"])
    exe = RetailSentimentExecutor(
        session_factory=lambda: db_session,
        runner=_BoomRunner(),
    )
    with pytest.raises(RuntimeError):
        await exe.execute(user_id="u_rs_e_3", triggered_at=datetime.now(UTC))
    jobs = db_session.query(JobRun).filter_by(job_type=JobType.RS_SNAPSHOT.value).all()
    assert len(jobs) == 1
    assert jobs[0].status == "failed"
    assert "boom" in (jobs[0].error or "")
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `uv run pytest packages/server/tests/scheduler/test_rs_executor.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Write the executor**

```python
# packages/server/src/openlia_server/scheduler/executors/rs.py
"""Retail Sentiment snapshot executor."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable, Protocol

from sqlalchemy.orm import Session

from openlia_server.db.models.content import Watchlist, WatchlistItem
from openlia_server.db.models.scheduler import JobRun
from openlia_server.scheduler.registry import JobType


class _Runner(Protocol):
    async def run_snapshot_for_tickers(self, *, tickers: list[str], user_id: str): ...


@dataclass
class RetailSentimentExecutor:
    session_factory: Callable[[], Session]
    runner: _Runner

    async def execute(self, *, user_id: str, triggered_at: datetime) -> None:
        db = self.session_factory()
        run = JobRun(
            id=str(uuid.uuid4()),
            job_type=JobType.RS_SNAPSHOT.value,
            user_id=user_id,
            triggered_at=triggered_at,
            status="running",
        )
        db.add(run)
        db.commit()

        try:
            tickers = self._tickers_for_user(db, user_id=user_id)
            if tickers:
                await self.runner.run_snapshot_for_tickers(tickers=tickers, user_id=user_id)
            run.status = "completed"
            run.completed_at = datetime.now(UTC)
            db.commit()
        except Exception as exc:
            run.status = "failed"
            run.completed_at = datetime.now(UTC)
            run.error = str(exc)[:512]
            db.commit()
            raise

    @staticmethod
    def _tickers_for_user(db: Session, *, user_id: str) -> list[str]:
        wl_ids = [
            row.id
            for row in db.query(Watchlist).filter_by(user_id=user_id).all()
        ]
        if not wl_ids:
            return []
        items = (
            db.query(WatchlistItem)
            .filter(WatchlistItem.watchlist_id.in_(wl_ids))
            .all()
        )
        seen: list[str] = []
        for it in items:
            if it.ticker not in seen:
                seen.append(it.ticker)
        return seen
```

- [ ] **Step 4: Wire into `scheduler/wiring.py`**

In `packages/server/src/openlia_server/scheduler/wiring.py`, add the executor to the factory:

```python
from openlia_server.scheduler.executors.rs import RetailSentimentExecutor
from openlia_server.services.rs_runner import RsRunner
# ... existing imports

# inside build_scheduler_service, after MR registration:
executors[JobType.RS_SNAPSHOT] = RetailSentimentExecutor(
    session_factory=session_factory,
    runner=rs_runner or _make_default_rs_runner(session_factory=session_factory, ...),
)
```

(Wire arguments match the surrounding pattern — see existing `EUScanExecutor` wiring for reference.)

- [ ] **Step 5: Run the test to confirm it passes**

Run: `uv run pytest packages/server/tests/scheduler/test_rs_executor.py -v`
Expected: PASS (3 tests).

Also re-run `uv run pytest packages/server/tests/scheduler/ -v` to make sure the wiring change didn't regress MB/EU/MR.

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/scheduler/executors/rs.py \
        packages/server/src/openlia_server/scheduler/wiring.py \
        packages/server/tests/scheduler/test_rs_executor.py
git commit -m "feat(scheduler): add RetailSentimentExecutor + wiring"
```

---

### Task 14: Server — Routes `/dashboard` + `/dashboard/history`

Two GET endpoints under `/departments/retail_sentiment`. Both authenticated.

`GET /dashboard` returns the latest snapshot for each ticker in the user's watchlist (lazy-computes by running the pipeline if no rows exist). `GET /dashboard/history?ticker=AAPL&days=30` returns history rows for a single ticker.

**Files:**
- Create: `packages/server/src/openlia_server/routes/departments/retail_sentiment.py`
- Modify: `packages/server/src/openlia_server/app.py` (mount router)
- Test: `packages/server/tests/routes/test_retail_sentiment_dashboard.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/server/tests/routes/test_retail_sentiment_dashboard.py
from datetime import UTC, datetime

import pytest


def test_get_dashboard_requires_auth(client) -> None:
    r = client.get("/departments/retail_sentiment/dashboard")
    assert r.status_code in (401, 403)


def test_get_dashboard_returns_latest_per_ticker(authed_client, seed_user, seed_watchlist, seed_snapshots) -> None:
    r = authed_client.get("/departments/retail_sentiment/dashboard")
    assert r.status_code == 200
    body = r.json()
    assert "tickers" in body
    # AAPL and TSLA seeded; each returns the latest snapshot.
    assert {t["ticker"] for t in body["tickers"]} == {"AAPL", "TSLA"}


def test_get_dashboard_history_requires_days_param(authed_client) -> None:
    r = authed_client.get("/departments/retail_sentiment/dashboard/history")
    assert r.status_code == 422


def test_get_dashboard_history_returns_rows(authed_client, seed_snapshots) -> None:
    r = authed_client.get("/departments/retail_sentiment/dashboard/history?ticker=AAPL&days=30")
    assert r.status_code == 200
    body = r.json()
    assert body["ticker"] == "AAPL"
    assert isinstance(body["points"], list)
    assert all("captured_at" in p and "sentiment_score" in p for p in body["points"])
```

- [ ] **Step 2: Run the test to confirm it fails** (404 or ModuleNotFoundError)

- [ ] **Step 3: Write the router factory**

```python
# packages/server/src/openlia_server/routes/departments/retail_sentiment.py
"""Retail Sentiment REST routes."""

from __future__ import annotations

from typing import Callable

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from openlia_server.db.models.auth import User
from openlia_server.db.models.content import Watchlist, WatchlistItem
from openlia_server.middleware.auth import build_require_auth
from openlia_server.services.rs_snapshot import history, latest_for_tickers


class _DashboardTickerResponse(BaseModel):
    ticker: str
    snapshot: dict
    captured_at: str


class _DashboardResponse(BaseModel):
    tickers: list[_DashboardTickerResponse]


class _HistoryPoint(BaseModel):
    captured_at: str
    sentiment_score: float
    buzz_volume: float
    sentiment_momentum: float


class _HistoryResponse(BaseModel):
    ticker: str
    points: list[_HistoryPoint]


def build_retail_sentiment_router(
    *, db_session_factory: Callable[[], Session], mode: str
) -> APIRouter:
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
    router = APIRouter(prefix="/departments/retail_sentiment", tags=["retail_sentiment"])

    def _session() -> Session:
        return db_session_factory()

    def _watchlist_tickers(db: Session, user_id: str) -> list[str]:
        wl_ids = [r.id for r in db.query(Watchlist).filter_by(user_id=user_id).all()]
        if not wl_ids:
            return []
        items = db.query(WatchlistItem).filter(WatchlistItem.watchlist_id.in_(wl_ids)).all()
        seen: list[str] = []
        for it in items:
            if it.ticker not in seen:
                seen.append(it.ticker)
        return seen

    @router.get("/dashboard", response_model=_DashboardResponse)
    def get_dashboard(user: User = Depends(require_auth)) -> _DashboardResponse:
        db = _session()
        tickers = _watchlist_tickers(db, user.id)
        latest = latest_for_tickers(db, tickers=tickers)
        payload = [
            _DashboardTickerResponse(
                ticker=t,
                snapshot=latest[t].snapshot_data,
                captured_at=latest[t].captured_at.isoformat(),
            )
            for t in tickers
            if t in latest
        ]
        return _DashboardResponse(tickers=payload)

    @router.get("/dashboard/history", response_model=_HistoryResponse)
    def get_history(
        ticker: str = Query(..., min_length=1, max_length=16),
        days: int = Query(..., ge=1, le=365),
        user: User = Depends(require_auth),
    ) -> _HistoryResponse:
        db = _session()
        rows = history(db, ticker=ticker.upper(), days=days)
        points = [
            _HistoryPoint(
                captured_at=r.captured_at.isoformat(),
                sentiment_score=float(r.snapshot_data.get("sentiment_score", 0.0)),
                buzz_volume=float(r.snapshot_data.get("buzz_volume", 0.0)),
                sentiment_momentum=float(r.snapshot_data.get("sentiment_momentum", 0.0)),
            )
            for r in rows
        ]
        return _HistoryResponse(ticker=ticker.upper(), points=points)

    return router
```

- [ ] **Step 4: Mount the router in `app.py`**

```python
# inside app factory
from openlia_server.routes.departments.retail_sentiment import build_retail_sentiment_router
app.include_router(
    build_retail_sentiment_router(db_session_factory=session_factory, mode=mode)
)
```

- [ ] **Step 5: Run the test to confirm it passes**

Run: `uv run pytest packages/server/tests/routes/test_retail_sentiment_dashboard.py -v`
Expected: PASS (4 tests).

- [ ] **Step 6: Also update the contract matrices**

Append rows to `planning/implementation-plans/endpoint-contract-matrix.md` and `route-authorization-matrix.md` for `GET /departments/retail_sentiment/dashboard` and `/dashboard/history` (auth=user; owner-scoped; both personal+company).

- [ ] **Step 7: Commit**

```bash
git add packages/server/src/openlia_server/routes/departments/retail_sentiment.py \
        packages/server/src/openlia_server/app.py \
        packages/server/tests/routes/test_retail_sentiment_dashboard.py \
        planning/implementation-plans/endpoint-contract-matrix.md \
        planning/implementation-plans/route-authorization-matrix.md
git commit -m "feat(server): add /departments/retail_sentiment/dashboard + /history routes"
```

---

### Task 15: Server — Routes `/config` GET/PUT

Per-user config access.

**Files:**
- Modify: `packages/server/src/openlia_server/routes/departments/retail_sentiment.py` (add GET/PUT)
- Test: extend `packages/server/tests/routes/test_retail_sentiment_dashboard.py` (or a new test file)

- [ ] **Step 1: Write the failing test**

```python
def test_get_config_returns_defaults(authed_client) -> None:
    r = authed_client.get("/departments/retail_sentiment/config")
    assert r.status_code == 200
    body = r.json()
    assert body["active_tab"] == "overview"
    assert body["metric_settings"]["divergence_threshold"] == 2.0


def test_put_config_merges(authed_client) -> None:
    payload = {"metric_settings": {"buzz_spike_multiplier": 2.0}, "refresh_interval_minutes": 30}
    r = authed_client.put("/departments/retail_sentiment/config", json=payload)
    assert r.status_code == 200
    body = r.json()
    assert body["refresh_interval_minutes"] == 30
    assert body["metric_settings"]["buzz_spike_multiplier"] == 2.0
    assert body["metric_settings"]["divergence_threshold"] == 2.0


def test_put_config_rejects_invalid(authed_client) -> None:
    r = authed_client.put(
        "/departments/retail_sentiment/config",
        json={"refresh_interval_minutes": -5},
    )
    assert r.status_code == 422
```

- [ ] **Step 2: Run the test to confirm it fails.** (404)

- [ ] **Step 3: Extend the router**

```python
class _ConfigResponse(BaseModel):
    active_tab: str
    refresh_interval_minutes: int
    metric_settings: dict
    filter_presets: list


class _ConfigPatchBody(BaseModel):
    active_tab: str | None = None
    refresh_interval_minutes: int | None = Field(default=None, ge=5, le=1440)
    metric_settings: dict | None = None
    filter_presets: list | None = None


@router.get("/config", response_model=_ConfigResponse)
def get_config(user: User = Depends(require_auth)) -> _ConfigResponse:
    db = _session()
    cfg = get_or_create_config(db, user_id=user.id)
    return _ConfigResponse(
        active_tab=cfg.active_tab,
        refresh_interval_minutes=cfg.refresh_interval_minutes,
        metric_settings=cfg.metric_settings,
        filter_presets=cfg.filter_presets,
    )


@router.put("/config", response_model=_ConfigResponse)
def put_config(body: _ConfigPatchBody, user: User = Depends(require_auth)) -> _ConfigResponse:
    db = _session()
    get_or_create_config(db, user_id=user.id)
    cfg = update_config(
        db,
        user_id=user.id,
        patch=RsConfigPatch(**body.model_dump(exclude_none=True)),
    )
    return _ConfigResponse(
        active_tab=cfg.active_tab,
        refresh_interval_minutes=cfg.refresh_interval_minutes,
        metric_settings=cfg.metric_settings,
        filter_presets=cfg.filter_presets,
    )
```

(Add imports: `from pydantic import Field`, `from openlia_server.services.rs_config import RsConfigPatch, get_or_create_config, update_config`.)

- [ ] **Step 4: Run the test.** Expected: PASS.

- [ ] **Step 5: Update matrices** as in Task 14.

- [ ] **Step 6: Commit.**

```bash
git commit -am "feat(server): add retail_sentiment /config GET/PUT"
```

---

### Task 16: Server — Route `/run` POST (on-demand snapshot)

`POST /departments/retail_sentiment/run` runs the pipeline synchronously for the user's watchlist (or a body-supplied `tickers` override). Returns `{snapshot_ids, spike_events}`.

**Files:**
- Modify: `packages/server/src/openlia_server/routes/departments/retail_sentiment.py`
- Test: `packages/server/tests/routes/test_retail_sentiment_run.py`

- [ ] **Step 1: Failing test**

```python
@pytest.mark.asyncio
async def test_run_triggers_pipeline(authed_client, seed_watchlist, stub_runner) -> None:
    r = authed_client.post("/departments/retail_sentiment/run", json={})
    assert r.status_code == 200
    body = r.json()
    assert "snapshot_ids" in body
    assert isinstance(body["snapshot_ids"], list)


@pytest.mark.asyncio
async def test_run_respects_tickers_override(authed_client, stub_runner) -> None:
    r = authed_client.post("/departments/retail_sentiment/run", json={"tickers": ["NVDA"]})
    assert r.status_code == 200
    assert stub_runner.last_tickers == ["NVDA"]


@pytest.mark.asyncio
async def test_run_empty_watchlist_no_error(authed_client, clean_watchlist, stub_runner) -> None:
    r = authed_client.post("/departments/retail_sentiment/run", json={})
    assert r.status_code == 200
    assert r.json()["snapshot_ids"] == []
```

- [ ] **Step 2: Run, observe failure.** (404)

- [ ] **Step 3: Extend the router**

```python
class _RunBody(BaseModel):
    tickers: list[str] | None = None


class _RunResponse(BaseModel):
    snapshot_ids: list[str]
    spike_events: list[dict]


@router.post("/run", response_model=_RunResponse)
async def post_run(
    body: _RunBody,
    user: User = Depends(require_auth),
    runner: RsRunner = Depends(get_rs_runner),
) -> _RunResponse:
    db = _session()
    tickers = body.tickers or _watchlist_tickers(db, user.id)
    if not tickers:
        return _RunResponse(snapshot_ids=[], spike_events=[])
    result = await runner.run_snapshot_for_tickers(tickers=tickers, user_id=user.id)
    return _RunResponse(
        snapshot_ids=result.snapshot_ids,
        spike_events=[e.model_dump(mode="json") for e in result.spike_events],
    )
```

(Add `get_rs_runner` dependency — construct from a module-level factory or from FastAPI app state. Wire a default injection in `app.py` or via `Depends(build_rs_runner_dep(...))` inside `build_retail_sentiment_router`.)

- [ ] **Step 4: Run, expect PASS.**

- [ ] **Step 5: Update matrices.**

- [ ] **Step 6: Commit.**

```bash
git commit -am "feat(server): add retail_sentiment /run on-demand endpoint"
```

---

### Task 17: Server — Routes `/schedule` GET/PUT

RS schedule is persisted in a generic scheduler table (same one MB/EU/MR use). `GET /schedule` returns the row if present; `PUT /schedule` upserts. Body shape: `{cron_expression, timezone, label, days_of_week}`. On change, call `SchedulerService.modify_schedule(...)` or `add_schedule(...)` to hot-reload.

**Files:**
- Modify: `packages/server/src/openlia_server/routes/departments/retail_sentiment.py`
- Test: `packages/server/tests/routes/test_retail_sentiment_schedule.py`

- [ ] **Step 1: Failing test**

```python
def test_get_schedule_returns_404_when_absent(authed_client) -> None:
    r = authed_client.get("/departments/retail_sentiment/schedule")
    assert r.status_code == 404


def test_put_schedule_creates(authed_client, fake_scheduler) -> None:
    r = authed_client.put(
        "/departments/retail_sentiment/schedule",
        json={
            "cron_expression": "0 9 * * *",
            "timezone": "America/Los_Angeles",
            "label": "Daily 9am",
            "days_of_week": [0, 1, 2, 3, 4],
        },
    )
    assert r.status_code == 200
    assert fake_scheduler.added_job_type.value == "rs_snapshot"


def test_get_schedule_after_put(authed_client, fake_scheduler) -> None:
    authed_client.put(
        "/departments/retail_sentiment/schedule",
        json={"cron_expression": "0 9 * * *", "timezone": "UTC"},
    )
    r = authed_client.get("/departments/retail_sentiment/schedule")
    assert r.status_code == 200
    assert r.json()["cron_expression"] == "0 9 * * *"


def test_put_rejects_invalid_cron(authed_client) -> None:
    r = authed_client.put(
        "/departments/retail_sentiment/schedule",
        json={"cron_expression": "garbage", "timezone": "UTC"},
    )
    assert r.status_code == 422
```

- [ ] **Step 2: Run, observe failure.**

- [ ] **Step 3: Extend the router** with GET + PUT for schedule. Persist to the generic `schedules` table used by MB/EU/MR (or to a new RS-specific table if the existing generic one was not built — this will be clear from Plan 6). For the most recent shipped code, the scheduler uses per-department tables; if an `rs_schedules` table does not exist, reuse `mb_schedules`-style shape inside `RsUserConfig.metric_settings["schedule"]` (JSON sub-doc) — this is acceptable because the scheduler service writes to APScheduler in memory and rebuilds from this JSON at startup.

Assert the constraint: one schedule per `(JobType.RS_SNAPSHOT, user_id)`.

- [ ] **Step 4: Run, PASS.**

- [ ] **Step 5: Matrices.**

- [ ] **Step 6: Commit.**

```bash
git commit -am "feat(server): add retail_sentiment /schedule GET/PUT"
```

---

### Task 18: Server — Route `/stocks/{ticker}/sentiment`

Per-ticker detailed view: latest snapshot + last-30-days history + per-source breakdown + computed active signals.

**Files:**
- Modify: `packages/server/src/openlia_server/routes/departments/retail_sentiment.py`
- Test: `packages/server/tests/routes/test_retail_sentiment_stocks.py`

- [ ] **Step 1: Failing test**

```python
def test_stock_sentiment_returns_detail(authed_client, seed_snapshots) -> None:
    r = authed_client.get("/departments/retail_sentiment/stocks/AAPL/sentiment")
    assert r.status_code == 200
    body = r.json()
    assert body["ticker"] == "AAPL"
    assert "latest" in body
    assert "history" in body
    assert "active_signals" in body
    assert isinstance(body["active_signals"], list)


def test_stock_sentiment_404_when_no_snapshots(authed_client) -> None:
    r = authed_client.get("/departments/retail_sentiment/stocks/ZZZZ/sentiment")
    assert r.status_code == 404
```

- [ ] **Step 2: Fail.**

- [ ] **Step 3: Implement**

```python
@router.get("/stocks/{ticker}/sentiment")
def get_stock_sentiment(ticker: str, user: User = Depends(require_auth)) -> dict:
    db = _session()
    latest = latest_for_tickers(db, tickers=[ticker.upper()])
    if ticker.upper() not in latest:
        raise HTTPException(status_code=404, detail="no snapshots for ticker")
    cfg = get_or_create_config(db, user_id=user.id)
    hist = history(db, ticker=ticker.upper(), days=30)
    signals = _compute_active_signals(latest[ticker.upper()].snapshot_data, cfg.metric_settings)
    return {
        "ticker": ticker.upper(),
        "latest": latest[ticker.upper()].snapshot_data,
        "captured_at": latest[ticker.upper()].captured_at.isoformat(),
        "history": [
            {
                "captured_at": r.captured_at.isoformat(),
                "sentiment_score": float(r.snapshot_data.get("sentiment_score", 0)),
                "buzz_volume": float(r.snapshot_data.get("buzz_volume", 0)),
            }
            for r in hist
        ],
        "active_signals": signals,
    }
```

where `_compute_active_signals(snap, thresholds)` inspects each of the 12 metric values against the user's thresholds and returns a list of `{metric_id, severity, message, value}` dicts.

- [ ] **Step 4: PASS.**

- [ ] **Step 5: Matrices.**

- [ ] **Step 6: Commit.**

```bash
git commit -am "feat(server): add retail_sentiment /stocks/{ticker}/sentiment endpoint"
```

---

### Task 19: Server — Route `/spikes`

`GET /spikes?days=7` returns detected volume spikes across the user's watchlist.

**Files:**
- Modify: `packages/server/src/openlia_server/routes/departments/retail_sentiment.py`
- Test: `packages/server/tests/routes/test_retail_sentiment_spikes.py`

- [ ] **Step 1: Failing test**

```python
def test_spikes_returns_empty_when_quiet(authed_client, seed_flat_snapshots) -> None:
    r = authed_client.get("/departments/retail_sentiment/spikes?days=7")
    assert r.status_code == 200
    assert r.json()["spikes"] == []


def test_spikes_returns_detected_events(authed_client, seed_spiky_snapshots) -> None:
    r = authed_client.get("/departments/retail_sentiment/spikes?days=7")
    assert r.status_code == 200
    tickers = {s["ticker"] for s in r.json()["spikes"]}
    assert "GME" in tickers


def test_spikes_days_param_clamped(authed_client) -> None:
    r = authed_client.get("/departments/retail_sentiment/spikes?days=500")
    assert r.status_code == 422
```

- [ ] **Step 2: Fail.**

- [ ] **Step 3: Implement**

```python
@router.get("/spikes")
def get_spikes(
    days: int = Query(7, ge=1, le=90),
    user: User = Depends(require_auth),
) -> dict:
    db = _session()
    tickers = _watchlist_tickers(db, user.id)
    now = datetime.now(UTC)
    spikes: list[dict] = []
    for t in tickers:
        hist = history(db, ticker=t, days=days + 1)
        if len(hist) < 8:
            continue
        buzz_today = float(hist[-1].snapshot_data.get("buzz_today", 0))
        buzz_hist = [float(r.snapshot_data.get("buzz_today", 0)) for r in hist[-8:-1]]
        ev = detect_spike(ticker=t, buzz_today=buzz_today, history=buzz_hist, detected_at=now)
        if ev:
            spikes.append(ev.model_dump(mode="json"))
    return {"spikes": spikes}
```

- [ ] **Step 4: PASS.**

- [ ] **Step 5: Matrices.**

- [ ] **Step 6: Commit.**

```bash
git commit -am "feat(server): add retail_sentiment /spikes endpoint"
```

---

### Task 20: Frontend — Typed API client

**Files:**
- Create: `frontend/src/api/retail-sentiment.ts`
- Test: `frontend/src/api/__tests__/retail-sentiment.test.ts`

- [ ] **Step 1: Failing test**

```typescript
// frontend/src/api/__tests__/retail-sentiment.test.ts
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  fetchDashboard,
  fetchHistory,
  fetchConfig,
  updateConfig,
  runSnapshot,
  fetchSchedule,
  putSchedule,
  fetchStock,
  fetchSpikes,
} from "../retail-sentiment";

const fetchMock = vi.fn();
beforeEach(() => {
  fetchMock.mockReset();
  globalThis.fetch = fetchMock as any;
});

afterEach(() => {
  vi.restoreAllMocks();
});

function ok(body: unknown) {
  return Promise.resolve({
    ok: true,
    json: () => Promise.resolve(body),
  } as Response);
}

describe("retail-sentiment api", () => {
  it("fetchDashboard hits /api/departments/retail_sentiment/dashboard", async () => {
    fetchMock.mockReturnValueOnce(ok({ tickers: [] }));
    const r = await fetchDashboard();
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/departments/retail_sentiment/dashboard",
      expect.objectContaining({ credentials: "include" }),
    );
    expect(r.tickers).toEqual([]);
  });

  it("fetchHistory builds query string", async () => {
    fetchMock.mockReturnValueOnce(ok({ ticker: "AAPL", points: [] }));
    await fetchHistory({ ticker: "AAPL", days: 30 });
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/departments/retail_sentiment/dashboard/history?ticker=AAPL&days=30",
      expect.any(Object),
    );
  });

  it("updateConfig PUTs merged patch", async () => {
    fetchMock.mockReturnValueOnce(ok({}));
    await updateConfig({ refresh_interval_minutes: 30 });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/departments/retail_sentiment/config");
    expect(init.method).toBe("PUT");
    expect(JSON.parse(init.body)).toEqual({ refresh_interval_minutes: 30 });
  });

  it("runSnapshot POSTs with tickers", async () => {
    fetchMock.mockReturnValueOnce(ok({ snapshot_ids: ["s1"], spike_events: [] }));
    await runSnapshot({ tickers: ["AAPL"] });
    expect(fetchMock.mock.calls[0][1].method).toBe("POST");
  });

  it("putSchedule sends cron + days_of_week", async () => {
    fetchMock.mockReturnValueOnce(ok({}));
    await putSchedule({ cron_expression: "0 9 * * *", timezone: "UTC" });
    expect(fetchMock.mock.calls[0][0]).toBe("/api/departments/retail_sentiment/schedule");
  });

  it("fetchSpikes includes days param", async () => {
    fetchMock.mockReturnValueOnce(ok({ spikes: [] }));
    await fetchSpikes({ days: 7 });
    expect(fetchMock.mock.calls[0][0]).toContain("?days=7");
  });
});
```

- [ ] **Step 2: Fail.**

- [ ] **Step 3: Write the client**

```typescript
// frontend/src/api/retail-sentiment.ts
export interface RsDashboardTicker {
  ticker: string;
  snapshot: Record<string, unknown>;
  captured_at: string;
}

export interface RsDashboardResponse {
  tickers: RsDashboardTicker[];
}

export interface RsHistoryPoint {
  captured_at: string;
  sentiment_score: number;
  buzz_volume: number;
  sentiment_momentum: number;
}

export interface RsHistoryResponse {
  ticker: string;
  points: RsHistoryPoint[];
}

export interface RsConfig {
  active_tab: string;
  refresh_interval_minutes: number;
  metric_settings: Record<string, unknown>;
  filter_presets: unknown[];
}

export interface RsSchedule {
  cron_expression: string;
  timezone: string;
  label?: string;
  days_of_week?: number[];
}

export interface RsSpikeEvent {
  ticker: string;
  detected_at: string;
  buzz: number;
  baseline_mean: number;
  baseline_stddev: number;
  z_score: number;
}

const BASE = "/api/departments/retail_sentiment";

async function request<T>(url: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(url, { credentials: "include", ...init });
  if (!resp.ok) {
    throw new Error(`RS API ${resp.status} ${resp.statusText}`);
  }
  return (await resp.json()) as T;
}

export function fetchDashboard(): Promise<RsDashboardResponse> {
  return request<RsDashboardResponse>(`${BASE}/dashboard`);
}

export function fetchHistory(args: { ticker: string; days: number }): Promise<RsHistoryResponse> {
  const qs = new URLSearchParams({ ticker: args.ticker, days: String(args.days) });
  return request<RsHistoryResponse>(`${BASE}/dashboard/history?${qs.toString()}`);
}

export function fetchConfig(): Promise<RsConfig> {
  return request<RsConfig>(`${BASE}/config`);
}

export function updateConfig(patch: Partial<RsConfig>): Promise<RsConfig> {
  return request<RsConfig>(`${BASE}/config`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(patch),
  });
}

export function runSnapshot(body: { tickers?: string[] } = {}): Promise<{
  snapshot_ids: string[];
  spike_events: RsSpikeEvent[];
}> {
  return request(`${BASE}/run`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

export function fetchSchedule(): Promise<RsSchedule | null> {
  return request<RsSchedule | null>(`${BASE}/schedule`).catch(() => null);
}

export function putSchedule(schedule: RsSchedule): Promise<RsSchedule> {
  return request<RsSchedule>(`${BASE}/schedule`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(schedule),
  });
}

export function fetchStock(ticker: string): Promise<{
  ticker: string;
  latest: Record<string, unknown>;
  captured_at: string;
  history: RsHistoryPoint[];
  active_signals: Array<{ metric_id: string; severity: string; message: string; value: number }>;
}> {
  return request(`${BASE}/stocks/${encodeURIComponent(ticker)}/sentiment`);
}

export function fetchSpikes(args: { days: number }): Promise<{ spikes: RsSpikeEvent[] }> {
  return request(`${BASE}/spikes?days=${args.days}`);
}
```

- [ ] **Step 4: PASS.**

- [ ] **Step 5: Commit.**

```bash
git add frontend/src/api/retail-sentiment.ts frontend/src/api/__tests__/retail-sentiment.test.ts
git commit -m "feat(frontend): add retail-sentiment typed API client"
```

---

### Task 21: Frontend — Hooks (`useRsDashboard`, `useRsHistory`, `useRsConfig`, `useRsSpikes`, `useRsSchedule`)

SWR-style hooks over the API client. Each hook returns `{data, error, isLoading, mutate}`.

**Files:**
- Create: `frontend/src/hooks/useRsDashboard.ts`
- Create: `frontend/src/hooks/useRsHistory.ts`
- Create: `frontend/src/hooks/useRsConfig.ts`
- Create: `frontend/src/hooks/useRsSpikes.ts`
- Create: `frontend/src/hooks/useRsSchedule.ts`
- Test: `frontend/src/hooks/__tests__/retail-sentiment-hooks.test.tsx`

- [ ] **Step 1: Failing test** (test all 5 hooks with `@testing-library/react-hooks` and mocked fetch).
- [ ] **Step 2: Fail.**
- [ ] **Step 3: Write hooks**. Each wraps `useSWR` from `swr` and re-exports the mutator.
- [ ] **Step 4: PASS.**
- [ ] **Step 5: Commit.**

```bash
git commit -am "feat(frontend): add retail-sentiment SWR hooks"
```

---

### Task 22: Frontend — `MetricCard` + `SentimentGauge` + `ReliabilityBadge`

Reusable visual atoms. `MetricCard` takes `label`, `value`, `unit`, `trendDelta`, `severity` and renders the spec's card style. `SentimentGauge` is a canvas/SVG arc from -1 to +1. `ReliabilityBadge` renders `N/M sources agree` with color coding.

**Files:**
- Create: `frontend/src/components/retail-sentiment/MetricCard.tsx`
- Create: `frontend/src/components/retail-sentiment/SentimentGauge.tsx`
- Create: `frontend/src/components/retail-sentiment/ReliabilityBadge.tsx`
- Test: `frontend/src/components/retail-sentiment/__tests__/metric-card.test.tsx`

- [ ] **Step 1: Failing test** — render each component, assert text + role + class names.
- [ ] **Step 2: Fail.**
- [ ] **Step 3: Implement** per spec card style (`bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[--radius-lg] p-4` etc).
- [ ] **Step 4: PASS.**
- [ ] **Step 5: Commit.**

```bash
git commit -am "feat(frontend): add RS MetricCard, SentimentGauge, ReliabilityBadge"
```

---

### Task 23: Frontend — `OverviewTab`

Composes headline tier (4 cards) + compact tier (8 cards) when a single ticker is selected. When "All" is selected, renders the summary cards + heat-map matrix (tickers × 6 key metrics).

**Files:**
- Create: `frontend/src/components/retail-sentiment/OverviewTab.tsx`
- Test: `frontend/src/components/retail-sentiment/__tests__/overview-tab.test.tsx`

- [ ] **Step 1: Failing test** — two scenarios: single-ticker layout vs "All" heat map.
- [ ] **Step 2: Fail.**
- [ ] **Step 3: Implement.** Use `MetricCard` atoms. Heat-map is a CSS grid with cell colors mapped by metric state.
- [ ] **Step 4: PASS.**
- [ ] **Step 5: Commit.**

```bash
git commit -am "feat(frontend): add RS OverviewTab"
```

---

### Task 24: Frontend — `PerStockTab` + `TrendChart`

`PerStockTab` fetches `/stocks/{ticker}/sentiment`, renders the 12 metric breakdown, trend charts (sentiment vs price overlay, buzz bars, momentum area), and the active-signals panel.

`TrendChart` is a Recharts line/area/bar wrapper configurable by series type.

**Files:**
- Create: `frontend/src/components/retail-sentiment/PerStockTab.tsx`
- Create: `frontend/src/components/retail-sentiment/TrendChart.tsx`
- Test: `frontend/src/components/retail-sentiment/__tests__/per-stock-tab.test.tsx`

- [ ] Steps 1–5 following TDD pattern. Commit:

```bash
git commit -am "feat(frontend): add RS PerStockTab + TrendChart"
```

---

### Task 25: Frontend — `SpikesTab`

Lists detected volume spikes from `/spikes?days=7`. Each row: ticker, buzz value, z-score, detected-at timestamp. Click a row to open `PerStockTab` for that ticker.

**Files:**
- Create: `frontend/src/components/retail-sentiment/SpikesTab.tsx`
- Test: `frontend/src/components/retail-sentiment/__tests__/spikes-tab.test.tsx`

- [ ] Steps 1–5. Commit:

```bash
git commit -am "feat(frontend): add RS SpikesTab"
```

---

### Task 26: Frontend — `ScheduleEditor` + `SettingsDrawer` + `SignalAlert`

`ScheduleEditor` is a modal dialog for editing the RS cron schedule (time + days_of_week + label + timezone).

`SettingsDrawer` is a 480px right drawer wrapping the thresholds + cross-source weights + per-metric toggles + watchlist management.

`SignalAlert` renders one active signal as a red/amber/green bordered card per the Insights-tab spec.

**Files:**
- Create: `frontend/src/components/retail-sentiment/ScheduleEditor.tsx`
- Create: `frontend/src/components/retail-sentiment/SettingsDrawer.tsx`
- Create: `frontend/src/components/retail-sentiment/SignalAlert.tsx`
- Test: `frontend/src/components/retail-sentiment/__tests__/schedule-editor.test.tsx`
- Test: `frontend/src/components/retail-sentiment/__tests__/settings-drawer.test.tsx`

- [ ] Steps 1–5 each. Commit:

```bash
git commit -am "feat(frontend): add RS ScheduleEditor, SettingsDrawer, SignalAlert"
```

---

### Task 27: Frontend — `RetailSentiment.tsx` page composition

Replace the placeholder with the full page: header + tab bar + ticker selector + active-tab body + help drawer. Wire hooks.

**Files:**
- Modify: `frontend/src/pages/departments/RetailSentiment.tsx`
- Test: `frontend/src/pages/departments/__tests__/retail-sentiment-page.test.tsx`

- [ ] **Step 1: Failing test**

```tsx
// frontend/src/pages/departments/__tests__/retail-sentiment-page.test.tsx
import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import RetailSentiment from "../RetailSentiment";

describe("RetailSentiment page", () => {
  it("renders the three tabs", () => {
    render(<RetailSentiment />);
    expect(screen.getByRole("tab", { name: /overview/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /per[- ]stock/i })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /spike/i })).toBeInTheDocument();
  });

  it("renders a settings trigger", () => {
    render(<RetailSentiment />);
    expect(screen.getByRole("button", { name: /settings/i })).toBeInTheDocument();
  });

  it("renders the help button at bottom-right", () => {
    render(<RetailSentiment />);
    expect(screen.getByRole("button", { name: /\?|help/i })).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Fail.**

- [ ] **Step 3: Rewrite the page**

```tsx
// frontend/src/pages/departments/RetailSentiment.tsx
import { useState } from "react";
import * as Tabs from "@radix-ui/react-tabs";
import { OverviewTab } from "../../components/retail-sentiment/OverviewTab";
import { PerStockTab } from "../../components/retail-sentiment/PerStockTab";
import { SpikesTab } from "../../components/retail-sentiment/SpikesTab";
import { SettingsDrawer } from "../../components/retail-sentiment/SettingsDrawer";
import { useRsDashboard } from "../../hooks/useRsDashboard";
import { useRsConfig } from "../../hooks/useRsConfig";

export default function RetailSentimentPage(): JSX.Element {
  const [selectedTicker, setSelectedTicker] = useState<string | "ALL">("ALL");
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [helpOpen, setHelpOpen] = useState(false);
  const dashboard = useRsDashboard();
  const config = useRsConfig();

  return (
    <div className="flex flex-col h-full">
      <header className="h-14 flex-shrink-0 bg-[--color-bg-base] border-b border-[--color-border-subtle] flex items-center justify-between">
        <h1 className="text-xl font-semibold text-[--color-text-primary] pl-6">
          Retail Sentiment
        </h1>
        <div className="flex items-center gap-3 pr-6">
          {/* Auto-refresh dropdown would go here */}
          <button
            type="button"
            aria-label="Settings"
            onClick={() => setSettingsOpen(true)}
            className="text-sm text-[--color-text-secondary] border border-[--color-border-subtle] px-3 py-1 rounded-md"
          >
            Settings
          </button>
        </div>
      </header>

      <Tabs.Root defaultValue="overview" className="flex flex-col flex-1 min-h-0">
        <Tabs.List
          className="flex items-center gap-1 px-6 bg-[--color-bg-base] border-b border-[--color-border-subtle]"
        >
          <Tabs.Trigger value="overview" className="px-4 py-2.5 text-sm">Overview</Tabs.Trigger>
          <Tabs.Trigger value="per-stock" className="px-4 py-2.5 text-sm">Per-Stock</Tabs.Trigger>
          <Tabs.Trigger value="spikes" className="px-4 py-2.5 text-sm">Spikes</Tabs.Trigger>
        </Tabs.List>

        {/* ticker selector */}
        <div className="flex items-center gap-2 px-6 py-2 border-b border-[--color-border-subtle] overflow-x-auto">
          <button
            type="button"
            onClick={() => setSelectedTicker("ALL")}
            className={`px-3 py-1 rounded-full text-sm ${selectedTicker === "ALL" ? "bg-[--color-surface-active] text-[--color-text-primary] font-medium" : "text-[--color-text-secondary] border border-[--color-border-subtle]"}`}
          >
            All
          </button>
          {dashboard.data?.tickers.map((t) => (
            <button
              type="button"
              key={t.ticker}
              onClick={() => setSelectedTicker(t.ticker)}
              className={`px-3 py-1 rounded-full text-sm ${selectedTicker === t.ticker ? "bg-[--color-surface-active] text-[--color-text-primary] font-medium" : "text-[--color-text-secondary] border border-[--color-border-subtle]"}`}
            >
              {t.ticker}
            </button>
          ))}
        </div>

        <div className="flex-1 min-h-0 overflow-y-auto p-6">
          <Tabs.Content value="overview">
            <OverviewTab selectedTicker={selectedTicker} dashboard={dashboard.data} />
          </Tabs.Content>
          <Tabs.Content value="per-stock">
            <PerStockTab ticker={selectedTicker === "ALL" ? undefined : selectedTicker} />
          </Tabs.Content>
          <Tabs.Content value="spikes">
            <SpikesTab />
          </Tabs.Content>
        </div>
      </Tabs.Root>

      <button
        type="button"
        aria-label="Help"
        onClick={() => setHelpOpen(true)}
        className="fixed bottom-4 right-4 w-8 h-8 rounded-full bg-[--color-bg-elevated] border border-[--color-border-subtle] shadow-sm text-sm text-[--color-text-secondary]"
      >
        ?
      </button>

      <SettingsDrawer
        open={settingsOpen}
        onClose={() => setSettingsOpen(false)}
        config={config.data}
      />
      {/* Help drawer (Metrics Deep Dive) would render here when helpOpen */}
    </div>
  );
}
```

- [ ] **Step 4: PASS.**

- [ ] **Step 5: Commit**

```bash
git add frontend/src/pages/departments/RetailSentiment.tsx \
        frontend/src/pages/departments/__tests__/retail-sentiment-page.test.tsx
git commit -m "feat(frontend): compose RetailSentiment dashboard page"
```

---

### Task 28: Manual smoke test + flip README row to Draft

- [ ] **Step 1: Start the backend**

```bash
uv run openlia serve
```

- [ ] **Step 2: Start the frontend**

```bash
cd frontend && npm run dev
```

- [ ] **Step 3: Log in and navigate to `/retail-sentiment`.**

  Verify:
  - Overview tab renders the 4 headline + 8 compact cards for a watchlist ticker (or empty state when no tickers).
  - Clicking "All" renders the heat map.
  - Clicking Per-Stock renders the deep-dive view with trend charts.
  - Clicking Spikes renders the spike list.
  - Settings drawer opens and saves threshold changes.
  - Schedule editor creates a new cron schedule.
  - Help `?` button opens the Metrics Deep Dive drawer.

- [ ] **Step 4: Verify the scheduler picks up the new job type**

```bash
uv run python -c "
from openlia_server.scheduler.registry import JobType, job_key
print('RS enum:', JobType.RS_SNAPSHOT.value)
print('Key shape:', job_key(JobType.RS_SNAPSHOT, 'u_test'))
"
```

Expected output:
```
RS enum: rs_snapshot
Key shape: rs_snapshot:u_test
```

- [ ] **Step 5: Run the merge-gate commands**

```bash
uv run ruff check . && uv run ruff format --check . && uv run pytest -q
cd frontend && npm run test && cd ..
```

Expected: all green.

- [ ] **Step 6: Flip README row to Draft**

In `planning/implementation-plans/README.md`, change Plan 20's row:

```
| 20 | 6 | Retail Sentiment dashboard (12 metrics, 3 tabs) | Draft | `2026-04-23-phase-20-retail-sentiment.md` |
```

- [ ] **Step 7: Commit and open PR**

```bash
git commit -am "docs(plan): Phase 20 (Retail Sentiment) draft complete — ready for review"
```

Open PR `feat/phase-20-retail-sentiment` → `main`.

---

## Out of Scope (v1)

These are deliberately omitted. If a user asks, add a follow-up plan.

- Word-cloud / treemap rendering for Narrative Concentration (v1 shows the ratio as a single metric card).
- Real-time SSE streaming — RS polls at the configured refresh interval per the spec's "No real-time streaming" non-goal.
- Backtesting module for threshold calibration.
- Intraday resolution below hourly granularity.
- Slack / email / Telegram notification sinks — notifications route through the existing `user_notifications` table only.
- Taiwan-market or non-English NLP classification.
- Report generation / PDF export — RS is dashboard-only.
- Cross-user signal sharing.

---

## Self-Review Checklist

- [x] Each of the 12 metrics has a dedicated test in `test_metrics.py` (Metric 1 through Metric 12 each individually verified; `compute_snapshot` integration test covers composition).
- [x] Each of the 3 tabs has a dedicated frontend task: `OverviewTab` (Task 23), `PerStockTab` (Task 24), `SpikesTab` (Task 25).
- [x] Scheduler enum extension is explicit (Task 9 adds `JobType.RS_SNAPSHOT` and maps it to `retail_sentiment` in `_DEPARTMENT_BY_JOB`).
- [x] `rs_classification_log` presence was verified first (absent in the shipped Plan 1B model file — only `RsUserConfig` and `RsSnapshot` exist). Task 8 adds the table via Alembic migration.
- [x] No placeholder steps — every task ends with a concrete green-test command + commit.
- [x] Table names match shipped models: `rs_user_config`, `rs_snapshots`, new `rs_classification_log`. ORM class names: `RsUserConfig`, `RsSnapshot`, `RsClassificationLog`.
- [x] All IDs are `String(36)` UUIDs generated via `str(uuid.uuid4())`.
- [x] HTTP prefixes bare on backend (`/departments/retail_sentiment/...`); frontend hits `/api/...`.
- [x] Auth uses `build_require_auth` router-factory pattern.
- [x] No SSE required — RS is polling-only per spec; no named-event framing work needed.
- [x] Scheduler one-per-(job_type, user_id) constraint respected — Task 17's `/schedule` PUT performs add-or-modify against the single `(JobType.RS_SNAPSHOT, user_id)` key.
- [x] Backend `User` imports from `openlia_server.db.models.auth`.
- [x] Runtime imports use `openlia.llm.runtime.prompts` (PromptLoader) — no `ReportRequest` since RS produces no markdown reports.
- [x] Merge-gate commands (`ruff check`, `ruff format --check`, `pytest`, `npm test`) appear in Task 28.
- [x] Endpoint + authorization matrices updated incrementally (noted in Tasks 14–19).
