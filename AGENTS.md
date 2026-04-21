<!-- code-review-graph MCP tools -->
## MCP Tools: code-review-graph

**IMPORTANT: This project has a knowledge graph. ALWAYS use the
code-review-graph MCP tools BEFORE using Grep/Glob/Read to explore
the codebase.** The graph is faster, cheaper (fewer tokens), and gives
you structural context (callers, dependents, test coverage) that file
scanning cannot.

### When to use graph tools FIRST

- **Exploring code**: `semantic_search_nodes` or `query_graph` instead of Grep
- **Understanding impact**: `get_impact_radius` instead of manually tracing imports
- **Code review**: `detect_changes` + `get_review_context` instead of reading entire files
- **Finding relationships**: `query_graph` with callers_of/callees_of/imports_of/tests_for
- **Architecture questions**: `get_architecture_overview` + `list_communities`

Fall back to Grep/Glob/Read **only** when the graph doesn't cover what you need.

### Key Tools

| Tool | Use when |
|------|----------|
| `detect_changes` | Reviewing code changes — gives risk-scored analysis |
| `get_review_context` | Need source snippets for review — token-efficient |
| `get_impact_radius` | Understanding blast radius of a change |
| `get_affected_flows` | Finding which execution paths are impacted |
| `query_graph` | Tracing callers, callees, imports, tests, dependencies |
| `semantic_search_nodes` | Finding functions/classes by name or keyword |
| `get_architecture_overview` | Understanding high-level codebase structure |
| `refactor_tool` | Planning renames, finding dead code |

### Workflow

1. The graph auto-updates on file changes (via hooks).
2. Use `detect_changes` for code review.
3. Use `get_affected_flows` to understand impact.
4. Use `query_graph` pattern="tests_for" to check coverage.


<claude-mem-context>
# Memory Context

# [OpenLIA] recent context, 2026-04-20 9:33pm PDT

Legend: 🎯session 🔴bugfix 🟣feature 🔄refactor ✅change 🔵discovery ⚖️decision
Format: ID TIME TYPE TITLE
Fetch details: get_observations([IDs]) | Search: mem-search skill

Stats: 50 obs (25,109t read) | 2,234,697t work | 99% savings

### Apr 20, 2026
S27 OpenLIA main branch post-merge code review — Phase 5 (LLM Runtime) and Phase 6 (Background Task Scheduling) quality assessment after git push/pull sync (Apr 20 at 9:32 AM)
S24 Switch to main branch to commit — Claude flagged risks before proceeding (Apr 20 at 9:32 AM)
S28 GitHub Branch Protection Ruleset Settings — Branch name pattern and recommended rules for protecting main (Apr 20 at 9:38 AM)
S31 claude-mem:timeline-report — Generate "Journey Into OpenLIA" narrative report from 110 persistent memory observations (Apr 20 at 9:52 AM)
S48 Create pull request for phase 0-6 audit remediation; note finding 9 deferred to next workflow (Apr 20 at 10:03 AM)
340 2:31p 🔴 Auth middleware `require_auth` gets `try/finally: db.close()` to guarantee session cleanup
341 2:32p ✅ Full server test suite green after complete session lifecycle refactor — 350 tests pass
342 " ✅ Full monorepo test suite green — 584 tests pass after session lifecycle refactor
343 2:33p 🔵 Ruff reports 40 B008 errors for `Depends()` in default arguments, plus 2 files need reformatting
344 " 🔵 All 40 ruff errors are B008 for `Depends()` — `ruff.toml` has `B` selected with no B008 exemption
345 2:34p ✅ ruff.toml updated to treat FastAPI `Depends`/`Query`/etc. as immutable calls, clearing all B008 errors
346 " ✅ Audit document updated: finding #7 marked resolved with full resolution summary
347 " 🔵 Full changeset for task 9: 12 modified + 3 new files, 290 insertions / 106 deletions on branch `fix/route-session-lifecycle`
348 2:35p ✅ Task 9 committed: `fix(routes): close DB sessions per-request via FastAPI dependency` — commit 46c66f6
349 " ✅ Branch `fix/route-session-lifecycle` pushed to GitHub — PR ready at TK-Chang239/OpenLIA
350 2:36p ✅ PR #10 created: "fix(routes): close DB sessions per-request via FastAPI dependency"
S49 Task 9: Route session lifecycle refactor — 38+ call sites across auth/admin/settings + test-fixture refactor (deferred from previous session) (Apr 20 at 2:36 PM)
351 7:59p 🔵 OpenLIA Codebase Graph Context for Phase 7 & 8 Review
352 8:01p 🔵 Phase 7 & 8 Change Set: 53 Frontend Files Committed to Main
353 8:05p 🔵 OpenLIA Planning Structure: Phase 7 = CLI Surface, Phase 8 = Frontend Shell
354 " 🔵 Phase 8 Frontend Shell: Full Source Review of All Implemented Modules
355 " ✅ AGENTS.md Updated with Code-Review-Graph MCP Tool Instructions
356 " 🔵 OpenLIA Codebase Community Structure: Backend-Dominant with Small Frontend Footprint
357 8:06p 🔵 Phase 7 CLI Surface Partially Implemented: Only serve/main Exist, Admin Subcommands Missing
358 " 🔵 Phase 8 Audit Note: Auth API Contract Mismatch Between Plan and Implementation
359 " 🔵 OpenLIA Full Backend Package Structure Confirmed Across Both Packages
360 8:07p 🔵 Phase 7 CLI Fully Implemented: 980+ Lines with All Sub-Apps and Commands
361 " 🔵 Phase 7 Wizard Reset: Uses Integer current_step=1 — Pre-Audit Drift Confirmed
362 " 🔵 CONFIRMED: Phase 8 Auth API Contract Mismatch — Frontend Uses Envelope Shape, Backend Returns Flat
363 " 🔵 Phase 8 Roadmap Status and Cross-Plan Contract Audit Summary
364 8:14p 🔵 OpenLIA Phase 7+ Plan Consistency Audit Reveals Critical Contract Drift
365 " 🔵 OpenLIA Phase 0-6 Quality Audit Found 7 Production-Readiness Gaps
366 8:15p 🟣 Phase 7-8 Implementation Review Audit Document Created
367 8:17p 🔵 OpenLIA Project Has Comprehensive Implementation Plan Structure (Phases 0–15)
368 8:29p 🔵 OpenLIA Phase 0-6 Quality Audit: Seven Critical Implementation Gaps
369 " 🔵 Phase 7+ Plan Consistency Audit: Cross-Plan Contract Drift Across Plans 8-15
370 " ⚖️ Cross-Plan Contracts Normalized and Locked in implementation-plans README
371 " 🔵 Phase 7-8 Post-Implementation Review: Three High-Severity Gaps Remain After Phase 8 Landing
372 8:31p 🔵 Plans 9-15 Body Code Still Contains Stale Patterns Despite Normalization Header Notes
373 " 🔵 Several Phase 0-6 Audit Issues Have Been Fixed in the Current Codebase
374 " 🔵 WizardState Model and CLI wizard reset Still Use Integer current_step Shape
375 " 🔵 Phase 11 Plan Has Normalization Notes but Body Still Creates Duplicate Admin Routes with Wrong Imports
376 " 🔵 LLM Admin Routes Are at /settings/admin/llm/* but Phase 11 Frontend Tests Hit /settings/models/*
377 8:34p 🔵 OpenLIA Planning Audit History Discovered
378 8:35p 🔵 OpenLIA Phase 0-8 vs Plan 9+ Consistency Audit: 7 High-Severity Blockers Found
379 8:36p ✅ Audit Document Written and Confirmed on Disk (569 Lines, Untracked)
380 8:59p 🔵 OpenLIA Codebase Architecture Overview via Code Review Graph
381 " ⚖️ OpenLIA Full-Stack Audit Plan Initiated with 8-Step Sequence
382 9:01p 🔵 OpenLIA Backend API Surface — Full Route Inventory
383 " 🔵 Frontend API Contract Gap — Only Auth and Notifications Wired
384 " 🔵 OpenLIA Database Schema — Full Model Inventory (3 Migrations, 30+ Tables)
385 " 🔵 Auth Middleware — Cookie-Based Session Validation with Dual-Mode Factory Pattern
386 " 🔵 LLM Runtime — ChatRunner and ReportRunner with Tool Loop and CancellationToken
387 " 🔵 Scheduler Architecture — APScheduler-Backed SchedulerService with Stubs for Unimplemented Departments
388 " 🔵 OpenLIA Deployment Profile — No Docker, uv Workspace + Vite Proxy, Two Deployment Modes
389 9:05p 🟣 OpenLIA Full-Stack Audit Documents Written — 7 Audit Files Committed

Access 2235k tokens of past work via get_observations([IDs]) or mem-search skill.
</claude-mem-context>