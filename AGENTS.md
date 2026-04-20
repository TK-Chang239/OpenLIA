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

# [OpenLIA] recent context, 2026-04-20 2:16pm PDT

Legend: 🎯session 🔴bugfix 🟣feature 🔄refactor ✅change 🔵discovery ⚖️decision
Format: ID TIME TYPE TITLE
Fetch details: get_observations([IDs]) | Search: mem-search skill

Stats: 50 obs (19,410t read) | 813,845t work | 98% savings

### Apr 20, 2026
S27 OpenLIA main branch post-merge code review — Phase 5 (LLM Runtime) and Phase 6 (Background Task Scheduling) quality assessment after git push/pull sync (Apr 20 at 9:32 AM)
S24 Switch to main branch to commit — Claude flagged risks before proceeding (Apr 20 at 9:32 AM)
S28 GitHub Branch Protection Ruleset Settings — Branch name pattern and recommended rules for protecting main (Apr 20 at 9:38 AM)
S31 claude-mem:timeline-report — Generate "Journey Into OpenLIA" narrative report from 110 persistent memory observations (Apr 20 at 9:52 AM)
260 11:34a 🔵 Two Parallel Auth Dependency Systems — middleware/auth.py vs auth/deps.py
261 " 🔵 ChatRunner and ReportRunner Tool Loop Is v1 — Single Round Only Despite Range(10) Guard
262 " 🔵 OpenLIA Phase 0–6 Full Audit — 581 Tests Green, Frontend Builds Clean, Ruff Clean
263 " 🔵 Phase 3 Data Requirements — Only equity_research Has Populated Manifest; 6 Other Departments Empty
264 " 🔵 LLM Resolution Chain — 4-Level Fallback with User Preference → Tier Default → Any in Tier → TierNotConfiguredError
272 12:02p 🔵 OpenLIA Phase 0–6 Audit — 7 Open Issues Before Phase 7+ Execution
273 " 🔵 OpenLIA Phase 7+ Plan Consistency Audit — 12 Drift Issues Block Execution
274 " ✅ Implementation Plans README Normalized With Cross-Plan Backend Contracts
275 " 🔵 OpenLIA Pre-Phase-7 Checklist — Remaining Items Before Execution
276 12:04p ⚖️ OpenLIA Backend Contract Documentation Task Created for Phase 7+
279 12:05p 🟣 OpenLIA Phase 7+ Remediation Work Queue — 8 Tasks Created
280 " ✅ OpenLIA Plans README — Cross-Plan Contracts Section Now Live (8 Contracts)
285 1:04p 🔴 FastAPI Auth Dependency Injection Syntax Fixed in Jobs and Notifications Routes
286 1:05p 🔴 Unused Imports Cleaned Up After Auth Dependency Syntax Fix
287 " 🔵 Full OpenLIA Test Suite Passes: 581 Tests
288 " 🔵 Env Var Mismatch: App Lifespan Uses OPENLIA_DATABASE_URL, Bootstrap Uses OPENLIA_DB_URL
289 1:06p 🔴 App Lifespan Unified to Use OPENLIA_DB_URL via resolve_db_url()
290 " 🔴 Secret Key File Creation Fixed: Atomic Write with O_EXCL|0600 Replaces Write-then-chmod Race
291 1:07p 🔵 SignupInvite Stores Raw Token, Not Hash — Unlike Session Model
292 1:08p 🔴 SignupInvite Model Column Renamed: token → token_hash for Secure Storage
293 " 🔵 admin.py Invite Routes Need Two Updates After token → token_hash Rename
294 1:09p 🔴 Invite Token Hashing Fully Implemented Across All Layers
295 " 🔴 Registration Tests Updated for token_hash: raw_token Stashed on Fixture Instance
296 1:10p 🔴 All Remaining Test Files Updated for SignupInvite token → token_hash Rename
297 " 🔵 uv Cache Permission Error: .git File in sdists-v9 Cache Dir
298 1:47p 🔵 OpenLIA Full Test Suite Passes at 581 Tests
299 " 🔵 LLM Runtime Tool Loop Intentionally Limited to One Round in v1
300 " 🔴 Multi-Round Tool Dispatch Enabled in ChatRunner and ReportRunner
301 " 🔵 FakeProvider Script Exhaustion Breaks Tool Loop Tests After Multi-Round Upgrade
302 1:48p 🔵 FakeProvider Script Architecture Exposed by Multi-Round Tool Loop
303 1:49p 🔴 Test Scripts Updated for Multi-Round Tool Loop — FakeProvider Turn Sequence Pattern Established
304 " 🔴 SQLModelRegistry Provider is_enabled Filter Added to SQL Queries and _load_row
305 1:50p 🔵 Route Handlers Use Raw db_session_factory() Without Context Manager — 38 Call Sites
306 " 🔵 Audit Documents Route Session Lifecycle Leak Pattern and Recommended Fix
307 1:51p ⚖️ Route Session Lifecycle Migration Deferred — Test Fixture Incompatibility
308 " ✅ Ruff Format Applied to test_routes_jobs.py
309 1:58p ✅ Pull Request Created with Task 9 Deferred to Next Workflow
310 " 🟣 Phase 0-6 Quality Audit Remediation Committed — 8 of 9 Findings Fixed
311 1:59p ✅ fix/phase-0-6-audit-remediation Branch Pushed to GitHub
S48 Create pull request for phase 0-6 audit remediation; note finding 9 deferred to next workflow (Apr 20 at 1:59 PM)
312 2:11p 🔵 GitHub CLI TLS Certificate Failure Blocks PR Status Checks
313 " 🔵 PR #9 (fix/phase-0-6-audit-remediation) Already Merged to Main
314 2:12p 🔵 PR #9 Merge Included auth/deps.py Deletion and Major Route Refactors
315 " 🔵 38 Unclosed db_session_factory() Call Sites Found Across Route Files
316 " ⚖️ Audit Prescribes session_dependency() Generator with Depends() Injection Pattern
317 2:13p 🔵 SessionLocal() Returns Bare Session — Routes Never Use Context Manager Protocol
318 " 🔵 Test Fixture Pattern lambda: db_session Completely Hides Session Lifecycle Bugs
319 " 🔵 routes/jobs.py Already Uses Correct Context Manager Pattern — Not in Scope for Task 9
320 " ⚖️ Task 9 Broken Into 6 Ordered Sub-Tasks for TDD Batch Migration
321 2:14p 🔵 middleware/auth.py require_auth is a Non-Generator Depends — Session Close Requires Different Fix
322 " 🟣 TDD Tests Written for make_session_dependency Helper Before Implementation

Access 814k tokens of past work via get_observations([IDs]) or mem-search skill.
</claude-mem-context>