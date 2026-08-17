# Stage 5 — Deferred backlog (audit 2026-08-16)

Stage 5 of `docs/audit-2026-08-16.md` covers "incomplete features." Autonomous execution did the **bounded fixes and completions** (Panic Thermometer editors + Releases table + header refresh; Macro Research header/poll/dashboard-list; Retail Sentiment Import-from-Portfolio; Setup wizard dead-endpoint cleanup; engine source-diversity guidance + web-search cap + v3 category trim) and **deferred the large speculative builds** below, with the product decision recorded for each. These are not regressions — they are pre-existing gaps consciously scheduled for later, so the branch stays shippable.

## Deferred, with decision

| Item | Decision | Why deferred |
|---|---|---|
| **5.A.1 Morning Briefing 3-tab rebuild** (Archive/Chat/Settings, viewer-split chat, Report Sections / Custom Sections / Notes UI) | **Accept the shipped single-feed + modals shape**; amend `MorningBriefingsPageSpec.md` to match rather than build the specced tab UI. | Largest single frontend delta in the audit; the shipped feed + Schedules/Library/Run-Now modals are functional. Building the 3-tab UI is speculative work with no user demand signal. |
| **5.A.4 Secretary / ER v3 i18n** (hardcoded English in `SecretaryPage.tsx`, `EquityResearchV3.tsx`) | Do later. | Bilingual is in scope but this is polish, not a correctness or security gap; bounded but sizable string-extraction work. |
| **5.C Macro Research "Smart Mode"** (LLM threshold self-adjustment) | Defer. | Specced (Function #4) but referenced nowhere in the frontend; a new feature, not a fix. |
| **5.D Retail Sentiment roadmap** — Evidence + Insights tabs, tab bar, all-ticker heat map, Metrics Deep-Dive drawer, 21+-ticker cost warning; dev-backlog Gaps 2-8 (per-source breakdown, evidence rows, score-impact decomposition, narrative clustering, 30d buzz baseline, engagement weighting, unified alerts) | Defer; only Import-from-Portfolio done now. | On-plan per the RS redesign's R5 ("ship engine + one view, defer the rest"); large multi-view build. |
| **5.E Portfolio remake deferred APIs** — holding timeseries, trade log, Lia alerts/verdicts, repo full-text search, cash holding type; KPI Day-P/L cell; NAV vs-SPX / Drawdown / Exposure tabs. Minor: single-group allocation enforced client-side only, dead `PortfolioHolding.name` column, no "Market closed" indicator, negative caching in PriceCache | Defer. | Mostly new backend API surfaces (a remake roadmap), not bounded fixes. The Stage 1 correctness fixes already repaired the *broken* portfolio behaviors. |
| **5.F.2 v3 connector-dispatcher access** (v3 can only reach EODHD, not Connectors-UI connectors, unlike every sibling engine) | Defer (needs careful design). | Real gap, but it changes the flagship engine's tool surface; warrants a deliberate design pass rather than an autonomous edit. The advertised-category trim (done) removes the misleading part now. |
| **5.F.3 v3-family text-only-turn hard-fail** (consider legacy reminder-and-continue) | Defer. | Behavior/UX choice; the current hard-fail is safe, just less forgiving. |
| **5.F.4 Dead instruction surfaces** — `equity_research.yaml` report slots, RS/MR batch prompts, `prompts/macro_research/*.yaml`, `subagent_runner.py` (662 lines), legacy EU v1 route | Document as intentionally-kept for now; do not delete autonomously. | Several are reachable via env flags (`OPENLIA_USE_SUBAGENT_RUNNER`) or are boot-validated; deleting risks breaking a reachable path. Needs a careful, tested removal pass. |
| **5.F.5 Morning Briefing backlog P0s** (MB-1 truncation continue-pass, MB-2 Anthropic json_schema) | Re-verify then decide. | The backlog predates the `report_mb` rework; must be re-checked against the current engine before building (may already be resolved). |
| **5.G Home backlog** — MB snapshot API, personalized suggestions, live recent pills, topbar status row | Defer. | Larger API builds (`dev-backlog/home.md`); the Home page already renders live data for its wired blocks. |

## Cross-reference
- CSRF finding on `GET /secretary/chat?q=` — see `docs/audit-2026-08-16-stage3-notes.md` (deferred; SSE contract change).
- Static HTML report fallback fidelity (2.6) — deferred in Stage 2 (misconfigured-deployment-only path).
- 1.B.6 issue hygiene (`gh` close/comment for #98/#109/#110/#176) — pending; `gh` writes are classifier-blocked, handed to the maintainer.
