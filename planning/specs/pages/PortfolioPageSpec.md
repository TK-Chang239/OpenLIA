# Portfolio Page Spec

> **Status:** SHIPPED — rewritten 2026-08-16 to match the shipped **holdings tracker**. The earlier version of this spec described a watchlist of tickers and listed holdings / P&L / allocation / CSV import-export as *Non-Goals*; those are the shipped feature set. This rewrite reflects reality.
>
> **Grounded in shipped code:** `frontend/src/portfolio/*` — `PortfolioShell.tsx`, `HoldingsTable.tsx`, `KpiBand.tsx`, `PerfChart.tsx`, `PortfolioAllocationCard.tsx`, `PortfolioPageHeader.tsx`, `AddEditDrawer.tsx`, `HoldingDetailDrawer.tsx`, `ImportCsvDialog.tsx`, `allocation.ts`, `formatCurrency.ts` — and `frontend/src/api/portfolio.ts`.

## Page Overview

The Portfolio page is a **holdings tracker**: the user records actual positions (ticker, shares, average cost, currency, optional group and notes) and the page computes and displays market value, unrealized P/L, weight, day change, and portfolio-value-over-time. It is a data page — no chat, no LLM.

The page is **market-scoped**. It is routed as `/portfolio/:market` (markets: `us`, `tw`) with a market toggle in the header; each market renders its own holdings, KPIs, chart, and allocation. Prices are sourced from EODHD and refreshed on a user-chosen cadence, or on demand.

### Multi-currency correctness (load-bearing behavior)

Holdings may be recorded in different currencies. **The page never sums or divides values across currencies without FX conversion, and it performs no FX conversion.** Concretely:

- **Single-currency portfolio** → the KPI band shows combined Total NAV and Unrealized P/L.
- **Mixed-currency portfolio** (`analytics.currencies_present.length > 1`) → combined totals are `null` from the API; the KPI band switches to a **per-currency segregated** view (one row per currency, market value + P/L, "By currency · no FX"), and a banner explains FX is unavailable. Group **allocation is suppressed** in mixed-currency mode (`computeAllocation` returns `[]`), because dividing raw market values by a cross-currency total is not valid without FX.

## Page Functionalities

1. **Holdings table** (`HoldingsTable`) — one row per position with columns: **Ticker** (+ company name), **Group**, **Shares**, **Avg Cost**, **Price** (last), **Day Change** (abs + %), **Market Value**, **Position P/L** (unrealized, abs + %), **Weight**. Columns are sortable; a per-column sort preference persists in `localStorage["portfolio:sort"]`. Rows can be filtered by group. Each row can show an intraday **sparkline**. Clicking a row opens the holding detail drawer.
2. **KPI band** (`KpiBand`) — Total NAV (with cost basis) and Unrealized P/L (abs + %), or the per-currency segregated view in mixed-currency mode (see above).
3. **Performance chart** (`PerfChart`) — portfolio value over a selectable range (`PerfRange`, e.g. 1W/1M/…), backed by the value-series API; a period-return banner shows the return over the actual data span.
4. **Allocation card** (`PortfolioAllocationCard` / `allocation.ts`) — group allocation as a share of NAV, one row per group (holdings with no group collect under "Untagged"), sorted by weight with Untagged last. Single-currency only.
5. **Add holding manually** (`AddEditDrawer`, create mode) — ticker, shares, cost basis, currency, group(s), notes, and an optional added-on date. Same drawer edits an existing holding.
6. **Import from CSV** (`ImportCsvDialog`) — bulk-create holdings from a CSV; reports created rows + per-row errors.
7. **Export to CSV** — the header exports the current holdings via `exportCsvUrl()`.
8. **Refresh prices** — a manual refresh button (`refreshPrices(market)`) with a 429 retry-after message, plus a **refresh cadence** preference (`RefreshCadence`, persisted via `updatePortfolioPrefs`) controlling automatic refresh.
9. **Holding detail drawer** (`HoldingDetailDrawer`) — per-position detail with Edit and Remove; Remove is undoable via a 5s toast that re-creates the holding.
10. **Groups** — holdings carry a group label (stored in the notes JSON blob). The client enforces a **single group per holding** for allocation (`allocation.ts`); inline group creation is supported (`createGroup`). (Note: the backend does not enforce the single-group rule — see the Portfolio remake backlog.)
11. **Lia alerts card** (`LiaAlertsCard`) — a sidebar placeholder for portfolio alerts/verdicts (deferred; renders based on whether holdings exist).
12. **Market switch** — the header market toggle navigates between `/portfolio/us` and `/portfolio/tw`; each market is an isolated view (the shell is keyed by market).

## Page Design

### Layout

Two-column responsive grid (`max-w-[1400px]`; collapses to one column below 1100px). Main column (top → bottom): page header → KPI band → mixed-currency banner (conditional) → performance chart → period-return banner (conditional) → holdings table. Right sidebar (sticky ≥1100px): allocation card → Lia alerts card. Each block fades/translates up on mount.

### Header (`PortfolioPageHeader`)

- Eyebrow line: "Personal · {market label} · {currency} · Last synced {time}" with an inline refresh-prices button.
- Title: "Portfolio".
- Controls: **Market toggle** (US / TW) · **Range picker** (perf window) · **Refresh cadence** selector · **Add** split button (Add manually / Import CSV). CSV export via `exportHref`.

### Drawers / dialogs

`AddEditDrawer` (create/edit), `HoldingDetailDrawer` (view/edit/remove), `ImportCsvDialog` (bulk import). Toasts (`ToastProvider`) surface save/remove/refresh/import results, including undo on remove.

## States

| State | Description |
|---|---|
| **Loading** | KPI/table skeletons while holdings load. |
| **Empty** | No holdings → empty table affordance; KPIs show `—`. |
| **Populated (single currency)** | Combined KPIs, allocation, chart, holdings table. |
| **Mixed currency** | Per-currency segregated KPI rows + FX-unavailable banner; allocation suppressed. |
| **Refreshing** | Refresh button spinner; 429 shows a retry-after message. |
| **Price unavailable** | A holding with no quote contributes 0 to totals and shows `—` where a price/value is missing. |

## Data Requirements

| Requirement | Type | Use |
|---|---|---|
| Stock quote | `stock_quote` | Last price, day change for each holding. |
| Company profile | `company_profile` | Company name for holding identification (`PortfolioHolding.name`). |
| Historical / value series | portfolio value series | Performance chart + period return. |
| Intraday prices | `intraday_prices` | Per-row sparklines. |

## Configurations

- **LLM:** none — the Portfolio page does not invoke an LLM.
- **Preferences:** refresh cadence (`updatePortfolioPrefs`); sort preference (localStorage).

## Non-Goals (current)

- **FX conversion / a single combined total across currencies.** Deliberately not done — mixed-currency portfolios are shown segregated per currency (see *Multi-currency correctness*).
- Price alerts / push notifications from this page (the Lia alerts card is a deferred placeholder).
- Trade log, realized P/L, cash holdings, and benchmark (vs-SPX) / drawdown / exposure analytics — deferred per the Portfolio remake backlog.
- Backend enforcement of the single-group-per-holding rule (currently client-only).
- A "Market closed" indicator (backlog).
