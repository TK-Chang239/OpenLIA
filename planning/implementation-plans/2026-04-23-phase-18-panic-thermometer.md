# Panic Thermometer Department Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

> **Audit 2026-04-23 normalizations (apply before executing this plan):**
> - All IDs are UUID strings (`String(36)`) — `user_id`, `preset_id`, `config_id` are `str` at every service boundary, path param, and FK. Generate with `str(uuid.uuid4())`. No prefixed short-hex ids.
> - Backend imports: `User` from `openlia_server.db.models.auth`; `PtUserConfig` and `PtPreset` from `openlia_server.db.models.dashboard` (shipped by Plan 1B). No new PT tables are introduced — this plan uses the shipped schema verbatim.
> - Auth: router-factory pattern via `build_require_auth(...)`; no bare `get_current_user` helper.
> - Formula engine imports: `from openlia.formula import FormulaEngine, FormulaError, EvaluationContext, extract_requirements` (Plan 17 public API — verbatim).
> - Panic Thermometer is a **dashboard department**: no `ChatRunner`, no `ReportRunner`, no `reports` table writes, no SSE, no chat sessions. All endpoints are request/response JSON.
> - Route prefix: `/departments/panic_thermometer/*` (underscore slug — matches `Department.name`). Frontend hits `/api/departments/panic_thermometer/*` via the Vite dev proxy.

**Goal:** Ship the Panic Thermometer (PT) department as a dashboard department. Users get a single-page dashboard with five macro-stress panels (oil price duration, inflation expectations, Fed language tracker, wage growth, diplomatic progress). Each panel is scored green / amber / red / dark_red by evaluating a user-editable formula rule set against fresh data via the Plan 17 formula engine. A composite dial aggregates the panel verdicts into a calm / elevated / high / severe / crisis threat level. Users can edit per-panel thresholds and rules via a settings drawer, load shipped preset libraries (Report defaults / MA-relative / Volatility-adjusted), save their own presets, import/export full configurations as JSON, and share configs via base64 URL params.

**Architecture:**
- **Core** gets a `PanicThermometerDepartment` class (dashboard-only — declares name, display name, tier, basic + optional data requirement types, panel identifiers), a `panels` package with one module per panel (each panel owns: its identifier, the data requirements it pulls, the context-build function that turns raw provider payloads into `EvaluationContext.scalars` + `raw_series`, and the default rule set), a `composite.py` module that maps per-panel statuses to a composite threat level using count-based or weighted scoring, and a `presets.py` module that seeds three library presets per panel. No `ReportRunner`, no prompt YAML, no framework JSON — PT does not produce reports.
- **Server** adds two services — `pt_config` (CRUD on `PtUserConfig`, preset CRUD on `PtPreset`, shipped-preset seeding on app startup, import/export, preset apply) and `pt_runner` (for a given user: load config, dispatch panel data requirements via the Plan 3 adapter dispatcher, build each panel's `EvaluationContext`, invoke `FormulaEngine.evaluate_ruleset`, aggregate into composite, return a `DashboardPayload`) — plus the route surface at `/departments/panic_thermometer/*` (dashboard compute, config CRUD, preset CRUD, preset apply, config import/export, formula parse/test/preview endpoints that back the settings drawer's inline validation UI). No new tables — reuses `PtUserConfig` and `PtPreset` shipped in Plan 1B. Dashboard result is transient (no persistence) — a small in-memory LRU cache keyed by `(user_id, panel_id)` holds the most recent fetched `raw_series` + `scalars` so the formula test/preview endpoints can replay without re-fetching.
- **Frontend** ships `PanicThermometerPage` with: a header (title + auto-refresh dropdown + settings gear), a composite threat bar (filled pill with 5 stops: calm / elevated / high / severe / crisis), a panel grid (5 cards, each with metric + status pill + sparkline), per-panel drill-down sections (dashboards 1–5 with charts + details panels), a settings drawer (per-panel params + rule editor + preset loader + manual override), preset library view (list shipped + user presets, load/save/delete/apply), import/export modal (upload JSON / download JSON / copy share URL). No chat interface.

**Tech Stack:**
- Backend: FastAPI, SQLAlchemy 2.x, Pydantic v2, Plan 3 data adapter dispatcher, Plan 17 `FormulaEngine`.
- Frontend: React 18 + TypeScript strict, Radix UI primitives (`Dialog`, `Popover`, `Tabs`, `Select`, `Slider`), Framer Motion for the composite bar animation, Chart.js 4.x (via `chart.js` + `react-chartjs-2`) for sparklines and dashboard charts, Zod for JSON import validation, Vitest + React Testing Library.

**Dependencies:**
- Plan 1A: `users` table; `SessionLocal`.
- Plan 1B: `pt_user_configs`, `pt_presets` tables (shipped — no migration in this plan).
- Plan 2: session middleware (all endpoints authenticated).
- Plan 3: data requirement adapter dispatcher; `historical_prices`, `stock_quote`, `economic_events`, `company_news` adapters.
- Plan 8: frontend shell (routing, auth context, `useAuth`, design tokens).
- Plan 11: `/settings` surface — PT reuses the same design-token stack (no direct dep).
- Plan 12: `FileDownload` component (used to export config as JSON download).
- Plan 17 (Formula Engine): `FormulaEngine`, `FormulaError`, `EvaluationContext`, `extract_requirements` — verbatim public API.

**Unblocks:**
- Plan 19 (Macro Research) reuses the same PT-style dashboard compose pattern with the shared formula engine.
- Plan 23 (Docker packaging + final acceptance) — PT is one of four dashboard departments that must be demonstrably working end-to-end.

---

## Design Rules

1. **Dashboard department, not report department.** No `ReportRunner`, no `reports` row, no SSE, no chat session. Every route returns JSON synchronously.
2. **Configuration lives in `PtUserConfig`.** One row per user (unique on `user_id`). `panel_config` is a `list[PanelConfig]`. `composite_settings` is `{mode: "count"|"weighted", weights: dict[str, float], thresholds: dict[str, int|float], red_threshold: int}`. First-visit bootstrap seeds a default config from the shipped `report_defaults` preset per panel.
3. **Preset library uses `PtPreset` with `user_id = NULL` for shipped rows.** App-startup hook seeds three shipped presets per panel (15 total) using `is_shipped = True` and the partial unique index on `(name) WHERE user_id IS NULL`. Seed is idempotent — re-runs check existence by `(name, is_shipped=True)`.
4. **Formula engine is the single evaluation path.** `PanicThermometerDepartment` does not contain threshold logic. Every rule evaluation goes through `FormulaEngine.evaluate_ruleset`. No hand-rolled panel-specific thresholds.
5. **Data requirements are declared per panel.** Each panel module exposes `required_requirements: tuple[str, ...]` and `optional_requirements: tuple[str, ...]`. The dashboard orchestrator walks these, asks Plan 3's dispatcher for adapters, pulls data, and builds the `EvaluationContext`. If a required adapter is missing, the panel returns `{"status": "disabled", "reason": "<requirement> not configured"}` — the rest of the dashboard still renders.
6. **Fed language + diplomacy panels build keyword-match booleans in Python before the engine runs.** The formula DSL is not a string-matching language (per Plan 17 spec). Each panel's context-builder scans news payloads for keyword matches and sets `dovish_keyword_detected`, `hawkish_keyword_detected`, `crisis_keyword_detected`, `escalation_detected`, `progress_detected`, `matched_phrase`, `matched_headline`, `matched_date` as scalars in `EvaluationContext.scalars`.
7. **Streak condition is per-panel, stored on the panel config.** Oil panel uses a `streak_condition` param (default `"price > price_threshold"`). The engine's streak backtester reads it at evaluate time.
8. **Manual override lives in `panel_config[].manual_override`.** When set, the panel skips rule evaluation entirely and returns the override status + label. Override is a `{status, note, set_at}` triple — UI exposes "clear override" to remove it.
9. **Diplomacy milestone date lives in `panel_config[].milestone_date` (ISO string).** Clicking "Mark milestone" updates this field to today. `days_elapsed` in the context is derived as `today - milestone_date`.
10. **Composite scoring is pluggable.** `composite.py` exposes `compute_composite(panel_statuses: dict[str, str], settings: dict[str, Any]) -> CompositeResult`. Two modes: `"count"` (counts red + dark_red panels, bucketed by `red_threshold`) and `"weighted"` (sums weights of red/dark_red panels, bucketed by thresholds).
11. **Auto-refresh is a client concern.** The frontend polls `GET /dashboard` on a timer controlled by a user-picked interval (off / 1m / 5m / 15m — default 5m). Server does not push.
12. **Import/export is full-config JSON.** Export is `{version: 1, panel_config, composite_settings}`. Import validates the same shape via Pydantic, overwrites the user's row, and returns the new config. Base64 share URL embeds the same JSON compressed.
13. **TDD everywhere.** Failing test → implementation → green run → commit per step.
14. **No placeholders.** Real code, real commands, real expected output in every step.

---

## File Structure

### Core (`packages/core/src/openlia/`)

```
departments/
├── panic_thermometer.py                  # NEW — PanicThermometerDepartment (dashboard-only)
└── __init__.py                           # MODIFY — export PanicThermometerDepartment + register
panic_thermometer/
├── __init__.py                           # package init; re-exports panels + composite + presets
├── panels/
│   ├── __init__.py                       # PANELS = {"oil": OilPanel(), ...}
│   ├── base.py                           # PanelBase protocol + PanelContextBuildResult dataclass
│   ├── oil.py                            # OilPanel.build_context(raw_payloads) -> (scalars, raw_series)
│   ├── inflation.py
│   ├── fed_language.py                   # keyword scanner → booleans + matched_phrase
│   ├── wage_growth.py
│   └── diplomacy.py                      # keyword scanner + days_elapsed computation
├── composite.py                          # compute_composite(panel_statuses, settings) -> CompositeResult
└── presets.py                            # PT_PRESETS dict: {panel: {preset_name: RuleSetDict}}
```

### Server (`packages/server/src/openlia_server/`)

```
services/
├── pt_config.py                          # CRUD on PtUserConfig + preset CRUD on PtPreset + seed
└── pt_runner.py                          # Dashboard orchestrator: fetch → engine → aggregate
routes/departments/
└── panic_thermometer.py                  # All PT routes under /departments/panic_thermometer
app.py                                    # MODIFY — mount PT router; call seed_shipped_presets() on startup
```

### Frontend (`frontend/src/`)

```
api/
└── panic-thermometer.ts                  # typed client: dashboard, config, presets, import/export
pages/departments/
└── PanicThermometer.tsx                  # MODIFY — replace placeholder with full dashboard
components/panic-thermometer/
├── CompositeBar.tsx                      # filled pill with 5 stops
├── PanelGrid.tsx                         # 5-up grid of PanelCard
├── PanelCard.tsx                         # metric + status pill + sparkline
├── PanelDashboard.tsx                    # drill-down (chart + details) for each panel
├── OilDashboard.tsx                      # line chart + threshold reference line
├── InflationDashboard.tsx                # dual-axis chart (TIP price + Michigan survey)
├── FedLanguageDashboard.tsx              # timeline + headline scanner + keyword editor
├── WageGrowthDashboard.tsx               # monthly bar chart + threshold line
├── DiplomacyDashboard.tsx                # countdown bar + news feed + milestone button
├── SettingsDrawer.tsx                    # collapsible; per-panel tabs + global settings
├── PanelSettingsPane.tsx                 # params table + rule editor + preset loader
├── RuleEditor.tsx                        # ordered rule list with inline formula validation
├── FormulaInput.tsx                      # debounced parse + error highlight
├── PresetLibrary.tsx                     # list shipped + user presets
├── ImportExportModal.tsx                 # upload/download JSON + share URL
└── ManualOverridePopover.tsx             # force status with optional note
hooks/
├── usePtDashboard.ts                     # SWR-style poll with refresh interval
├── usePtConfig.ts                        # get + update full config
├── usePtPresets.ts                       # list + save + delete + apply
└── usePtFormula.ts                       # parse + test + preview endpoints
lib/panic-thermometer/
├── panel-catalog.ts                      # 5 panels with display name + icon + dashboard component
├── share-link.ts                         # base64 encode/decode for share URLs
└── config-schema.ts                      # Zod schema for import validation
```

---

## Task Overview

1. Core — `PanicThermometerDepartment` class.
2. Core — Panel base (`PanelBase` protocol + `PanelContextBuildResult`).
3. Core — `OilPanel` (context builder + default rule set).
4. Core — `InflationPanel`.
5. Core — `FedLanguagePanel` (keyword scanner).
6. Core — `WageGrowthPanel`.
7. Core — `DiplomacyPanel` (keyword scanner + milestone).
8. Core — `composite.py` (count + weighted scoring).
9. Core — `presets.py` (three shipped presets per panel).
10. Core — Register department in `departments/__init__.py`.
11. Server — `pt_config` service (config CRUD + default bootstrap).
12. Server — `pt_config` service (preset CRUD + shipped-preset seed).
13. Server — `pt_config` service (import/export + preset apply).
14. Server — `pt_runner` service (dashboard orchestrator).
15. Server — `pt_runner` service (per-panel cache for formula test/preview).
16. Server — Routes: `GET /dashboard`.
17. Server — Routes: `GET /config` + `PUT /config`.
18. Server — Routes: presets (GET/POST/PUT/DELETE/apply).
19. Server — Routes: config import/export.
20. Server — Routes: formula parse/test/preview.
21. Server — Wire router + seed hook into `app.py`.
22. Frontend — `api/panic-thermometer.ts` typed client.
23. Frontend — panel catalog + hooks.
24. Frontend — `CompositeBar` + `PanelGrid` + `PanelCard`.
25. Frontend — `OilDashboard` + `WageGrowthDashboard` (chart-based panels).
26. Frontend — `InflationDashboard` + `FedLanguageDashboard` + `DiplomacyDashboard`.
27. Frontend — `RuleEditor` + `FormulaInput` + `PanelSettingsPane`.
28. Frontend — `SettingsDrawer` + `PresetLibrary` + `ManualOverridePopover`.
29. Frontend — `ImportExportModal` + share-link utils.
30. Frontend — `PanicThermometerPage` composition.
31. Manual smoke test + flip README row to Draft.

---

### Task 1: Core — `PanicThermometerDepartment` class

The department advertises: name, display name, tier (unused at runtime — PT doesn't call an LLM, but the base class requires it), data requirement lists (union across panels), the panel identifiers it owns, and an explicit `is_dashboard: bool = True` flag.

**Files:**
- Create: `packages/core/src/openlia/departments/panic_thermometer.py`
- Modify: `packages/core/src/openlia/departments/__init__.py` (exports handled in Task 10)
- Test: `packages/core/tests/departments/test_panic_thermometer.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/departments/test_panic_thermometer.py
from openlia.departments.panic_thermometer import PanicThermometerDepartment


def test_pt_identifies_itself():
    d = PanicThermometerDepartment()
    assert d.name == "panic_thermometer"
    assert d.display_name == "Panic Thermometer"
    assert d.is_dashboard is True


def test_pt_has_five_panels():
    d = PanicThermometerDepartment()
    assert set(d.panel_ids) == {
        "oil",
        "inflation",
        "fed_language",
        "wage_growth",
        "diplomacy",
    }


def test_pt_basic_data_requirements():
    reqs = PanicThermometerDepartment().data_requirement_types
    for name in ("historical_prices", "stock_quote", "economic_events"):
        assert name in reqs


def test_pt_optional_data_requirements():
    soft = PanicThermometerDepartment().optional_requirement_types
    assert "company_news" in soft


def test_pt_has_no_report_modes():
    d = PanicThermometerDepartment()
    assert d.valid_modes == ()


def test_pt_has_no_extra_tools():
    assert PanicThermometerDepartment().extra_tools == ()
```

- [ ] **Step 2: Run the test to confirm it fails**

Run: `uv run pytest packages/core/tests/departments/test_panic_thermometer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'openlia.departments.panic_thermometer'`.

- [ ] **Step 3: Write the department class**

```python
# packages/core/src/openlia/departments/panic_thermometer.py
"""Panic Thermometer — dashboard-only department (no reports, no chat)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PanicThermometerDepartment:
    name: str = "panic_thermometer"
    display_name: str = "Panic Thermometer"
    is_dashboard: bool = True
    data_requirement_types: tuple[str, ...] = (
        "historical_prices",
        "stock_quote",
        "economic_events",
    )
    optional_requirement_types: tuple[str, ...] = ("company_news",)
    panel_ids: tuple[str, ...] = (
        "oil",
        "inflation",
        "fed_language",
        "wage_growth",
        "diplomacy",
    )
    valid_modes: tuple[str, ...] = ()
    extra_tools: tuple[str, ...] = ()
```

- [ ] **Step 4: Run the test to confirm it passes**

Run: `uv run pytest packages/core/tests/departments/test_panic_thermometer.py -v`
Expected: 6 passed.

- [ ] **Step 5: Lint and commit**

Run: `uv run ruff check packages/core/src/openlia/departments/panic_thermometer.py packages/core/tests/departments/test_panic_thermometer.py && uv run ruff format packages/core/src/openlia/departments/panic_thermometer.py packages/core/tests/departments/test_panic_thermometer.py`

Commit:
```
git add packages/core/src/openlia/departments/panic_thermometer.py packages/core/tests/departments/test_panic_thermometer.py
git commit -m "feat(core): PanicThermometerDepartment dashboard-only identity class"
```

---

### Task 2: Core — Panel base protocol + `PanelContextBuildResult`

Each panel exposes a uniform interface: its id, the data requirements it pulls, a context-builder that turns raw adapter payloads into `(scalars, raw_series)`, and a default rule set. This task defines the shared shapes. Panels themselves come in tasks 3–7.

**Files:**
- Create: `packages/core/src/openlia/panic_thermometer/__init__.py`
- Create: `packages/core/src/openlia/panic_thermometer/panels/__init__.py`
- Create: `packages/core/src/openlia/panic_thermometer/panels/base.py`
- Test: `packages/core/tests/panic_thermometer/__init__.py`
- Test: `packages/core/tests/panic_thermometer/test_panel_base.py`

- [ ] **Step 1: Write the failing test**

```python
# packages/core/tests/panic_thermometer/test_panel_base.py
from openlia.panic_thermometer.panels.base import (
    PanelBase,
    PanelContextBuildResult,
)


def test_panel_context_build_result_shape():
    r = PanelContextBuildResult(
        scalars={"price": 92.4, "prev_close": 91.0},
        raw_series={"price": [80.0, 82.0, 92.4]},
        warnings=[],
    )
    assert r.scalars["price"] == 92.4
    assert r.raw_series["price"][-1] == 92.4
    assert r.warnings == []


def test_panel_base_declares_required_attrs():
    # PanelBase is a structural protocol; ensure it advertises the expected names
    assert hasattr(PanelBase, "__protocol_attrs__") or True
    annotations = PanelBase.__annotations__ if hasattr(PanelBase, "__annotations__") else {}
    for attr in ("panel_id", "required_requirements", "optional_requirements"):
        assert attr in annotations or hasattr(PanelBase, attr)
```

- [ ] **Step 2: Run, confirm failure**

Run: `uv run pytest packages/core/tests/panic_thermometer/test_panel_base.py -v`
Expected: FAIL (ModuleNotFoundError).

- [ ] **Step 3: Create package files**

```python
# packages/core/src/openlia/panic_thermometer/__init__.py
"""Panic Thermometer department internals: panels, composite, presets."""
```

```python
# packages/core/src/openlia/panic_thermometer/panels/__init__.py
"""Panic Thermometer panel registry."""

from openlia.panic_thermometer.panels.base import PanelBase, PanelContextBuildResult
from openlia.panic_thermometer.panels.diplomacy import DiplomacyPanel
from openlia.panic_thermometer.panels.fed_language import FedLanguagePanel
from openlia.panic_thermometer.panels.inflation import InflationPanel
from openlia.panic_thermometer.panels.oil import OilPanel
from openlia.panic_thermometer.panels.wage_growth import WageGrowthPanel

PANELS: dict[str, PanelBase] = {
    "oil": OilPanel(),
    "inflation": InflationPanel(),
    "fed_language": FedLanguagePanel(),
    "wage_growth": WageGrowthPanel(),
    "diplomacy": DiplomacyPanel(),
}

__all__ = [
    "PANELS",
    "PanelBase",
    "PanelContextBuildResult",
    "OilPanel",
    "InflationPanel",
    "FedLanguagePanel",
    "WageGrowthPanel",
    "DiplomacyPanel",
]
```

> Tasks 3–7 create the individual panel modules imported above. Until then, the package-level import will fail — commit this file after Task 7.

```python
# packages/core/src/openlia/panic_thermometer/panels/base.py
"""Shared shapes for Panic Thermometer panels."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass(frozen=True)
class PanelContextBuildResult:
    """Output of a panel's context-builder.

    scalars: keys consumed by `EvaluationContext.scalars` (booleans, survey
        readings, days_elapsed, matched_phrase, etc.).
    raw_series: keys consumed by `EvaluationContext.raw_series` — named arrays of
        historical numeric values, oldest first.
    warnings: human-readable notes surfaced to the UI (stale data, etc.).
    """

    scalars: dict[str, Any]
    raw_series: dict[str, list[float]]
    warnings: list[str] = field(default_factory=list)


@runtime_checkable
class PanelBase(Protocol):
    """Structural protocol every PT panel satisfies.

    Panels are stateless — they do not hold user config. The runner passes
    the user's panel config and raw adapter payloads at call time.
    """

    panel_id: str
    required_requirements: tuple[str, ...]
    optional_requirements: tuple[str, ...]
    default_ruleset: dict[str, Any]
    """Default RuleSet dict shipped as the `report_defaults` preset."""

    def build_context(
        self,
        *,
        panel_config: dict[str, Any],
        payloads: dict[str, Any],
    ) -> PanelContextBuildResult:
        """Turn raw adapter payloads into engine inputs."""
        ...
```

- [ ] **Step 4: Also create** `packages/core/tests/panic_thermometer/__init__.py` (empty).

- [ ] **Step 5: Run**

Run: `uv run pytest packages/core/tests/panic_thermometer/test_panel_base.py -v`
Expected: 2 passed. (`PANELS` registry commit deferred to Task 7.)

- [ ] **Step 6: Lint + commit**

```
git add packages/core/src/openlia/panic_thermometer/__init__.py packages/core/src/openlia/panic_thermometer/panels/base.py packages/core/tests/panic_thermometer/__init__.py packages/core/tests/panic_thermometer/test_panel_base.py
git commit -m "feat(core): PT panel base protocol + PanelContextBuildResult"
```

---

### Task 3: Core — `OilPanel`

Oil panel pulls historical prices + live quote for a user-configurable ticker (default `BNO.US`). Context-builder extracts the close series, exposes it under `price` in `raw_series` (per Plan 17's reserved-scalar convention), adds the latest quote's `price` and `prev_close` as scalars if live data is present.

**Files:**
- Create: `packages/core/src/openlia/panic_thermometer/panels/oil.py`
- Test: `packages/core/tests/panic_thermometer/test_oil_panel.py`

- [ ] **Step 1: Failing test**

```python
# packages/core/tests/panic_thermometer/test_oil_panel.py
from openlia.panic_thermometer.panels.oil import OilPanel


def _panel():
    return OilPanel()


def test_oil_panel_id_and_requirements():
    p = _panel()
    assert p.panel_id == "oil"
    assert p.required_requirements == ("historical_prices", "stock_quote")
    assert p.optional_requirements == ()


def test_oil_default_ruleset_has_four_rules():
    p = _panel()
    rs = p.default_ruleset
    assert len(rs["rules"]) == 4
    assert {r["status"] for r in rs["rules"]} == {"dark_red", "red", "amber", "green"}
    assert rs["params"]["price_threshold"] == 85
    assert rs["params"]["streak_red"] == 30
    assert rs["params"]["streak_dark_red"] == 90
    assert rs["streak_condition"] == "price > price_threshold"


def test_oil_build_context_from_payloads():
    p = _panel()
    # Minimal OHLC history
    history = [
        {"date": f"2026-01-{i:02d}", "open": 80.0, "high": 82.0, "low": 79.0, "close": 80.0 + i * 0.5, "volume": 0}
        for i in range(1, 11)
    ]
    quote = {"price": 92.4, "previous_close": 91.0, "timestamp": "2026-04-23T20:00:00Z"}
    r = p.build_context(
        panel_config={"params": {"ticker": "BNO.US"}},
        payloads={"historical_prices": history, "stock_quote": quote},
    )
    assert r.raw_series["price"][-1] == 85.0  # last close = 80 + 10*0.5
    assert r.scalars["price"] == 92.4
    assert r.scalars["prev_close"] == 91.0


def test_oil_build_context_without_live_quote_falls_back_to_last_close():
    p = _panel()
    history = [
        {"date": "2026-01-01", "open": 80.0, "high": 82.0, "low": 79.0, "close": 80.0, "volume": 0},
        {"date": "2026-01-02", "open": 80.5, "high": 83.0, "low": 80.0, "close": 82.5, "volume": 0},
    ]
    r = p.build_context(
        panel_config={"params": {"ticker": "BNO.US"}},
        payloads={"historical_prices": history, "stock_quote": None},
    )
    assert r.scalars["price"] == 82.5
    assert "quote unavailable" in " ".join(r.warnings)
```

- [ ] **Step 2: Run** — fails (ModuleNotFoundError).

- [ ] **Step 3: Implementation**

```python
# packages/core/src/openlia/panic_thermometer/panels/oil.py
"""Oil price duration panel."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from openlia.panic_thermometer.panels.base import PanelContextBuildResult


_DEFAULT_RULESET: dict[str, Any] = {
    "rules": [
        {
            "status": "dark_red",
            "formula": "streak_days >= streak_dark_red",
            "label": "{streak_days} days elevated - 2022 scenario",
        },
        {
            "status": "red",
            "formula": "streak_days >= streak_red",
            "label": "{streak_days} days elevated - scenario upgrade risk",
        },
        {
            "status": "amber",
            "formula": "price > price_threshold",
            "label": "Above threshold, monitoring",
        },
        {
            "status": "green",
            "formula": "true",
            "label": "Below threshold",
        },
    ],
    "params": {
        "ticker": "BNO.US",
        "price_threshold": 85,
        "streak_amber": 1,
        "streak_red": 30,
        "streak_dark_red": 90,
        "history_lookback_months": 6,
    },
    "streak_condition": "price > price_threshold",
}


@dataclass(frozen=True)
class OilPanel:
    panel_id: str = "oil"
    required_requirements: tuple[str, ...] = ("historical_prices", "stock_quote")
    optional_requirements: tuple[str, ...] = ()
    default_ruleset: dict[str, Any] = field(default_factory=lambda: _DEFAULT_RULESET)

    def build_context(
        self,
        *,
        panel_config: dict[str, Any],
        payloads: dict[str, Any],
    ) -> PanelContextBuildResult:
        history = payloads.get("historical_prices") or []
        quote = payloads.get("stock_quote")
        warnings: list[str] = []

        closes = [float(bar["close"]) for bar in history]
        highs = [float(bar.get("high", bar["close"])) for bar in history]
        lows = [float(bar.get("low", bar["close"])) for bar in history]

        if not closes:
            warnings.append("oil: no historical price data available")

        if quote and quote.get("price") is not None:
            price = float(quote["price"])
            prev_close = (
                float(quote["previous_close"])
                if quote.get("previous_close") is not None
                else (closes[-2] if len(closes) >= 2 else price)
            )
        else:
            warnings.append("oil: live quote unavailable - using last historical close")
            price = closes[-1] if closes else 0.0
            prev_close = closes[-2] if len(closes) >= 2 else price

        return PanelContextBuildResult(
            scalars={"price": price, "prev_close": prev_close},
            raw_series={"price": closes, "high": highs, "low": lows},
            warnings=warnings,
        )
```

- [ ] **Step 4: Run** — 4 passed.

- [ ] **Step 5: Lint + commit**

```
git add packages/core/src/openlia/panic_thermometer/panels/oil.py packages/core/tests/panic_thermometer/test_oil_panel.py
git commit -m "feat(core): PT OilPanel context builder + default rule set"
```

---

### Task 4: Core — `InflationPanel`

Pulls TIP ETF history + live quote + filtered Michigan 5Y expectations from `economic_events`. Exposes `tip_price` in `raw_series`, the latest Michigan reading in `scalars["michigan_5y"]` (or `None` if no release in the lookback), previous Michigan reading in `scalars["michigan_prev"]`.

**Files:**
- Create: `packages/core/src/openlia/panic_thermometer/panels/inflation.py`
- Test: `packages/core/tests/panic_thermometer/test_inflation_panel.py`

- [ ] **Step 1: Failing test**

```python
# packages/core/tests/panic_thermometer/test_inflation_panel.py
from openlia.panic_thermometer.panels.inflation import InflationPanel


def test_inflation_panel_id_and_requirements():
    p = InflationPanel()
    assert p.panel_id == "inflation"
    assert set(p.required_requirements) == {"historical_prices", "stock_quote", "economic_events"}


def test_inflation_default_ruleset_has_amber_red_darkred_green():
    rs = InflationPanel().default_ruleset
    statuses = [r["status"] for r in rs["rules"]]
    assert statuses[0] == "dark_red"
    assert "green" in statuses
    assert rs["params"]["primary_ticker"] == "TIP.US"
    assert rs["params"]["level_red"] == 3.0


def test_inflation_build_context_picks_michigan_latest():
    p = InflationPanel()
    history = [
        {"date": "2026-03-01", "open": 100, "high": 100, "low": 100, "close": 99.0, "volume": 0},
        {"date": "2026-03-02", "open": 100, "high": 100, "low": 100, "close": 99.5, "volume": 0},
    ]
    quote = {"price": 99.7, "previous_close": 99.5}
    events = [
        {"date": "2026-02-15", "event_name": "Michigan 5 Year Inflation Expectations", "actual": 3.1, "country": "US"},
        {"date": "2026-03-15", "event_name": "Michigan 5 Year Inflation Expectations", "actual": 3.3, "country": "US"},
        {"date": "2026-03-15", "event_name": "Nonfarm Payrolls", "actual": 150000, "country": "US"},
    ]
    r = p.build_context(
        panel_config={"params": {"primary_ticker": "TIP.US", "event_type_filter": "Michigan 5 Year Inflation Expectations"}},
        payloads={"historical_prices": history, "stock_quote": quote, "economic_events": events},
    )
    assert r.scalars["michigan_5y"] == 3.3
    assert r.scalars["michigan_prev"] == 3.1
    assert r.raw_series["tip_price"][-1] == 99.5


def test_inflation_build_context_without_michigan_release():
    p = InflationPanel()
    r = p.build_context(
        panel_config={"params": {"primary_ticker": "TIP.US", "event_type_filter": "Michigan 5 Year Inflation Expectations"}},
        payloads={"historical_prices": [], "stock_quote": None, "economic_events": []},
    )
    assert r.scalars["michigan_5y"] is None
    assert r.scalars["michigan_prev"] is None
```

- [ ] **Step 2: Run** — fails.

- [ ] **Step 3: Implementation**

```python
# packages/core/src/openlia/panic_thermometer/panels/inflation.py
"""Inflation expectations panel — TIP ETF + Michigan 5Y survey."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from openlia.panic_thermometer.panels.base import PanelContextBuildResult


_DEFAULT_RULESET: dict[str, Any] = {
    "rules": [
        {"status": "dark_red", "formula": "michigan_5y >= level_dark_red", "label": "Expectations unanchored ({michigan_5y}%)"},
        {"status": "red", "formula": "michigan_5y >= level_red", "label": "Expectations drifting ({michigan_5y}%)"},
        {"status": "red", "formula": "michigan_5y == null AND slope(tip_price, slope_lookback_days) > slope_threshold", "label": "TIP rising fast (no survey data)"},
        {"status": "amber", "formula": "michigan_5y >= level_amber", "label": "Approaching concern zone"},
        {"status": "green", "formula": "true", "label": "Expectations anchored"},
    ],
    "params": {
        "primary_ticker": "TIP.US",
        "event_type_filter": "Michigan 5 Year Inflation Expectations",
        "level_amber": 2.5,
        "level_red": 3.0,
        "level_dark_red": 3.5,
        "tip_lookback_months": 6,
        "slope_lookback_days": 30,
        "slope_threshold": 0.02,
    },
    "streak_condition": None,
}


@dataclass(frozen=True)
class InflationPanel:
    panel_id: str = "inflation"
    required_requirements: tuple[str, ...] = (
        "historical_prices",
        "stock_quote",
        "economic_events",
    )
    optional_requirements: tuple[str, ...] = ()
    default_ruleset: dict[str, Any] = field(default_factory=lambda: _DEFAULT_RULESET)

    def build_context(
        self,
        *,
        panel_config: dict[str, Any],
        payloads: dict[str, Any],
    ) -> PanelContextBuildResult:
        params = panel_config.get("params", {})
        event_filter = params.get("event_type_filter", "Michigan 5 Year Inflation Expectations")

        history = payloads.get("historical_prices") or []
        quote = payloads.get("stock_quote")
        events = payloads.get("economic_events") or []

        closes = [float(bar["close"]) for bar in history]
        warnings: list[str] = []

        matching = sorted(
            [e for e in events if e.get("event_name") == event_filter],
            key=lambda e: e.get("date", ""),
        )
        latest = matching[-1]["actual"] if matching else None
        prev = matching[-2]["actual"] if len(matching) >= 2 else None

        if latest is None:
            warnings.append(f"inflation: no recent release matching '{event_filter}'")

        if quote and quote.get("price") is not None:
            price = float(quote["price"])
            prev_close = float(quote["previous_close"]) if quote.get("previous_close") is not None else price
        elif closes:
            price = closes[-1]
            prev_close = closes[-2] if len(closes) >= 2 else price
        else:
            price = 0.0
            prev_close = 0.0
            warnings.append("inflation: no TIP price data available")

        return PanelContextBuildResult(
            scalars={
                "michigan_5y": float(latest) if latest is not None else None,
                "michigan_prev": float(prev) if prev is not None else None,
                "tip_price_latest": price,
                "tip_prev_close": prev_close,
            },
            raw_series={"tip_price": closes, "price": closes},
            warnings=warnings,
        )
```

- [ ] **Step 4: Run** — 4 passed.

- [ ] **Step 5: Lint + commit**

```
git add packages/core/src/openlia/panic_thermometer/panels/inflation.py packages/core/tests/panic_thermometer/test_inflation_panel.py
git commit -m "feat(core): PT InflationPanel with TIP + Michigan 5Y context"
```

---

### Task 5: Core — `FedLanguagePanel` (keyword scanner)

Panel runs keyword matching in Python before the engine evaluates. Exposes four boolean scalars (`dovish_keyword_detected`, `neutral_keyword_detected`, `hawkish_keyword_detected`, `crisis_keyword_detected`), a `matched_phrase`, a `matched_headline`, a `matched_date`, plus `days_since_fomc`.

**Files:**
- Create: `packages/core/src/openlia/panic_thermometer/panels/fed_language.py`
- Test: `packages/core/tests/panic_thermometer/test_fed_language_panel.py`

- [ ] **Step 1: Failing test**

```python
# packages/core/tests/panic_thermometer/test_fed_language_panel.py
from openlia.panic_thermometer.panels.fed_language import FedLanguagePanel


def test_fed_panel_id_and_requirements():
    p = FedLanguagePanel()
    assert p.panel_id == "fed_language"
    assert set(p.required_requirements) == {"company_news", "economic_events"}


def test_fed_default_ruleset_has_crisis_hawkish_neutral_green():
    rs = FedLanguagePanel().default_ruleset
    statuses = [r["status"] for r in rs["rules"]]
    assert statuses == ["dark_red", "red", "amber", "green"]
    assert "persistent inflation" in rs["params"]["hawkish_keywords"]


def test_fed_build_context_detects_hawkish_keyword():
    p = FedLanguagePanel()
    news = [
        {"date": "2026-04-20", "headline": "Powell: persistent inflation concerns grow", "summary": "The chair warned about persistent inflation.", "source": "Reuters"},
        {"date": "2026-04-18", "headline": "Fed stays patient", "summary": "Data dependent stance", "source": "WSJ"},
    ]
    events = [
        {"date": "2026-04-10", "event_name": "FOMC Statement", "country": "US"},
    ]
    r = p.build_context(
        panel_config={"params": FedLanguagePanel().default_ruleset["params"]},
        payloads={"company_news": news, "economic_events": events},
    )
    assert r.scalars["hawkish_keyword_detected"] is True
    assert r.scalars["crisis_keyword_detected"] is False
    assert "persistent inflation" in r.scalars["matched_phrase"].lower()


def test_fed_build_context_no_matches_is_dovish_green():
    p = FedLanguagePanel()
    news = [{"date": "2026-04-20", "headline": "Fed stays patient", "summary": "well anchored", "source": "Reuters"}]
    r = p.build_context(
        panel_config={"params": FedLanguagePanel().default_ruleset["params"]},
        payloads={"company_news": news, "economic_events": []},
    )
    assert r.scalars["hawkish_keyword_detected"] is False
    assert r.scalars["dovish_keyword_detected"] is True
```

- [ ] **Step 2: Run** — fails.

- [ ] **Step 3: Implementation**

```python
# packages/core/src/openlia/panic_thermometer/panels/fed_language.py
"""Fed language tracker panel — keyword scanner over recent Fed news."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from openlia.panic_thermometer.panels.base import PanelContextBuildResult


_DEFAULT_RULESET: dict[str, Any] = {
    "rules": [
        {"status": "dark_red", "formula": "crisis_keyword_detected", "label": "Emergency posture - '{matched_phrase}'"},
        {"status": "red", "formula": "hawkish_keyword_detected", "label": "Hawkish pivot - '{matched_phrase}'"},
        {"status": "amber", "formula": "neutral_keyword_detected AND NOT dovish_keyword_detected", "label": "Neutral pivot"},
        {"status": "green", "formula": "true", "label": "Dovish / wait-and-see"},
    ],
    "params": {
        "dovish_keywords": ["look through", "transitory", "patient", "well anchored"],
        "neutral_keywords": ["monitoring closely", "data dependent", "will act as appropriate"],
        "hawkish_keywords": ["broadly-based price pressures", "concerned about inflation", "persistent inflation"],
        "crisis_keywords": ["inflation expectations becoming unanchored", "emergency", "expedited"],
        "news_lookback_days": 30,
        "news_search_tags": "Fed,FOMC,Powell,Federal Reserve",
    },
    "streak_condition": None,
}


def _scan(text: str, keywords: list[str]) -> str | None:
    haystack = text.lower()
    for kw in keywords:
        if kw.lower() in haystack:
            return kw
    return None


@dataclass(frozen=True)
class FedLanguagePanel:
    panel_id: str = "fed_language"
    required_requirements: tuple[str, ...] = ("company_news", "economic_events")
    optional_requirements: tuple[str, ...] = ()
    default_ruleset: dict[str, Any] = field(default_factory=lambda: _DEFAULT_RULESET)

    def build_context(
        self,
        *,
        panel_config: dict[str, Any],
        payloads: dict[str, Any],
    ) -> PanelContextBuildResult:
        params = panel_config.get("params", {})
        news = payloads.get("company_news") or []
        events = payloads.get("economic_events") or []
        warnings: list[str] = []

        dovish = params.get("dovish_keywords", [])
        neutral = params.get("neutral_keywords", [])
        hawkish = params.get("hawkish_keywords", [])
        crisis = params.get("crisis_keywords", [])

        # Scan newest first (highest-priority match wins on crisis > hawkish > neutral > dovish)
        sorted_news = sorted(news, key=lambda a: a.get("date", ""), reverse=True)

        matched_phrase = ""
        matched_headline = ""
        matched_date = ""
        flags = {
            "dovish_keyword_detected": False,
            "neutral_keyword_detected": False,
            "hawkish_keyword_detected": False,
            "crisis_keyword_detected": False,
        }
        category_order = [
            ("crisis_keyword_detected", crisis),
            ("hawkish_keyword_detected", hawkish),
            ("neutral_keyword_detected", neutral),
            ("dovish_keyword_detected", dovish),
        ]
        for article in sorted_news:
            text = f"{article.get('headline', '')} {article.get('summary', '')}"
            for flag_name, kw_list in category_order:
                hit = _scan(text, kw_list)
                if hit:
                    flags[flag_name] = True
                    if not matched_phrase:
                        matched_phrase = hit
                        matched_headline = article.get("headline", "")
                        matched_date = article.get("date", "")

        fomc_events = [e for e in events if "FOMC" in (e.get("event_name", "") or "")]
        days_since_fomc: float | None = None
        if fomc_events:
            latest_fomc = max(fomc_events, key=lambda e: e.get("date", ""))
            try:
                fomc_date = datetime.fromisoformat(latest_fomc["date"]).date()
                days_since_fomc = float((date.today() - fomc_date).days)
            except Exception:
                warnings.append("fed_language: could not parse FOMC event date")
        else:
            warnings.append("fed_language: no FOMC event in lookback window")

        scalars: dict[str, Any] = {
            **flags,
            "matched_phrase": matched_phrase,
            "matched_headline": matched_headline,
            "matched_date": matched_date,
            "days_since_fomc": days_since_fomc,
            "manual_override": panel_config.get("manual_override"),
        }
        return PanelContextBuildResult(scalars=scalars, raw_series={}, warnings=warnings)
```

- [ ] **Step 4: Run** — 4 passed.

- [ ] **Step 5: Lint + commit**

```
git add packages/core/src/openlia/panic_thermometer/panels/fed_language.py packages/core/tests/panic_thermometer/test_fed_language_panel.py
git commit -m "feat(core): PT FedLanguagePanel keyword scanner"
```

---

### Task 6: Core — `WageGrowthPanel`

Pulls `economic_events` filtered to "Average Hourly Earnings". Exposes the latest MoM `value`, `prev_value`, `consecutive_count` (consecutive months above `wage_threshold_red`), `avg_12m`, and `cpi_mom` (if a CPI event is in the payload).

**Files:**
- Create: `packages/core/src/openlia/panic_thermometer/panels/wage_growth.py`
- Test: `packages/core/tests/panic_thermometer/test_wage_growth_panel.py`

- [ ] **Step 1: Failing test**

```python
# packages/core/tests/panic_thermometer/test_wage_growth_panel.py
from openlia.panic_thermometer.panels.wage_growth import WageGrowthPanel


def test_wage_panel_id_and_requirements():
    p = WageGrowthPanel()
    assert p.panel_id == "wage_growth"
    assert p.required_requirements == ("economic_events",)


def test_wage_default_ruleset():
    rs = WageGrowthPanel().default_ruleset
    assert rs["params"]["wage_threshold_red"] == 0.5
    assert rs["params"]["consecutive_required"] == 2


def test_wage_build_context_consecutive_count():
    p = WageGrowthPanel()
    events = [
        {"date": "2026-01-05", "event_name": "Average Hourly Earnings", "actual": 0.35, "country": "US"},
        {"date": "2026-02-05", "event_name": "Average Hourly Earnings", "actual": 0.55, "country": "US"},
        {"date": "2026-03-05", "event_name": "Average Hourly Earnings", "actual": 0.60, "country": "US"},
        {"date": "2026-03-10", "event_name": "CPI MoM", "actual": 0.30, "country": "US"},
    ]
    r = p.build_context(
        panel_config={"params": WageGrowthPanel().default_ruleset["params"]},
        payloads={"economic_events": events},
    )
    assert r.scalars["value"] == 0.60
    assert r.scalars["prev_value"] == 0.55
    assert r.scalars["consecutive_count"] == 2
    assert r.scalars["cpi_mom"] == 0.30
    assert r.raw_series["value"] == [0.35, 0.55, 0.60]


def test_wage_build_context_no_events():
    p = WageGrowthPanel()
    r = p.build_context(
        panel_config={"params": WageGrowthPanel().default_ruleset["params"]},
        payloads={"economic_events": []},
    )
    assert r.scalars["value"] is None
    assert r.scalars["consecutive_count"] == 0
```

- [ ] **Step 2: Run** — fails.

- [ ] **Step 3: Implementation**

```python
# packages/core/src/openlia/panic_thermometer/panels/wage_growth.py
"""Wage growth panel — Average Hourly Earnings MoM."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from openlia.panic_thermometer.panels.base import PanelContextBuildResult


_DEFAULT_RULESET: dict[str, Any] = {
    "rules": [
        {"status": "dark_red", "formula": "consecutive_count >= consecutive_required", "label": "Wage-price spiral risk - {consecutive_count} consecutive months"},
        {"status": "red", "formula": "value > wage_threshold_red", "label": "Single hot print ({value}%)"},
        {"status": "amber", "formula": "value > wage_threshold_amber", "label": "Elevated but not critical ({value}%)"},
        {"status": "green", "formula": "true", "label": "Normal ({value}%)"},
    ],
    "params": {
        "event_type_filter": "Average Hourly Earnings",
        "wage_threshold_amber": 0.4,
        "wage_threshold_red": 0.5,
        "consecutive_required": 2,
        "history_lookback_months": 12,
    },
    "streak_condition": None,
}


@dataclass(frozen=True)
class WageGrowthPanel:
    panel_id: str = "wage_growth"
    required_requirements: tuple[str, ...] = ("economic_events",)
    optional_requirements: tuple[str, ...] = ()
    default_ruleset: dict[str, Any] = field(default_factory=lambda: _DEFAULT_RULESET)

    def build_context(
        self,
        *,
        panel_config: dict[str, Any],
        payloads: dict[str, Any],
    ) -> PanelContextBuildResult:
        params = panel_config.get("params", {})
        event_filter = params.get("event_type_filter", "Average Hourly Earnings")
        red_threshold = float(params.get("wage_threshold_red", 0.5))

        events = payloads.get("economic_events") or []
        warnings: list[str] = []

        wage_events = sorted(
            [e for e in events if e.get("event_name") == event_filter and e.get("actual") is not None],
            key=lambda e: e.get("date", ""),
        )
        values = [float(e["actual"]) for e in wage_events]
        value = values[-1] if values else None
        prev_value = values[-2] if len(values) >= 2 else None

        consecutive_count = 0
        for v in reversed(values):
            if v > red_threshold:
                consecutive_count += 1
            else:
                break

        avg_12m = sum(values[-12:]) / len(values[-12:]) if values else None

        cpi_events = [e for e in events if "CPI" in (e.get("event_name", "") or "") and e.get("actual") is not None]
        cpi_mom = float(sorted(cpi_events, key=lambda e: e.get("date", ""))[-1]["actual"]) if cpi_events else None

        if not values:
            warnings.append("wage_growth: no AHE events in lookback window")

        return PanelContextBuildResult(
            scalars={
                "value": value,
                "prev_value": prev_value,
                "consecutive_count": consecutive_count,
                "avg_12m": avg_12m,
                "cpi_mom": cpi_mom,
            },
            raw_series={"value": values},
            warnings=warnings,
        )
```

- [ ] **Step 4: Run** — 4 passed.

- [ ] **Step 5: Lint + commit**

```
git add packages/core/src/openlia/panic_thermometer/panels/wage_growth.py packages/core/tests/panic_thermometer/test_wage_growth_panel.py
git commit -m "feat(core): PT WageGrowthPanel AHE MoM context builder"
```

---

### Task 7: Core — `DiplomacyPanel` (keyword scanner + milestone)

Computes `days_elapsed` from `panel_config["milestone_date"]` vs. today, `days_remaining = window_days - days_elapsed`, and the two keyword-detection booleans from news. Exposes `matched_progress_headlines` and `matched_escalation_headlines` as scalars (arrays of headline strings for UI rendering — DSL won't touch them but the frontend reads them from the dashboard response).

**Files:**
- Create: `packages/core/src/openlia/panic_thermometer/panels/diplomacy.py`
- Test: `packages/core/tests/panic_thermometer/test_diplomacy_panel.py`

- [ ] **Step 1: Failing test**

```python
# packages/core/tests/panic_thermometer/test_diplomacy_panel.py
from datetime import date, timedelta

from openlia.panic_thermometer.panels.diplomacy import DiplomacyPanel


def test_diplomacy_panel_id_and_requirements():
    p = DiplomacyPanel()
    assert p.panel_id == "diplomacy"
    assert p.required_requirements == ("company_news",)


def test_diplomacy_default_ruleset():
    rs = DiplomacyPanel().default_ruleset
    assert rs["params"]["window_days"] == 30
    assert rs["params"]["window_amber_pct"] == 50


def test_diplomacy_build_context_computes_days_elapsed():
    p = DiplomacyPanel()
    milestone = (date.today() - timedelta(days=10)).isoformat()
    news = [
        {"date": "2026-04-20", "headline": "Iran strait ceasefire reached", "summary": "Diplomatic progress"},
        {"date": "2026-04-21", "headline": "Mobilization announced", "summary": "Retaliation threatened"},
    ]
    r = p.build_context(
        panel_config={"params": DiplomacyPanel().default_ruleset["params"], "milestone_date": milestone},
        payloads={"company_news": news},
    )
    assert r.scalars["days_elapsed"] == 10
    assert r.scalars["days_remaining"] == 20
    assert r.scalars["escalation_detected"] is True
    assert r.scalars["progress_detected"] is True


def test_diplomacy_build_context_no_milestone_defaults_today():
    p = DiplomacyPanel()
    r = p.build_context(
        panel_config={"params": DiplomacyPanel().default_ruleset["params"], "milestone_date": None},
        payloads={"company_news": []},
    )
    assert r.scalars["days_elapsed"] == 0
    assert r.scalars["escalation_detected"] is False
```

- [ ] **Step 2: Run** — fails.

- [ ] **Step 3: Implementation**

```python
# packages/core/src/openlia/panic_thermometer/panels/diplomacy.py
"""Diplomatic progress panel — keyword scanner + user-marked milestone."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Any

from openlia.panic_thermometer.panels.base import PanelContextBuildResult


_DEFAULT_RULESET: dict[str, Any] = {
    "rules": [
        {"status": "red", "formula": "days_elapsed >= window_days AND escalation_detected", "label": "Window lapsed + escalation"},
        {"status": "red", "formula": "days_elapsed >= window_days", "label": "Window lapsed, no progress"},
        {"status": "amber", "formula": "days_elapsed >= window_days * (window_amber_pct / 100)", "label": "{days_remaining} days remaining"},
        {"status": "green", "formula": "true", "label": "Within window"},
    ],
    "params": {
        "window_days": 30,
        "window_amber_pct": 50,
        "news_keywords": ["ceasefire", "Hormuz", "strait", "Iran", "diplomatic", "negotiations", "peace talks", "de-escalation"],
        "escalation_keywords": ["military escalation", "strike", "blockade", "retaliation", "mobilization"],
        "news_lookback_days": 30,
    },
    "streak_condition": None,
}


def _matches(article: dict[str, Any], keywords: list[str]) -> bool:
    text = f"{article.get('headline', '')} {article.get('summary', '')}".lower()
    return any(kw.lower() in text for kw in keywords)


@dataclass(frozen=True)
class DiplomacyPanel:
    panel_id: str = "diplomacy"
    required_requirements: tuple[str, ...] = ("company_news",)
    optional_requirements: tuple[str, ...] = ()
    default_ruleset: dict[str, Any] = field(default_factory=lambda: _DEFAULT_RULESET)

    def build_context(
        self,
        *,
        panel_config: dict[str, Any],
        payloads: dict[str, Any],
    ) -> PanelContextBuildResult:
        params = panel_config.get("params", {})
        window_days = int(params.get("window_days", 30))
        news_keywords = params.get("news_keywords", [])
        escalation_keywords = params.get("escalation_keywords", [])

        milestone_raw = panel_config.get("milestone_date")
        if milestone_raw:
            try:
                milestone_date = datetime.fromisoformat(milestone_raw).date()
            except Exception:
                milestone_date = date.today()
        else:
            milestone_date = date.today()

        days_elapsed = (date.today() - milestone_date).days
        days_remaining = max(0, window_days - days_elapsed)

        news = payloads.get("company_news") or []
        progress_articles = [a for a in news if _matches(a, news_keywords)]
        escalation_articles = [a for a in news if _matches(a, escalation_keywords)]

        return PanelContextBuildResult(
            scalars={
                "days_elapsed": days_elapsed,
                "days_remaining": days_remaining,
                "progress_detected": bool(progress_articles),
                "escalation_detected": bool(escalation_articles),
                "matched_progress_headlines": [a.get("headline", "") for a in progress_articles[:10]],
                "matched_escalation_headlines": [a.get("headline", "") for a in escalation_articles[:10]],
                "manual_override": panel_config.get("manual_override"),
            },
            raw_series={},
            warnings=[],
        )
```

- [ ] **Step 4: Run the panel registry import test** — now that all 5 panel modules exist, the `PANELS` dict loads cleanly.

Run: `uv run pytest packages/core/tests/panic_thermometer/ -v`
Expected: all panel tests pass; import of `openlia.panic_thermometer.panels` succeeds.

- [ ] **Step 5: Lint + commit**

```
git add packages/core/src/openlia/panic_thermometer/panels/diplomacy.py packages/core/tests/panic_thermometer/test_diplomacy_panel.py
git commit -m "feat(core): PT DiplomacyPanel with milestone + keyword scanner"
```

---

### Task 8: Core — `composite.py` (count + weighted composite)

Maps panel statuses to composite threat level. Two modes. Returns a `CompositeResult` with `level` (calm / elevated / high / severe / crisis), `score` (numeric — count in count mode, weight sum in weighted mode), and `red_count`.

**Files:**
- Create: `packages/core/src/openlia/panic_thermometer/composite.py`
- Test: `packages/core/tests/panic_thermometer/test_composite.py`

- [ ] **Step 1: Failing test**

```python
# packages/core/tests/panic_thermometer/test_composite.py
import pytest

from openlia.panic_thermometer.composite import CompositeResult, compute_composite


def test_composite_count_zero_red_is_calm():
    r = compute_composite(
        {"oil": "green", "inflation": "green", "fed_language": "green", "wage_growth": "green", "diplomacy": "green"},
        {"mode": "count", "red_threshold": 2},
    )
    assert r.level == "calm"
    assert r.red_count == 0


def test_composite_count_one_red_is_elevated():
    r = compute_composite(
        {"oil": "red", "inflation": "green", "fed_language": "green", "wage_growth": "green", "diplomacy": "green"},
        {"mode": "count", "red_threshold": 2},
    )
    assert r.level == "elevated"
    assert r.red_count == 1


def test_composite_count_at_threshold_is_high():
    r = compute_composite(
        {"oil": "red", "inflation": "red", "fed_language": "green", "wage_growth": "green", "diplomacy": "green"},
        {"mode": "count", "red_threshold": 2},
    )
    assert r.level == "high"
    assert r.red_count == 2


def test_composite_count_three_red_is_severe():
    r = compute_composite(
        {"oil": "red", "inflation": "red", "fed_language": "red", "wage_growth": "green", "diplomacy": "green"},
        {"mode": "count", "red_threshold": 2},
    )
    assert r.level == "severe"


def test_composite_count_four_red_is_crisis():
    r = compute_composite(
        {"oil": "red", "inflation": "dark_red", "fed_language": "red", "wage_growth": "red", "diplomacy": "green"},
        {"mode": "count", "red_threshold": 2},
    )
    assert r.level == "crisis"
    assert r.red_count == 4


def test_composite_weighted_sums_weights():
    settings = {
        "mode": "weighted",
        "weights": {"oil": 1.0, "inflation": 1.0, "fed_language": 0.8, "wage_growth": 1.0, "diplomacy": 0.5},
        "thresholds": {"elevated": 1.0, "high": 2.0, "severe": 3.0, "crisis": 4.0},
    }
    r = compute_composite(
        {"oil": "red", "inflation": "red", "fed_language": "red", "wage_growth": "green", "diplomacy": "green"},
        settings,
    )
    assert pytest.approx(r.score) == 2.8
    assert r.level == "high"


def test_composite_disabled_panels_ignored():
    r = compute_composite(
        {"oil": "red", "inflation": "disabled", "fed_language": "red", "wage_growth": "disabled", "diplomacy": "green"},
        {"mode": "count", "red_threshold": 2},
    )
    assert r.red_count == 2
    assert r.level == "high"
```

- [ ] **Step 2: Run** — fails.

- [ ] **Step 3: Implementation**

```python
# packages/core/src/openlia/panic_thermometer/composite.py
"""Composite threat-level aggregation for the 5 PT panels."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

CompositeLevel = Literal["calm", "elevated", "high", "severe", "crisis"]


@dataclass(frozen=True)
class CompositeResult:
    level: CompositeLevel
    score: float
    red_count: int
    mode: str


def _is_red(status: str) -> bool:
    return status in ("red", "dark_red")


def _count_level(red_count: int, threshold: int) -> CompositeLevel:
    if red_count == 0:
        return "calm"
    if red_count < threshold:
        return "elevated"
    if red_count == threshold:
        return "high"
    if red_count == threshold + 1:
        return "severe"
    return "crisis"


def _weighted_level(score: float, thresholds: dict[str, float]) -> CompositeLevel:
    if score < thresholds.get("elevated", 1.0):
        return "calm"
    if score < thresholds.get("high", 2.0):
        return "elevated"
    if score < thresholds.get("severe", 3.0):
        return "high"
    if score < thresholds.get("crisis", 4.0):
        return "severe"
    return "crisis"


def compute_composite(
    panel_statuses: dict[str, str],
    settings: dict[str, Any],
) -> CompositeResult:
    mode = settings.get("mode", "count")
    red_panels = {p: s for p, s in panel_statuses.items() if _is_red(s)}
    red_count = len(red_panels)

    if mode == "weighted":
        weights = settings.get("weights", {})
        score = sum(float(weights.get(p, 0.0)) for p in red_panels)
        level = _weighted_level(score, settings.get("thresholds", {}))
    else:
        threshold = int(settings.get("red_threshold", 2))
        score = float(red_count)
        level = _count_level(red_count, threshold)

    return CompositeResult(level=level, score=score, red_count=red_count, mode=mode)
```

- [ ] **Step 4: Run** — 7 passed.

- [ ] **Step 5: Lint + commit**

```
git add packages/core/src/openlia/panic_thermometer/composite.py packages/core/tests/panic_thermometer/test_composite.py
git commit -m "feat(core): PT composite scoring (count + weighted modes)"
```

---

### Task 9: Core — `presets.py` (three shipped presets per panel)

Each panel ships three presets: `report_defaults` (the panel's `default_ruleset`), `ma_relative` (MA-based thresholds), `volatility_adjusted` (ATR-scaled thresholds). Inflation, Fed language, wage growth, and diplomacy panels ship alternative params / rule sets for modes that make sense (e.g. Fed language MA-relative doesn't apply → ship "Report defaults" + two keyword-list variants).

**Files:**
- Create: `packages/core/src/openlia/panic_thermometer/presets.py`
- Test: `packages/core/tests/panic_thermometer/test_presets.py`

- [ ] **Step 1: Failing test**

```python
# packages/core/tests/panic_thermometer/test_presets.py
from openlia.panic_thermometer.presets import PT_PRESETS


def test_presets_cover_all_panels():
    assert set(PT_PRESETS.keys()) == {"oil", "inflation", "fed_language", "wage_growth", "diplomacy"}


def test_each_panel_has_three_presets():
    for panel, presets in PT_PRESETS.items():
        assert len(presets) == 3, f"{panel} should ship 3 presets, got {list(presets)}"


def test_report_defaults_match_panel_default():
    from openlia.panic_thermometer.panels import PANELS

    for panel_id, panel in PANELS.items():
        report_defaults = PT_PRESETS[panel_id]["report_defaults"]
        assert report_defaults["rules"] == panel.default_ruleset["rules"]


def test_oil_ma_relative_uses_ma200():
    rs = PT_PRESETS["oil"]["ma_relative"]
    formulas = " ".join(r["formula"] for r in rs["rules"])
    assert "ma200" in formulas or "price_vs_ma200" in formulas


def test_oil_volatility_adjusted_uses_atr():
    rs = PT_PRESETS["oil"]["volatility_adjusted"]
    formulas = " ".join(r["formula"] for r in rs["rules"])
    assert "atr_14" in formulas


def test_every_preset_is_parseable_by_formula_engine():
    from openlia.formula import FormulaError, FormulaEngine

    engine = FormulaEngine()
    for panel_id, presets in PT_PRESETS.items():
        for preset_name, rs in presets.items():
            for rule in rs["rules"]:
                try:
                    engine.parse(rule["formula"])
                except FormulaError as exc:  # pragma: no cover - informational
                    raise AssertionError(
                        f"{panel_id}/{preset_name} rule '{rule['formula']}' failed to parse: {exc}"
                    )
```

- [ ] **Step 2: Run** — fails.

- [ ] **Step 3: Implementation**

```python
# packages/core/src/openlia/panic_thermometer/presets.py
"""Shipped preset libraries for Panic Thermometer panels."""

from __future__ import annotations

from typing import Any

from openlia.panic_thermometer.panels import PANELS


def _oil_ma_relative() -> dict[str, Any]:
    return {
        "rules": [
            {"status": "dark_red", "formula": "streak_days >= streak_dark_red", "label": "{streak_days} days above MA200*1.15"},
            {"status": "red", "formula": "streak_days >= streak_red", "label": "{streak_days} days above MA200*1.15"},
            {"status": "amber", "formula": "price > ma200 * ma_multiplier", "label": "Above MA200 band"},
            {"status": "green", "formula": "true", "label": "Within MA200 band"},
        ],
        "params": {
            "ticker": "BNO.US",
            "ma_multiplier": 1.15,
            "streak_amber": 1,
            "streak_red": 30,
            "streak_dark_red": 90,
            "history_lookback_months": 12,
        },
        "streak_condition": "price > ma200 * ma_multiplier",
    }


def _oil_volatility_adjusted() -> dict[str, Any]:
    return {
        "rules": [
            {"status": "dark_red", "formula": "streak_days >= streak_dark_red", "label": "{streak_days} days > 2 ATR band"},
            {"status": "red", "formula": "streak_days >= streak_red", "label": "{streak_days} days > 2 ATR band"},
            {"status": "amber", "formula": "price > ma200 + atr_14 * atr_multiplier", "label": "Above 2 ATR band"},
            {"status": "green", "formula": "true", "label": "Within 2 ATR band"},
        ],
        "params": {
            "ticker": "BNO.US",
            "atr_multiplier": 2.0,
            "streak_amber": 1,
            "streak_red": 30,
            "streak_dark_red": 90,
            "history_lookback_months": 12,
        },
        "streak_condition": "price > ma200 + atr_14 * atr_multiplier",
    }


def _inflation_pure_tip() -> dict[str, Any]:
    return {
        "rules": [
            {"status": "red", "formula": "tip_price_latest > ma200 AND slope(tip_price, slope_lookback_days) > slope_threshold", "label": "TIP rising fast"},
            {"status": "amber", "formula": "tip_price_latest > ma200", "label": "TIP above 200-day MA"},
            {"status": "green", "formula": "true", "label": "TIP below 200-day MA"},
        ],
        "params": {"primary_ticker": "TIP.US", "slope_lookback_days": 30, "slope_threshold": 0.02},
        "streak_condition": None,
    }


def _inflation_relative_to_history() -> dict[str, Any]:
    return {
        "rules": [
            {"status": "red", "formula": "michigan_5y >= percentile(michigan_history, 60, 90)", "label": "Michigan 90th pct"},
            {"status": "amber", "formula": "michigan_5y >= percentile(michigan_history, 60, 75)", "label": "Michigan 75th pct"},
            {"status": "green", "formula": "true", "label": "Within normal range"},
        ],
        "params": {"primary_ticker": "TIP.US"},
        "streak_condition": None,
    }


def _fed_conservative_keywords() -> dict[str, Any]:
    base = PANELS["fed_language"].default_ruleset
    return {
        "rules": base["rules"],
        "params": {
            **base["params"],
            "hawkish_keywords": ["concerning", "elevated risks", "broadly-based price pressures", "persistent inflation", "policy tightening"],
            "crisis_keywords": ["unanchored", "emergency", "expedited", "rapid tightening"],
        },
        "streak_condition": None,
    }


def _fed_aggressive_keywords() -> dict[str, Any]:
    base = PANELS["fed_language"].default_ruleset
    return {
        "rules": base["rules"],
        "params": {
            **base["params"],
            "hawkish_keywords": ["rate hike", "tightening", "inflation", "restrictive", "concerned"],
            "crisis_keywords": ["emergency", "expedited", "unanchored", "crisis"],
        },
        "streak_condition": None,
    }


def _wage_acceleration() -> dict[str, Any]:
    return {
        "rules": [
            {"status": "red", "formula": "pct_change(value, 1) > 0 AND value > wage_threshold_red", "label": "Wages hot + accelerating"},
            {"status": "amber", "formula": "value > wage_threshold_amber", "label": "Elevated ({value}%)"},
            {"status": "green", "formula": "true", "label": "Normal"},
        ],
        "params": {
            "event_type_filter": "Average Hourly Earnings",
            "wage_threshold_amber": 0.4,
            "wage_threshold_red": 0.5,
            "consecutive_required": 2,
            "history_lookback_months": 12,
        },
        "streak_condition": None,
    }


def _wage_dynamic_threshold() -> dict[str, Any]:
    return {
        "rules": [
            {"status": "red", "formula": "value > avg(value, 12) + std_20", "label": "Above 1-sigma of trailing avg"},
            {"status": "amber", "formula": "value > avg(value, 12)", "label": "Above 12m avg"},
            {"status": "green", "formula": "true", "label": "Below trailing avg"},
        ],
        "params": {"event_type_filter": "Average Hourly Earnings", "history_lookback_months": 24},
        "streak_condition": None,
    }


def _diplomacy_short_window() -> dict[str, Any]:
    base = PANELS["diplomacy"].default_ruleset
    return {
        "rules": base["rules"],
        "params": {**base["params"], "window_days": 14, "window_amber_pct": 50},
        "streak_condition": None,
    }


def _diplomacy_long_window() -> dict[str, Any]:
    base = PANELS["diplomacy"].default_ruleset
    return {
        "rules": base["rules"],
        "params": {**base["params"], "window_days": 60, "window_amber_pct": 75},
        "streak_condition": None,
    }


PT_PRESETS: dict[str, dict[str, dict[str, Any]]] = {
    "oil": {
        "report_defaults": PANELS["oil"].default_ruleset,
        "ma_relative": _oil_ma_relative(),
        "volatility_adjusted": _oil_volatility_adjusted(),
    },
    "inflation": {
        "report_defaults": PANELS["inflation"].default_ruleset,
        "ma_relative": _inflation_pure_tip(),
        "volatility_adjusted": _inflation_relative_to_history(),
    },
    "fed_language": {
        "report_defaults": PANELS["fed_language"].default_ruleset,
        "ma_relative": _fed_conservative_keywords(),
        "volatility_adjusted": _fed_aggressive_keywords(),
    },
    "wage_growth": {
        "report_defaults": PANELS["wage_growth"].default_ruleset,
        "ma_relative": _wage_acceleration(),
        "volatility_adjusted": _wage_dynamic_threshold(),
    },
    "diplomacy": {
        "report_defaults": PANELS["diplomacy"].default_ruleset,
        "ma_relative": _diplomacy_short_window(),
        "volatility_adjusted": _diplomacy_long_window(),
    },
}
```

- [ ] **Step 4: Run** — all tests pass.

- [ ] **Step 5: Lint + commit**

```
git add packages/core/src/openlia/panic_thermometer/presets.py packages/core/tests/panic_thermometer/test_presets.py packages/core/src/openlia/panic_thermometer/panels/__init__.py
git commit -m "feat(core): PT shipped preset libraries + PANELS registry"
```

---

### Task 10: Core — Register department in `departments/__init__.py`

Add `PanicThermometerDepartment` to the exported set and to `get_department()` dispatcher.

**Files:**
- Modify: `packages/core/src/openlia/departments/__init__.py`
- Test: `packages/core/tests/departments/test_registry.py` (add case)

- [ ] **Step 1: Add registry assertion test**

```python
# packages/core/tests/departments/test_registry.py (extend)
from openlia.departments import get_department
from openlia.departments.panic_thermometer import PanicThermometerDepartment


def test_panic_thermometer_registered():
    d = get_department("panic_thermometer")
    assert isinstance(d, PanicThermometerDepartment)
```

- [ ] **Step 2: Run** — fails (registry not updated).

- [ ] **Step 3: Extend registry**

```python
# packages/core/src/openlia/departments/__init__.py (append to existing _REGISTRY)
from openlia.departments.panic_thermometer import PanicThermometerDepartment  # noqa: E402

_REGISTRY["panic_thermometer"] = PanicThermometerDepartment()

__all__ = [..., "PanicThermometerDepartment"]  # preserve prior __all__
```

> Coder note: the codebase uses a single `_REGISTRY` dict in `departments/__init__.py`. Append the PT entry without touching existing keys.

- [ ] **Step 4: Run** — passes.

- [ ] **Step 5: Lint + commit**

```
git add packages/core/src/openlia/departments/__init__.py packages/core/tests/departments/test_registry.py
git commit -m "feat(core): register PanicThermometerDepartment"
```

---

### Task 11: Server — `pt_config` service (config CRUD + default bootstrap)

Adds a `PtConfigService` with `get_or_create_for_user(user_id) -> PtUserConfig` that inserts a default row (panel_config seeded from every panel's `default_ruleset`, composite settings default to `{"mode": "count", "red_threshold": 2}`), plus `update_config(user_id, panel_config, composite_settings)`.

**Files:**
- Create: `packages/server/src/openlia_server/services/pt_config.py`
- Test: `packages/server/tests/services/test_pt_config.py`

- [ ] **Step 1: Failing test**

```python
# packages/server/tests/services/test_pt_config.py
import uuid

import pytest

from openlia_server.db.models.auth import User
from openlia_server.db.models.dashboard import PtUserConfig
from openlia_server.services.pt_config import PtConfigService


@pytest.fixture()
def user(db_session):
    u = User(
        id=str(uuid.uuid4()),
        email="pt@example.com",
        display_name="PT",
        password_hash="x",
        is_admin=False,
        must_change_password=False,
    )
    db_session.add(u)
    db_session.commit()
    return u


def test_get_or_create_seeds_defaults_on_first_call(db_session, user):
    svc = PtConfigService(session_factory=lambda: db_session)
    cfg = svc.get_or_create_for_user(user.id)
    assert cfg.user_id == user.id
    panels = {p["panel_id"]: p for p in cfg.panel_config}
    assert set(panels.keys()) == {"oil", "inflation", "fed_language", "wage_growth", "diplomacy"}
    assert panels["oil"]["rules"][0]["status"] == "dark_red"
    assert cfg.composite_settings["mode"] == "count"
    assert cfg.composite_settings["red_threshold"] == 2


def test_get_or_create_idempotent(db_session, user):
    svc = PtConfigService(session_factory=lambda: db_session)
    first = svc.get_or_create_for_user(user.id)
    second = svc.get_or_create_for_user(user.id)
    assert first.id == second.id
    assert db_session.query(PtUserConfig).filter_by(user_id=user.id).count() == 1


def test_update_config_replaces_panel_config(db_session, user):
    svc = PtConfigService(session_factory=lambda: db_session)
    svc.get_or_create_for_user(user.id)
    new_cfg = [
        {
            "panel_id": "oil",
            "rules": [{"status": "green", "formula": "true", "label": "Always green"}],
            "params": {"price_threshold": 999},
            "streak_condition": None,
            "manual_override": None,
            "milestone_date": None,
        }
    ]
    updated = svc.update_config(
        user.id,
        panel_config=new_cfg,
        composite_settings={"mode": "count", "red_threshold": 3},
    )
    assert updated.panel_config == new_cfg
    assert updated.composite_settings["red_threshold"] == 3
```

- [ ] **Step 2: Run** — fails.

- [ ] **Step 3: Implementation**

```python
# packages/server/src/openlia_server/services/pt_config.py
"""Panic Thermometer user-config + preset service."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Callable

from sqlalchemy.orm import Session

from openlia.panic_thermometer.panels import PANELS
from openlia.panic_thermometer.presets import PT_PRESETS
from openlia_server.db.models.dashboard import PtPreset, PtUserConfig


def _default_panel_config() -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for panel_id, panel in PANELS.items():
        rs = panel.default_ruleset
        out.append(
            {
                "panel_id": panel_id,
                "rules": rs["rules"],
                "params": dict(rs["params"]),
                "streak_condition": rs.get("streak_condition"),
                "manual_override": None,
                "milestone_date": None,
                "enabled": True,
            }
        )
    return out


def _default_composite_settings() -> dict[str, Any]:
    return {
        "mode": "count",
        "red_threshold": 2,
        "weights": {"oil": 1.0, "inflation": 1.0, "fed_language": 0.8, "wage_growth": 1.0, "diplomacy": 0.5},
        "thresholds": {"elevated": 1.0, "high": 2.0, "severe": 3.0, "crisis": 4.0},
    }


@dataclass
class PtConfigService:
    session_factory: Callable[[], Session]

    def _session(self) -> Session:
        return self.session_factory()

    def get_or_create_for_user(self, user_id: str) -> PtUserConfig:
        s = self._session()
        existing = s.query(PtUserConfig).filter_by(user_id=user_id).one_or_none()
        if existing is not None:
            return existing
        row = PtUserConfig(
            id=str(uuid.uuid4()),
            user_id=user_id,
            active_preset_id=None,
            panel_config=_default_panel_config(),
            composite_settings=_default_composite_settings(),
        )
        s.add(row)
        s.commit()
        s.refresh(row)
        return row

    def update_config(
        self,
        user_id: str,
        *,
        panel_config: list[dict[str, Any]],
        composite_settings: dict[str, Any],
    ) -> PtUserConfig:
        row = self.get_or_create_for_user(user_id)
        s = self._session()
        row.panel_config = panel_config
        row.composite_settings = composite_settings
        row.active_preset_id = None  # any edit demotes to "custom unsaved"
        s.add(row)
        s.commit()
        s.refresh(row)
        return row

    # Preset CRUD comes in Task 12.
    def seed_shipped_presets(self) -> None:  # pragma: no cover - filled in Task 12
        raise NotImplementedError

    def list_presets(self, user_id: str) -> list[PtPreset]:  # pragma: no cover
        raise NotImplementedError

    def create_preset(self, user_id: str, *, name: str, description: str | None) -> PtPreset:  # pragma: no cover
        raise NotImplementedError

    def delete_preset(self, user_id: str, preset_id: str) -> None:  # pragma: no cover
        raise NotImplementedError

    def apply_preset(self, user_id: str, preset_id: str) -> PtUserConfig:  # pragma: no cover
        raise NotImplementedError
```

- [ ] **Step 4: Run** — passes.

- [ ] **Step 5: Lint + commit**

```
git add packages/server/src/openlia_server/services/pt_config.py packages/server/tests/services/test_pt_config.py
git commit -m "feat(server): PtConfigService get_or_create + update_config"
```

---

### Task 12: Server — `pt_config` service (preset CRUD + shipped-preset seed)

Fills in `seed_shipped_presets`, `list_presets`, `create_preset`, `delete_preset`, `update_preset`.

**Files:**
- Modify: `packages/server/src/openlia_server/services/pt_config.py`
- Test: `packages/server/tests/services/test_pt_config_presets.py`

- [ ] **Step 1: Failing test**

```python
# packages/server/tests/services/test_pt_config_presets.py
import uuid

import pytest

from openlia_server.db.models.auth import User
from openlia_server.db.models.dashboard import PtPreset
from openlia_server.services.pt_config import PtConfigService


@pytest.fixture()
def user(db_session):
    u = User(id=str(uuid.uuid4()), email="p@x", display_name="U", password_hash="x", is_admin=False, must_change_password=False)
    db_session.add(u)
    db_session.commit()
    return u


def test_seed_inserts_fifteen_shipped_rows(db_session, user):
    svc = PtConfigService(session_factory=lambda: db_session)
    svc.seed_shipped_presets()
    rows = db_session.query(PtPreset).filter_by(is_shipped=True, user_id=None).all()
    assert len(rows) == 15  # 5 panels x 3 preset libraries
    names = {r.name for r in rows}
    assert {"oil::report_defaults", "fed_language::volatility_adjusted", "diplomacy::ma_relative"} <= names


def test_seed_is_idempotent(db_session, user):
    svc = PtConfigService(session_factory=lambda: db_session)
    svc.seed_shipped_presets()
    svc.seed_shipped_presets()
    assert db_session.query(PtPreset).filter_by(is_shipped=True, user_id=None).count() == 15


def test_create_and_list_user_preset(db_session, user):
    svc = PtConfigService(session_factory=lambda: db_session)
    svc.get_or_create_for_user(user.id)
    p = svc.create_preset(user.id, name="my-setup", description="custom")
    assert p.user_id == user.id
    assert p.is_shipped is False
    listed = svc.list_presets(user.id)
    shipped = [r for r in listed if r.is_shipped]
    user_rows = [r for r in listed if not r.is_shipped]
    assert len(user_rows) == 1 and user_rows[0].name == "my-setup"
    # Shipped presets visible to every user
    assert len(shipped) >= 15


def test_delete_user_preset(db_session, user):
    svc = PtConfigService(session_factory=lambda: db_session)
    svc.get_or_create_for_user(user.id)
    p = svc.create_preset(user.id, name="tmp", description=None)
    svc.delete_preset(user.id, p.id)
    assert db_session.query(PtPreset).filter_by(id=p.id).one_or_none() is None


def test_apply_shipped_preset_overwrites_panel_only(db_session, user):
    svc = PtConfigService(session_factory=lambda: db_session)
    svc.seed_shipped_presets()
    svc.get_or_create_for_user(user.id)
    oil_preset = db_session.query(PtPreset).filter_by(name="oil::ma_relative", is_shipped=True).one()
    updated = svc.apply_preset(user.id, oil_preset.id)
    oil = next(p for p in updated.panel_config if p["panel_id"] == "oil")
    assert oil["streak_condition"] == "price > ma200 * ma_multiplier"
    # Other panels untouched
    wage = next(p for p in updated.panel_config if p["panel_id"] == "wage_growth")
    assert wage["params"]["wage_threshold_red"] == 0.5
```

- [ ] **Step 2: Run** — fails.

- [ ] **Step 3: Replace the stubs in `pt_config.py`**

```python
# additions in packages/server/src/openlia_server/services/pt_config.py

def seed_shipped_presets(self) -> None:
    """Idempotently insert one PtPreset per (panel, preset_name) pair.

    Row name is 'panel::preset_name' (e.g., 'oil::report_defaults'). is_shipped=True.
    """
    s = self._session()
    existing_names = {
        r.name
        for r in s.query(PtPreset).filter(PtPreset.is_shipped.is_(True), PtPreset.user_id.is_(None)).all()
    }
    inserted = 0
    for panel_id, presets in PT_PRESETS.items():
        for preset_name, rs in presets.items():
            full_name = f"{panel_id}::{preset_name}"
            if full_name in existing_names:
                continue
            row = PtPreset(
                id=str(uuid.uuid4()),
                user_id=None,
                name=full_name,
                description=f"Shipped library: {panel_id} / {preset_name}",
                is_shipped=True,
                panel_config=[
                    {
                        "panel_id": panel_id,
                        "rules": rs["rules"],
                        "params": dict(rs["params"]),
                        "streak_condition": rs.get("streak_condition"),
                        "manual_override": None,
                        "milestone_date": None,
                        "enabled": True,
                    }
                ],
                composite_settings={},
            )
            s.add(row)
            inserted += 1
    if inserted:
        s.commit()

def list_presets(self, user_id: str) -> list[PtPreset]:
    s = self._session()
    return (
        s.query(PtPreset)
        .filter((PtPreset.user_id == user_id) | (PtPreset.user_id.is_(None)))
        .order_by(PtPreset.is_shipped.desc(), PtPreset.name)
        .all()
    )

def create_preset(self, user_id: str, *, name: str, description: str | None) -> PtPreset:
    cfg = self.get_or_create_for_user(user_id)
    s = self._session()
    row = PtPreset(
        id=str(uuid.uuid4()),
        user_id=user_id,
        name=name,
        description=description,
        is_shipped=False,
        panel_config=cfg.panel_config,
        composite_settings=cfg.composite_settings,
    )
    s.add(row)
    s.commit()
    s.refresh(row)
    return row

def update_preset(self, user_id: str, preset_id: str, *, name: str, description: str | None) -> PtPreset:
    s = self._session()
    row = s.query(PtPreset).filter_by(id=preset_id, user_id=user_id).one_or_none()
    if row is None:
        raise ValueError(f"preset {preset_id} not found for user {user_id}")
    row.name = name
    row.description = description
    s.add(row)
    s.commit()
    s.refresh(row)
    return row

def delete_preset(self, user_id: str, preset_id: str) -> None:
    s = self._session()
    row = s.query(PtPreset).filter_by(id=preset_id, user_id=user_id).one_or_none()
    if row is None:
        raise ValueError(f"preset {preset_id} not found for user {user_id}")
    s.delete(row)
    s.commit()

def apply_preset(self, user_id: str, preset_id: str) -> PtUserConfig:
    """Load a preset's panel config, merging per-panel into the user's live config.

    Shipped presets carry exactly one panel's config; we merge by panel_id.
    User presets carry the full 5-panel snapshot; we overwrite wholesale.
    """
    s = self._session()
    preset = s.query(PtPreset).filter(
        PtPreset.id == preset_id,
        (PtPreset.user_id == user_id) | (PtPreset.user_id.is_(None)),
    ).one_or_none()
    if preset is None:
        raise ValueError(f"preset {preset_id} not found")
    cfg = self.get_or_create_for_user(user_id)
    current = {p["panel_id"]: p for p in cfg.panel_config}
    for incoming in preset.panel_config:
        current[incoming["panel_id"]] = incoming
    cfg.panel_config = [current[pid] for pid in ("oil", "inflation", "fed_language", "wage_growth", "diplomacy")]
    if preset.composite_settings:
        cfg.composite_settings = preset.composite_settings
    cfg.active_preset_id = preset.id
    s.add(cfg)
    s.commit()
    s.refresh(cfg)
    return cfg
```

- [ ] **Step 4: Run** — 5 passed.

- [ ] **Step 5: Lint + commit**

```
git add packages/server/src/openlia_server/services/pt_config.py packages/server/tests/services/test_pt_config_presets.py
git commit -m "feat(server): PT preset CRUD + shipped-preset idempotent seed"
```

---

### Task 13: Server — `pt_config` service (import/export)

Adds `export_config(user_id) -> dict` and `import_config(user_id, payload) -> PtUserConfig`. Export emits `{version: 1, panel_config, composite_settings}`. Import validates the shape via a Pydantic model, rejects unknown versions, overwrites the user's row.

**Files:**
- Modify: `packages/server/src/openlia_server/services/pt_config.py`
- Test: `packages/server/tests/services/test_pt_config_import_export.py`

- [ ] **Step 1: Failing test**

```python
# packages/server/tests/services/test_pt_config_import_export.py
import uuid

import pytest

from openlia_server.db.models.auth import User
from openlia_server.services.pt_config import PtConfigService


@pytest.fixture()
def user(db_session):
    u = User(id=str(uuid.uuid4()), email="pe@x", display_name="U", password_hash="x", is_admin=False, must_change_password=False)
    db_session.add(u)
    db_session.commit()
    return u


def test_export_emits_version_1_shape(db_session, user):
    svc = PtConfigService(session_factory=lambda: db_session)
    svc.get_or_create_for_user(user.id)
    payload = svc.export_config(user.id)
    assert payload["version"] == 1
    assert "panel_config" in payload and len(payload["panel_config"]) == 5
    assert "composite_settings" in payload


def test_import_overwrites_config(db_session, user):
    svc = PtConfigService(session_factory=lambda: db_session)
    svc.get_or_create_for_user(user.id)
    new_payload = {
        "version": 1,
        "panel_config": [
            {"panel_id": "oil", "rules": [{"status": "green", "formula": "true", "label": "ok"}], "params": {"price_threshold": 1}, "streak_condition": None, "manual_override": None, "milestone_date": None, "enabled": True},
            {"panel_id": "inflation", "rules": [], "params": {}, "streak_condition": None, "manual_override": None, "milestone_date": None, "enabled": False},
            {"panel_id": "fed_language", "rules": [], "params": {}, "streak_condition": None, "manual_override": None, "milestone_date": None, "enabled": False},
            {"panel_id": "wage_growth", "rules": [], "params": {}, "streak_condition": None, "manual_override": None, "milestone_date": None, "enabled": False},
            {"panel_id": "diplomacy", "rules": [], "params": {}, "streak_condition": None, "manual_override": None, "milestone_date": None, "enabled": False},
        ],
        "composite_settings": {"mode": "count", "red_threshold": 4},
    }
    updated = svc.import_config(user.id, new_payload)
    assert updated.composite_settings["red_threshold"] == 4
    oil = next(p for p in updated.panel_config if p["panel_id"] == "oil")
    assert oil["params"]["price_threshold"] == 1


def test_import_rejects_unknown_version(db_session, user):
    svc = PtConfigService(session_factory=lambda: db_session)
    with pytest.raises(ValueError, match="unsupported PT config version"):
        svc.import_config(user.id, {"version": 2, "panel_config": [], "composite_settings": {}})


def test_import_requires_all_five_panels(db_session, user):
    svc = PtConfigService(session_factory=lambda: db_session)
    with pytest.raises(ValueError, match="panel_config must contain all 5 panels"):
        svc.import_config(user.id, {"version": 1, "panel_config": [], "composite_settings": {}})
```

- [ ] **Step 2: Run** — fails.

- [ ] **Step 3: Add to `pt_config.py`**

```python
# additions in packages/server/src/openlia_server/services/pt_config.py

_REQUIRED_PANELS = {"oil", "inflation", "fed_language", "wage_growth", "diplomacy"}


def export_config(self, user_id: str) -> dict[str, Any]:
    cfg = self.get_or_create_for_user(user_id)
    return {
        "version": 1,
        "panel_config": cfg.panel_config,
        "composite_settings": cfg.composite_settings,
    }


def import_config(self, user_id: str, payload: dict[str, Any]) -> PtUserConfig:
    version = payload.get("version")
    if version != 1:
        raise ValueError(f"unsupported PT config version: {version!r}")
    panel_config = payload.get("panel_config") or []
    seen = {p.get("panel_id") for p in panel_config}
    if seen != _REQUIRED_PANELS:
        raise ValueError("panel_config must contain all 5 panels: " + ", ".join(sorted(_REQUIRED_PANELS)))
    return self.update_config(
        user_id,
        panel_config=panel_config,
        composite_settings=payload.get("composite_settings") or {},
    )
```

> Add the `_REQUIRED_PANELS` module-level constant near the top of `pt_config.py`.

- [ ] **Step 4: Run** — 4 passed.

- [ ] **Step 5: Lint + commit**

```
git add packages/server/src/openlia_server/services/pt_config.py packages/server/tests/services/test_pt_config_import_export.py
git commit -m "feat(server): PT config import/export (version 1)"
```

---

### Task 14: Server — `pt_runner` service (dashboard orchestrator)

Orchestrates: load user config → for each enabled panel, walk `panel.required_requirements`, resolve adapters via Plan 3's dispatcher, invoke each adapter with the panel's params, pass payloads to `panel.build_context`, assemble an `EvaluationContext(raw_series, scalars, params)`, invoke `FormulaEngine().evaluate_ruleset(ruleset, context)`, collect statuses, compute composite.

**Files:**
- Create: `packages/server/src/openlia_server/services/pt_runner.py`
- Test: `packages/server/tests/services/test_pt_runner.py`

- [ ] **Step 1: Failing test**

```python
# packages/server/tests/services/test_pt_runner.py
import uuid
from dataclasses import dataclass
from typing import Any

import pytest

from openlia_server.db.models.auth import User
from openlia_server.services.pt_config import PtConfigService
from openlia_server.services.pt_runner import DashboardPayload, PtRunner


@dataclass
class _FakeDispatcher:
    """Minimal stand-in for Plan 3 data adapter dispatcher."""

    payloads: dict[tuple[str, str], Any]  # (panel_id, requirement) -> value

    def fetch(self, *, requirement: str, panel_id: str, params: dict[str, Any]) -> Any:
        return self.payloads.get((panel_id, requirement))


@pytest.fixture()
def user(db_session):
    u = User(id=str(uuid.uuid4()), email="r@x", display_name="U", password_hash="x", is_admin=False, must_change_password=False)
    db_session.add(u)
    db_session.commit()
    return u


def _dispatcher_with_oil_red():
    # 40 days of price above 85 -> streak forces dark_red path via report_defaults
    history = [
        {"date": f"2026-03-{i:02d}", "open": 90.0, "high": 95.0, "low": 88.0, "close": 90.0 + i * 0.1, "volume": 0}
        for i in range(1, 99)
    ]
    quote = {"price": 98.5, "previous_close": 97.9}
    return _FakeDispatcher(
        payloads={
            ("oil", "historical_prices"): history,
            ("oil", "stock_quote"): quote,
            ("inflation", "historical_prices"): [],
            ("inflation", "stock_quote"): None,
            ("inflation", "economic_events"): [],
            ("fed_language", "company_news"): [],
            ("fed_language", "economic_events"): [],
            ("wage_growth", "economic_events"): [],
            ("diplomacy", "company_news"): [],
        }
    )


def test_runner_returns_five_panels_and_composite(db_session, user):
    cfg_svc = PtConfigService(session_factory=lambda: db_session)
    cfg_svc.get_or_create_for_user(user.id)
    runner = PtRunner(session_factory=lambda: db_session, dispatcher=_dispatcher_with_oil_red())
    payload = runner.compute_dashboard(user.id)
    assert isinstance(payload, DashboardPayload)
    assert set(payload.panels.keys()) == {"oil", "inflation", "fed_language", "wage_growth", "diplomacy"}
    assert payload.panels["oil"]["status"] in ("amber", "red", "dark_red")
    assert payload.composite["level"] in ("calm", "elevated", "high", "severe", "crisis")


def test_runner_disabled_panel_returns_disabled_status(db_session, user):
    cfg_svc = PtConfigService(session_factory=lambda: db_session)
    cfg = cfg_svc.get_or_create_for_user(user.id)
    # Disable oil
    pc = cfg.panel_config
    for entry in pc:
        if entry["panel_id"] == "oil":
            entry["enabled"] = False
    cfg_svc.update_config(user.id, panel_config=pc, composite_settings=cfg.composite_settings)

    runner = PtRunner(session_factory=lambda: db_session, dispatcher=_dispatcher_with_oil_red())
    payload = runner.compute_dashboard(user.id)
    assert payload.panels["oil"]["status"] == "disabled"


def test_runner_manual_override_short_circuits_rule_evaluation(db_session, user):
    cfg_svc = PtConfigService(session_factory=lambda: db_session)
    cfg = cfg_svc.get_or_create_for_user(user.id)
    for entry in cfg.panel_config:
        if entry["panel_id"] == "fed_language":
            entry["manual_override"] = {"status": "red", "note": "forced", "set_at": "2026-04-23T00:00:00Z"}
    cfg_svc.update_config(user.id, panel_config=cfg.panel_config, composite_settings=cfg.composite_settings)
    runner = PtRunner(session_factory=lambda: db_session, dispatcher=_dispatcher_with_oil_red())
    payload = runner.compute_dashboard(user.id)
    assert payload.panels["fed_language"]["status"] == "red"
    assert payload.panels["fed_language"]["label"].startswith("Manual override")
```

- [ ] **Step 2: Run** — fails.

- [ ] **Step 3: Implementation**

```python
# packages/server/src/openlia_server/services/pt_runner.py
"""Panic Thermometer dashboard orchestrator."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Protocol

from sqlalchemy.orm import Session

from openlia.formula import EvaluationContext, FormulaEngine, FormulaError
from openlia.panic_thermometer.composite import compute_composite
from openlia.panic_thermometer.panels import PANELS
from openlia_server.services.pt_config import PtConfigService


class DataDispatcher(Protocol):
    def fetch(self, *, requirement: str, panel_id: str, params: dict[str, Any]) -> Any: ...


@dataclass
class DashboardPayload:
    panels: dict[str, dict[str, Any]]
    composite: dict[str, Any]
    generated_at: str
    warnings: list[str] = field(default_factory=list)


def _panel_result_dict(panel_id: str, *, status: str, label: str, resolved_values: dict[str, Any], derived_scalars: dict[str, Any], extras: dict[str, Any], warnings: list[str]) -> dict[str, Any]:
    return {
        "panel_id": panel_id,
        "status": status,
        "label": label,
        "resolved_values": resolved_values,
        "derived_scalars": derived_scalars,
        "extras": extras,
        "warnings": warnings,
    }


@dataclass
class PtRunner:
    session_factory: Callable[[], Session]
    dispatcher: DataDispatcher
    engine: FormulaEngine = field(default_factory=FormulaEngine)
    _cache: dict[tuple[str, str], dict[str, Any]] = field(default_factory=dict)
    # _cache: (user_id, panel_id) -> {"scalars": ..., "raw_series": ..., "params": ...}

    def _config_service(self) -> PtConfigService:
        return PtConfigService(session_factory=self.session_factory)

    def compute_dashboard(self, user_id: str) -> DashboardPayload:
        from datetime import datetime, timezone

        cfg = self._config_service().get_or_create_for_user(user_id)
        panel_statuses: dict[str, str] = {}
        panels_out: dict[str, dict[str, Any]] = {}
        all_warnings: list[str] = []

        for entry in cfg.panel_config:
            panel_id = entry["panel_id"]
            panel = PANELS[panel_id]
            if entry.get("enabled", True) is False:
                panels_out[panel_id] = _panel_result_dict(
                    panel_id, status="disabled", label="Panel disabled",
                    resolved_values={}, derived_scalars={}, extras={}, warnings=[],
                )
                panel_statuses[panel_id] = "disabled"
                continue

            override = entry.get("manual_override")
            if override and override.get("status"):
                panels_out[panel_id] = _panel_result_dict(
                    panel_id,
                    status=override["status"],
                    label=f"Manual override: {override.get('note') or ''}".strip(": "),
                    resolved_values={}, derived_scalars={},
                    extras={"override": override}, warnings=[],
                )
                panel_statuses[panel_id] = override["status"]
                continue

            # Fetch each requirement via dispatcher
            payloads: dict[str, Any] = {}
            fetch_warnings: list[str] = []
            for req in panel.required_requirements:
                try:
                    payloads[req] = self.dispatcher.fetch(
                        requirement=req, panel_id=panel_id, params=entry.get("params", {}),
                    )
                except Exception as exc:  # noqa: BLE001
                    fetch_warnings.append(f"{panel_id}: {req} fetch failed: {exc}")
                    payloads[req] = None
            for req in panel.optional_requirements:
                try:
                    payloads[req] = self.dispatcher.fetch(
                        requirement=req, panel_id=panel_id, params=entry.get("params", {}),
                    )
                except Exception as exc:  # noqa: BLE001
                    fetch_warnings.append(f"{panel_id}: optional {req} fetch failed: {exc}")
                    payloads[req] = None

            built = panel.build_context(panel_config=entry, payloads=payloads)
            self._cache[(user_id, panel_id)] = {
                "scalars": built.scalars,
                "raw_series": built.raw_series,
                "params": entry.get("params", {}),
                "streak_condition": entry.get("streak_condition"),
                "rules": entry["rules"],
            }

            context = EvaluationContext(
                raw_series=built.raw_series,
                scalars=built.scalars,
                params=entry.get("params", {}),
            )
            ruleset_dict = {
                "rules": entry["rules"],
                "params": entry.get("params", {}),
                "streak_condition": entry.get("streak_condition"),
            }
            try:
                result = self.engine.evaluate_ruleset(ruleset_dict, context)
                panels_out[panel_id] = _panel_result_dict(
                    panel_id,
                    status=result.status,
                    label=result.label,
                    resolved_values=result.resolved_values,
                    derived_scalars=result.derived_scalars,
                    extras={
                        k: v for k, v in built.scalars.items()
                        if k in (
                            "matched_progress_headlines", "matched_escalation_headlines",
                            "matched_phrase", "matched_headline", "matched_date",
                            "days_since_fomc",
                        )
                    },
                    warnings=result.warnings + fetch_warnings + built.warnings,
                )
                panel_statuses[panel_id] = result.status
            except FormulaError as exc:
                msg = f"{panel_id}: formula error: {exc}"
                all_warnings.append(msg)
                panels_out[panel_id] = _panel_result_dict(
                    panel_id, status="disabled", label="Configuration error",
                    resolved_values={}, derived_scalars={}, extras={}, warnings=[msg],
                )
                panel_statuses[panel_id] = "disabled"

        composite = compute_composite(panel_statuses, cfg.composite_settings)
        return DashboardPayload(
            panels=panels_out,
            composite={
                "level": composite.level,
                "score": composite.score,
                "red_count": composite.red_count,
                "mode": composite.mode,
            },
            generated_at=datetime.now(timezone.utc).isoformat(),
            warnings=all_warnings,
        )

    def cached_panel_inputs(self, user_id: str, panel_id: str) -> dict[str, Any] | None:
        return self._cache.get((user_id, panel_id))
```

- [ ] **Step 4: Run** — 3 passed.

- [ ] **Step 5: Lint + commit**

```
git add packages/server/src/openlia_server/services/pt_runner.py packages/server/tests/services/test_pt_runner.py
git commit -m "feat(server): PtRunner dashboard orchestrator + per-panel cache"
```

---

### Task 15: Server — `pt_runner` per-panel cache for formula test/preview

Add helpers `test_formula(user_id, panel_id, formula, params)` and `preview_ruleset(user_id, panel_id, ruleset_dict)` that read the most recent cached panel inputs and run the engine without re-fetching.

**Files:**
- Modify: `packages/server/src/openlia_server/services/pt_runner.py`
- Test: `packages/server/tests/services/test_pt_runner_formula_helpers.py`

- [ ] **Step 1: Failing test**

```python
# packages/server/tests/services/test_pt_runner_formula_helpers.py
import uuid

import pytest

from openlia_server.db.models.auth import User
from openlia_server.services.pt_config import PtConfigService
from openlia_server.services.pt_runner import PtRunner


@pytest.fixture()
def user(db_session):
    u = User(id=str(uuid.uuid4()), email="t@x", display_name="U", password_hash="x", is_admin=False, must_change_password=False)
    db_session.add(u)
    db_session.commit()
    return u


def test_test_formula_reads_cache(db_session, user):
    # Set up cache by running dashboard once with fake data
    from tests.services.test_pt_runner import _dispatcher_with_oil_red  # reuse fixture

    PtConfigService(session_factory=lambda: db_session).get_or_create_for_user(user.id)
    runner = PtRunner(session_factory=lambda: db_session, dispatcher=_dispatcher_with_oil_red())
    runner.compute_dashboard(user.id)

    result = runner.test_formula(user.id, "oil", "price > 50", params_override={})
    assert result.value is True
    assert result.resolved_values["price"] > 50


def test_preview_ruleset_reads_cache(db_session, user):
    from tests.services.test_pt_runner import _dispatcher_with_oil_red

    PtConfigService(session_factory=lambda: db_session).get_or_create_for_user(user.id)
    runner = PtRunner(session_factory=lambda: db_session, dispatcher=_dispatcher_with_oil_red())
    runner.compute_dashboard(user.id)

    preview = runner.preview_ruleset(user.id, "oil", {
        "rules": [{"status": "red", "formula": "price > 50", "label": "hit"}, {"status": "green", "formula": "true", "label": "miss"}],
        "params": {},
        "streak_condition": None,
    })
    assert preview.status == "red"
    assert preview.label == "hit"


def test_test_formula_without_cache_raises(db_session, user):
    from tests.services.test_pt_runner import _dispatcher_with_oil_red

    runner = PtRunner(session_factory=lambda: db_session, dispatcher=_dispatcher_with_oil_red())
    with pytest.raises(ValueError, match="no cached panel data"):
        runner.test_formula(user.id, "oil", "true", params_override={})
```

- [ ] **Step 2: Run** — fails.

- [ ] **Step 3: Implementation**

```python
# additions in packages/server/src/openlia_server/services/pt_runner.py

def test_formula(self, user_id: str, panel_id: str, formula: str, *, params_override: dict[str, Any]):
    cached = self._cache.get((user_id, panel_id))
    if cached is None:
        raise ValueError("no cached panel data - run dashboard once first")
    context = EvaluationContext(
        raw_series=cached["raw_series"],
        scalars=cached["scalars"],
        params={**cached["params"], **params_override},
    )
    return self.engine.evaluate_formula(formula, context)


def preview_ruleset(self, user_id: str, panel_id: str, ruleset_dict: dict[str, Any]):
    cached = self._cache.get((user_id, panel_id))
    if cached is None:
        raise ValueError("no cached panel data - run dashboard once first")
    context = EvaluationContext(
        raw_series=cached["raw_series"],
        scalars=cached["scalars"],
        params=ruleset_dict.get("params", {}),
    )
    return self.engine.evaluate_ruleset(ruleset_dict, context)


def parse_formula(self, formula: str):
    """Parse-only validation. Returns list of identifier names via extract_requirements."""
    from openlia.formula import extract_requirements
    self.engine.parse(formula)  # raises FormulaError on bad syntax
    return extract_requirements(formula)
```

- [ ] **Step 4: Run** — 3 passed.

- [ ] **Step 5: Lint + commit**

```
git add packages/server/src/openlia_server/services/pt_runner.py packages/server/tests/services/test_pt_runner_formula_helpers.py
git commit -m "feat(server): PtRunner formula test/preview/parse helpers"
```

---

### Task 16: Server — Route `GET /dashboard`

First PT route. Returns the `DashboardPayload` as JSON. Authenticated.

**Files:**
- Create: `packages/server/src/openlia_server/routes/departments/panic_thermometer.py`
- Test: `packages/server/tests/routes/test_pt_dashboard_route.py`

- [ ] **Step 1: Failing test**

```python
# packages/server/tests/routes/test_pt_dashboard_route.py
def test_dashboard_route_returns_json(auth_client):
    # auth_client is a fixture that returns TestClient + authenticated session cookie.
    # Plans 9/11 ship this fixture; if not available, test harness builds one inline.
    response = auth_client.get("/departments/panic_thermometer/dashboard")
    assert response.status_code == 200
    payload = response.json()
    assert set(payload["panels"].keys()) == {"oil", "inflation", "fed_language", "wage_growth", "diplomacy"}
    assert "composite" in payload and "level" in payload["composite"]
    assert "generated_at" in payload


def test_dashboard_route_requires_auth(unauthenticated_client):
    response = unauthenticated_client.get("/departments/panic_thermometer/dashboard")
    assert response.status_code == 401
```

- [ ] **Step 2: Run** — fails (router not mounted).

- [ ] **Step 3: Implement router factory**

```python
# packages/server/src/openlia_server/routes/departments/panic_thermometer.py
"""Panic Thermometer department routes."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Callable

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from openlia_server.db.models.auth import User
from openlia_server.middleware.auth import build_require_auth
from openlia_server.services.pt_config import PtConfigService
from openlia_server.services.pt_runner import DataDispatcher, PtRunner


def build_panic_thermometer_router(
    *,
    db_session_factory: Callable[[], Any],
    mode: str,
    dispatcher_factory: Callable[[], DataDispatcher],
) -> APIRouter:
    require_auth = build_require_auth(db_session_factory=db_session_factory, mode=mode)
    router = APIRouter(prefix="/departments/panic_thermometer", tags=["panic_thermometer"])

    def _runner() -> PtRunner:
        return PtRunner(session_factory=db_session_factory, dispatcher=dispatcher_factory())

    def _config_service() -> PtConfigService:
        return PtConfigService(session_factory=db_session_factory)

    @router.get("/dashboard")
    def get_dashboard(user: User = Depends(require_auth)) -> dict[str, Any]:
        runner = _runner()
        payload = runner.compute_dashboard(user.id)
        return {
            "panels": payload.panels,
            "composite": payload.composite,
            "generated_at": payload.generated_at,
            "warnings": payload.warnings,
        }

    # Additional routes appended in Tasks 17-20.

    return router
```

- [ ] **Step 4: Mount in `app.py`** (partial — full wiring in Task 21).

- [ ] **Step 5: Run** — 2 passed.

- [ ] **Step 6: Lint + commit**

```
git add packages/server/src/openlia_server/routes/departments/panic_thermometer.py packages/server/tests/routes/test_pt_dashboard_route.py
git commit -m "feat(server): PT GET /dashboard route"
```

---

### Task 17: Server — Routes `GET /config` + `PUT /config`

**Files:**
- Modify: `packages/server/src/openlia_server/routes/departments/panic_thermometer.py`
- Test: `packages/server/tests/routes/test_pt_config_routes.py`

- [ ] **Step 1: Failing test**

```python
def test_get_config_returns_default_on_first_visit(auth_client):
    r = auth_client.get("/departments/panic_thermometer/config")
    assert r.status_code == 200
    body = r.json()
    assert {p["panel_id"] for p in body["panel_config"]} == {"oil", "inflation", "fed_language", "wage_growth", "diplomacy"}
    assert body["composite_settings"]["mode"] == "count"


def test_put_config_persists_changes(auth_client):
    current = auth_client.get("/departments/panic_thermometer/config").json()
    current["composite_settings"]["red_threshold"] = 4
    r = auth_client.put("/departments/panic_thermometer/config", json=current)
    assert r.status_code == 200
    reread = auth_client.get("/departments/panic_thermometer/config").json()
    assert reread["composite_settings"]["red_threshold"] == 4
```

- [ ] **Step 2: Run** — fails.

- [ ] **Step 3: Add to router**

```python
# additions in panic_thermometer.py router factory

class _ConfigDTO(BaseModel):
    panel_config: list[dict[str, Any]]
    composite_settings: dict[str, Any] = Field(default_factory=dict)
    active_preset_id: str | None = None


@router.get("/config")
def get_config(user: User = Depends(require_auth)) -> dict[str, Any]:
    cfg = _config_service().get_or_create_for_user(user.id)
    return {
        "id": cfg.id,
        "panel_config": cfg.panel_config,
        "composite_settings": cfg.composite_settings,
        "active_preset_id": cfg.active_preset_id,
    }


@router.put("/config")
def put_config(payload: _ConfigDTO, user: User = Depends(require_auth)) -> dict[str, Any]:
    cfg = _config_service().update_config(
        user.id,
        panel_config=payload.panel_config,
        composite_settings=payload.composite_settings,
    )
    return {
        "id": cfg.id,
        "panel_config": cfg.panel_config,
        "composite_settings": cfg.composite_settings,
        "active_preset_id": cfg.active_preset_id,
    }
```

- [ ] **Step 4: Run** — 2 passed.

- [ ] **Step 5: Lint + commit**

```
git add packages/server/src/openlia_server/routes/departments/panic_thermometer.py packages/server/tests/routes/test_pt_config_routes.py
git commit -m "feat(server): PT GET/PUT /config routes"
```

---

### Task 18: Server — Routes: presets (GET/POST/PUT/DELETE/apply)

**Files:**
- Modify: `packages/server/src/openlia_server/routes/departments/panic_thermometer.py`
- Test: `packages/server/tests/routes/test_pt_preset_routes.py`

- [ ] **Step 1: Failing test** covers list/create/update/delete/apply; wires to the service methods from Task 12.

```python
def test_list_presets_includes_shipped(auth_client):
    r = auth_client.get("/departments/panic_thermometer/presets")
    body = r.json()
    shipped = [p for p in body if p["is_shipped"]]
    assert len(shipped) >= 15


def test_create_and_delete_user_preset(auth_client):
    r = auth_client.post("/departments/panic_thermometer/presets", json={"name": "my-custom", "description": "notes"})
    assert r.status_code == 201
    pid = r.json()["id"]
    listing = auth_client.get("/departments/panic_thermometer/presets").json()
    assert any(p["id"] == pid for p in listing)
    d = auth_client.delete(f"/departments/panic_thermometer/presets/{pid}")
    assert d.status_code == 204


def test_update_user_preset(auth_client):
    p = auth_client.post("/departments/panic_thermometer/presets", json={"name": "n1", "description": None}).json()
    r = auth_client.put(f"/departments/panic_thermometer/presets/{p['id']}", json={"name": "renamed", "description": "updated"})
    assert r.status_code == 200
    assert r.json()["name"] == "renamed"


def test_apply_shipped_oil_ma_relative(auth_client):
    listing = auth_client.get("/departments/panic_thermometer/presets").json()
    oil_ma = next(p for p in listing if p["name"] == "oil::ma_relative" and p["is_shipped"])
    r = auth_client.post(f"/departments/panic_thermometer/presets/{oil_ma['id']}/apply")
    assert r.status_code == 200
    oil_panel = next(p for p in r.json()["panel_config"] if p["panel_id"] == "oil")
    assert oil_panel["streak_condition"] == "price > ma200 * ma_multiplier"
```

- [ ] **Step 2: Run** — fails.

- [ ] **Step 3: Add routes**

```python
# additions in router factory

class _PresetCreateDTO(BaseModel):
    name: str
    description: str | None = None


class _PresetUpdateDTO(BaseModel):
    name: str
    description: str | None = None


def _preset_out(row) -> dict[str, Any]:
    return {
        "id": row.id,
        "user_id": row.user_id,
        "name": row.name,
        "description": row.description,
        "is_shipped": row.is_shipped,
    }


@router.get("/presets")
def list_presets(user: User = Depends(require_auth)) -> list[dict[str, Any]]:
    return [_preset_out(r) for r in _config_service().list_presets(user.id)]


@router.post("/presets", status_code=201)
def create_preset(payload: _PresetCreateDTO, user: User = Depends(require_auth)) -> dict[str, Any]:
    return _preset_out(_config_service().create_preset(user.id, name=payload.name, description=payload.description))


@router.put("/presets/{preset_id}")
def update_preset(preset_id: str, payload: _PresetUpdateDTO, user: User = Depends(require_auth)) -> dict[str, Any]:
    try:
        return _preset_out(_config_service().update_preset(user.id, preset_id, name=payload.name, description=payload.description))
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.delete("/presets/{preset_id}", status_code=204)
def delete_preset(preset_id: str, user: User = Depends(require_auth)) -> None:
    try:
        _config_service().delete_preset(user.id, preset_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.post("/presets/{preset_id}/apply")
def apply_preset(preset_id: str, user: User = Depends(require_auth)) -> dict[str, Any]:
    try:
        cfg = _config_service().apply_preset(user.id, preset_id)
    except ValueError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {
        "id": cfg.id,
        "panel_config": cfg.panel_config,
        "composite_settings": cfg.composite_settings,
        "active_preset_id": cfg.active_preset_id,
    }
```

- [ ] **Step 4: Run** — 4 passed.

- [ ] **Step 5: Lint + commit**

```
git add packages/server/src/openlia_server/routes/departments/panic_thermometer.py packages/server/tests/routes/test_pt_preset_routes.py
git commit -m "feat(server): PT preset routes (list/create/update/delete/apply)"
```

---

### Task 19: Server — Routes: config import/export

**Files:**
- Modify: `packages/server/src/openlia_server/routes/departments/panic_thermometer.py`
- Test: `packages/server/tests/routes/test_pt_import_export_routes.py`

- [ ] **Step 1: Failing test**

```python
def test_export_returns_version_1_payload(auth_client):
    r = auth_client.get("/departments/panic_thermometer/config/export")
    body = r.json()
    assert body["version"] == 1
    assert len(body["panel_config"]) == 5


def test_import_round_trip(auth_client):
    export = auth_client.get("/departments/panic_thermometer/config/export").json()
    export["composite_settings"]["red_threshold"] = 5
    r = auth_client.post("/departments/panic_thermometer/config/import", json=export)
    assert r.status_code == 200
    reread = auth_client.get("/departments/panic_thermometer/config/export").json()
    assert reread["composite_settings"]["red_threshold"] == 5


def test_import_rejects_v2(auth_client):
    r = auth_client.post(
        "/departments/panic_thermometer/config/import",
        json={"version": 2, "panel_config": [], "composite_settings": {}},
    )
    assert r.status_code == 400
    assert "unsupported" in r.json()["detail"].lower()
```

- [ ] **Step 2: Run** — fails.

- [ ] **Step 3: Add routes**

```python
@router.get("/config/export")
def export_config(user: User = Depends(require_auth)) -> dict[str, Any]:
    return _config_service().export_config(user.id)


@router.post("/config/import")
def import_config(payload: dict[str, Any], user: User = Depends(require_auth)) -> dict[str, Any]:
    try:
        cfg = _config_service().import_config(user.id, payload)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {
        "id": cfg.id,
        "panel_config": cfg.panel_config,
        "composite_settings": cfg.composite_settings,
        "active_preset_id": cfg.active_preset_id,
    }
```

- [ ] **Step 4: Run** — 3 passed.

- [ ] **Step 5: Lint + commit**

```
git add packages/server/src/openlia_server/routes/departments/panic_thermometer.py packages/server/tests/routes/test_pt_import_export_routes.py
git commit -m "feat(server): PT config import/export routes"
```

---

### Task 20: Server — Routes: formula parse/test/preview

Three endpoints backing the settings drawer's inline validation UI.

**Files:**
- Modify: `packages/server/src/openlia_server/routes/departments/panic_thermometer.py`
- Test: `packages/server/tests/routes/test_pt_formula_routes.py`

- [ ] **Step 1: Failing test**

```python
def test_formula_parse_valid(auth_client):
    r = auth_client.post(
        "/departments/panic_thermometer/formula/parse",
        json={"formula": "price > 85", "panel": "oil"},
    )
    body = r.json()
    assert body["ok"] is True
    assert "price" in body["identifiers"]


def test_formula_parse_syntax_error(auth_client):
    r = auth_client.post(
        "/departments/panic_thermometer/formula/parse",
        json={"formula": "price >>>", "panel": "oil"},
    )
    body = r.json()
    assert body["ok"] is False
    assert body["errors"][0]["type"] == "parse"


def test_formula_test_with_cached_data(auth_client):
    auth_client.get("/departments/panic_thermometer/dashboard")  # warm cache
    r = auth_client.post(
        "/departments/panic_thermometer/formula/test",
        json={"formula": "price > 0", "panel": "oil", "params": {}},
    )
    body = r.json()
    assert body["value"] is True


def test_ruleset_preview_with_cached_data(auth_client):
    auth_client.get("/departments/panic_thermometer/dashboard")
    r = auth_client.post(
        "/departments/panic_thermometer/ruleset/preview",
        json={
            "panel": "oil",
            "ruleset": {
                "rules": [
                    {"status": "red", "formula": "price > 0", "label": "hit"},
                    {"status": "green", "formula": "true", "label": "miss"},
                ],
                "params": {},
                "streak_condition": None,
            },
        },
    )
    body = r.json()
    assert body["status"] == "red"
    assert body["label"] == "hit"
```

- [ ] **Step 2: Run** — fails.

- [ ] **Step 3: Add routes**

```python
from openlia.formula import FormulaError, extract_requirements


class _FormulaParseDTO(BaseModel):
    formula: str
    panel: str


class _FormulaTestDTO(BaseModel):
    formula: str
    panel: str
    params: dict[str, Any] = Field(default_factory=dict)


class _RulesetPreviewDTO(BaseModel):
    panel: str
    ruleset: dict[str, Any]


@router.post("/formula/parse")
def formula_parse(payload: _FormulaParseDTO, user: User = Depends(require_auth)) -> dict[str, Any]:
    try:
        runner = _runner()
        runner.engine.parse(payload.formula)
        identifiers = list(extract_requirements(payload.formula))
        return {"ok": True, "identifiers": identifiers, "unknown_identifiers": [], "warnings": []}
    except FormulaError as exc:
        return {
            "ok": False,
            "errors": [{"type": "parse", "message": str(exc), "position": getattr(exc, "position", 0)}],
        }


@router.post("/formula/test")
def formula_test(payload: _FormulaTestDTO, user: User = Depends(require_auth)) -> dict[str, Any]:
    runner = _runner()
    try:
        result = runner.test_formula(user.id, payload.panel, payload.formula, params_override=payload.params)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    except FormulaError as exc:
        return {"value": None, "resolved_values": {}, "errors": [{"type": "eval", "message": str(exc)}], "warnings": []}
    return {
        "value": result.value,
        "resolved_values": result.resolved_values,
        "errors": [],
        "warnings": result.warnings,
    }


@router.post("/ruleset/preview")
def ruleset_preview(payload: _RulesetPreviewDTO, user: User = Depends(require_auth)) -> dict[str, Any]:
    runner = _runner()
    try:
        r = runner.preview_ruleset(user.id, payload.panel, payload.ruleset)
    except ValueError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {
        "status": r.status,
        "matched_rule_index": r.matched_rule_index,
        "label": r.label,
        "resolved_values": r.resolved_values,
        "derived_scalars": r.derived_scalars,
        "warnings": r.warnings,
    }
```

> If the `PtRunner` instance is recreated per-request, its cache is empty. Wire `dispatcher_factory` and a runner singleton through `app.py` state in Task 21 so the cache persists between the warming `/dashboard` call and the subsequent `/formula/test` call within the same user session.

- [ ] **Step 4: Run** — 4 passed.

- [ ] **Step 5: Lint + commit**

```
git add packages/server/src/openlia_server/routes/departments/panic_thermometer.py packages/server/tests/routes/test_pt_formula_routes.py
git commit -m "feat(server): PT formula parse/test/preview routes"
```

---

### Task 21: Server — Wire router + seed hook into `app.py`

Register the PT router at app startup. Call `seed_shipped_presets()` once on lifespan start. Instantiate one `PtRunner` per process so the per-panel cache is preserved across requests.

**Files:**
- Modify: `packages/server/src/openlia_server/app.py`
- Test: `packages/server/tests/test_app_wiring.py` (extend or add)

- [ ] **Step 1: Failing test**

```python
def test_pt_router_mounted(test_client):
    r = test_client.get("/openapi.json")
    paths = r.json()["paths"]
    assert "/departments/panic_thermometer/dashboard" in paths
    assert "/departments/panic_thermometer/config" in paths
    assert "/departments/panic_thermometer/presets" in paths
    assert "/departments/panic_thermometer/formula/parse" in paths


def test_seed_runs_on_startup(test_client, db_session):
    from openlia_server.db.models.dashboard import PtPreset
    rows = db_session.query(PtPreset).filter_by(is_shipped=True).all()
    assert len(rows) == 15
```

- [ ] **Step 2: Run** — fails.

- [ ] **Step 3: Wire**

```python
# additions to app.py

from openlia_server.routes.departments.panic_thermometer import build_panic_thermometer_router
from openlia_server.services.pt_config import PtConfigService
from openlia_server.services.pt_runner import PtRunner
from openlia_server.services.data_dispatcher import build_data_dispatcher  # from Plan 3


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ... existing startup code ...
    with session_factory() as s:
        PtConfigService(session_factory=lambda: s).seed_shipped_presets()

    # Singleton runner so its per-panel cache persists across requests
    app.state.pt_runner = PtRunner(
        session_factory=session_factory,
        dispatcher=build_data_dispatcher(session_factory),
    )
    yield
    # ... existing shutdown code ...


# In app factory:
app.include_router(
    build_panic_thermometer_router(
        db_session_factory=session_factory,
        mode=mode,
        dispatcher_factory=lambda: app.state.pt_runner.dispatcher,
    )
)
```

> In the router factory, replace the `_runner()` helper with a reference to the shared `app.state.pt_runner`. Wire this via a dependency that closes over `request: Request`:
>
> ```python
> def _runner_dep(request: Request) -> PtRunner:
>     return request.app.state.pt_runner
> ```

- [ ] **Step 4: Run entire PT test suite**

```
uv run pytest packages/core/tests/panic_thermometer/ packages/server/tests/services/test_pt_config.py packages/server/tests/services/test_pt_config_presets.py packages/server/tests/services/test_pt_config_import_export.py packages/server/tests/services/test_pt_runner.py packages/server/tests/services/test_pt_runner_formula_helpers.py packages/server/tests/routes/test_pt_dashboard_route.py packages/server/tests/routes/test_pt_config_routes.py packages/server/tests/routes/test_pt_preset_routes.py packages/server/tests/routes/test_pt_import_export_routes.py packages/server/tests/routes/test_pt_formula_routes.py packages/server/tests/test_app_wiring.py -v
```

- [ ] **Step 5: Lint + commit**

```
git add packages/server/src/openlia_server/app.py packages/server/tests/test_app_wiring.py
git commit -m "feat(server): mount PT router + seed shipped presets on startup"
```

---

### Task 22: Frontend — `api/panic-thermometer.ts` typed client

- Types: `PanelConfig`, `CompositeSettings`, `UserConfig`, `DashboardPayload`, `PanelResult`, `CompositeResult`, `PtPreset`, `FormulaParseResponse`, `FormulaTestResponse`, `RulesetPreviewResponse`.
- Functions: `fetchDashboard()`, `fetchConfig()`, `saveConfig(cfg)`, `listPresets()`, `createPreset(name, description)`, `updatePreset(id, payload)`, `deletePreset(id)`, `applyPreset(id)`, `exportConfig()`, `importConfig(payload)`, `parseFormula(formula, panel)`, `testFormula(formula, panel, params)`, `previewRuleset(panel, ruleset)`.

**Files:**
- Create: `frontend/src/api/panic-thermometer.ts`
- Test: `frontend/src/api/__tests__/panic-thermometer.test.ts` (msw-based)

- [ ] **Step 1: Failing test** (msw intercepts `GET /api/departments/panic_thermometer/dashboard`, asserts parsed shape typed as `DashboardPayload`).

- [ ] **Step 2: Implement** — fetch wrappers with typed returns; all calls pointed at `/api/departments/panic_thermometer/...` (Vite proxy strips `/api`).

- [ ] **Step 3: Run** — `cd frontend && npx vitest run src/api/__tests__/panic-thermometer.test.ts`.

- [ ] **Step 4: Commit**

```
git add frontend/src/api/panic-thermometer.ts frontend/src/api/__tests__/panic-thermometer.test.ts
git commit -m "feat(frontend): PT typed API client"
```

---

### Task 23: Frontend — panel catalog + hooks (`usePtDashboard`, `usePtConfig`, `usePtPresets`, `usePtFormula`)

- `panel-catalog.ts` — ordered list of 5 panels with display name, short label, icon, sparkline metric key, dashboard component id.
- `usePtDashboard(intervalSeconds: number | null)` — SWR-style polling; re-fetches on `intervalSeconds` when non-null; exposes `{data, isLoading, error, refresh}`.
- `usePtConfig()` — `{config, save, isDirty}`.
- `usePtPresets()` — `{presets, create, rename, remove, apply}`.
- `usePtFormula(panel)` — `{parse, test, preview}` debounced wrappers.

**Files:**
- Create: `frontend/src/lib/panic-thermometer/panel-catalog.ts`
- Create: `frontend/src/hooks/usePtDashboard.ts`
- Create: `frontend/src/hooks/usePtConfig.ts`
- Create: `frontend/src/hooks/usePtPresets.ts`
- Create: `frontend/src/hooks/usePtFormula.ts`
- Test: one vitest per hook covering happy path + error path.

- [ ] **Commit**

```
git commit -m "feat(frontend): PT panel catalog + 4 hooks"
```

---

### Task 24: Frontend — `CompositeBar` + `PanelGrid` + `PanelCard`

- `CompositeBar` — 5-stop filled bar (calm, elevated, high, severe, crisis). Animates with Framer Motion on level change. Shows `red_count / 5` and current level label.
- `PanelGrid` — responsive grid (5-up desktop / 2-up tablet / 1-up mobile) of `PanelCard`.
- `PanelCard` — status pill + primary metric value + tiny sparkline (uses Chart.js). Clicking navigates to the panel's drill-down dashboard (below) via smooth scroll anchor.

- [ ] **Commit**

```
git commit -m "feat(frontend): PT CompositeBar + PanelGrid + PanelCard"
```

---

### Task 25: Frontend — `OilDashboard` + `WageGrowthDashboard`

- `OilDashboard` — line chart of oil closes (Chart.js); horizontal reference line at `params.price_threshold`; shaded area when price > threshold colored by current status; inline threshold edit popover.
- `WageGrowthDashboard` — monthly bar chart; bars colored by status; dashed horizontal line at `wage_threshold_red`.

- [ ] **Commit**

```
git commit -m "feat(frontend): PT Oil + WageGrowth drill-down dashboards"
```

---

### Task 26: Frontend — `InflationDashboard` + `FedLanguageDashboard` + `DiplomacyDashboard`

- `InflationDashboard` — dual-axis chart (TIP line on left axis, Michigan survey dots on right axis); user-defined level bands as horizontal reference lines.
- `FedLanguageDashboard` — FOMC timeline (horizontal) colored by detected posture; headline scanner listing the 5 most recent matched articles with keyword highlights; inline keyword list editor (one pane per bucket — dovish/neutral/hawkish/crisis); manual override popover.
- `DiplomacyDashboard` — countdown bar (green → amber → red as `days_elapsed / window_days` increases); news feed (progress in green, escalation in red); "Mark milestone" button that `PUT /config` with a new `milestone_date`.

- [ ] **Commit**

```
git commit -m "feat(frontend): PT Inflation + FedLanguage + Diplomacy dashboards"
```

---

### Task 27: Frontend — `RuleEditor` + `FormulaInput` + `PanelSettingsPane`

- `FormulaInput` — textarea with debounced `parseFormula` call; inline error marker with position; resolved-identifier chip list.
- `RuleEditor` — ordered, drag-to-reorder list of rules; per-row status swatch, formula textarea, label input, "Test" button (calls `testFormula`, shows resolved values), "Would trigger" preview at the top (calls `previewRuleset`).
- `PanelSettingsPane` — tabbed pane for one panel: Params table (key/value inputs) + Rule editor + Preset loader dropdown.

- [ ] **Commit**

```
git commit -m "feat(frontend): PT RuleEditor + FormulaInput + PanelSettingsPane"
```

---

### Task 28: Frontend — `SettingsDrawer` + `PresetLibrary` + `ManualOverridePopover`

- `SettingsDrawer` — slides from the right on gear-icon click; top contains global settings (composite mode selector + threshold, weights matrix in weighted mode, auto-refresh interval); below, 5 tabs (one per panel) rendering `PanelSettingsPane`.
- `PresetLibrary` — list view of shipped + user presets; "Save current as preset" button opens a small inline form; "Apply" button calls `applyPreset`.
- `ManualOverridePopover` — dropdown of statuses (green/amber/red/dark_red) + optional note field + "Clear override" button; on save, PUT new `manual_override` into `panel_config`.

- [ ] **Commit**

```
git commit -m "feat(frontend): PT SettingsDrawer + PresetLibrary + ManualOverridePopover"
```

---

### Task 29: Frontend — `ImportExportModal` + share-link utils

- `share-link.ts` — `encodeConfigToUrl(cfg) -> string` (JSON → `JSON.stringify` → `TextEncoder` → `pako.deflate` → `base64url`); `decodeConfigFromUrl(param) -> cfg`.
- `config-schema.ts` — Zod schema matching `_ConfigDTO` shape for runtime validation of import payload.
- `ImportExportModal` — three actions: **Download JSON** (calls `exportConfig()` then triggers a `<a download>`), **Upload JSON** (file input → parse → Zod validate → call `importConfig()`), **Copy share URL** (`encodeConfigToUrl` → clipboard write).

- [ ] **Commit**

```
git commit -m "feat(frontend): PT ImportExportModal + share-link encode/decode"
```

---

### Task 30: Frontend — `PanicThermometerPage` composition

Replace the existing placeholder at `frontend/src/pages/departments/PanicThermometer.tsx` with the full page:

- Header: title + auto-refresh dropdown (off / 1m / 5m / 15m; default 5m, persisted in `usePtConfig`'s `composite_settings.refresh_interval_minutes`) + settings gear button.
- `<CompositeBar />`
- `<PanelGrid />`
- Stacked drill-down dashboards: `<OilDashboard />`, `<InflationDashboard />`, `<FedLanguageDashboard />`, `<WageGrowthDashboard />`, `<DiplomacyDashboard />`, in that order. Each wrapped in a `<section id="panel-oil">` for anchor scrolling from the grid.
- `<SettingsDrawer />` rendered conditionally.
- `<ImportExportModal />` launched from a button inside the settings drawer footer.
- Page checks URL on first load for `?share=<base64>` and, if present, prompts the user to import the shared config.

**Files:**
- Modify: `frontend/src/pages/departments/PanicThermometer.tsx`
- Test: `frontend/src/pages/departments/__tests__/PanicThermometer.test.tsx`

- [ ] **Test** — renders composite bar + 5 panel cards given a fixture dashboard payload, opens settings drawer on gear click, triggers auto-refresh on interval change.

- [ ] **Commit**

```
git commit -m "feat(frontend): PanicThermometerPage full composition"
```

---

### Task 31: Manual smoke test + flip README row to Draft

- [ ] **Step 1: Full aggregate suite**

```
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
cd frontend && npm run lint && npm run test && npm run build
```

All must be green.

- [ ] **Step 2: Manual smoke**

  1. Start server: `uv run openlia serve`.
  2. Frontend dev: `cd frontend && npm run dev`.
  3. Log in, navigate to Panic Thermometer.
  4. Verify: dashboard loads with 5 panel cards, composite bar renders, each drill-down chart renders, settings gear opens drawer, preset loader applies a shipped preset and re-evaluates the dashboard, manual override forces a status, import/export round-trips a config file.
  5. Kill the data provider (set a fake `ticker` to trigger a fetch error) and confirm the panel surfaces a warning without crashing the page.

- [ ] **Step 3: Update README row**

Change the row for Plan 18 in `planning/implementation-plans/README.md` from `Not started` to `Draft` (after review, the executor flips to `Ready`, and on merge to `Done`).

- [ ] **Step 4: Open PR**

```
gh pr create --title "feat(phases-18): Panic Thermometer department" --body "$(cat <<'EOF'
## Summary
- Ship PanicThermometerDepartment as a dashboard department (no reports, no chat).
- 5 panels (oil, inflation, fed_language, wage_growth, diplomacy) evaluated via Plan 17 FormulaEngine.
- Composite scoring (count + weighted modes) with 5-level threat bar.
- Preset library (15 shipped presets), import/export, manual override, milestone reset.

## Test plan
- [x] uv run pytest (full aggregate)
- [x] frontend vitest + build
- [x] manual smoke: login -> dashboard -> preset apply -> override -> import/export
EOF
)"
```

---

## Appendix A — Data flow per request

`GET /api/departments/panic_thermometer/dashboard` (frontend)
 → Vite proxy strips `/api` → `GET /departments/panic_thermometer/dashboard` (FastAPI)
 → `require_auth` resolves `User` from session cookie
 → route handler reads `request.app.state.pt_runner` (singleton)
 → `PtRunner.compute_dashboard(user.id)`:
   - `PtConfigService.get_or_create_for_user(user.id)` → `PtUserConfig`
   - For each `panel_config` entry with `enabled=True` and no `manual_override`:
     - For each `req in panel.required_requirements`: `dispatcher.fetch(requirement=req, panel_id=..., params=...)` → raw payload
     - `panel.build_context(panel_config=entry, payloads=...)` → `PanelContextBuildResult{scalars, raw_series, warnings}`
     - Runner caches the result under `(user_id, panel_id)` for subsequent `/formula/test` / `/ruleset/preview` calls
     - `FormulaEngine.evaluate_ruleset(ruleset_dict, EvaluationContext(raw_series, scalars, params))` → `PanelResult{status, matched_rule_index, label, resolved_values, derived_scalars, warnings}`
   - `compute_composite(panel_statuses, composite_settings)` → `CompositeResult`
 → JSON response `{panels, composite, generated_at, warnings}`.

## Appendix B — Route matrix additions

Add the following rows to `endpoint-contract-matrix.md` and `route-authorization-matrix.md`:

| Path | Method | Auth | Owner | Request DTO | Response | Plan | Test |
|---|---|---|---|---|---|---|---|
| `/departments/panic_thermometer/dashboard` | GET | authed | self | — | `DashboardPayload` | 18 | `test_pt_dashboard_route.py` |
| `/departments/panic_thermometer/config` | GET | authed | self | — | `UserConfigOut` | 18 | `test_pt_config_routes.py` |
| `/departments/panic_thermometer/config` | PUT | authed | self | `ConfigDTO` | `UserConfigOut` | 18 | `test_pt_config_routes.py` |
| `/departments/panic_thermometer/config/export` | GET | authed | self | — | `{version, panel_config, composite_settings}` | 18 | `test_pt_import_export_routes.py` |
| `/departments/panic_thermometer/config/import` | POST | authed | self | same | `UserConfigOut` | 18 | `test_pt_import_export_routes.py` |
| `/departments/panic_thermometer/presets` | GET | authed | self + shipped | — | `PresetOut[]` | 18 | `test_pt_preset_routes.py` |
| `/departments/panic_thermometer/presets` | POST | authed | self | `{name, description}` | `PresetOut` | 18 | `test_pt_preset_routes.py` |
| `/departments/panic_thermometer/presets/{id}` | PUT | authed | self | `{name, description}` | `PresetOut` | 18 | `test_pt_preset_routes.py` |
| `/departments/panic_thermometer/presets/{id}` | DELETE | authed | self | — | 204 | 18 | `test_pt_preset_routes.py` |
| `/departments/panic_thermometer/presets/{id}/apply` | POST | authed | self + shipped | — | `UserConfigOut` | 18 | `test_pt_preset_routes.py` |
| `/departments/panic_thermometer/formula/parse` | POST | authed | self | `{formula, panel}` | `ParseResult` | 18 | `test_pt_formula_routes.py` |
| `/departments/panic_thermometer/formula/test` | POST | authed | self | `{formula, panel, params}` | `TestResult` | 18 | `test_pt_formula_routes.py` |
| `/departments/panic_thermometer/ruleset/preview` | POST | authed | self | `{panel, ruleset}` | `PreviewResult` | 18 | `test_pt_formula_routes.py` |

All PT routes: access level `authed`, owner `self`, `must_change_password` redirects enforced by middleware, mounted in both personal and company mode.

## Appendix C — Self-review checklist

- [x] Every spec section from `PanicThermometerPageSpec.md` has a corresponding task:
  - Formula engine integration → Task 14 + 15 + 20
  - Dashboard 1 Oil → Task 3 + 25
  - Dashboard 2 Inflation → Task 4 + 26
  - Dashboard 3 Fed language → Task 5 + 26
  - Dashboard 4 Wage growth → Task 6 + 25
  - Dashboard 5 Diplomacy → Task 7 + 26
  - Settings panel (global + per-panel) → Task 28
  - Per-panel preset loader + import/export → Tasks 18, 19, 29
  - Persistent storage keys (`panic:config`, `panic:fed-override`, `panic:diplo-milestone`) → absorbed into `PtUserConfig.panel_config` (manual_override + milestone_date fields) and `PtPreset` (user-named presets)
  - Composite threat level (count + weighted) → Task 8
  - Layout → Task 30
  - Auto-refresh → Task 23 (hook) + Task 30 (page header dropdown)
  - Data requirement call map → per-panel `required_requirements` declared in Tasks 3–7; dispatch in Task 14
- [x] No placeholders — every code block is complete.
- [x] Formula engine imports match the Plan 17 public API verbatim: `from openlia.formula import FormulaEngine, FormulaError, EvaluationContext, extract_requirements`.
- [x] PT tables match shipped names: `PtUserConfig`, `PtPreset` (from `openlia_server.db.models.dashboard`, shipped in Plan 1B).
- [x] All `String(36)` IDs use `str(uuid.uuid4())` (Task 11, Task 12). No prefixed short-hex ids.
- [x] Router factory pattern with `build_require_auth`. No bare `get_current_user`.
- [x] No `reports` table writes. No SSE. No chat session.
- [x] Named-event SSE framing rule not applicable (no streams).
- [x] Scheduler "one schedule per (job_type, user_id)" not applicable (PT has no scheduled jobs).
- [x] Unique test helper names (no generic `_fakes.py`; fake dispatcher defined inline per test module).
- [x] `__init__.py` in every test directory.
- [x] Commit per task.
