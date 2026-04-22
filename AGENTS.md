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

# [OpenLIA] recent context, 2026-04-22 10:45am PDT

Legend: 🎯session 🔴bugfix 🟣feature 🔄refactor ✅change 🔵discovery ⚖️decision
Format: ID TIME TYPE TITLE
Fetch details: get_observations([IDs]) | Search: mem-search skill

Stats: 50 obs (22,106t read) | 1,054,880t work | 98% savings

### Apr 20, 2026
S48 Create pull request for phase 0-6 audit remediation; note finding 9 deferred to next workflow (Apr 20 at 10:03 AM)
S49 Task 9: Route session lifecycle refactor — 38+ call sites across auth/admin/settings + test-fixture refactor (deferred from previous session) (Apr 20 at 1:59 PM)
S50 REM-P0-006 Complete: Route Authorization Matrix Created (Apr 20 at 2:36 PM)
### Apr 21, 2026
S51 Plan 10 Setup Wizard Doc Rewrite + wizard_state Migration Scoped Together (Apr 21 at 4:14 PM)
S52 Phase 9 Audit Remediation Committed to fix/phase-9-audit-findings (Apr 21 at 7:36 PM)
S53 CI Failing Due to Black Formatting Violations (Apr 21 at 9:44 PM)
S54 Remediation Checklist Status Updates for REM-P0-005 and REM-P0-006 (Apr 21 at 9:51 PM)
567 10:26p ✅ Plan 11 `ResetRequestsPanel` Tests and JSX Fully Corrected to Match Real Admin API
### Apr 22, 2026
568 9:06a ✅ REM-P0-004 Plan Cleanup: Plans 9–15 Substantially Trimmed
569 " 🔵 OpenLIA Server DB Layer Structure Confirmed During Plan Review
570 9:07a 🔵 Plans 9–15 Correctly Use Router-Factory Auth Pattern After Cleanup
571 " 🔵 REM-P0-004 Remediation Checklist Status Is In-Progress, Not Complete
572 9:12a 🔵 Phase 14 Equity Research Router Architecture Confirmed
573 9:13a 🔴 Phase 14 Plan Fixed: Route Handlers Moved Inside Factory Closure
574 " ✅ Remediation Checklist REM-P0-004 Marked Complete
575 9:15a 🔵 OpenLIA Remediation Checklist Status: 21 of 22 Items Remain Open
576 9:22a 🔵 Remediation Checklist Current State: Only REM-P0-004 Complete
577 9:23a 🔵 Remediation Work Exists on Unreachable Commits Not Merged to Main
578 " 🔵 Local main Is Behind origin/main — Significant Remediation Work Already Merged Remotely
579 9:24a ✅ Remediation Checklist Merge Gates Updated for REM-P0-004 Completion Across All Plans
580 9:34a 🔵 OpenLIA Endpoint Contract Matrix Structure and Coverage
581 " ✅ Remediation Checklist Status Updates for REM-P0-005 and REM-P0-006
S55 REM-P0-007 — Implement setup status and first-run gate (last P0 blocker) — scope decision pending before implementation begins (Apr 22 at 9:34 AM)
582 9:43a 🔵 OpenLIA PR #19 Merge Conflicts Identified and Resolution Started
583 " 🔴 PR #19 Merge Conflicts Resolved Across Three Documentation Files
584 9:44a 🔵 Phase-10 Plan Conflict Resolution Removed Key Shipping Notes from origin/main
585 9:45a 🔴 Phase-10 Resolution Corrected to --ours; Rebase on openai/rem-p0-004-clean-plan-11-15 Ready to Continue
586 " ✅ Remediation Checklist Updated to Reflect REM-P0-004, REM-P0-005, REM-P0-006 Completion
587 9:50a 🔵 REM-P0-007: Setup Status and First-Run Gate — Last P0 Blocker
588 " 🔵 REM-P0-007 Codebase State: Setup Infrastructure Is Entirely Missing
589 9:51a 🔵 App.tsx AuthProvider Problem and app.py Integration Points for Setup Wizard
590 " 🔵 REM-P0-007 Complete Gap Analysis: 8 Critical Missing Components
S56 Review of REM-P0-007 logical ordering in implementation plans (Apr 22 at 9:51 AM)
591 10:02a ⚖️ Review of REM-P0-007 logical ordering in implementation plans
592 10:05a ⚖️ REM-P0-007 folded into Plan 10 execution scope
593 10:06a ✅ Remediation checklist REM-P0-007 gate entry updated and committed on Plan 10 branch
594 10:09a 🔵 Phase 10 Setup Wizard Implementation Plan Pre-Flight Review
595 10:10a 🔵 Pre-Flight: DEPARTMENT_DEFAULT_TIERS Lives in core Package, Not server
596 " 🔵 Pre-Flight: Plan Task 9 Code Calls Non-Existent llm_providers Service Functions
597 " 🔵 Pre-Flight: Confirmed Shipped Infrastructure — deps, passwords, wizard_state, router pattern
S57 Pre-Flight: DEPARTMENT_DEFAULT_TIERS Lives in core Package, Not server (Apr 22 at 10:10 AM)
598 10:12a 🔵 Reusable `_run_connection_test` helper exists in settings.py for LLM provider pinging
599 " 🔵 ModelTier StrEnum has three values: thinking, everyday, quick
600 10:13a ✅ Phase 10 Task 9 Step 3 rewritten to match shipped llm_providers service surface
601 10:14a 🔵 Frontend router is at `frontend/src/router/routes.tsx`, not `frontend/src/router.tsx`
602 10:18a 🔵 Phase 10 Setup Wizard Implementation Plan Structure
603 " 🔵 data_providers.py Service API Surface
604 " 🔵 WizardService Design: ENV Override Resolution and Session Token
605 " 🔵 Setup Router Factory Pattern: build_setup_router
606 10:19a 🔵 services.auth.users.create_user Does Not Exist
607 " 🔵 Task 10 dp_svc API Mismatch: list_all, create_and_test, reorder, update_api_key Missing
608 " 🔵 Wizard Step Order and advance_step Logic
609 " 🔵 Task 9 /setup/models: Plan Updated 2026-04-22 to Match Actual llm_providers API
610 10:20a 🔵 DataProvider Model Has No category or priority Columns
611 " 🔵 wizard_svc Needs Additional Functions: set_signup_policy, set_config, finalize
612 " 🔵 Frontend Setup Wizard Directory Structure
613 " 🔵 AI Review Route: Background Task Must Open Its Own DB Session
614 10:21a 🔵 Plan 10 Second-Pass Review: RED — 4 Critical Fixes Required Before Execution
615 10:22a ✅ Plan 10 Task 8 Rewritten: create_first_admin Uses Manual User Row Construction
616 " 🔵 ADAPTERS Registry Only Contains EODHDAdapter; create_provider Requires Enum Parameters

Access 1055k tokens of past work via get_observations([IDs]) or mem-search skill.
</claude-mem-context>