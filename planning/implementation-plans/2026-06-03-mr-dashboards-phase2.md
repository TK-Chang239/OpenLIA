# MR Dashboards Phase 2 — World Order + Four Seasons Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add two more live Macro Research dashboards — World Order (T4) and Four Seasons (T2) — using the proven `debt_cycle` vertical-slice pattern.

**Architecture:** First generalize the `report_dash_mr` engine, which is currently `debt_cycle`-hardcoded in two spots (the system-prompt template and the single `classify_debt_cycle` tool), into per-slug registries. Then add each dashboard as: a typed Pydantic payload (mirroring `dalio_copy/types.ts`), a light deterministic classifier in `macro_research/quant/`, a classify tool + system prompt, and a live frontend view (mirroring `DebtCycleView`). Heavy statistical engines (Markov / Monte-Carlo / VAR) are deferred — those tiles are LLM-authored narrative/`computed-lite` for now, with honest provenance.

**Tech Stack:** Python (Pydantic v2, dataclasses), `report_v2_3.research` tool API, React/TS/Vite, vitest, pytest.

**Scope decisions (locked with user, 2026-06-03):** Defer heavy quant; build the two self-contained dashboards (World Order + Four Seasons) this round. All-Weather (needs portfolio layer), Five Forces (depends on T1/T4), and Summary (aggregates all) are a later round.

**Reference pattern — the `debt_cycle` slice (read before starting):**
- Payload: `packages/core/src/openlia/macro_research/payloads.py` (`DebtCycleData` + sub-models)
- Classifier: `packages/core/src/openlia/macro_research/quant/classification.py`
- Classify + emit tools: `packages/core/src/openlia/llm/runtime/report_dash_mr/tools/dashboard_tools.py`
- Catalog: `packages/core/src/openlia/llm/runtime/report_dash_mr/tools/registry.py`
- Prompt: `packages/core/src/openlia/llm/runtime/report_dash_mr/prompts.py`
- Engine test: `packages/core/tests/runtime/report_dash_mr/test_runner_debt_cycle.py`
- Frontend live view: `frontend/src/pages/departments/macro_research/DebtCycleView.tsx`
- Snapshot: `packages/core/src/openlia/macro_research/snapshot.py`

The server route and scheduler are already generic: `GET/POST /dashboards/{slug}` and the executor gate on `implemented_dashboard_slugs()`, which is backed by `PAYLOAD_MODEL_BY_SLUG`. Adding a slug there makes it schedulable/refreshable automatically — **no route or scheduler changes needed.**

---

## Task 1: Generalize the engine to per-slug prompt + classify tool

Refactor only. `debt_cycle` behavior must stay equivalent (its engine test stays green).

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/report_dash_mr/tools/dashboard_tools.py`
- Modify: `packages/core/src/openlia/llm/runtime/report_dash_mr/tools/registry.py`
- Modify: `packages/core/src/openlia/llm/runtime/report_dash_mr/prompts.py`
- Test: `packages/core/tests/runtime/report_dash_mr/test_implemented_dashboards.py` (extend)

- [ ] **Step 1: Add a classify-tool-by-slug map in `dashboard_tools.py`.**

Keep `build_classify_debt_cycle_tool` as-is. Below `PAYLOAD_MODEL_BY_SLUG`, add:

```python
from collections.abc import Callable

# Per-slug deterministic classify-tool builders. A slug present here gets its
# classifier tool added to the catalog alongside emit_dashboard. New dashboards
# register their builder here.
CLASSIFY_TOOL_BY_SLUG: dict[str, Callable[[], ResearchTool]] = {
    "debt_cycle": build_classify_debt_cycle_tool,
}
```

- [ ] **Step 2: Use the map in `registry.build_catalog`.**

Replace the hardcoded classify tool with a lookup. In `registry.py` change the import to include `CLASSIFY_TOOL_BY_SLUG` and the core-tools assembly:

```python
from .dashboard_tools import (
    CLASSIFY_TOOL_BY_SLUG,
    PAYLOAD_MODEL_BY_SLUG,
    build_emit_dashboard_tool,
)
...
    core: list[ResearchTool] = [build_emit_dashboard_tool(workspace, payload_model)]
    classify_builder = CLASSIFY_TOOL_BY_SLUG.get(dashboard_slug)
    if classify_builder is not None:
        core.append(classify_builder())
```

(Drop the now-unused `build_classify_debt_cycle_tool` import from `registry.py`.)

- [ ] **Step 3: Make the prompt per-slug.** In `prompts.py`, introduce a per-slug spec and select by `request.dashboard_slug`. Add near the top:

```python
@dataclass(frozen=True)
class DashboardPromptSpec:
    """Per-dashboard prompt content: the numbered workflow, the payload-shape
    description block, and the indicator-sourcing hint for the connectors block."""
    workflow: str
    payload_shape: str
    indicator_hint: str
```

Move the current debt-cycle workflow / payload-shape text out of `_PROMPT_TEMPLATE` into a `DASHBOARD_PROMPT_SPECS: dict[str, DashboardPromptSpec]` entry keyed `"debt_cycle"` (verbatim copy of today's `# Workflow` body and `# DebtCycleData payload shape` body, and the indicator hint string currently embedded in `_render_connectors_block`'s eodhd/web_search lines). Reduce `_PROMPT_TEMPLATE` to a shared skeleton with `{workflow}` and `{payload_shape}` placeholders. In `build_system_prompt`, look up the spec:

```python
    spec = DASHBOARD_PROMPT_SPECS.get(request.dashboard_slug)
    if spec is None:
        raise ValueError(f"no prompt spec for dashboard {request.dashboard_slug!r}")
```

Thread `spec.indicator_hint` into `_render_connectors_block` (replace the hardcoded "US dollar index and TIPS real yields" line with `indicator_hint`; keep the FRED/IMF/Treasury fallback guidance generic).

- [ ] **Step 4: Extend `test_implemented_dashboards.py`** to assert `set(CLASSIFY_TOOL_BY_SLUG) <= set(PAYLOAD_MODEL_BY_SLUG)` (every classifier has a payload model) and that `build_system_prompt` raises `ValueError` for an unknown slug. Run:

`uv run pytest packages/core/tests/runtime/report_dash_mr/ -q` — Expected: PASS (incl. the existing `test_runner_debt_cycle.py`, proving the refactor preserved debt_cycle).

- [ ] **Step 5: Commit.** `git commit -m "refactor(mr): per-slug prompt + classify-tool registries in report_dash_mr"`

---

## Task 2: World Order payload model

**Files:**
- Modify: `packages/core/src/openlia/macro_research/payloads.py`
- Test: `packages/core/tests/macro_research/test_payloads_world_order.py`
- Reference shape: `frontend/src/lib/macro_research/dalio_copy/types.ts:343-482` (`WorldOrderData` + `T4*`)
- Reference instance: `frontend/src/lib/macro_research/dalio_copy/world_order.ts` (`WORLD_ORDER_FALLBACK`)

- [ ] **Step 1: Write the failing test.** It must load the `WORLD_ORDER_FALLBACK` object's field values (transcribe the fallback instance into a Python dict fixture, adding `generated_at`) and assert `WorldOrderData.model_validate(fixture)` succeeds and round-trips. Pattern: mirror `packages/core/tests/macro_research/test_payloads.py`.

- [ ] **Step 2: Run it — Expected: FAIL** (`WorldOrderData` undefined).

- [ ] **Step 3: Add `WorldOrderData` + its `T4*` sub-models to `payloads.py`**, mirroring `types.ts:343-482` verbatim. Reuse `Tone` (red/amber/green/blue) and existing `Prose` where shapes match. New sub-models needed (names mirror the TS): `T4ScorecardRow`, `T4ReserveSeries`, `T4ReserveChart`, `T4StageCell` (with `state: Literal["past","active","future"]`, optional `weight: int | None`), `T4DalioQuote`, `T4MarkerRow`, `T4AnalogCell`, `T4ShiftAssessment`, `T4GoldRangeStat`, `T4CurrencyRow`, plus the nested `empireCycle` / `analogs` / `wealthShift` / `investment` groups (use inline sub-models, e.g. `WorldOrderScorecard`, `EmpireCycle`, `Analogs`, `WealthShift`, `Investment`, `GoldRange`, `CurrencyBlock`, `SovereignBond`, `ProsePair`). End the model with the redesign additions:
```python
    provenance: Provenance = Provenance.LIVE
    generated_at: datetime
```

- [ ] **Step 4: Run it — Expected: PASS.**

- [ ] **Step 5: Commit.** `git commit -m "feat(mr): WorldOrderData payload model"`

---

## Task 3: World Order classifier

**Files:**
- Create: `packages/core/src/openlia/macro_research/quant/world_order.py`
- Test: `packages/core/tests/macro_research/test_world_order_classify.py`

Light deterministic RAG + empire-stage composite, parallel to `classify_debt_cycle`. Defer the spec's composite-index series to the LLM (reference/live tiles).

- [ ] **Step 1: Write failing tests** for known input → known stage (see thresholds below): an all-green set → `"Early"`/`green`; two-red set → `"Late"`/`red`; one-red-one-amber → `"Mid"`/`amber`.

- [ ] **Step 2: Run — Expected: FAIL.**

- [ ] **Step 3: Implement.** Inputs are the four scorecard values the engine gathers:

```python
from dataclasses import dataclass
from typing import Literal

Tone = Literal["red", "amber", "green"]

# Initial Dalio-flavored defaults; tunable.
_RESERVE_SHARE_WARN = 60.0      # USD % of global FX reserves; below = erosion
_RESERVE_SHARE_CRIT = 55.0
_CB_GOLD_WARN = 400.0           # net CB gold purchases, tonnes/yr; above = de-dollarization
_CB_GOLD_CRIT = 800.0
_TREASURY_TREND_WARN = 0.0      # foreign UST holdings YoY %; below 0 = amber
_TREASURY_TREND_CRIT = -2.0     # below = red
_DXY_WARN = 102.0               # mirror debt_cycle debasement bands
_DXY_CRIT = 98.0


@dataclass(frozen=True)
class WorldOrderInputs:
    usd_reserve_share: float
    cb_gold_purchases: float
    foreign_treasury_trend: float
    dxy: float


@dataclass(frozen=True)
class WorldOrderClassification:
    stage: str
    severity: Tone
    indicator_statuses: dict[str, Tone]
    red_count: int
    amber_count: int


def _bucket_low(value, warn, crit):  # lower value = worse
    if value <= crit:
        return "red"
    if value <= warn:
        return "amber"
    return "green"


def _bucket_high(value, warn, crit):  # higher value = worse
    if value >= crit:
        return "red"
    if value >= warn:
        return "amber"
    return "green"


def classify_world_order(inputs: WorldOrderInputs) -> WorldOrderClassification:
    statuses = {
        "usd_reserve_share": _bucket_low(inputs.usd_reserve_share, _RESERVE_SHARE_WARN, _RESERVE_SHARE_CRIT),
        "cb_gold_purchases": _bucket_high(inputs.cb_gold_purchases, _CB_GOLD_WARN, _CB_GOLD_CRIT),
        "foreign_treasury_trend": _bucket_low(inputs.foreign_treasury_trend, _TREASURY_TREND_WARN, _TREASURY_TREND_CRIT),
        "dxy": _bucket_low(inputs.dxy, _DXY_WARN, _DXY_CRIT),
    }
    red = sum(1 for s in statuses.values() if s == "red")
    amber = sum(1 for s in statuses.values() if s == "amber")
    if red >= 2:
        stage, severity = "Late (Stage 5-6)", "red"
    elif red == 1 or amber >= 2:
        stage, severity = "Mid (Stage 4-5)", "amber"
    else:
        stage, severity = "Early (Stage 3)", "green"
    return WorldOrderClassification(
        stage=stage, severity=severity, indicator_statuses=statuses,
        red_count=red, amber_count=amber,
    )
```

- [ ] **Step 4: Run — Expected: PASS.**

- [ ] **Step 5: Commit.** `git commit -m "feat(mr): world_order deterministic classifier"`

---

## Task 4: World Order classify tool + prompt + register

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/report_dash_mr/tools/dashboard_tools.py`
- Modify: `packages/core/src/openlia/llm/runtime/report_dash_mr/prompts.py`

- [ ] **Step 1:** Add `build_classify_world_order_tool()` to `dashboard_tools.py`, mirroring `build_classify_debt_cycle_tool` — four numeric params (`usd_reserve_share`, `cb_gold_purchases`, `foreign_treasury_trend`, `dxy`), call `classify_world_order`, return `ToolResult` with `payload={"stage","severity","indicator_statuses"}` and `ComputedSource(method="classify_world_order", derived_from=["(inputs)"])`. Import `WorldOrderData`, `WorldOrderInputs`, `classify_world_order`.

- [ ] **Step 2:** Register both maps:
```python
PAYLOAD_MODEL_BY_SLUG = {"debt_cycle": DebtCycleData, "world_order": WorldOrderData}
CLASSIFY_TOOL_BY_SLUG = {"debt_cycle": build_classify_debt_cycle_tool, "world_order": build_classify_world_order_tool}
```

- [ ] **Step 3:** Add a `"world_order"` entry to `DASHBOARD_PROMPT_SPECS` in `prompts.py`. `indicator_hint`: "USD share of global FX reserves (IMF COFER), net central-bank gold purchases (WGC), foreign holdings of US Treasuries (TIC), and the dollar index (DXY)." `workflow`: gather those four (value + as-of), call `classify_world_order`, use returned `stage`/`severity`/`indicator_statuses` verbatim, then write the reserve-share history (`reserveChart`), empire-cycle stage strip (anchored on the returned stage), analogs, wealth-shift, investment theses, and verdict from cited data and reasoning. `payload_shape`: describe the `WorldOrderData` keys (transcribe from `types.ts:429-482`, same style as the debt_cycle block).

- [ ] **Step 4: Run** `uv run pytest packages/core/tests/runtime/report_dash_mr/ -q` — Expected: PASS (`implemented_dashboard_slugs()` now includes `world_order`).

- [ ] **Step 5: Commit.** `git commit -m "feat(mr): wire world_order classify tool + prompt"`

---

## Task 5: World Order engine run test (fake tools → golden payload)

**Files:**
- Test: `packages/core/tests/runtime/report_dash_mr/test_runner_world_order.py`

- [ ] **Step 1:** Mirror `test_runner_debt_cycle.py`: drive `Runner` with `dashboard_slug="world_order"`, a fake `LLMSession` scripted to (a) call `classify_world_order`, (b) call `emit_dashboard` with a valid `WorldOrderData`, and a stub transport/dispatcher. Assert `result.status == "completed"`, `result.payload is not None`, and the payload validates as `WorldOrderData` (the emit tool already validates; assert key fields like `phaseBox`-equivalent `verdict.tone`/`scorecard.rows`). Reuse the debt_cycle test's fakes.

- [ ] **Step 2: Run — Expected: PASS. Step 3: Commit.** `git commit -m "test(mr): world_order engine run"`

---

## Task 6: World Order live frontend view

**Files:**
- Modify: `frontend/src/pages/departments/macro_research/WorldOrderView.tsx`
- Test: `frontend/src/pages/departments/macro_research/__tests__/Views.test.tsx` (extend)

- [ ] **Step 1:** Convert `WorldOrderView` to the `DebtCycleView` live pattern. Copy the state machinery from `DebtCycleView.tsx` verbatim (the `POLL_INTERVAL_MS`/`POLL_MAX_ATTEMPTS` consts, `data`/`loading`/`generatedAt`/`generating`/`note`/`pollRef` state, `stopPolling`/`load`/`startPolling`/`onGenerate`, `useEffect(() => { load(); return stopPolling; }, [])`, the `already_running` branch, and the `if (loading) return <DashLoading/>; if (!data) return <DashEmpty .../>;` guards). Use `getDashboard<WorldOrderData>("world_order")` and `runAssessment("world_order")`. Then **keep the existing JSX render body and all helper sub-components unchanged** — only swap `const data = WORLD_ORDER_FALLBACK` for the fetched `data` and remove the throwaway `setLive`/`useEffect`. Remove the now-unused `WORLD_ORDER_FALLBACK` import. Add `DashEmpty`, `DashLoading` to the widgets import.

- [ ] **Step 2:** In `Views.test.tsx`, add a `WorldOrderView` live test mirroring the existing `DebtCycleView` block: mock `getDashboard` to resolve a payload, assert key rendered text; and a generate→poll test. Keep the existing static-render assertions working against the mocked payload.

- [ ] **Step 3: Run** `npx vitest run src/pages/departments/macro_research/__tests__/Views.test.tsx` and `npm run lint` (tsc) — Expected: PASS / clean.

- [ ] **Step 4: Commit.** `git commit -m "feat(mr): world_order live view"`

---

## Task 7: Four Seasons payload model

**Files:**
- Modify: `packages/core/src/openlia/macro_research/payloads.py`
- Test: `packages/core/tests/macro_research/test_payloads_four_seasons.py`
- Reference shape: `types.ts:129-246` (`FourSeasonsData` + `T2*`)
- Reference instance: `frontend/src/lib/macro_research/dalio_copy/four_seasons.ts`

- [ ] **Step 1: Write the failing test** — validate `FourSeasonsData` against a fixture transcribed from `FOUR_SEASONS_FALLBACK` (plus `generated_at`).
- [ ] **Step 2: Run — FAIL.**
- [ ] **Step 3: Add `FourSeasonsData` + `T2*` sub-models** mirroring `types.ts:129-246`. Note: `T2Tone` adds `"purple"` — define `T2Tone = Literal["red","amber","green","blue","purple"]` locally (do NOT widen the shared `Tone`). Sub-models: `T2ScorecardRow` (with `direction: Literal["up","down","flat"]`), `T2QuadrantSeason`, `T2QuadrantMarker` (`variant: Literal["now","prev"]`), `T2VerdictSide`, `T2ProseCard`, `T2AssetCard`, `T2Note`, and the nested groups (`quadrant.seasons` as a model with `tl/tr/bl/br`, `verdict` with `sideCards`, `transitionRisk`, `assetPlaybook`). Append `provenance` + `generated_at`.
- [ ] **Step 4: Run — PASS. Step 5: Commit.** `git commit -m "feat(mr): FourSeasonsData payload model"`

---

## Task 8: Four Seasons classifier (port + extend)

**Files:**
- Create: `packages/core/src/openlia/macro_research/quant/seasons.py`
- Test: `packages/core/tests/macro_research/test_seasons_classify.py`

Port the season logic from the legacy `dashboards/four_seasons.py` `T3_compute` and add deterministic quadrant-marker placement.

- [ ] **Step 1: Write failing tests:** Spring (gdp=2.5, pmi=54, cpi=1.8 → `"Spring"`/`green`, growth_axis `"rising"`, inflation_axis `"falling"`); Autumn (gdp=0.2, pmi=47, cpi=4.0 → `"Autumn"`/`red`); a mixed set → `"Transitioning"`/confidence `"transitioning"`; and assert `0 <= marker_x_pct <= 100` and `0 <= marker_y_pct <= 100`.

- [ ] **Step 2: Run — FAIL.**

- [ ] **Step 3: Implement** `classify_four_seasons(SeasonsInputs) -> SeasonsClassification`:

```python
from dataclasses import dataclass
from typing import Literal

Tone = Literal["red", "amber", "green"]


@dataclass(frozen=True)
class SeasonsInputs:
    pmi: float
    gdp_yoy: float
    cpi_yoy: float
    credit_spread: float


@dataclass(frozen=True)
class SeasonsClassification:
    season: str
    severity: Tone
    confidence: str
    growth_axis: str
    inflation_axis: str
    marker_x_pct: int   # 0=contraction .. 100=expansion
    marker_y_pct: int   # 0=disinflation .. 100=inflation
    best_assets: list[str]
    worst_assets: list[str]
```

Reuse the legacy thresholds verbatim (`growth_rising = gdp_yoy > 1.0 and pmi >= 50`, etc.), the Spring/Summer/Autumn/Winter/Transitioning mapping + severities, the `confidence` (`clear`/`mixed`/`transitioning`) rule, the axis strings, and the `_playbook` mapping (return `best_assets`/`worst_assets`). Add deterministic marker placement:

```python
def _clamp_pct(v: float) -> int:
    return max(0, min(100, round(v)))

# Growth axis: PMI 45->0, 55->100 (10-pt band around the 50 boundary).
marker_x_pct = _clamp_pct((pmi - 45.0) * 10.0)
# Inflation axis: CPI 1%->0, 5%->100.
marker_y_pct = _clamp_pct((cpi_yoy - 1.0) * 25.0)
```

- [ ] **Step 4: Run — PASS. Step 5: Commit.** `git commit -m "feat(mr): four_seasons deterministic classifier"`

---

## Task 9: Four Seasons classify tool + prompt + register

**Files:**
- Modify: `packages/core/src/openlia/llm/runtime/report_dash_mr/tools/dashboard_tools.py`
- Modify: `packages/core/src/openlia/llm/runtime/report_dash_mr/prompts.py`

- [ ] **Step 1:** Add `build_classify_four_seasons_tool()` (params: `pmi`, `gdp_yoy`, `cpi_yoy`, `credit_spread`; returns `payload={"season","severity","confidence","growth_axis","inflation_axis","marker_x_pct","marker_y_pct","best_assets","worst_assets"}`).
- [ ] **Step 2:** Add `"four_seasons"` to both `PAYLOAD_MODEL_BY_SLUG` and `CLASSIFY_TOOL_BY_SLUG`.
- [ ] **Step 3:** Add a `"four_seasons"` `DASHBOARD_PROMPT_SPECS` entry. `indicator_hint`: "ISM/S&P Global manufacturing PMI, real GDP YoY, headline + core CPI YoY, and an IG/HY credit spread proxy." `workflow`: gather those, call `classify_four_seasons`, use the returned season/axes/marker/playbook verbatim (place the quadrant marker at `marker_x_pct`/`marker_y_pct`), then write the scorecard trend reads, parallels, transition-risk bull/bear, asset playbook, and synthesis. `payload_shape`: transcribe `FourSeasonsData` keys from `types.ts:213-246`.
- [ ] **Step 4: Run** `uv run pytest packages/core/tests/runtime/report_dash_mr/ -q` — Expected PASS. **Step 5: Commit.** `git commit -m "feat(mr): wire four_seasons classify tool + prompt"`

---

## Task 10: Four Seasons engine run test

**Files:** Test: `packages/core/tests/runtime/report_dash_mr/test_runner_four_seasons.py`
- [ ] Mirror Task 5 with `dashboard_slug="four_seasons"`, a session scripted to call `classify_four_seasons` then `emit_dashboard` with a valid `FourSeasonsData`. Assert completed + payload validates. Run — PASS. Commit `test(mr): four_seasons engine run`.

---

## Task 11: Four Seasons live frontend view

**Files:**
- Modify: `frontend/src/pages/departments/macro_research/FourSeasonsView.tsx`
- Test: `frontend/src/pages/departments/macro_research/__tests__/Views.test.tsx` (extend)

- [ ] **Step 1:** Same `DebtCycleView` live-conversion as Task 6, using `getDashboard<FourSeasonsData>("four_seasons")` / `runAssessment("four_seasons")`. Keep the JSX body + helper components; swap `FOUR_SEASONS_FALLBACK` for fetched `data`; remove throwaway `setLive`; add `DashEmpty`/`DashLoading` imports.
- [ ] **Step 2:** Add `FourSeasonsView` live + generate→poll tests to `Views.test.tsx`.
- [ ] **Step 3: Run** the Views test + `npm run lint` — PASS / clean. **Step 4: Commit.** `git commit -m "feat(mr): four_seasons live view"`

---

## Task 12: Snapshot derivation + frontend gate + cleanup

**Files:**
- Modify: `packages/core/src/openlia/macro_research/snapshot.py`
- Test: `packages/core/tests/macro_research/test_snapshot.py` (extend)
- Modify: `frontend/src/pages/departments/macro_research/MRSettingsPanel.tsx`

- [ ] **Step 1:** Add `economic_season_from_payload(payload: FourSeasonsData) -> str` returning the season name. The season is not a top-level field of `FourSeasonsData` — derive it from the verdict/scorecard. Simplest stable source: parse it from `payload.verdict.title` is brittle; instead read the active quadrant marker. **Decision:** return the `name` of the season cell whose quadrant the `now`-variant marker falls in (top-left/top-right/bottom-left/bottom-right via `marker.xPct`/`yPct` >= 50 thresholds) — implement a small pure helper mapping (xPct>=50, yPct>=50)->`quadrant.seasons.tr.name`, etc. Write a unit test with a fixture marker in each quadrant.
- [ ] **Step 2:** Run `uv run pytest packages/core/tests/macro_research/ -q` — PASS.
- [ ] **Step 3:** Update `MRSettingsPanel.tsx:15`: `const IMPLEMENTED_DASHBOARDS = ["debt_cycle", "world_order", "four_seasons"];`
- [ ] **Step 4: Commit.** `git commit -m "feat(mr): economic_season snapshot + enable world_order/four_seasons Run Now"`

---

## Task 13: Full verification

- [ ] **Step 1:** `uv run pytest packages/core/tests/macro_research/ packages/core/tests/runtime/report_dash_mr/ packages/server/tests/test_macro_research/ -q` — all green.
- [ ] **Step 2:** `uv run ruff check . && uv run ruff format --check .` — clean (format the touched files if needed).
- [ ] **Step 3:** `cd frontend && npx vitest run && npm run lint` — full suite green (modulo the pre-existing `SettingsShellBlocker` AbortSignal error), tsc clean.
- [ ] **Step 4:** Update this plan + the spec if anything diverged (CLAUDE.md rule 9). Then `superpowers:finishing-a-development-branch`.

---

## Notes / deferred (do NOT do this round)
- Heavy quant: Markov transition matrix (T2), Monte-Carlo (T3), VAR causality (T5) — later quant phase.
- Curated reference datasets (1900–2026 composites, reserve snapshots) — LLM-sourced for now with `reference`/`live` provenance.
- All-Weather (T3, per-user/portfolio), Five Forces (T5, depends on T1/T4), Summary (aggregates all) — next round.
- Deleting `dalio_copy/*.ts` fallback files: defer until all views are migrated (Summary still consumes some).
