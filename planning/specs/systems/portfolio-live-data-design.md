# Portfolio Live Data & Chart Timeframes — System Design

**Status:** Locked design after grilling session (2026-05-10).
**Scope:** Backend price-refresh architecture + portfolio-level summary section + chart-timeframe selectors.
**Supersedes:** "Real-Time Price Data" and "Price Refresh" sections in `planning/specs/pages/PortfolioPageSpec.md` (those should be updated to reference this doc).

---

## Goal

Replace the existing in-memory `PriceCache` + per-request EODHD fetch model with a server-scheduled, DB-backed quote system. Add portfolio-level summary visuals (value chart + allocation donut + period numbers) and per-ticker chart-timeframe controls. Keep EODHD spend low by deduping fetches per-ticker across all users.

---

## Architecture

```
+--------------------------+
|   APScheduler            |
|   JobType.PORTFOLIO_     |  per-tick: compute due tickers,
|     PRICE_REFRESH        |  call fetch_and_upsert(ticker)
+----------+---------------+
           |
           v
+--------------------------+        +-------------------------+
| fetch_and_upsert(ticker) |------->|   portfolio_quotes      |  (one row per ticker)
+----------+---------------+        +-------------------------+
           |
           +----- intraday point --> portfolio_quote_intraday  (today, wiped daily)
           |
           +----- post-close ------> portfolio_quote_daily     (per ticker × trade_date)
```

Routes read from these tables; they never call EODHD on the request path (except the user-driven `/refresh-prices` button and the search route, which already does an on-demand company-profile fetch).

---

## Locked decisions

### 1. Refresh cadence

- Per-user preference: `user_prefs[portfolio.refresh_cadence]` ∈ `{"hourly", "daily", "weekly", "manual"}`.
- Default `"daily"`.
- UI label for `"manual"`: **"No Auto-refresh"**.
- **Floor semantics**: cadence is a freshness floor, not a fetch throttle. A user picking Weekly still sees the latest hourly data if any other user holds the same ticker with `"hourly"`.
- A ticker is in the scheduler's fetch union if **at least one** user holding it has cadence ≠ `"manual"`. A ticker held only by `"manual"` users is fetched only when one of them clicks Refresh.

### 2. Scheduler (one global APScheduler job, `JobType.PORTFOLIO_PRICE_REFRESH`)

Fires:

| Trigger | When | Action |
|---|---|---|
| Top of hour | `cron: minute=0`, every hour, UTC | Compute union, fetch any ticker whose `fetched_at` older than `min_user_cadence` |
| US post-close | `cron: minute=30 hour=20` Mon–Fri UTC (≈ 4:30pm ET) | Upsert canonical close for US tickers into `portfolio_quote_daily` |
| TWSE post-close | `cron: minute=0 hour=6` Mon–Fri UTC (≈ 2:00pm Taipei) | Upsert canonical close for TWSE tickers |
| Wake-up sweep | Date trigger at `now+5s` on `SchedulerService.start()` | One-shot catch-up for any ticker `fetched_at < now − 1h` |

Per-tick logic:

```python
def portfolio_price_tick(now_utc):
    tickers = scheduler_union(session)   # [(ticker, min_cadence_s), ...]
    for ticker, min_cadence in tickers:
        row = get_quote(ticker)
        age = now - (row.fetched_at if row else datetime.min)
        if row is not None and age < min_cadence:
            continue
        if (not is_market_open(ticker, now)) and age < timedelta(hours=72):
            continue   # market closed and we have a fresh-enough number
                       # (72h covers Fri-close → Sun-night with margin)
        fetch_and_upsert(ticker)
    if fire_is_post_close_for_market(now_utc):
        for ticker in tickers_in_market(market):
            upsert_daily_close(ticker)
```

Cadence → seconds: `hourly=3600, daily=86400, weekly=604800, manual=None`.

### 3. Market hours

- Hardcoded sessions for **NYSE/NASDAQ** (M–F 9:30–16:00 ET) and **TWSE** (M–F 9:00–13:30 Taipei). No holiday calendar in v1 — accept the ~10 wasted fetches/year/ticker on holidays.
- Fallback for tickers from other markets: treat as "always open" and fetch at user cadence.
- `is_market_open(ticker, now_utc)` lives in a new `openlia_server/services/market_hours.py` module.

### 4. Quote storage schemas

**`portfolio_quotes`** — one row per ticker, upserted on every fetch:

| Column | Type | Notes |
|---|---|---|
| `ticker` | `String(32)`, PK | upper-cased |
| `last_price` | `Numeric(20,6)`, nullable | |
| `previous_close` | `Numeric(20,6)`, nullable | |
| `day_open` | `Numeric(20,6)`, nullable | |
| `day_high` | `Numeric(20,6)`, nullable | |
| `day_low` | `Numeric(20,6)`, nullable | |
| `volume` | `BigInteger`, nullable | |
| `currency` | `String(8)`, nullable | |
| `quote_at` | `DateTime(timezone=True)`, nullable | provider-reported quote timestamp |
| `fetched_at` | `DateTime(timezone=True)`, **not null** | our write time |
| `source` | `String(32)` | connector id (`"eodhd"`, `"fmp"`, etc.) |

Day-change is computed on read: `last_price - previous_close`.

**`portfolio_quote_intraday`** — scheduler tick points, wiped at trading-day boundary:

| Column | Type | Notes |
|---|---|---|
| `ticker` | `String(32)` | composite PK with `ts` |
| `ts` | `DateTime(tz)` | scheduler tick time, UTC |
| `close` | `Numeric(20,6)` | last_price at tick |

Index: `(ticker, ts)`. Wiped at the start of each US trading day by the post-close-US fire (lazy: delete `WHERE ts < today_start_utc`).

**`portfolio_quote_daily`** — official closing series:

| Column | Type | Notes |
|---|---|---|
| `ticker` | `String(32)` | composite PK with `trade_date` |
| `trade_date` | `Date` | session date |
| `open` | `Numeric(20,6)`, nullable | |
| `high` | `Numeric(20,6)`, nullable | |
| `low` | `Numeric(20,6)`, nullable | |
| `close` | `Numeric(20,6)`, not null | |
| `volume` | `BigInteger`, nullable | |

Populated by:
- **5Y backfill on add**: when `POST /portfolio/holdings` succeeds, an async task calls EODHD `/eod/{ticker}?from=today-5y` and bulk-inserts.
- **Post-close fire**: appends today's row.

### 5. New-ticker UX

`POST /portfolio/holdings` returns 201 immediately; an async background task calls `fetch_and_upsert(ticker)` + `backfill_daily(ticker, years=5)`. Frontend shows the row immediately with a "*Fetching latest price…*" loading caption until quote arrives. Frontend auto-refetches `/analytics` after ~1.5s.

### 6. Manual refresh button

`POST /portfolio/refresh-prices`:
- Calls `fetch_and_upsert` for **all of the calling user's** holdings inline (no global dedupe in v1).
- 30s per-user cooldown (existing).
- Returns `{prices: {...}}` for frontend reconciliation.

### 7. Endpoints

| Method | Path | Purpose |
|---|---|---|
| `GET` | `/portfolio/analytics` | Snapshot: totals, positions (current snapshot), allocations, last_quote_at, display_currency, fx_rates_used |
| `GET` | `/portfolio/value-series?timeframe={t}` | Portfolio value over time + period_return_abs/pct, clamped to inception with `actual_span` |
| `GET` | `/portfolio/ticker-series?timeframe={t}` | Per-ticker close series + per-ticker period_change_pct |
| `GET` | `/portfolio/prefs` | Per-user portfolio prefs |
| `PUT` | `/portfolio/prefs` | Update prefs (cadence, display_currency, top/bottom timeframe, view_mode, sort orders) |
| `POST` | `/portfolio/refresh-prices` | Manual refresh (existing) |

All existing routes (`/holdings*`, `/groups*`, `/search`, `/import-csv`, `/export-csv`) keep their shapes.

`timeframe` ∈ `{"1d","1w","1m","3m","6m","ytd","1y","5y"}`.

Response shapes specified in §10 of the grill log; copy:

```jsonc
// GET /portfolio/value-series?timeframe=1m
{
  "timeframe": "1m",
  "actual_span": {"start": "2026-04-10", "end": "2026-05-10"},
  "points": [{"date": "2026-04-10", "value": "12345.67"}, ...],
  "period_return_abs": "234.10",
  "period_return_pct": "0.0234",
  "display_currency": "USD"
}

// GET /portfolio/ticker-series?timeframe=1m
{
  "timeframe": "1m",
  "series": {"AAPL": [{"ts": "...", "close": "..."}, ...]},
  "period_change_pct": {"AAPL": "0.085"},
  "display_currency": "USD"
}
```

### 8. Portfolio value chart math (top section)

For each day `t` in `[max(picker_start, earliest_holding.added_at), today]`:
```
value(t) = Σᵢ (sharesᵢ_current × closeᵢ(t))   over holdings where addedᵢ ≤ t
```

- Uses **current shares** (no transactions table; share-quantity edits retroactively redraw the chart).
- Includes a holding only from its `added_at` forward.
- Daily resolution from `portfolio_quote_daily`; for "today" use `portfolio_quotes.last_price`.

**Period Return** = `(value_at_actual_span_end − value_at_actual_span_start) / value_at_actual_span_start`. UI caption: "*since {actual_span.start}*".

**Unrealized P&L** (separate tile) = `Σ(sharesᵢ × last_priceᵢ − sharesᵢ × cost_basisᵢ)` — current snapshot, not timeframe-dependent.

### 9. FX / multi-currency

- `user_prefs[portfolio.display_currency]`, default `"USD"`.
- Single-currency portfolios skip FX entirely.
- Mixed currencies: convert per-row `last_price × shares` to display currency using **current spot** from the connector's `fx_rate` capability. Apply same current spot to historical values (documented limitation: a chart caption reads "*USD value uses current FX*").
- If no connector supports `fx_rate`, degrade gracefully:
  - Top section shows per-currency tiles (no aggregate chart).
  - Allocation donut splits per-currency.
  - Banner: "*Multi-currency totals unavailable — configure an FX-capable connector*".

### 10. UI placement

| Control | Location |
|---|---|
| Top timeframe picker (1D…5Y) | Above portfolio value chart |
| Bottom timeframe picker (1D…5Y) | Above ticker grid, alongside sort dropdown |
| Refresh cadence | Gear popover in page header (top-right) |
| Display currency | Same gear popover |
| Freshness banner ("Updated 12 min ago" / "Stale") | Below controls bar |
| Manual refresh button | Stays in controls bar |

### 11. Empty/edge states

- 0 holdings → hide top section, show existing empty-state card.
- Holdings exist but daily backfill not done → top numbers strip shows "—" for Period Return, chart skeleton with "*Building historical data…*".
- FX unavailable → per-currency degradation per §9.

### 12. Equity Research click-through

Clicking a ticker always opens a **new** Equity Research chat session pre-loaded with that ticker. No prompt, no reuse. (Resolves the page spec's open question.)

---

## Build order

Six TDD phases, each ends in a green run of the full server suite + a brief frontend type-check:

1. **Phase 1** — `portfolio_quotes` table + scheduler hourly fire + wake-up sweep + `/analytics` reads from DB + Frontend freshness banner.
2. **Phase 2** — `user_prefs[portfolio.refresh_cadence]` + `/portfolio/prefs` + gear popover + scheduler floor-semantics.
3. **Phase 3** — `portfolio_quote_daily` + 5Y backfill + post-close fires + `/portfolio/value-series` + top picker + portfolio chart + Period Return tile.
4. **Phase 4** — `portfolio_quote_intraday` + intraday upsert in scheduler ticks + `/portfolio/ticker-series` + bottom picker + per-ticker change badge.
5. **Phase 5** — `user_prefs[portfolio.display_currency]` + FX path + per-currency degradation.
6. **Phase 6** — Allocation donut.

---

## Code locations

| Concern | File |
|---|---|
| DB models | `packages/server/src/openlia_server/db/models/content.py` (add `PortfolioQuote`, `PortfolioQuoteIntraday`, `PortfolioQuoteDaily`) |
| Alembic migrations | `packages/server/src/openlia_server/db/migrations/versions/` |
| Quote service | `packages/server/src/openlia_server/services/portfolio_quotes.py` (new) |
| Backfill service | `packages/server/src/openlia_server/services/portfolio_backfill.py` (new) |
| Market hours | `packages/server/src/openlia_server/services/market_hours.py` (new) |
| Scheduler executor | `packages/server/src/openlia_server/scheduler/executors/portfolio_prices.py` (new) |
| Scheduler registry | `packages/server/src/openlia_server/scheduler/registry.py` (add `PORTFOLIO_PRICE_REFRESH`) |
| Scheduler wiring | `packages/server/src/openlia_server/scheduler/wiring.py` (register executor + cron fires) |
| Routes | `packages/server/src/openlia_server/routes/portfolio.py` (add prefs, value-series, ticker-series; update analytics) |
| Frontend API client | `frontend/src/api/portfolio.ts` |
| Frontend page | `frontend/src/pages/PortfolioPage.tsx` |

---

## Known limitations (v1)

- No transactions ledger; share-quantity edits retroactively redraw the chart.
- Holiday calendar not implemented — small fetch waste on US/TWSE holidays.
- Historical FX not stored; multi-currency historical totals use current spot.
- Daily backfill is 5Y; selecting "5Y" timeframe for a portfolio younger than 5Y just clamps to inception.
- No global dedupe inside `/refresh-prices` — three users clicking refresh on AAPL within 1s triggers 3× EODHD calls.
