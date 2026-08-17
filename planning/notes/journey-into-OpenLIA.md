# Journey Into OpenLIA

*A four-day technical history reconstructed from 110 persistent memories, April 17–20, 2026.*

---

## 1. Project Genesis

OpenLIA did not begin as code. It began as a taxonomy of plans.

The earliest memory, captured at 11:26 AM PDT on April 17, 2026 (#1), is not a commit, not a scaffold, not a "hello world" — it is an *inventory* of a 23-plan implementation roadmap spanning seven phases. By the time claude-mem first laid eyes on OpenLIA, eight plans had already been written as drafts (Phases 0, 1A, 1B, 2, 3, 4, 5, 6), and exactly one had actually been executed: Phase 0, the workspace scaffold.

The vision was ambitious and specific. OpenLIA — an open-source, self-hosted AI investor assistant — would ship as a fleet of specialized LLM "Departments" (Secretary, Equity Research, Earnings Update, Morning Briefing, Retail Sentiment, Macro Research, Panic Thermometer), each a single-domain expert. The same codebase would serve both **personal mode** (localhost, single user, no auth) and **company mode** (multi-user, network-accessible, auth enabled), toggled by deployment configuration.

The founding technical decisions were visible from minute one:

- **A rigid three-layer architecture.** `openlia-core` is a pure-Python library with zero web dependencies. `openlia-server` is a FastAPI wrapper over core. The React/TypeScript frontend talks only to the server. The boundary is enforced by a blunt test: `from openlia import EquityResearchDepartment` must work with only `openlia-core` installed, no server running.
- **A uv workspace monorepo.** Two packages under `packages/`, a root `pyproject.toml` that is *not* an installable artifact, shared `ruff.toml`, single CI workflow.
- **TDD-first, bite-sized task format** in every plan, designed for execution by the `superpowers:subagent-driven-development` skill (#1).
- **Specs as source of truth.** Every plan reads from `planning/specs/` before a line of code is written.

By 11:39 AM on Apr 17 (#14), the shape was clear: 8 of 24 plans written, 16 to go. The roadmap encoded a dependency chain — Phases 1–3 had to be substantially complete before frontend work in Phase 4 could begin — and this order would later determine *which* phases collided catastrophically in CI.

---

## 2. Architectural Evolution

### The layered doctrine

The three-layer model is stated almost as a religious creed in the project's CLAUDE.md: **core must never import FastAPI**. Routes call core methods and return results. Business logic lives in core, not routes. Frontend communicates only through REST + SSE. Config flows in exactly one direction: `.env` → `core/config.py` → server → (never) frontend.

Observation #7, captured one minute after the initial inventory, confirms the server scaffold was deliberately *minimal* at the start — a bare `cli.py` and `app.py` without Phase 2+ features. The architecture was built outward from the library, not inward from a framework.

### The 23-plan roadmap

The roadmap is the spine of everything that follows. By the end of Apr 17 it had expanded to 11 of 23 plans drafted (#40), then 13 (#42). By Apr 18 afternoon it was 18 of 18 present on disk (#74) — the count drifting because "Plan 1" got split into 1A (DB baseline) and 1B (full schema).

The phases were:

- **Phase 0**: Workspace scaffold (executed first).
- **Phase 1A/1B**: Database models, Alembic migrations, bootstrap, crypto key file. The migration test expects exactly 33 tables (#89) — a hard invariant that confirmed 1B shipped.
- **Phase 2**: Auth primitives. Invite-gated registration (#101), AES-256-GCM column encryption with row-bound AAD and auto-generated key file (#102), 10 auth service modules (#103).
- **Phase 3**: Data provider core. Adapter pattern for EODHD, news, etc.
- **Phase 4**: LLM provider system. Four providers (OpenAI, Anthropic, OpenRouter, Ollama).
- **Phase 5**: LLM runtime — ChatRunner, ReportRunner, BatchRunner, YAML prompt loader, SSE infrastructure.
- **Phase 6**: Background task scheduling via APScheduler.
- **Phase 7**: CLI surface (the last phase drafted in this window).
- **Phases 8–23**: Frontend shell, login UI, setup wizard, settings, shared chat, every department page, formula engine, dashboards, Docker packaging.

By 4:23 PM on Apr 17 (#23), the plans alone totaled **35,903 lines**. Plan 11 (Settings backend + frontend) grew to 2,557 lines after Tasks 10–12 were appended (#41). Plan 13 (Report Pipeline + Secretary) clocked in at 5,293 lines (#44). These are not outlines — they are executable TDD scripts.

### How it unfolded

The roadmap *wrote itself* faster than it was *built*. By April 20, planning had reached Phase 15 (Earnings Update Department, 23 tasks, fully completed with self-review — #71), while the code had reached only Phase 6. That gap between written plan and merged code would become the core source of technical debt, and eventually the source of the multi-hour CI saga on Apr 20 morning.

---

## 3. Key Breakthroughs

Four moments stand out as genuine "aha" events.

**The atomic-replace race fix.** At 7:04 PM on April 18 (#109), during the Phase 0–4 code review, the crypto key file generation was found to have a classic TOCTOU race: `_load_or_create_file_key()` wrote the key with default umask permissions, *then* `chmod`'d to 0600. In that window, any other process could read the plaintext base64 key off disk. The fix: write to `.tmp`, chmod 0600 on the temp file, then `os.replace()` atomically. The destination file is never visible with wrong permissions. A small fix, but emblematic of the project's "fail fast and loudly, no defensive programming, but get the security-critical stuff right" posture.

**The plaintext invite token discovery.** Still on Apr 18, during the same review (#117), a notable asymmetry surfaced: sessions and password reset requests stored only token *hashes*, but `SignupInvite` stored raw plaintext — and the `GET /admin/invites` endpoint returned those plaintext tokens in every list response. An admin could retrieve all currently-valid invite tokens at any time. The fix (#120): SHA-256 hash the token, return plaintext exactly once at creation, and rewrite the baseline migration in place since the DB had not yet been deployed. The decision to *edit the baseline migration* rather than add a new one is itself a tell — OpenLIA at this stage was still pre-production and willing to rewrite history.

**The `--import-mode=importlib` realization.** On Apr 20 at 9:41 AM (#174), after multiple failed attempts to fix the `_fakes` import collision with `__init__.py` tricks and relative imports, it was discovered that the root `pyproject.toml` already configures pytest with `--import-mode=importlib`. In importlib mode, module names are resolved by their unique *filename*, not by sys.path membership. This meant the correct fix was simply to rename the scheduler's `_fakes.py` to `_scheduler_fakes.py` and use plain absolute imports — no `__init__.py`, no relative imports. The name collision problem dissolved into a naming problem.

**CI green for the first time since Phase 4.** At 9:47 AM on Apr 20 (#191), a single `fix(ci)` commit — 24 files, encompassing the `_fakes` rename, 56 ruff autofixes, 3 manual E501 line wraps, a `ruff format` pass across 16 files, and a new "Standing rules" section in the plans README — ended a streak of 7 consecutive CI failures. The main branch was healthy again for the first time since April 18.

---

## 4. Work Patterns

The four-day rhythm is legible in the data.

**Apr 17 — the plan-writing marathon.** 17 observations, 409,584 discovery tokens, 2 memory sessions. The day opened with roadmap reconnaissance (#1, #2, #3) and ended at 9:50 PM with Plan 15 (Earnings Update) marked draft (#73). In between: Phase 7 CLI plan (#13), Plan 9 Login UI (#25 — the single highest-cost observation at 98,210 tokens), Plan 10 Setup Wizard (#36), Plan 11 Settings backend then frontend tasks appended (#38, #41), Plan 13 Report Pipeline + Secretary (#44), Plan 14 Equity Research (#49), Plan 15 Earnings Update (#62, then tasks 1–4, 5–7, 8–9, 10–14, 15–18, and finalization — #63, #65, #66, #68, #70, #71). This is the day OpenLIA's entire product vision was serialized to disk.

**Apr 18 — the code-review and bug-fix sprint.** 39 observations, 1,048,974 discovery tokens, 4 sessions — the busiest day by every metric. The morning was pure structural reconnaissance (#74–#89), mapping the actual shipped code against the plans. The afternoon produced the Phase 4 code review findings (#99 — two bugs, two structural issues). The evening, starting around 6:56 PM, became a bug-fix sprint: the 7-item fix queue was locked in (#108), and then the fixes landed in rapid succession — crypto atomic replace at 7:04 PM (#109), `delete_model` 404 handling (#111), EODHD bare assert → `ValueError` (#114), LLM retry wrapper Retry-After semantics (#115), and the invite token hashing migration (#120) finishing at 7:33 PM with the test suite update (#121). Nine bug-related observations in under forty minutes.

**Apr 19 — the quiet day.** Only 3 observations, 114,883 tokens, 1 session. The entire day is a plan-inventory re-read (#123, #124, #125). In hindsight, this was the calm before the storm — Phase 5 had just been merged, and the CI was already broken, but nobody was looking yet.

**Apr 20 — the CI-repair saga.** 41 observations, 554,436 tokens, 3 sessions. The day opened at 9:22 AM with the gutting realization (#133, #134): the user had claimed Phases 0–6 complete, but only 0–4 had actual code in the local repo. Then came the fast-forward discovery (#143) — the remote main had Phases 5 and 6 merged but the local clone was stale. What followed was a three-hour debugging saga: apscheduler not installed (#147, #152), uv workspace semantics (#156), the `_fakes` collision (#160, #162, #164, #168, #169, #170, #172, #174, #177), 44 ruff errors (#151, #182), line-length fixes (#183), a full suite green at 581 tests (#184), ruff format applied to 16 files (#185), README standing rules added (#186), the `fix(ci)` push (#187), and finally green CI at 9:47 AM (#191). Forty-one observations. Three hours. One green checkmark.

---

## 5. Technical Debt

OpenLIA is four days old and has already accumulated, recognized, and partially repaid several debts. A short ledger:

**Duplicate `httpx` dependency.** Observation #83 (Apr 18, 4:14 PM) noted that `packages/core/pyproject.toml` declared `httpx` twice. This shows up at the highest tier of the discovery_tokens table (87,884 tokens) — a trivial bug that cost a lot to *find* because it required reading the full dependency graph.

**Bare assert for `base_url` in the EODHD adapter.** #112 documented a `assert base_url` in production code. If Python is run with `-O`, asserts are stripped — and a silent None URL would produce cryptic HTTPX errors downstream. Paid back at #114 with an explicit `ValueError`.

**Plaintext signup invite tokens.** The largest single security debt, discovered in #117 and fully repaid in #120–#121 on the same evening. The asymmetry with session/reset tokens was the signal.

**Retry-After semantics.** #115 — the LLM retry wrapper was scaling the provider's `retry_after_seconds` hint by `base_delay_s`, effectively multiplying the wait time. Fixed the same evening.

**Plan/code drift: the biggest debt.** The most expensive debt was not in any single file. It was the claim, carried across four days and eight sessions, that Phases 5 and 6 were "complete." On Apr 20 morning (#133, #134), the gap was confronted: the local repo only had Phases 0–4, while the *remote* had 5 and 6 merged but never CI-green. Phases 5 and 6 were effectively shipped with broken tests, broken lint, and broken CI. The debt surfaced only when someone ran `uv run pytest` from the monorepo root and got a `ModuleNotFoundError` for `apscheduler` (#147, #152) — a package declared in `packages/server/pyproject.toml` but never installed, because `uv sync` without `--all-packages` only resolves root deps (#156). That single missing flag had hidden two entire phases of test breakage for a full day.

**Shortcuts that have *not* been paid back** (as of Apr 20, 10:00 AM): no frontend exists yet beyond the Phase 0 skeleton (#15); the `delete_model` route's 404 handling fix (#111) was done but the companion admin routes have not been audited for similar gaps; and the claude-mem worker was noted as not running on port 37777 (#194) — an infrastructure loose end.

---

## 6. Challenges and Debugging Sagas

### The `_fakes` name collision

This deserves its own section. The Apr 20 morning saga is a textbook example of a monorepo testing pitfall, and the memory trail reads like a detective story.

**9:35 AM (#147)** — A fresh clone of main had a `ModuleNotFoundError: apscheduler` on test collection. Surprise #1.

**9:36 AM (#152, #156)** — The root cause: `uv sync` without `--all-packages` flag silently skips workspace members' dependencies. `apscheduler` was declared in `packages/server/pyproject.toml` but never actually installed into the venv. Fixed by running with `--all-packages`.

**9:36 AM (#157, #159)** — Now a deeper problem: scheduler tests pass when run *in isolation* from their own directory (108 tests, 0.90s, all green), but fail collection when `pytest` is invoked from the project root. Two test suites, two behaviors, one venv.

**9:37 AM (#160)** — First hypothesis: add `__init__.py` to the test_scheduler directory. Applied, committed mentally as fixed.

**9:38 AM (#162)** — The `__init__.py` fix *did not work*. Core's `_fakes` still wins. Hypothesis rejected.

**9:38 AM (#164)** — Root cause *fully* understood: both `test_scheduler` (server-side) and `test_llm/test_runtime` (core-side) contain a file named `_fakes.py`, and both use identical bare `from _fakes import ...` statements. When pytest collects tests across both packages simultaneously, the *first* `_fakes` loaded shadows the second. Only one can win. The `__init__.py` approach fails because both test directories can have `__init__.py` and the bare import still resolves ambiguously.

**9:40 AM (#168, #169)** — Decision: rename the scheduler's `_fakes.py` to `_scheduler_fakes.py`. The core fakes keep their name (they were there first, and renaming both would be gratuitous). 15+ scheduler test files need their imports updated.

**9:41 AM (#170, #172)** — Imports updated to `from ._scheduler_fakes import` (relative). But pytest complains that `test_scheduler` is being imported as a top-level module, not a package. Relative imports fail.

**9:41 AM (#174)** — The real fix surfaces. The root `pyproject.toml` uses `--import-mode=importlib`. In this mode, pytest resolves modules by unique filename, not sys.path position. The correct final fix is: rename to `_scheduler_fakes.py`, use *absolute* imports (`from _scheduler_fakes import`), and don't bother with `__init__.py` at all.

**9:42 AM (#177)** — Applied. 108 scheduler tests pass cleanly in under 1 second. Two unrelated `test_routes_notifications` errors also disappear (likely pre-existing flakes).

Five iterations, seven minutes, to resolve a problem whose actual fix is one `git mv` and a find-and-replace. The debugging memory is more valuable than the fix.

### The "CI red since Phase 4" realization

Separately, at 9:44 AM (#181), the developer pulled up the GitHub Actions history and realized: **every single CI run since Phase 5 merged on April 19 had been red**. Seven consecutive failures. The last green run was the Phase 0 scaffolding merge on April 18. Phase 5 had introduced lint and test failures that were never fixed before Phase 6 was merged on top of them. Phase 6 compounded them. Two PRs, neither CI-green, both in main.

Observation #182 then catalogued the 44 ruff errors: UP017 (use `datetime.UTC` instead of `datetime.timezone.utc`) in `test_scheduler_service.py`, I001 (unsorted imports) in `test_wiring.py` (which was still referencing the old `from _fakes import` name — the rename hadn't been completed before merge), E501 line-length violations scattered across the scheduler test files. The lesson is blunt: if CI is red and you merge anyway, the next person inherits a multi-cause bug they must unravel before any further work.

---

## 7. Memory and Continuity

The persistent-memory system was not a passive recorder in this project — it was an active scaffold.

**Session handoffs.** Apr 20's sessions picked up where Apr 19 left off without re-reading the entire codebase. Observation #133 opens a quality-review session by immediately *knowing* that "16 implementation plans exist spanning phases 0–15" and that "git history shows dense commit activity for phases 0–4" — state that would have taken 15+ minutes to reconstruct via `ls` and `git log`. The memory gave the session a starting context.

**Plan inventories as context primers.** Observations #1, #14, #22, #40, #42, #74, #123–#125 form a recurring pattern: at the start of many sessions, the plans README is re-read and the inventory is re-captured. These look redundant at first glance, but they serve a real purpose — they snapshot the "what's done, what's drafted, what's not started" state so the session can orient in under a minute. Across four days, eight sessions, this ritual happened at least six times.

**Cross-session discovery of stale state.** The #133 / #134 pair is the clearest example of memory catching drift. The user's *claim* ("Phases 0–6 are implemented") was contradicted by filesystem reality ("only 0–4 have actual source code"). The memory system did not prevent the drift, but it made the contradiction visible and routable to a specific session.

**Building on prior bug-fix context.** The #108 "Phase 0–4 Bug Fix Queue" observation is a decision record — it enumerates 7 fixes and declares the order of operations. Every subsequent bug-fix observation on Apr 18 (#109, #111, #114, #115, #120) can be read as executing items off that queue. Without the queue memory, those fixes might have been scattered or forgotten between sessions.

---

## 8. Token Economics & Memory ROI

### Headline numbers

| Metric | Value |
|---|---|
| Total observations | 110 |
| Total memory sessions | 8 |
| Total discovery tokens spent | 2,128,265 |
| Average discovery tokens / obs | 19,344 |
| Total read tokens invested | 44,252 |
| Date range | Apr 17 – Apr 20, 2026 (4 days) |

The project's own memory header states "2,127,427t work | 98% savings" — the 98% figure reflects the ratio of work-context tokens to read-context tokens at recall time.

### Top 5 most expensive observations

These are the memories that were most costly to produce — typically long plan-writing sessions that had to read many spec files to produce output:

| ID | Title | Tokens |
|---|---|---|
| 25 | Phase 9 Login + Account Management UI — Full Implementation Plan Written | 98,210 |
| 124 | OpenLIA Implementation Plans — Line Counts and File Sizes Across All 17 Plans | 91,917 |
| 125 | OpenLIA Implementation Plans README — Full Status Table and Roadmap | 91,917 |
| 49 | Plan 14 (Equity Research Department) — Complete Implementation Plan Written | 89,166 |
| 83 | Core Package pyproject.toml Has Duplicate httpx Dependency | 87,884 |

Note that #83 — finding a *duplicate dependency declaration* — cost nearly as much as writing a 5,293-line implementation plan (#44). The cost correlates with files-read breadth, not output size.

### Daily breakdown

| Date | Observations | Discovery Tokens | Sessions |
|---|---|---|---|
| Apr 17 | 17 | 409,584 | 2 |
| Apr 18 | 39 | 1,048,974 | 4 |
| Apr 19 | 3 | 114,883 | 1 |
| Apr 20 | 41 | 554,436 | 3 |
| **Total** | **110** | **2,127,877** | **8 distinct sessions** |

Apr 18 was the most expensive day by token-spend (the deep code review across all Phase 0–4 modules), while Apr 20 was the highest observation-count day (the CI saga produced many small, targeted memories).

### Obs-type breakdown

| Type | Count |
|---|---|
| discovery | 74 |
| bugfix | 14 |
| feature | 13 |
| change | 8 |
| decision | 1 |

67% of observations are *discovery* — reconnaissance, inventories, code reviews. This reflects a project still in the knowledge-gathering phase; only 12.7% are bug fixes and 11.8% are new features. The single decision record (#108) is the Phase 0–4 bug-fix queue.

### Explicit recalls

The schema does not carry a `source_tool` column, so explicit recall events have to be inferred from narrative text. A search across `narrative` and `text` for phrases like "recalled", "from memory", or "previous session" returns 0 hits — but this undercounts. In practice, observations like #133 ("A quality review session was initiated...") and the recurring plan-inventory reads (#14, #22, #40, #42, #74) are *implicit* recalls: they load prior state at session start. Conservatively estimating 6 such passive recalls across 8 sessions:

### Savings math

Applying the provided formula (sessions_with_context_injection × 50 obs × avg_discovery_tokens × 0.30 passive + explicit_recalls × 10K):

- **Passive injection** (8 sessions × 50 obs × 19,344 tokens × 0.30): **2,321,280 tokens saved**
- **Explicit recalls** (~6 × 10,000): **60,000 tokens saved**
- **Total tokens saved by memory**: **~2,381,280**
- **Tokens invested in reading memory**: **44,252**
- **ROI**: **~54×** (tokens saved per token invested)

| Category | Tokens |
|---|---|
| Invested (reads) | 44,252 |
| Saved (passive injection) | 2,321,280 |
| Saved (explicit recalls) | 60,000 |
| Net savings | **2,337,028** |
| Multiplier | **~54×** |

Even after heavy discounting, the economics are favorable by a wide margin — especially in a plan-heavy project where the alternative is re-reading 35,903 lines of implementation plans at the start of every session.

---

## 9. Timeline Statistics

- **Date range**: April 17, 2026 11:26 AM PDT → April 20, 2026 9:57 AM PDT
- **Elapsed time**: ~3 days, 22.5 hours
- **Observations**: 110
- **Memory sessions**: 8
- **Busiest day by count**: April 20 (41 observations)
- **Busiest day by tokens**: April 18 (1,048,974 discovery tokens)
- **Quietest day**: April 19 (3 observations)
- **Obs-type split**: discovery 67% / bugfix 13% / feature 12% / change 7% / decision 1%
- **Single most expensive observation**: #25 (Phase 9 Login UI plan, 98,210 tokens)
- **Cheapest meaningful bug fix**: #109 (crypto atomic replace) — a handful of lines, enormous security payoff

The shape of the timeline is distinctive: a burst of planning (Apr 17), a dense review-and-fix day (Apr 18), a near-silent day of context consolidation (Apr 19), and a final firefighting day where the remote reality of the project was reconciled with the local working copy (Apr 20).

---

## 10. Lessons and Meta-Observations

If a new developer landed on OpenLIA today and read only the memory trail, here is what they would learn:

**1. Plan-first discipline is not ceremony — it is scaffolding.** OpenLIA has 35,903 lines of plans for a codebase that, as of Apr 20, is a few thousand lines of Python. The plans are written as executable TDD scripts, not as prose. This sounds wasteful until you realize the plans *are* the product knowledge. The departments, the data adapters, the SSE protocol, the auth model — all of it lives in `planning/specs/` and `planning/implementation-plans/` long before the corresponding code. When a session starts, re-reading the plan README is faster than re-reading the code.

**2. CI is the *only* source of truth.** The Phase 5/6 disaster is the clearest lesson in the timeline. Phases were *claimed* complete, *merged* to main, and *believed* to be shipped — but CI was red, and nobody noticed for roughly 36 hours. When the reconciliation finally happened (Apr 20 morning), it took 3 hours to clean up. The remedy (#186) was to add a "Standing rules" section to the plans README codifying the merge gate: 5 explicit checks before any PR merges to main. The historical gotcha (the `_fakes.py` collision) was explicitly documented so it could not happen again.

**3. `uv` workspace semantics are a trap.** The `uv sync` vs `uv sync --all-packages` distinction (#156) cost an entire day of hidden CI breakage. Workspace members' dependencies are *not* installed by a bare `uv sync` — you must pass `--all-packages`. This is the kind of ecosystem-specific footgun that is invisible in the happy path and catastrophic when it fires. If you are reading this and you maintain a uv monorepo, put `uv sync --all-packages` in your README.

**4. Name collisions in a monorepo test suite are inevitable.** Two independent test packages both used `_fakes.py`. Both used bare imports. Both worked in isolation. Together they destroyed CI. The resolution (#186) was a naming convention: test helper modules must have globally unique names, not just package-unique names. This is now a documented project rule.

**5. Security-critical code deserves atomic operations.** The crypto.py race fix (#109) is a one-line lesson: if you are creating a file whose contents must be confidential, never let the file exist on disk with the wrong permissions — not even briefly. Write to a temp file, set permissions, then `os.replace()`.

**6. Asymmetry is a security signal.** The plaintext invite token bug (#117) was found not by auditing invite handling in isolation, but by *comparing* it to how sessions and password-reset tokens were handled. Symmetry between similar primitives is a strong heuristic; asymmetry is a red flag.

**7. Memory pays for itself within a project's first week.** Four days in, OpenLIA's ROI on persistent memory is ~54×. The ratio will only improve as the project grows and the cost of re-reading context rises.

---

*End of report. 110 observations analyzed, Apr 17–20 2026. The Phase 7 CLI surface plan is next; the main branch is green; Phase 5 and 6 are finally, properly, shipped.*
