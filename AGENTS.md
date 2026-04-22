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

# [OpenLIA] recent context, 2026-04-21 9:26pm PDT

Legend: 🎯session 🔴bugfix 🟣feature 🔄refactor ✅change 🔵discovery ⚖️decision
Format: ID TIME TYPE TITLE
Fetch details: get_observations([IDs]) | Search: mem-search skill

Stats: 50 obs (20,498t read) | 983,109t work | 98% savings

### Apr 20, 2026
S27 OpenLIA main branch post-merge code review — Phase 5 (LLM Runtime) and Phase 6 (Background Task Scheduling) quality assessment after git push/pull sync (Apr 20 at 9:32 AM)
S24 Switch to main branch to commit — Claude flagged risks before proceeding (Apr 20 at 9:32 AM)
S28 GitHub Branch Protection Ruleset Settings — Branch name pattern and recommended rules for protecting main (Apr 20 at 9:38 AM)
S31 claude-mem:timeline-report — Generate "Journey Into OpenLIA" narrative report from 110 persistent memory observations (Apr 20 at 9:52 AM)
S48 Create pull request for phase 0-6 audit remediation; note finding 9 deferred to next workflow (Apr 20 at 10:03 AM)
S49 Task 9: Route session lifecycle refactor — 38+ call sites across auth/admin/settings + test-fixture refactor (deferred from previous session) (Apr 20 at 1:59 PM)
S50 REM-P0-006 Complete: Route Authorization Matrix Created (Apr 20 at 2:36 PM)
### Apr 21, 2026
449 4:29p 🔵 Existing WizardState tests assert integer current_step — must be updated alongside REM-P1-006 migration
450 4:37p ✅ WizardState Model Migrated to String-Based Step Tracking
451 4:40p 🟣 WizardState Model Migrated from Integer Steps to Named String Steps
452 " 🔴 WizardState Reset Tests Updated to Assert Full Field Reset
453 " 🔵 uv Cache Permission Error Blocking Test Execution
454 4:41p ✅ WizardState Named-Step Schema Tests Pass
455 " ✅ Full DB Test Suite Passes After WizardState Schema Changes
456 " ✅ Full Server Test Suite Green After WizardState Migration
457 " 🔵 Alembic Config Location in OpenLIA Server Package
458 4:42p 🔵 OpenLIA Phase 10 Setup Wizard Implementation Plan Structure
459 " 🔵 Phase 10 Tasks 2–3 Design: WizardService and wizard_gate Middleware
460 4:43p 🔵 Phase 10 Tasks 4–6 Design: Setup Routes, Session Cookie, and Takeover Endpoint
461 " ✅ Phase 10 Plan Updated with Critical Implementation Corrections (2026-04-21 Rewrite)
462 6:42p 🔵 Phase 10 Setup Wizard Plan Structure — 28 Tasks Across Backend + Frontend
463 " 🔵 OpenLIA LLM Adapter Interface — LLMProvider Protocol with LLMRequest/LLMResponse
464 " 🔴 AI Review Runner Plan Corrected — LLMProvider Interface Mismatch Fixed
465 6:43p 🔴 Task 13 Test Mock Further Corrected — Dynamic type() Objects Replaced with Real LLMResponse
466 " 🔵 wizard.py Service Does Not Exist Yet — Phase 10 Tasks 2–15 Are Unimplemented
467 6:56p ✅ WizardState Model Reshaped: Integer Steps → Named String Steps
468 " 🟣 serve CLI: Environment-Variable-Driven Host/Port with Mode-Aware Defaults
469 " 🔴 log_cli_event: source="cli" Is Now Enforced, Cannot Be Overridden by Callers
470 " 🟣 Admin CLI Password Reset Now Emits Auditable AuthEvent with source="cli"
471 " 🟣 Jobs Route Returns 503 When Scheduler Is Disabled
472 7:36p ⚖️ Plan 10 Setup Wizard Doc Rewrite + wizard_state Migration Scoped Together
S51 Plan 10 Setup Wizard Doc Rewrite + wizard_state Migration Scoped Together (Apr 21 at 7:36 PM)
473 9:10p 🔵 Audit Remediation Status: 18 of 30 Items Still Not Started
474 " 🔵 must-change-password Not Reliably Enforced in Auth Flow
475 " 🔵 Setup First-Run Flow Absent: No Backend Setup Router Mounted
476 " 🔵 Production Scheduler and Static Serving Wiring Still Stubbed or Missing
477 " 🔵 Frontend Test Suite Exits Nonzero Due to AbortSignal Unhandled Rejection
478 9:11p 🔴 Fixed: /auth/session Now Returns must_change_password Field
479 9:12p 🔴 Frontend getSession() API Now Propagates must_change_password on Session Restore
480 9:13p 🔵 OpenLIA Phase 9+ Remediation Checklist Implementation Status Audit
482 9:14p 🔵 OpenLIA Phase 9+ Remediation Checklist Current Status Mapped
481 " 🔵 Code Review Graph Index Does Not Reflect Unstaged Remediation Changes
483 9:15p 🔵 Auth Middleware Gap: No must_change_password Enforcement in build_require_auth
484 " 🔵 Verified Implementation of 7 Completed Remediation Items via Source Inspection
485 " 🟣 REM-P1-001: build_require_active_user and build_require_active_admin Added to Auth Middleware
487 9:16p 🔵 build_require_active_user Exists in Middleware But Is Not Wired to Any Route
488 " 🔵 app.py Passes report_runner=None and batch_runner=None to Production Scheduler
489 " 🔵 Plans 11-15 Executable Snippets Still Contain Stale Auth and Import Patterns
490 " 🟣 Comprehensive Endpoint Contract Matrix and Route Authorization Matrix Created
486 " 🟣 REM-P1-001 Complete: All Product Routes Migrated to must_change_password-Aware Dependencies
491 9:18p 🔵 REM-P1-001 Must-Change-Password Enforcement Is Nearly Complete — Only Settings Data-Providers Gap Remains
492 " 🔵 Frontend MustChangePasswordGate Is Fully Implemented and Wraps All Protected Routes
493 " 🔵 72 Backend Tests and 20 Frontend Auth Tests Pass Clean on Branch fix/phase-9-audit-findings
494 " 🔵 LLM Runtime Multi-Round Tool Loop and TierNotConfiguredError Error Events Are Fully Tested
495 9:19p 🔵 REM-P1-011 Multi-Round Tool Loop Tests Cover Single-Round But Not Back-to-Back Two-Round Scenarios
496 9:22p 🔵 Server Test Suite Passes 425 Tests After Auth Middleware Migration
497 9:23p 🟣 REM-P1-017: Production Static Frontend Serving with SPA Fallback Added to app.py
498 " 🔵 App.test.tsx Has Pre-existing Unhandled AbortSignal Rejection from React Router

Access 983k tokens of past work via get_observations([IDs]) or mem-search skill.
</claude-mem-context>