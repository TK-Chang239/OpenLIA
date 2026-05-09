# Macro Research — Dev Backlog (May 2026)

## Status

Frontend visual remake landed in the `ui-remake` branch (May 2026). All six
surfaces (Summary + T1–T5) render the OpenLIAv3 design vocabulary against
**hardcoded April 2026 fallback data** sourced from
`frontend/src/lib/macro_research/dalio_copy/`. Each fallback constant
is typed (`DebtCycleData`, `FourSeasonsData`, …) — those types are the
**eventual API contract**: when the backend produces a payload of the
matching shape, the view's `?? *_FALLBACK` clause goes away and the
fallback file is deleted.

To find every backend-coupled spot, grep:

```
grep -rn 'TODO(backend)' frontend/src/lib/macro_research frontend/src/pages/departments/macro_research
```

## Backend gaps — by dashboard

The DashboardAssembler currently produces tiered T1–T5 outputs scoped to
phase / season / coverage / assessment / smart-mode. The redesign expects a
flat per-dashboard payload. Two ways forward, both compatible:

1. **Wrap-and-flatten**: keep the existing `T3_compute` / `T4` outputs and
   add a `present_for_<slug>(...)` method per dashboard module that maps
   tier outputs into `DebtCycleData` / `FourSeasonsData` / etc.
2. **New endpoint**: add `GET /api/departments/macro_research/dashboards/{slug}/view`
   that returns the typed view shape directly. Existing `/dashboards/{slug}`
   stays for raw tier inspection.

### T1 — Debt Cycle (`frontend/src/lib/macro_research/dalio_copy/debt_cycle.ts`)

| Field | Status | Backend source |
|---|---|---|
| `header.title`, `subtitle`, `livePill`, `refreshLabel` | static | derived |
| `hero.stats[]` (Debt/GDP, Interest/Revenue, Real 10Y, Phase confidence) | needs wiring | T3_compute already has phase + indicator_statuses; extend with values |
| `formulaEngine.cards[]` (4 cards: Debt/GDP, Interest/Revenue, Real 10Y, Foreign UST share) | needs wiring | T1 inputs + threshold module per indicator |
| `formulaEngine.cards[].trailHeights` | needs wiring | new — historical 12mo series |
| `policySpace.cards[]` (Monetary + Fiscal) | needs wiring | new — Fed funds, SOMA size, structural deficit |
| `historicalAnalog.cards[]` | needs LLM-generated | T4 prompt (or new T1 narrative prompt) |
| `assetPlaybook.cards[]` (Gold, UST, USD, SPX, BTC) | needs wiring | quote integration (already exists for retail-sentiment) |
| `synthesis` | needs LLM-generated | T4-style assessment |
| `sources` | static | derived |

### T2 — Four Seasons (`four_seasons.ts`)

| Field | Status | Backend source |
|---|---|---|
| `quadrant.markers[]` (Q1'25, Q2'26 dot positions) | needs wiring | derive from GDP/CPI normalised z-scores |
| `quadrant.trail` | needs wiring | last-N quarters |
| `transition.matrix.rows[]` | needs wiring | Markov estimation (12y window) |
| `transition.triggers.rows[]` | needs LLM | trigger narrative |
| `playbook.rows[]` | static reference data | hardcoded — historical Sharpe per regime |
| `synthesis` | needs LLM | |

### T3 — All-Weather (`all_weather.ts`)

| Field | Status | Backend source |
|---|---|---|
| `coverageRadar.vertices[]` | needs wiring | derive from portfolio + season betas |
| `allocation.capital.legend[]` | needs wiring | portfolio holdings |
| `allocation.risk.rows[]` | needs wiring | EWMA σ 60d window per holding |
| `stress.cards[]` (Stagflation '70, GFC '08, COVID, Twin Shock) | static historical | hardcoded reference returns |
| `rebalance.rows[]` | needs LLM | suggested action narrative |
| `synthesis` | needs LLM | |

### T4 — World Order (`world_order.ts`)

| Field | Status | Backend source |
|---|---|---|
| `composite.gaugePct`, `composite.main.value` | needs wiring | composite index reconstruction |
| `bigCycleChart.years[]`, `series[]` (US + China composite, 1900–2026) | needs wiring | hardcoded historical (slow-moving), backend optional |
| `empireStages.stages[]` (Stage 5 active) | needs wiring | stage classifier |
| `internalMarkers.rows[]` (5 markers) | needs wiring | wealth gap / polarization / debt monetization / populist share / external rival composites |
| `reserveCurrency.snapshots[]` (1999, 2014, today) | needs wiring | IMF COFER quarterly (existing T4 data plus 1999/2014 cached snapshots) |
| `conflictLadder.pairs[]` (US/CN, US/RU, CN/region) | needs LLM + curated feed | escalation count per pair |
| `synthesis` | needs LLM | |

### T5 — Five Forces (`five_forces.ts`)

| Field | Status | Backend source |
|---|---|---|
| `composite.gaugePct`, `composite.main.value` | needs wiring | weighted force composite |
| `forceScorecard.cards[]` (F1–F5) | needs wiring | F1 derived from T1; F3 derived from T4; F2/F4/F5 are new dedicated modules |
| `causality.nodes[]`, `edges[]` | needs wiring | VAR(2) over 1900–2026 (β estimates) |
| `scenarios.rows[]` | needs LLM + Monte Carlo | scenario probability weights |
| `watchlist.triggers[]` | needs LLM | force-specific watch triggers |
| `synthesis` | needs LLM | |

### Summary (`summary.ts`)

| Field | Status | Backend source |
|---|---|---|
| `hero.stats[]` (Growth nowcast, Core PCE, FCI, 10Y) | needs new endpoint | each is a different existing time series |
| `regimeQuadrant.markers[]`, `trail[]` | needs wiring | composite of growth + inflation z-scores |
| `todaysRead.headline`, `body`, `tags` | needs LLM | morning briefing tie-in |
| `frameworkStatus.cards[]` (5 dashboard mini-states) | needs wiring | per-dashboard summary |
| `nowcasts.cards[]` (4 nowcasts) | needs new endpoint | growth nowcast / core PCE / FCI / net liquidity |
| `rates.centralBanks.rows[]` (FED/ECB/BOJ/BOE/PBOC) | needs new endpoint | OIS-implied curves |
| `rates.yieldCurve.data` | needs new endpoint | 7-tenor curve, current/1w-ago/1y-fwd |
| `rates.crossAsset.sections[]` | needs new endpoint | quote integration (existing) |
| `watchlist.calendar.items[]` | needs new endpoint | economic calendar feed |
| `watchlist.flashpoints.items[]` | needs LLM + curated feed | geopolitical event tracker |

## Smaller follow-ups

- **MRSettingsPanel** — new "Run assessment now" section added with one button per
  dashboard. Smart Mode toggle dropped from per-view headers; not yet wired to a
  default-state toggle in the drawer (TODO).
- **Auto-refresh** — design has 5min/15min/Off; we use those values.
  Live polling refetches the active dashboard (existing behaviour).
- **Dark mode** — should work via tokens.css; not visually verified.
- **Tests** — old per-view tests assumed SmartMode/RunAssessment in the
  view header; replaced with new tests targeting the design vocabulary
  (Hero/Verdict/scorecard/quadrant). API integration is exercised via
  `MacroResearch.test.tsx` (route + tab + auto-refresh) and the
  individual view tests render the FALLBACK happy-path.
- **Settings drawer drawer** — design recommends a slide-in animation; we
  use a plain right-anchored overlay. Animation is a polish item.
- **Quadrant marker positions in T2/Summary** — placed by `xPct/yPct` from the
  fallback. When backend wires growth/inflation z-scores in, map them
  through `normalize(value, scaleMin, scaleMax) -> [0,100]` per axis.
- **Reserve currency 1999/2014 snapshots** are intentionally hardcoded —
  they don't change. Only "Today" needs live wiring.

## When wiring backend, the migration playbook

For each dashboard:

1. Make the API endpoint return a payload conforming to `<Slug>Data`
   (`DebtCycleData`, etc.). Use the FALLBACK constant as the reference.
2. In the view, replace:
   ```tsx
   const data: DebtCycleData = DEBT_CYCLE_FALLBACK;
   ```
   with:
   ```tsx
   const [data, setData] = useState<DebtCycleData | null>(null);
   useEffect(() => {
     getDashboardView<DebtCycleData>("debt_cycle").then(setData);
   }, []);
   if (!data) return <SkeletonView />;
   ```
3. Delete `frontend/src/lib/macro_research/dalio_copy/<slug>.ts` once no
   view imports the fallback.
4. Update tests to mock the fetch and assert the rendered view matches.
