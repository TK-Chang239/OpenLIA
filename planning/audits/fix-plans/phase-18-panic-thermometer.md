# Phase 18 — Panic Thermometer fix plan (→ 100%)

**Current:** ~72% shipped. **Root cause:** DEFERRED + IMPLEMENTER + SPEC_DRIFT.

**Gap summary.** Backend orchestrator, formula wiring, route surface, and
DB tables shipped (`pt_runner.py`, `routes/departments/panic_thermometer.py`,
`db/models/dashboard.py`, migration `2026-04-17-1200`). All five core
panel context-builders ship as well (`panels/oil.py`, `inflation.py`,
`fed_language.py`, `wage_growth.py`, `diplomacy.py`). What is missing
spans three buckets:

1. **Frontend drill-downs and rule editor.** `PanicThermometer.tsx` is
   a header + composite bar + 5 metric-card grid + settings drawer. The
   five chart-based drill-down dashboards (Oil line chart, Inflation
   dual-axis, Fed timeline+keyword scanner, Wage bar chart, Diplomacy
   countdown+news feed) are absent. `RuleEditor`, `FormulaInput`,
   `PanelSettingsPane`, `ManualOverridePopover`, `ImportExportModal`,
   and `PanelDashboard` frame are all unimplemented (the drawer only
   shows preset list + composite-mode label + Export/Import buttons —
   no params table, no rule list, no manual-override UI).
2. **Spec-drift on derived scalars.** Both `OilPanel.build_context`
   (returns `{"price","prev_close"}` only) and `InflationPanel`
   (returns `michigan_5y`, `tip_price_latest`, `price`, `prev_close`)
   omit the spec-mandated derived scalars `ma20/ma50/ma100/ma200`,
   `price_vs_ma200`, `ma50_vs_ma200`, `atr_14`, `std_20`, `high_52w`,
   `low_52w`, `pct_from_high`, `pct_from_low`. `presets.py` ships
   `_oil_ma_relative` and `_oil_volatility_adjusted` referencing
   `ma200`, `atr_14`, `ma_multiplier`, `atr_multiplier` — these
   identifiers resolve nowhere, so applying either preset produces a
   `FormulaError("undefined identifier 'ma200'")` per Phase 17's
   parser semantics, which the runner converts to "Configuration
   error / disabled" — silent breakage of two of three shipped preset
   modes the moment a real dispatcher is wired (P1-10 today; bigger
   than that flag suggests).
3. **Trigger / notification log + auto-refresh wiring.** No
   `pt_trigger_events` table, no notification firing on composite
   level transitions. The plan's "Phase 4 — Alerts" deliverable was
   skipped. `usePtDashboard` polls but the composite bar has no
   transition detector and the user never gets notified when status
   moves from `calm → severe`.

Server tests **do exist**: `test_pt_runner.py` (134 LoC),
`test_pt_config.py` (68), `test_pt_config_presets.py`,
`test_pt_config_import_export.py`, `test_pt_runner_formula_helpers.py`,
and HTTP suite `test_routes/departments/test_panic_thermometer.py`
(262). The master tracker §5 row for Phase 18 is **stale** — those
files landed with PR #33 (memory observation 809) and PR #36 (memory
observation 777). The remaining real test gap is per-panel core-side
unit tests (`panels/test_*.py` directory does not exist) and all
frontend vitests for PT.

**Tasks (in execution order):**

1. **NEW-18-01 — Add MA / ATR / 52w derived scalars to `OilPanel.build_context`.**
   - File: `packages/core/src/openlia/panic_thermometer/panels/oil.py`.
   - Compute from the `closes/highs/lows` arrays already extracted: `ma20`,
     `ma50`, `ma100`, `ma200` (simple averages of trailing window;
     `None` if insufficient bars), `price_vs_ma200 = price / ma200`,
     `ma50_vs_ma200 = ma50 / ma200`, `atr_14` (Wilder/SMA over true
     range), `std_20` (std of pct-returns), `high_52w = max(closes[-252:])`,
     `low_52w = min(closes[-252:])`, `pct_from_high = (price-high_52w)/high_52w`,
     `pct_from_low = (price-low_52w)/low_52w`. Inject into `scalars`.
   - Plan ref: PT spec "Data context" + Phase 17 plan task NEW-17-03
     (`from_raw_series` lifecycle).
   - Acceptance: applying `_oil_ma_relative` preset against synthetic
     history evaluates `price > ma200 * ma_multiplier` to a real bool,
     not a FormulaError; new core test
     `panels/test_oil_panel.py::test_ma_relative_preset_evaluates`.
   - Closes: master-tracker P1-10 (Oil portion).

2. **NEW-18-02 — Add MA scalars to `InflationPanel.build_context`.**
   - File: `packages/core/src/openlia/panic_thermometer/panels/inflation.py`.
   - Compute on the TIP `closes` series: `ma200`, `tip_ma200`,
     `tip_ma50`, `pct_from_high`. Inject into `scalars` so
     `_inflation_pure_tip` preset (which references `ma200`)
     evaluates without FormulaError.
   - Acceptance: `panels/test_inflation_panel.py::test_pure_tip_preset_evaluates`;
     resolves `tip_price_latest > ma200 and pct_change(tip_price, 30) > 0.02`.
   - Closes: master-tracker P1-10 (Inflation portion).

3. **NEW-18-03 — Streak backtest correctness for MA-relative streaks.**
   - File: `packages/server/src/openlia_server/services/pt_runner.py`
     (`_compute_streak_days`).
   - Today the loop replaces `local_scalars["price"]` with each trailing
     close but does **not** recompute MA / ATR scalars per bar. So
     `_oil_ma_relative.streak_condition = "price > ma200 * ma_multiplier"`
     compares each historical price against today's `ma200`, not the
     `ma200` as-of that bar. The streak is therefore biased.
   - Fix: when streak condition references any of `{ma20,ma50,ma100,ma200,
     atr_14,std_20,high_52w,low_52w}`, recompute that scalar over the
     trailing slice ending at the current backtest index.
   - Acceptance: synthetic series where price stays flat but MA rises
     produces shrinking streak as backtest walks back; covered by
     `test_pt_runner.py::test_streak_recomputes_ma_per_bar`.

4. **NEW-18-04 — Persist composite-level transitions + emit notifications.**
   - Files: new model `db/models/dashboard.py` `PtTriggerEvent` (id,
     user_id, level_from, level_to, occurred_at, payload_json), new
     migration `db/migrations/versions/2026-04-25-XXXX_pt_trigger_events.py`,
     `services/pt_runner.py.compute_dashboard` records a row when the
     newly-computed `composite.level` differs from the most recent
     persisted level for that user. Wire to `notifications` service so
     a `panic_thermometer.level_change` event fires.
   - Plan ref: PT spec "Phase 4 — Alerts" + master tracker §10 Phase
     18 entry "trigger event log".
   - Acceptance: `test_pt_runner.py::test_level_transition_inserts_trigger_event`
     + `::test_no_event_when_level_unchanged`.

5. **NEW-18-05 — Ship `OilDashboard` drill-down.**
   - File: create `frontend/src/components/panic-thermometer/OilDashboard.tsx`.
   - Chart.js line chart of `raw_series.price`, threshold reference
     line read from `panel_config.params.price_threshold` (or computed
     from `ma200` when params include `ma_multiplier`). Region above
     threshold shaded by current status color from `STATUS_COLORS`.
     Metric card above chart: streak days + price + status pill.
   - Spec ref: PanicThermometerPageSpec "Dashboard 1 — Oil price duration".
   - Acceptance: vitest renders chart with threshold line; clicking
     Oil panel card scrolls to `#panel-oil-dashboard` section instead
     of just a card scroll.

6. **NEW-18-06 — Ship `InflationDashboard`, `WageGrowthDashboard`,
   `FedLanguageDashboard`, `DiplomacyDashboard` drill-downs.**
   - Files (all new under `frontend/src/components/panic-thermometer/`):
     - `InflationDashboard.tsx` — dual-axis (TIP price line + Michigan
       survey points), level bands as horizontal references on right
       axis.
     - `WageGrowthDashboard.tsx` — monthly bar chart colored by
       per-bar status, dashed threshold line, "consecutive count"
       badge.
     - `FedLanguageDashboard.tsx` — FOMC timeline (dots colored by
       posture per event), top-5 headline scanner with matched phrase
       highlighted in status color, four editable keyword textareas
       (dovish / neutral / hawkish / crisis), inline manual-override
       toggle.
     - `DiplomacyDashboard.tsx` — countdown progress bar (green →
       amber → red gradient driven by `days_remaining/window_days`),
       last-10 news feed with progress vs escalation hits highlighted
       in opposite colors, "Mark milestone" button that PUTs
       `panel_config[i].milestone_date = today` via `saveConfig`.
   - Spec ref: PanicThermometerPageSpec dashboards 2–5 sections.
   - Acceptance: each component renders against a fixture
     `DashboardPayload`; diplomacy "Mark milestone" round-trips and
     refetches dashboard.

7. **NEW-18-07 — Ship `PanelSettingsPane` + `RuleEditor` +
   `FormulaInput`.**
   - Files (all new under `frontend/src/components/panic-thermometer/`):
     - `PanelSettingsPane.tsx` — for each `PanelConfig`: params
       key/value table with inline edit, rule editor, preset loader
       row, manual-override popover trigger, "Test" button that calls
       `previewRuleset` and renders `status` + `matched_rule_index` +
       `resolved_values`.
     - `RuleEditor.tsx` — ordered `Rule[]` list with reorder
       (`button` arrows, no DnD lib), add/delete, status dropdown,
       inline label edit, `FormulaInput` for the condition.
     - `FormulaInput.tsx` — debounced (300ms) `parseFormula(panel,
       formula)` call; renders inline error message + position when
       `ok=false`; renders identifier chips when `ok=true`,
       cross-referencing `cached.scalars` keys to flag unknown ones
       red.
   - Wire all three into `SettingsDrawer.tsx` replacing the current
     "Composite mode: count" stub line; expose one accordion per panel.
   - Spec ref: PanicThermometerPageSpec "Settings panel" + "Formula
     engine implementation notes / Validation".
   - Acceptance: vitest `RuleEditor.test.tsx::edits_persist_via_saveConfig`
     and `FormulaInput.test.tsx::shows_parse_error_within_300ms`.

8. **NEW-18-08 — Ship `ManualOverridePopover` + `ImportExportModal` +
   user-preset CRUD UI.**
   - Files: `ManualOverridePopover.tsx` (radio for status × text note;
     PUTs `panel_config[i].manual_override = {status, note, set_at}`),
     `ImportExportModal.tsx` (file picker + JSON textarea + "Copy
     share link" button generating base64 query param via new
     `frontend/src/lib/panic-thermometer/share-link.ts`). Extend
     `PresetLibrary.tsx` with "Save current as preset" form (calls
     `createPreset`) and rename via `updatePreset`.
   - Acceptance: export → mutate config → import round-trip restores
     byte-identical config; share-link parser hydrates URL on mount.

9. **NEW-18-09 — Ship `PanelDashboard` frame + global page composition.**
   - File: `frontend/src/components/panic-thermometer/PanelDashboard.tsx`.
   - Wraps a drill-down child with title, "last updated" timestamp,
     warnings details, and a per-panel settings gear that opens the
     drawer scrolled to that panel's section.
   - Update `pages/departments/PanicThermometer.tsx` to render five
     `PanelDashboard` instances under the `PanelGrid`, replacing the
     "scroll to nothing" `onPanelClick` handler.
   - Acceptance: page now contains five `<section data-testid="pt-drilldown-${id}">`
     elements; smoke vitest asserts presence.

10. **NEW-18-10 — Per-panel core unit tests.**
    - Files (all new under
      `packages/core/tests/panic_thermometer/panels/`):
      - `test_oil_panel.py` — derived scalars math (NEW-18-01),
        ma_relative streak (NEW-18-03), no-history graceful warning.
      - `test_inflation_panel.py` — survey vs missing-survey
        branches, michigan_5y_missing flag, derived TIP MAs.
      - `test_fed_language_panel.py` — keyword precedence (crisis
        wins over hawkish), `days_since_fomc` parsing, no-FOMC
        warning surface.
      - `test_wage_growth_panel.py` — `consecutive_count` reset on
        below-threshold print, `avg_12m` calc, `cpi_mom` extraction
        with mixed CPI / Core CPI events.
      - `test_diplomacy_panel.py` — milestone_date defaulting to
        today when null/unparseable, escalation override of progress.
    - Acceptance: `uv run pytest packages/core/tests/panic_thermometer/panels`
      green.

11. **NEW-18-11 — Frontend vitests.**
    - Files: `frontend/src/__tests__/panic-thermometer/`
      - `PanicThermometer.test.tsx` — composite bar, refresh
        select, drill-down sections present.
      - `RuleEditor.test.tsx` — reorder, add, delete, parse-error
        surface.
      - `FormulaInput.test.tsx` — debounce + parseFormula call shape.
      - `OilDashboard.test.tsx` — threshold reference line drawn
        from params.price_threshold.
      - `DiplomacyDashboard.test.tsx` — Mark-milestone PUT shape.
      - `PresetLibrary.test.tsx` — apply / delete / save-as paths.
      - `ImportExportModal.test.tsx` — round-trip.
    - Acceptance: `cd frontend && npm run test -- panic-thermometer`
      green.

12. **NEW-18-12 — Server route-test coverage for new endpoints.**
    - File: extend
      `packages/server/tests/test_routes/departments/test_panic_thermometer.py`.
    - Add cases (current suite already covers `/dashboard`,
      `/config`, `/presets/*`, `/formula/parse`, `/formula/test`,
      `/ruleset/preview`):
      - `/config/import` rejects malformed payload with 400.
      - `/config/export` round-trips via `/config/import`.
      - `/presets/{id}/apply` with non-existent id → 404.
      - `/presets/{id}` PUT/DELETE on shipped preset → 403 or 409
        (per `pt_config.update_preset` raising `ValueError`; pick one
        contract and document; today it raises 404 — verify intent).
      - `/formula/test` returns 409 when no cached panel inputs.
    - Acceptance: `uv run pytest packages/server/tests/test_routes/departments/test_panic_thermometer.py`
      green at +5 cases.

13. **NEW-18-13 — Migration + model for `pt_trigger_events`.**
    - Files: `db/models/dashboard.py` adds `PtTriggerEvent`, new
      migration `2026-04-25-XXXX_pt_trigger_events.py`. Update
      `tests/test_migrations.py::EXPECTED_TABLES` set.
    - Acceptance: `uv run alembic upgrade head` clean against
      Postgres + SQLite; migrations test green.

14. **NEW-18-14 — Master-tracker §5 stale-row correction (doc-only).**
    - File: `planning/audits/2026-04-24-master-completeness-and-repair-tracker.md`
      §5 line 448–450.
    - Replace "Phase 18 — `test_pt_routes.py`, `test_pt_runner.py`,
      `test_pt_config.py`, per-panel core tests for InflationPanel,
      FedLanguagePanel, WageGrowthPanel, DiplomacyPanel" with: "Phase
      18 — per-panel core tests (`packages/core/tests/panic_thermometer/panels/`),
      all PT frontend vitests. (Server route + service tests already
      shipped via PR #33 / PR #36 — observation 809, 777.)"
    - Acceptance: doc PR.

15. **NEW-18-15 — Spec-drift reconciliation: rules schema field
    name.**
    - The spec uses `condition` interchangeably with `formula` (e.g.
      "edit the rule condition"). Codebase + DTO + Pydantic models +
      DB JSON use `formula`. Pin the contract to `formula` in the
      spec and grep-update planning docs.
    - File: `planning/specs/pages/departments/PanicThermometerPageSpec.md`.
    - Acceptance: `grep -n "rule.condition\| condition " planning/specs/pages/departments/PanicThermometerPageSpec.md`
      returns no rule-shape mentions.

16. **NEW-18-16 — Color threshold token check.**
    - The spec maps `dark_red → "dark red"` for crisis level. Frontend
      `PanelCard.tsx` STATUS_COLORS maps `dark_red →
      var(--color-border-error)` (a border token, not a fill). Map
      `dark_red` to a dedicated `--color-feedback-error-strong` (or
      whichever token Phase 8 chose) and add it to the design tokens
      file if absent.
    - Acceptance: visual snapshot + token presence assertion.

**Verification:**
```
uv run pytest packages/server/tests/services/test_pt_runner.py \
              packages/server/tests/test_routes/departments/test_panic_thermometer.py \
              packages/core/tests/panic_thermometer/panels && \
cd frontend && npm run test -- panic-thermometer && \
uv run alembic upgrade head
```
Manual: open PT page, five cards green; click Oil → drill-down chart
with threshold line; open settings → edit a rule formula to junk →
inline error within 300ms; apply `_oil_ma_relative` preset → no
FormulaError; mark diplomacy milestone → days_elapsed resets;
export → re-import → byte-identical config; force composite
transition (set 2 manual overrides to red) → trigger event row +
notification.
