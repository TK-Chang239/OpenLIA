# Portfolio Page Remake — Backlog

Tracks deferred work surfaced during the `ui-remake` Portfolio rebuild
(2026-05-06). Every placeholder in the rebuilt page is listed here with
an explicit API name so the wiring path is obvious when each backend
extension lands.

## Deferred APIs

| ID | Region | What it unblocks |
|---|---|---|
| `PORTFOLIO_DAY_PL_API` | KPI band: Day P/L cell + per-row DAY Δ % | Day-over-day delta for the book and per holding. Needs t-1 close snapshot. |
| `PORTFOLIO_NAV_TIMESERIES_API` | Perf chart card | NAV/vs-SPX/Drawdown/Exposure series (range 1D/1W/1M/YTD/ALL). |
| `PORTFOLIO_HOLDING_DAYCHG_API` | Holdings table DAY Δ column | Per-holding daily change %. |
| `PORTFOLIO_HOLDING_SPARKLINE_API` | Holdings table 7D column | Real 7d price points per holding. |
| `PORTFOLIO_HOLDING_TIMESERIES_API` | Drawer mini chart | Per-holding price series (1D/1W/1M/YTD). |
| `PORTFOLIO_TRADE_LOG_API` | Drawer "Recent activity" | Add/buy/sell events per holding. |
| `PORTFOLIO_LIA_ALERTS_API` | Right-rail Alerts card | Real alerts (drift, risk, catalyst, etc.). |
| `PORTFOLIO_LIA_VERDICTS_API` | Drawer "LIA take" + Holdings FLAG column | Per-holding BUY/HOLD/SELL/RISK verdicts. |
| `REPO_BODY_FULLTEXT_SEARCH` | Drawer "Related reports" section | Extend `services/repo.py` `q` filter to also LIKE against `Report.content_md`, so a ticker search hits reports that mention the symbol in body text — not only those whose title contains it. Used by `HoldingDetailDrawer` lazy fetch. |
| `PORTFOLIO_CASH_HOLDING_TYPE` | Cash row | Schema for cash positions; currently dropped from the table. |

## Closed Decisions

| Q | Choice | Rationale |
|---|---|---|
| Scope | Hybrid pixel-match + preserved features | Keep working CRUD/CSV/sort behind on-design affordances. |
| Header overflow | Split-button on `ADD POSITION ▾` (`Add manually` / `Import CSV…`); refresh icon next to "LAST SYNCED" eyebrow | Discoverability — bulk-add is just adding. |
| Range pills | Drive perf chart only, not KPI band or holdings | KPI cells declare their own timeframe. |
| Row click | Open 480px slide-in detail drawer | Richer than nav-only; deeper than no-op. |
| Drawer section 5 | Related Reports across Equity Research / Earnings Update / Morning Briefings; click → Repository deep-link | Replaces speculative catalysts feed; reuses existing repo. |
| Sort | Click column headers; default WEIGHT desc; persist in `localStorage` | Removes the standalone SortControl. |
| Filter flyout | Groups (real, single-select per holding, multi-select for filtering) + Flag (disabled until verdicts API) | Single-group constraint prevents allocation > 100%. |
| Columns flyout | Lock TICKER/NAME/WEIGHT/PRICE; toggle DAY Δ / POS P/L / 7D / FLAG; persist | Reduces noise without hiding the spine. |
| Right rail | 320px sticky, 2 cards (Portfolio Allocation, LIA Alerts) | Composer dropped per user request. |
| Allocation math | Each holding belongs to ≤ 1 group; market_value sums per-group / total_market_value; `Untagged` bucket for groups.length === 0 | Single-group rule guarantees totals ≤ 100%. |
| Cash row | Dropped (no schema concept) | Backlog: `PORTFOLIO_CASH_HOLDING_TYPE`. |
| First-load motion | 40ms stagger top→bottom, 240ms duration; reduced-motion opt-out | Same Framer Motion pattern as Home. |
| Responsive | <1100px rail stacks; <768px KPI 2×2; <560px table h-scrolls | Don't try to reflow the table. |

## Future enhancements (not blocking)

- `PORTFOLIO_DEPT_DISPATCH` — let dropped Ask-LIA composer (or rail mini-composer) submit directly to a portfolio agent rather than navigating to Secretary.
- Drag-to-rearrange Groups order (admin UI).
- "Sync from broker" connector.
