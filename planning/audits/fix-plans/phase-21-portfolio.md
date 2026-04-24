# Phase 21 — Portfolio fix plan (→ 100%)

**Current:** ~55% shipped. **Root cause:** mixed (IMPLEMENTER monolith, DEFERRED stubs, SCOPE-CUT components/hooks).

**Gap summary.** Backend CRUD + analytics + CSV + cooldown ship and are wire-tested, but the price provider is a `_NoopPriceProvider` that returns `None`, the `/portfolio/search` route echoes the query, and the planned 17-piece frontend module collapsed into a single 295-line `PortfolioPage.tsx` (header + 3 analytics cards + flat form + flat HTML `<table>`). No `frontend/src/portfolio/` folder exists; none of the planned components, hooks, or vitest specs were created. The page is therefore disconnected from the spec on every interactive axis: no group tabs, no list/card toggle, no per-group sort, no sparkline/area chart, no search-and-add combobox, no group-assignment popup, no group context menu, no toast/undo, no swipe-to-remove, no ticker→Equity-Research deep-link, no market-closed indicator, no empty state, no view-mode/sort persistence. The shipped page also disregards spec Non-Goals (cost-basis entry, P&L, allocations are surfaced) — addenda allowed by Plan 21 but their UI affordances also need to land cleanly.

---

## Inventory — Plan 21 vs. shipped

| Plan task | Spec ref | Shipped artifact | Gap |
|---|---|---|---|
| Task 1 — `services/portfolio_prices.py` (TTL cache + adapter dispatch) | §6 Real-Time Price Data | `PriceCache` shipped; `_NoopPriceProvider` is the default factory | Adapter dispatch absent; `get_price` is sync (plan + Task 15 expect `await provider.get_quote`) |
| Task 2 — `services/portfolio.py` CRUD + groups codec + reference helper | §1–3 | Shipped, with `notes` JSON codec and `get_reference_holdings` | OK |
| Task 3 — Analytics totals/allocation/P&L | Addendum | `compute_analytics` shipped, route returns positions+allocations | OK (numbers); no per-group filter on the route |
| Task 4 — CSV import/export | Addendum | Shipped; round-trip wire test exists | OK |
| Task 5 — `routes/portfolio.py` | §1–7 | Shipped; uses `PATCH` (plan Task 21 references `PUT`) | `/search` is a query-echo stub; `refresh-prices` reaches into `cache._cache` |
| Task 6 — Wire router | — | `app.py` mounts via `build_portfolio_router` | OK |
| Task 7 — `api/portfolio.ts` typed client | — | Shipped (`fetchHoldings`, `createHolding`, `updateHolding`, `deleteHolding`, `fetchAnalytics`, `refreshPrices`, `importCsv`, `exportCsvUrl`, `searchTickers`) | OK |
| Task 8 — `useHoldings` + `useAnalytics` | — | NOT SHIPPED — page calls API directly | Missing |
| Task 9 — `useLocalPref` + `useSortedHoldings` | §Sort Order, View Mode | NOT SHIPPED | Missing |
| Task 10 — `Sparkline` + `AreaChart` SVG primitives | §List View, §Card View | NOT SHIPPED | Missing |
| Task 11 — `HoldingsList` (List View) | §List View | NOT SHIPPED — replaced by flat `<table>` | Missing |
| Task 12 — `HoldingsGrid` (Card View) | §Card View | NOT SHIPPED | Missing |
| Task 13 — `GroupTabs` + `SortControl` + `ViewToggle` | §Group Tab Bar, §Sort, §View toggle | NOT SHIPPED | Missing |
| Task 14 — `SearchAndAdd` combobox + group-assignment popup | §Search and Add Flow | NOT SHIPPED — replaced by 4-input flat form | Missing |
| Task 15 — `/portfolio/search` over adapter | §Search Results Dropdown | Stub returns `[{ticker: q, name: null}]` | Missing real lookup |
| Task 16 — `AddEditDrawer` | (addendum) | NOT SHIPPED | Missing |
| Task 17 — `ImportCsvDialog` | (addendum) | NOT SHIPPED — replaced by file `<input>` button | Missing |
| Task 18 — `AnalyticsCards` + `PriceRefreshButton` | (addendum) | Inlined in `PortfolioPage.tsx` | Missing component split + rate-limit feedback |
| Task 19 — `PortfolioShell` + `PortfolioPage` | §Layout | `PortfolioPage.tsx` is the entire shell | Missing decomposition |
| Task 20 — Register `/portfolio` route + sidebar entry | — | Sidebar entry present (`/portfolio` listed in app.py route table) | Verify sidebar icon + smoke |
| Task 21 — Cross-plan docs (endpoint matrix, auth matrix, MB helper) | — | Helper shipped; matrix rows status unverified | Verify matrix rows |
| Task 22 — Final acceptance | — | N/A | Re-run gate after fixes |

Shipped vitest files for portfolio: **0**. Shipped server tests for portfolio: 3 (`test_portfolio.py`, `test_portfolio_prices.py`, `test_portfolio_routes.py`) but none cover real adapter wiring or search-by-name.

---

## Top bugs (verified)

1. **Pricing is a no-op (`packages/server/src/openlia_server/services/portfolio_prices.py:90–96`).** `_NoopPriceProvider.get_price` returns `None` for every ticker, and `get_default_provider()` is the production factory. Result: `/portfolio/analytics` always reports `last_price=null`, `market_value=null`, `unrealized_pl=null`, and `/portfolio/refresh-prices` returns `{prices: {AAPL: null, ...}}`. The 60s TTL "hits" because every miss caches `None`. The plan called for a real adapter dispatch (Task 1, Step 4: "wrap the configured `FinancialAdapter`" with `await adapter.get_quote(ticker)`).

2. **`POST /portfolio/refresh-prices` mutates a private cache attribute (`routes/portfolio.py:200`).** Handler does `cache._cache.pop(h.ticker.upper(), None)` to force-refresh. This breaks encapsulation, will silently drift if `PriceCache` adds a second backing store, and means a malformed PUT could leave `_last_refresh_by_user` in an inconsistent state. The plan specified `cache.invalidate(tickers)` as a public method (Task 1 acceptance: "force-refresh path uses a public invalidate method"). Add `PriceCache.invalidate(tickers)` and call it from the route.

3. **`GET /portfolio/search` is a query echo (`routes/portfolio.py:225–235`).** Returns `[{"ticker": q.upper(), "name": null}]` regardless of input — even for nonsense like `q=ZZZZZ`. The wire test `test_search_echoes_query` enforces the bug rather than a real lookup. Spec §Search Results Dropdown requires symbol + company name + exchange label (NASDAQ/NYSE/TWSE). Plan Task 15 specifies probing `company_profile` via the configured adapter and returning `[]` when `quote.last_price is None`.

---

## Surprises

- **The shipped page violates the spec's Non-Goals on purpose.** Spec §Non-Goals (v1) explicitly disables P&L, cost-basis entry, allocations, and CSV import/export. Plan 21 §"Checklist — scope addenda beyond the spec" calls these out as intentional additions. Fix-plan must keep the addenda but layer the spec-mandated UX (groups, view modes, sort, sparkline, ER deep-link) on top — not delete the addenda components.
- **Groups storage is a JSON blob inside `notes`** (`services/portfolio.py:53–73`). The codec is well-tested, but the route currently has no endpoints to list/create/rename/reorder/delete groups — the UI must derive groups by walking holdings. Plan §Design Rule 9 anticipates this; spec §Group Context Menu requires Rename/Reorder/Delete. Need a service-layer group helper plus dedicated endpoints (or a documented client-side reconciliation pattern) before the GroupTabs component can ship correctly.
- **Plan documents mismatch the shipped routes.** Plan Task 21 references `PUT /portfolio/holdings/{id}` and `POST /portfolio/holdings/import` — shipped routes are `PATCH /portfolio/holdings/{id}` and `POST /portfolio/import-csv`. The endpoint-contract-matrix and route-authorization-matrix rows must be appended with the actual verbs/paths, not the plan's draft.
- **No core layer for portfolio.** `packages/core/src/openlia/portfolio/` does not exist. All logic lives in `packages/server/`. That is fine for v1 (no LLM), but the cross-plan helper `get_reference_holdings` is therefore a server-side import — Plan 16's Morning Briefing must consume it via `openlia_server.services.portfolio`, not `openlia.portfolio`.
- **Existing test `test_search_echoes_query` will fail once Task 15 lands** — must be rewritten to monkeypatch the adapter and assert real shape `{ticker, name, exchange}`.

---

## Fix tasks (execution order)

### NEW-21-01 — Real EODHD-backed `PortfolioPriceProvider` + `cache.invalidate`
- **Files:** `packages/server/src/openlia_server/services/portfolio_prices.py` (replace `_NoopPriceProvider`, add `invalidate`); `packages/server/src/openlia_server/routes/portfolio.py` (drop `cache._cache.pop` for `cache.invalidate`); `packages/server/src/openlia_server/app.py` (wire `price_provider_factory` from the configured `FinancialAdapter`/registry); `packages/server/tests/test_services/test_portfolio_prices.py` (extend).
- **Spec ref:** §6 Real-Time Price Data; Plan Task 1 Step 4.
- **Acceptance:** With a fake adapter exposing `get_quote("AAPL") -> Quote(last_price=Decimal("150.0"))`, `cache.fetch_many(provider, ["AAPL"])` returns `{"AAPL": Decimal("150.0")}` on first call and a cache hit on the second; `provider.get_quote` raising `DataNotAvailable` returns `{"AAPL": None}` (200, not 5xx); `PriceCache.invalidate(["AAPL"])` removes only `AAPL`; `app.py` resolves the factory from `app.state.financial_adapter` and falls back to `_NoopPriceProvider` only when no adapter is configured (with a warning log).

### NEW-21-02 — Adapter-backed `/portfolio/search` over `company_profile`
- **Files:** `packages/server/src/openlia_server/routes/portfolio.py` (replace handler); `packages/server/tests/test_routes/test_portfolio_routes.py` (rewrite `test_search_echoes_query`).
- **Spec ref:** §Search Results Dropdown (symbol + company name + exchange label).
- **Acceptance:** `GET /portfolio/search?q=APP` against a fake adapter exposing `get_company_profile` returns `[{"ticker": "AAPL", "name": "Apple Inc.", "exchange": "NASDAQ"}]`; `q=""` returns `[]`; adapter raise → `[]` (graceful). Response model is a typed `SearchResultOut(BaseModel)` with `exchange: str | None`. Existing duplicate-prevention: result rows for tickers already in the user's portfolio carry `already_added: True`.

### NEW-21-03 — Frontend module decomposition into `frontend/src/portfolio/`
- **Files:** create directory `frontend/src/portfolio/` and add the 14 planned components + 4 hooks; rewrite `frontend/src/pages/PortfolioPage.tsx` as a thin route wrapper.
  - Components: `PortfolioShell.tsx`, `SearchAndAdd.tsx`, `GroupTabs.tsx`, `SortControl.tsx`, `ViewToggle.tsx`, `HoldingsList.tsx`, `HoldingsGrid.tsx`, `AddEditDrawer.tsx`, `ImportCsvDialog.tsx`, `AnalyticsCards.tsx`, `PriceRefreshButton.tsx`, `Sparkline.tsx`, `AreaChart.tsx`, `EmptyState.tsx`.
  - Hooks: `useHoldings.ts`, `useAnalytics.ts`, `useSortedHoldings.ts`, `useLocalPref.ts`.
- **Spec ref:** §Layout, §List View, §Card View, §States.
- **Acceptance:** `frontend/src/pages/PortfolioPage.tsx` ≤ 30 LOC and renders only `<PortfolioShell />`. Each component file has a sibling `*.test.tsx` (vitest); shell test asserts shell renders both view modes via `useLocalPref`.

### NEW-21-04 — `SearchAndAdd` combobox + Group-Assignment popup
- **Files:** `frontend/src/portfolio/SearchAndAdd.tsx`, `SearchAndAdd.test.tsx`.
- **Spec ref:** §Search and Add Flow, §Search Results Dropdown, §Group Assignment Popup.
- **Acceptance:** 300ms debounce; `role="combobox"` with `aria-expanded`; `role="listbox"` results; ArrowUp/ArrowDown/Enter/Escape keyboard nav; "Already added" rows non-actionable; on add, popup appears below the bar with "All" checked-and-disabled and existing user groups as opt-in checkboxes; auto-dismiss after 4s; calls `createHolding({groups: [...]})`.

### NEW-21-05 — `GroupTabs` + group context menu (rename/reorder/delete) + group service endpoints
- **Files:** `frontend/src/portfolio/GroupTabs.tsx`, `GroupContextMenu.tsx`, `GroupTabs.test.tsx`; `packages/server/src/openlia_server/services/portfolio.py` (add `list_groups`, `rename_group`, `reorder_groups`, `delete_group`); `routes/portfolio.py` (`GET/POST/PATCH/DELETE /portfolio/groups`); `tests/test_services/test_portfolio.py` + `test_routes/test_portfolio_routes.py`.
- **Spec ref:** §Groups, §Group Context Menu.
- **Acceptance:** "All" tab is implicit, always first, never editable; `+ New Group` inline input creates an empty group; right-click/long-press opens menu with Rename, Reorder…, Delete (Trash2, `--color-feedback-error`); delete-confirm popover preserves tickers in All; reorder via drag persists across reload via the new endpoints (no longer client-side only); rename updates every holding whose `groups` JSON contains the old name in a single transaction.

### NEW-21-06 — `SortControl` + `ViewToggle` + per-group sort persistence
- **Files:** `frontend/src/portfolio/SortControl.tsx`, `ViewToggle.tsx`, `useLocalPref.ts`, `useSortedHoldings.ts` and matching tests.
- **Spec ref:** §Sort Order, §View Mode Toggle.
- **Acceptance:** Four sort options (A→Z, Z→A, Price ↓, Price ↑); `useSortedHoldings` keys preference per group via `portfolio:sort:{groupId}` in localStorage; `useLocalPref` persists view mode under `portfolio:view`; toggling view animates 150ms crossfade; newly added tickers are inserted in current sort order, not appended.

### NEW-21-07 — `HoldingsList` (List View) with sparkline, hover-remove, swipe-to-remove
- **Files:** `frontend/src/portfolio/HoldingsList.tsx`, `Sparkline.tsx` (inline SVG), tests.
- **Spec ref:** §List View, §Responsive Behavior.
- **Acceptance:** ~60px row, ticker + company name + 80×28 sparkline + price + metric badge; sparkline color derived from sign of daily change; metric badge tappable to toggle $/%; hover (desktop) reveals trash icon; mobile swipe-left reveals red delete zone; sparkline column hidden under `md`; row click navigates to ER (NEW-21-09).

### NEW-21-08 — `HoldingsGrid` (Card View) with area chart
- **Files:** `frontend/src/portfolio/HoldingsGrid.tsx`, `AreaChart.tsx`, tests.
- **Spec ref:** §Card View, §Responsive Behavior.
- **Acceptance:** Cards 160px min-width; area chart fills ~100px zone with green/red gradient + matching line; card grid `grid-cols-1 md:grid-cols-2 lg:grid-cols-3`; sectioned grouping when "All" tab active (group section header + count + divider); group context menu icon on each section header.

### NEW-21-09 — Ticker → Equity Research deep-link
- **Files:** `HoldingsList.tsx`, `HoldingsGrid.tsx` (`onClick` → `useNavigate("/departments/equity-research?ticker=${SYM}")`); `frontend/src/pages/EquityResearch.tsx` (read `?ticker=` and pre-load).
- **Spec ref:** §Ticker Detail Navigation (Functionality §7).
- **Acceptance:** vitest asserts `navigate` is called with `/departments/equity-research?ticker=AAPL`; ER page initializes a new chat session with the ticker pre-populated.

### NEW-21-10 — Toast notifications + Undo for add/remove/group-delete
- **Files:** `frontend/src/components/primitives/Toast.tsx` (or reuse), `frontend/src/portfolio/PortfolioShell.tsx` toast provider.
- **Spec ref:** §Feedback & Messaging, §Toast Notification Design.
- **Acceptance:** Add → "AAPL added to Portfolio" (4s); Remove → "AAPL removed" + Undo (5s) that re-creates the holding via stored snapshot; Group delete → "Group 'Tech' deleted" + Undo restores group membership; max 3 stacked toasts; entry/exit animations match spec timings.

### NEW-21-11 — `AnalyticsCards` + `PriceRefreshButton` with rate-limit feedback
- **Files:** `frontend/src/portfolio/AnalyticsCards.tsx`, `PriceRefreshButton.tsx` and tests.
- **Spec ref:** Plan Task 18.
- **Acceptance:** Three cards (Market Value, Cost Basis, Unrealized P/L) with positive/negative semantic color; refresh button surfaces 429 → "Try again in N seconds"; success → toast "Prices refreshed"; allocation chart (donut or bar) renders from `analytics.allocations`.

### NEW-21-12 — `AddEditDrawer` + `ImportCsvDialog` (real components)
- **Files:** `frontend/src/portfolio/AddEditDrawer.tsx`, `ImportCsvDialog.tsx` and tests.
- **Spec ref:** Plan Tasks 16, 17 (addenda).
- **Acceptance:** Drawer (`role="dialog" aria-modal`) with create/edit modes, ticker disabled in edit; CSV dialog accepts file or paste, previews parsed rows + per-row errors before commit, surfaces `created`/`errors` counts after submit; both replace the inline form/file-input on the current page.

### NEW-21-13 — Empty / Loading / Market-closed / Error states
- **Files:** `frontend/src/portfolio/EmptyState.tsx`, state branches in `HoldingsList`/`HoldingsGrid`, `PortfolioShell`.
- **Spec ref:** §States.
- **Acceptance:** Empty: `BarChart2` icon + "Your portfolio is empty" heading + "Search above to add tickers"; Loading: skeleton rows/cards (`animate-pulse`); Market Closed: "Market closed" `text-xs text-tertiary` indicator in the sort bar derived from a `last_quote_at` field on the analytics response; Error: sparkline → `—`, price `—`, badge hidden, refresh icon revealed on hover.

### NEW-21-14 — Endpoint + auth matrix rows; sidebar entry verification
- **Files:** `planning/implementation-plans/endpoint-contract-matrix.md`, `route-authorization-matrix.md`, `frontend/src/components/sidebar/*` (verify `BarChart2` Portfolio entry).
- **Spec ref:** Plan Task 21.
- **Acceptance:** Rows reflect actual verbs: `PATCH /portfolio/holdings/{id}` (not PUT), `POST /portfolio/import-csv` (not `/holdings/import`), `GET /portfolio/export-csv` (not `/holdings/export`), plus the new `/portfolio/groups` endpoints and `/portfolio/search` (now adapter-backed). All flagged `authenticated`, `owner-scoped`, `must-change-password → blocked`, mounted in both modes.

### NEW-21-15 — Test coverage parity
- **Backend:** extend `test_portfolio_prices.py` with adapter dispatch + `invalidate`; rewrite `test_search_echoes_query` → adapter-backed lookup; add `test_groups_endpoints.py` for the new group routes; add `test_portfolio.py::test_rename_group_updates_all_holdings`.
- **Frontend:** vitest spec files for every new component + hook (≥14 specs). Verify with `cd frontend && npm test -- --run portfolio`.
- **Spec ref:** Plan Task 22.
- **Acceptance:** `uv run pytest packages/server/tests/test_routes/test_portfolio_routes.py packages/server/tests/test_services/test_portfolio*.py -q` green; `cd frontend && npm test -- --run portfolio && npm run build` green.

---

## Verification

```bash
uv run ruff check . && uv run ruff format --check .
uv run pytest packages/server/tests/test_routes/test_portfolio_routes.py packages/server/tests/test_services/test_portfolio*.py -q
cd frontend && npm test -- --run portfolio && npm run build
```

Manual smoke (per spec §Behavior & Interactions): add AAPL via search-and-add → assignment popup → assign to "Tech" → toggle list/card view → re-sort by price desc → click AAPL row → lands in Equity Research with ticker pre-loaded → return → remove → Undo restores within 5s → group context menu → rename "Tech" → "Megacap" → all member holdings reflect rename.

## Rollback

Revert in reverse task order. NEW-21-01 is the only change with runtime impact on a fresh environment without a configured adapter — keep the `_NoopPriceProvider` fallback path so the page degrades gracefully (sparkline `—`, price `—`) rather than 500-ing.
