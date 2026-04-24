# Phase 18 — Panic Thermometer fix plan (→ 100%)


**Current:** ~72% shipped. **Root cause:** DEFERRED + IMPLEMENTER.

**Gap summary:** Five drill-down dashboards, `PanelDashboard` frame, `RuleEditor`/`FormulaInput`/`PanelSettingsPane`/`ManualOverridePopover`/`ImportExportModal`/`PresetLibrary` UI deferred or stubbed; panel context builders missing derived-scalar wiring; route-layer test suite and per-panel core tests for Inflation/FedLanguage/WageGrowth/Diplomacy absent.

**Tasks (in execution order):**

1. **P1-10 — Panel context builders populate derived scalars** (depends on Phase 17 NEW-17-03).
   - Files: `panels/oil.py`, `inflation.py`, `wage_growth.py` — switch to `EvaluationContext.from_raw_series(...)`.
   - Acceptance: MA-relative preset evaluates red correctly against synthetic `price > ma200 * 1.2` history.

2. **NEW-18-01 — Ship `OilDashboard` + `WageGrowthDashboard` drill-downs (chart-based panels).**
   - Files: create `frontend/src/components/panic-thermometer/OilDashboard.tsx` (Chart.js line chart + threshold line from `panel_config.params.price_threshold`); `WageGrowthDashboard.tsx` (monthly bar chart + threshold line).
   - Spec ref: PanicThermometerPageSpec drill-down sections.
   - Acceptance: clicking Oil panel card opens drill-down with live chart.

3. **NEW-18-02 — Ship `InflationDashboard` + `FedLanguageDashboard` + `DiplomacyDashboard`.**
   - Files: `InflationDashboard.tsx` (dual-axis: TIP price + Michigan 5y survey); `FedLanguageDashboard.tsx` (timeline + headline scanner + editable keyword lists); `DiplomacyDashboard.tsx` (countdown bar + news feed + "Mark milestone" button).
   - Acceptance: each renders; diplomacy milestone button round-trips to `PtUserConfig.panel_config[i].milestone_date`.

4. **NEW-18-03 — Ship `RuleEditor` + `FormulaInput` + `PanelSettingsPane`.**
   - Files: `RuleEditor.tsx` (ordered `Rule[]` list + reorder handles + add/delete); `FormulaInput.tsx` (debounced `POST /formula/parse` + inline error); `PanelSettingsPane.tsx` (params table + rule editor + preset loader).
   - Spec ref: PanicThermometerPageSpec "Settings drawer / per-panel tab".
   - Acceptance: editing rule condition shows parse error inline within 300ms.

5. **NEW-18-04 — Ship `ManualOverridePopover` + `ImportExportModal` + flesh out `PresetLibrary`.**
   - Files: `ManualOverridePopover.tsx` (sets `panel_config[i].manual_override`); `ImportExportModal.tsx` (upload/download JSON / copy base64 share URL via `lib/panic-thermometer/share-link.ts`); extend `PresetLibrary.tsx` for save/delete user presets.
   - Acceptance: export → delete config → import round-trip produces byte-identical config.

6. **NEW-18-05 — Add server test suite + per-panel tests.**
   - Files: `packages/server/tests/test_panic_thermometer/test_pt_routes.py`, `test_pt_runner.py`, `test_pt_config.py`; `packages/core/tests/panic_thermometer/panels/test_inflation_panel.py`, `test_fed_language_panel.py`, `test_wage_growth_panel.py`, `test_diplomacy_panel.py`.
   - Acceptance: `uv run pytest packages/server/tests/test_panic_thermometer packages/core/tests/panic_thermometer -v` green.

7. **NEW-18-06 — Frontend auto-refresh dropdown wiring check.**
   - Files: `PanicThermometer.tsx` — verify header hosts auto-refresh select (off / 1m / 5m / 15m default 5m); `usePtDashboard` polls on interval.
   - Acceptance: selecting "1m" triggers `GET /dashboard` every 60s.

**Verification:** `uv run pytest packages/server/tests/test_panic_thermometer packages/core/tests/panic_thermometer && cd frontend && npm run test -- panic-thermometer`; manual: open PT, five cards green, drill down, edit broken rule → inline error, export/import round-trip OK.
