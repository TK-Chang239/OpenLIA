# Frontend Demo Mode — Design

A fake-data build of the OpenLIA frontend so anyone can click through every app
page and feel the full product with no backend, no API keys, and no risk.

## Goal

Ship a static, self-contained demo of the existing frontend. A visitor opens it,
lands on Home, and can navigate every in-app page — all seven departments plus
Portfolio, Repository, Memory, and Settings — populated with believable fake
data. Streaming generation replays itself live. Nothing mutates. Deployable to
any static host and linkable from the landing page.

## Non-goals

- No login, register, or setup-wizard pages (gates are bypassed).
- No real LLM or data-provider calls; no real report generation.
- No persistence — refreshing resets everything.
- No changes to the real app's runtime behavior when the demo flag is off.

## Key decisions (from brainstorming)

- **Build:** demo mode inside the existing frontend behind `VITE_DEMO_MODE`, not a
  forked copy. One source of truth, no drift.
- **Fidelity:** full live replay of streaming cockpits (Equity Research, Morning
  Briefing, Earnings Update) and Secretary chat.
- **Interactivity:** fully read-only. Reconciled with live replay as **auto-play**:
  replays start on page load; the visitor never types or clicks "Generate";
  inputs and mutating controls are disabled.
- **Scope:** app pages only — no auth/wizard pages.

## Architecture

### One flag, two shims

The build is the normal frontend compiled with `VITE_DEMO_MODE=true`. At boot, in
`main.tsx`, before React renders, `installDemo()` runs when the flag is set and
installs two global interceptors:

1. **`globalThis.fetch`** is replaced by a demo router. Every request to `/api/*`
   (whether via `fetchJson`, the legacy `_request`, or the chat stream's direct
   `fetch`) is matched by method + path and answered from fake data. Responses are
   real `Response` objects: JSON for normal endpoints, or a streaming
   `ReadableStream` body emitting SSE frames for the chat stream endpoint.
   Non-`/api` requests fall through to the original `fetch`.

2. **`globalThis.EventSource`** is replaced by `DemoEventSource`, a minimal,
   spec-shaped shim. Based on the requested URL it schedules a scripted sequence
   of named events (`run.started`, `tool.called`, `tool.completed`,
   `section.written`, `chart.emitted`, `run.completed`) on timers, then closes.
   The notifications stream opens and stays silent.

Both shims read from the same fake-data modules, so a report shown in a list
matches the report the cockpit "generates."

### Code layout (all new, all under the flag)

```
frontend/src/demo/
  installDemo.ts        # entry: installs fetch + EventSource shims; no-op if flag off
  fetchRouter.ts        # method+path -> Response (JSON or stream)
  DemoEventSource.ts    # EventSource shim replaying per-URL scripts
  streams.ts            # scripted SSE sequences + chat token stream builder
  clock.ts              # fixed "as of" date + small timing helpers
  DemoBadge.tsx         # sidebar "Demo - illustrative data" badge + disclaimer
  data/
    bootstrap.ts        # session(404), setup(status), dept-health
    home.ts
    chat.ts
    equity-research.ts
    earnings-update.ts
    morning-briefing.ts
    retail-sentiment.ts
    macro-research.ts
    panic-thermometer.ts
    portfolio.ts
    repository.ts
    memory.ts
    settings.ts
```

Nothing in `demo/` is imported unless `VITE_DEMO_MODE` is set (a single guarded
dynamic import in `main.tsx`), so the production bundle and tests are unaffected.

### Bootstrap gate handling

The app makes two gating calls on first load; the demo answers them to land
straight in the app in no-auth personal mode:

- `GET /api/auth/session` -> `404` (triggers personal mode + synthetic local user)
- `GET /api/setup/status` -> `{ wizard_completed: true, mode: "personal", ... }`
- department health -> all departments enabled/healthy

Login/register/wizard routes still exist in the router but are never linked and
never reached.

## Read-only + auto-replay behavior

- **Streaming pages** open with a run already in progress that auto-replays to
  completion via `DemoEventSource`, then shows the finished report. A finished
  report also opens in the viewer so the page is rich immediately. An optional
  quiet "Replay" affordance may re-trigger the script (never a real generate).
- **Secretary** shows a scripted session; the last assistant turn auto-streams
  token-by-token on load. The chat input is disabled ("Chat is disabled in the
  demo").
- **Mutating controls** (save to repo, delete, edit schedule/settings, add
  connector, run-now) render disabled with a quiet "Demo" tooltip. Where
  disabling is impractical, the handler is a silent no-op.
- **Search/filter that runs client-side** (Repository) stays fully functional over
  the seeded list — read-only and genuinely useful.

## Per-page fake-data inventory

- **Home** — time-of-day greeting (client date), Morning Briefing snapshot (lede,
  rating, four metrics), ticker strip, portfolio glance sparkline + day change,
  suggested grid (static), recent reports strip.
- **Secretary** — session list; one multi-turn conversation with tool-call chips
  and a report thumbnail; final reply auto-streams.
- **Equity Research** — runs list; one auto-replaying run; one finished
  multi-section report (sections, charts, sources) rendered in the viewer.
- **Earnings Update** — watchlist cards, recent earnings notes feed, one
  auto-replay, read-only schedule.
- **Morning Briefing** — hero briefing, feed grouped by recency, cabinet
  templates/instructions, read-only schedules, one auto-replay.
- **Retail Sentiment** — 12-metric dashboard (Overview / Evidence / Insights) for
  a couple of watchlist tickers.
- **Macro Research** — Summary tab + five Dalio framework dashboards (T1 Debt
  Cycle, T2 Four Seasons, T3 All-Weather, T4 World Order, T5 Five Forces) with
  regime bars, score tables, verdict pills.
- **Panic Thermometer** — five stress panels (Oil, Inflation, Fed Language, Wage
  Growth, Diplomacy) with green/amber/red status rolling into a composite threat
  level; threshold-rule viewer.
- **Portfolio** — US and Taiwan books; value series across 1D/1M/3M/1Y/ALL; P/L,
  KPI band, holdings table.
- **Repository** — seeded library across departments/dates; working full-text
  search and department/date filters.
- **Memory** — pending proposals + confirmed beliefs.
- **Settings** — user prefs, models list, connectors list; all read-only.

## Dataset persona

A single fictional investor with a tech-tilted book. US holdings: NVDA, AAPL,
MSFT, GOOGL, AMZN, PLTR. Taiwan holdings: TSMC (2330.TW) and a couple of peers.
Real ticker symbols with clearly illustrative, internally consistent numbers,
frozen to a fixed "as of" date (defined in `clock.ts`) so nothing looks stale.

## Honesty + wayfinding

A small "Demo - illustrative data" badge replaces the version line in the sidebar
footer, with a one-line "not real market data, not investment advice" note. This
keeps the demo honest without adding chrome.

## Deployment

- New script `build:demo` -> `VITE_DEMO_MODE=true vite build --outDir dist-demo`.
- `dist-demo/` is fully static: runs under `vite preview` and deploys to any
  static host. Add an SPA fallback (`404.html` copy of `index.html`) so deep links
  resolve on hosts like GitHub Pages.
- Later, link it from the landing page as the "Explore the departments" / live
  demo target.

## Testing

- Demo code is plain TypeScript with unit-testable seams: `fetchRouter` (path ->
  response) and `DemoEventSource` (script -> event order).
- Smoke tests: demo boots to Home; each department route renders without throwing;
  one replay reaches `run.completed`; Repository search filters the seeded list.
- The existing test suite must stay green — demo modules are import-guarded, so
  real code paths are untouched.

## Build order

1. Scaffold `installDemo`, `fetchRouter`, `DemoEventSource`, `clock`, and the
   `main.tsx` guarded import. Wire bootstrap fixtures (session/setup/health) so the
   app boots to Home. Add `build:demo` + SPA fallback. Prove it boots.
2. Fill fixtures per department (parallelizable): Home, Portfolio, Repository,
   Memory, Settings first (static-shaped), then the streaming departments with
   their replay scripts.
3. Add the Demo badge/disclaimer and smoke tests. Verify `build:demo`, then a
   click-through pass.
