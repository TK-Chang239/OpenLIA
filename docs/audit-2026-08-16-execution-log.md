# Audit 2026-08-16 — Execution Log

Running record of the staged remediation of `docs/audit-2026-08-16.md`, executed autonomously via subagents. Each stage is its own branch + PR, verified green in CI, merged before the next. This log is the durable narrative; `docs/audit-2026-08-16.md` is the plan and the per-stage `*-notes.md` / `*-deferred.md` docs hold detail.

## Status at a glance

| Stage | Scope | PR | State |
|---|---|---|---|
| 0 | Public-exposure emergencies + un-red CI | #279 | **Merged** |
| 1 | Correctness bugs (portfolio, engines, scheduler) | #280 | **Merged** |
| 2 | Report rendering (PDF, tables, charts, tombstone, sanitization) | #281 | **Merged** |
| 3 | Company-mode / multi-user hardening | #282 | **Merged** |
| 4 | Documentation reconciliation | #283 | **Merged** |
| 5 | Incomplete features | #284 | **Open, CI running** |
| 6 | Open-source release | — | Not started |

## Stage 0 (#279, merged) — public-exposure + CI
- **0.1 History purge (copyrighted PDFs):** rewrote git history with `git-filter-repo` removing `個股報告/`, `產業報告/`, all `*.pdf` (47 broker PDFs + the Ray Dalio PDF + an orphaned test fixture); deleted 101 stale merged remote branches (recovery map in scratchpad); force-pushed rewritten `main` + 98 branches (the user ran the force-push — classifier-blocked for me; branch protection required temporarily allowing force-push). **REMAINING (user-only):** a GitHub Support request to GC the unreferenced blobs still reachable via `refs/pull/*/head`.
- **0.2** setup-wizard takeover spoof closed (real transport-peer capture before ProxyHeaders rewrite + `require_wizard_active` on `/setup/takeover`).
- **0.3** `/admin/guardrail-events` → `build_require_active_admin` (was any-authed read+wipe).
- **0.4** must-change-password gate enforced on 20 routers.
- **0.5** CI un-red: reformatted `test_auth_routes.py`, pinned `ruff==0.15.11` (root cause: unpinned ruff drifted the formatter); fixed a flaky `MorningBriefingSnapshotCard` test.
- **0.6** committed the demo-mode work, gitignored build cruft.

## Stage 1 (#280, merged) — correctness
- **1.A** Portfolio: repaired dead ticker search + 5Y backfill (kwarg mismatch `symbol`→`ticker`), manual-refresh wiping scheduler quote fields (`_KEEP` sentinel), EODHD env fallback, Home connect-EODHD state; total-P&L phantom loss (cost gated on price); multi-currency segregation (correctness-only, no FX — product decision); DST post-close capture (16:30 America/New_York).
- **1.B** Engines: `max_tokens` overflow clamp (4 sessions); RS prompt rewritten to real catalog (product decision); capability-override threaded into 6 web-search gates; EU scheduler connector key; shared `tool_dispatch.py` off-thread 120s cap in 4 runners.
- Process note: first attempt lost work to a subagent's file-restore gymnastics under a session-limit interruption; re-ran with hardened guardrails (never checkout/stash/restore; targeted tests only; strict file ownership; ignore cross-import errors). This guardrail set was used for all later stages.

## Stage 2 (#281, merged) — report rendering
Print `\!important` escape bug (TOC shipped in every PDF); table overflow wrappers; chart empty-guards + uniform scaling; **report disclaimer added to all exports** (v3/EU/MB had none — real liability); LLM-HTML sanitization (`html:False` with trusted chart-figure injection relocated after render); tombstone report UI + 410 message; `matplotlib`/`markdown-it-py` added to `openlia-core` deps; dead render code + 2 latent viewer crashes removed; `@tailwindcss/typography` installed. Caught two audit inaccuracies (the "dead v2 repo exports" were live; a naive sanitization flip would have broken charts).

## Stage 3 (#282, merged) — company-mode hardening
Skills per-user isolation (`DatabaseSkillStore`, system-toggle + folder-install admin-gated); cookie-Secure #257 (deduped helper + CLI plain-HTTP warning); `local` user blocked from admin reset on migration (product decision); admin self/last-admin disable guards + in-app promote/demote; invite public URL #258; admin rate-limiting. Investigation (`docs/audit-2026-08-16-stage3-notes.md`): graph flag safe, scheduler `user_id` correct, **NEW CSRF finding** — `GET /secretary/chat?q=` triggers an LLM run + persists a message with only the auth cookie (deferred; SSE-contract change).

## Stage 4 (#283, merged) — docs reconciliation
Rewrote the stale `planning/README.md` entry point (was a v2.2 build guide citing 5 dead paths); supersede banners on v2.2/v2.3 docs; wrote 4 missing page specs (ER v3, EU v2, Home, Memory) + fixed 5 stale specs; regenerated both route matrices from the live app (41 routers) + a coverage test; fixed false claims (`config.py` stub not loader; Fernet not AES-256-GCM); `.env.example` 17→58 vars; `projectStructure.md` 29→83 tables; GAPS stale banner.

## Stage 5 (#284, open — CI running) — incomplete features
All bounded work committed and pushed; PR #284 open.
- **5.D / 5.A.3 Retail Sentiment:** Import-from-Portfolio wired; dead setup review-endpoint removed.
- **5.C Macro Research:** real header date; no-op poll removed; dashboard list de-hardcoded via `listDashboards`.
- **5.B Panic Thermometer:** each section's edit callback now routes to its own drawer target (new `SettingsDrawer` `focus` prop expands the correct panel and scrolls to a sub-editor); added contract-safe milestone-date and status-override editors plus a Fed keywords editor (verified `PUT /config` round-trips `manual_override`/`milestone_date`/`params`); added an Off/1/5/15min header auto-refresh control sharing the drawer's state; derived the composite "red of total" from the live panel count. **ReleasesTable stays unrendered** — no live economic-calendar feed exists; its only source is a static mock, so rendering it would ship fabricated economic prints as live data (deferral recorded).
- **5.F engine:** positively-phrased source-diversity guidance (#176) in v3/EU/MB/RS prompts; native web-search cap made explicit and provider-local (Anthropic reads request then its own default; Gemini/OpenAI documented as no-wire-cap) and threaded into all four v3-family sessions; trimmed v3 `CATEGORY_INDEX` from 9 advertised categories to the 2 with real tools (`business_quality`, `forensic_ratios`), cleaning up the dangling references.
- **Verification:** core ruff clean + `import openlia` ok + `CATEGORY_INDEX` == 2 keys + 509 targeted engine/adapter tests pass; frontend `tsc` clean + build ✓ + full vitest 1369/1369.
- **Deferred** (per-item decisions in `-stage5-deferred.md`): MB 3-tab rebuild, Portfolio remake APIs, RS Evidence/Insights tabs, Home backlog, v3 connector-dispatcher access, dead-instruction-surface removal, Secretary/ER i18n, MB backlog P0s, Smart Mode, and the PT ReleasesTable feed.

## Stage 6 (not started) — open-source release
Ship the artifacts every doc promises (GHCR image, PyPI packages, git tags — issue #262; reconcile 3 inconsistent image names); merge the README rewrite; add SECURITY.md/CONTRIBUTING/issue templates + financial disclaimer; repo hygiene (root scratch docs, `/Users/tkchang` paths in source); first-run pass on a clean machine.

## Standing user-only / classifier-blocked items
- **0.1** GitHub Support GC request for `refs/pull/*/head` blobs.
- **1.B.6** issue hygiene: `gh issue close 98`, `close 109`, `comment 110`, `comment 176` (exact commands handed off in-conversation).
- PR merges: the auto-mode classifier blocks `gh pr merge` in fully-autonomous stretches; each merge so far was run after an explicit user "proceed".

## Operating notes
- Per-stage flow: branch from clean main → parallel subagents (hardened guardrails) → consolidated verification (core+server pytest, frontend build+vitest, ruff) → logical-group commits → push → PR → watch CI green → merge.
- Resume state of record lives in the memory file `project_full_audit_2026_08_16.md`; this log is the human-readable narrative.
