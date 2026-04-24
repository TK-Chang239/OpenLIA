# Phase 21 — Portfolio fix plan (→ 100%)


**Current:** ~55% shipped. **Root cause:** mixed (IMPLEMENTER monolith + DEFERRED stubs).

**Gap summary:** Page collapsed into 295-line `PortfolioPage.tsx` instead of the 17 planned components; `_NoopPriceProvider` default; `/portfolio/search` stub; no toast system; no ticker→ER navigation; groups-via-notes JSON not surfaced in UI.

**Tasks (in execution order):**

1. **P1-07 — Replace `_NoopPriceProvider` with real EODHD-backed `PortfolioPriceProvider` + `await` async fetch.**
   - Files: `services/portfolio_prices.py` (real impl — TTL cache + adapter dispatch); `routes/portfolio.py` (add `await` in analytics path); `app.py` (wire `provider_factory` from data-provider registry).
   - Spec ref: "Real-Time Price Data" §6.
   - Acceptance: `test_portfolio_prices.py` asserts 60s TTL hit, `DataNotAvailable` graceful fallback, `change_pct` present.

2. **P1-08 — Replace `/portfolio/search` stub with real ticker lookup.**
   - Files: `routes/portfolio.py` (search handler); `services/portfolio.py` (lookup via `company_profile` adapter + exchange field).
   - Spec ref: "Search Results Dropdown".
   - Acceptance: `GET /portfolio/search?q=APP` returns AAPL with name="Apple Inc." exchange="NASDAQ".

3. **NEW-21-01 — Decompose monolith into planned components.**
   - Files: create under `frontend/src/components/portfolio/`: `HoldingsList.tsx`, `HoldingsGrid.tsx`, `GroupTabs.tsx`, `SortControl.tsx`, `ViewToggle.tsx`, `SearchAndAdd.tsx`, `AddEditDrawer.tsx`, `ImportCsvDialog.tsx`, `AnalyticsCards.tsx`, `PriceRefreshButton.tsx`, `Sparkline.tsx`, `AreaChart.tsx`, `GroupAssignmentPopup.tsx`, `GroupContextMenu.tsx`, `PortfolioShell.tsx`. Create hooks `useHoldings.ts`, `useAnalytics.ts`, `useLocalPref.ts`, `useSortedHoldings.ts`. Rewrite `PortfolioPage.tsx` as thin shell.
   - Plan ref: Tasks 7–19.
   - Spec ref: "User Interface Design".
   - Why new: collapsed decomposition flagged in cross-cutting §7 pattern 2 but no standing ID.
   - Acceptance: each component has vitest; page renders List + Card with view persistence via `localStorage`.

4. **NEW-21-02 — Ticker row/card click opens new ER chat with ticker pre-loaded.**
   - Files: `HoldingsList.tsx` + `HoldingsGrid.tsx` (onClick → `/departments/equity-research?ticker={SYM}`); `EquityResearch.tsx` (read `?ticker=`).
   - Spec ref: Functionality §7.
   - Acceptance: vitest — click AAPL row → `navigate` called with expected URL.

5. **NEW-21-03 — Toast notifications + Undo on add/remove/group-delete.**
   - Files: `frontend/src/components/primitives/Toast.tsx` (new or reuse); wire into `PortfolioShell`.
   - Spec ref: "Feedback & Messaging" + "Toast Notification Design".
   - Acceptance: manual — remove ticker shows toast w/ Undo that restores within 5s.

6. **NEW-21-04 — Groups tabs reorder drag + inline rename + delete confirm popover.**
   - Files: `GroupTabs.tsx`, `GroupContextMenu.tsx`; service-side `notes` JSON codec exposing `groups`.
   - Spec ref: "Group Context Menu".
   - Acceptance: reorder persists via `PUT /portfolio/holdings/{id}` notes blob; "All" cannot be moved/deleted.

7. **NEW-21-05 — Market-closed + stale states, swipe-to-remove on mobile, sort persisted per-group.**
   - Files: `HoldingsList.tsx`, `useSortedHoldings.ts` (per-group localStorage key).
   - Spec ref: "States" + "Sort Order".
   - Acceptance: vitest asserts per-group sort preference retained across group switch.

**Verification:** `uv run pytest packages/server/tests/test_portfolio* && cd frontend && npm run test -- portfolio && npm run build`.
