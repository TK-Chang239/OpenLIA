# Report Chat Follow-up — Design

**Date:** 2026-05-17
**Status:** Draft — pending implementation plan
**Branch:** to be created from `feat/subagent-report-architecture` after that branch ships
**Spec sibling:** `docs/superpowers/specs/2026-05-16-subagent-report-architecture-design.md` (this feature depends on the subagent runner shipping first)

---

## Problem

Today, once an equity research report is generated, the user has no first-class way to discuss it with the AI. They can ask follow-ups in the same chat thread, but the model has no structured memory of the report's context, no access to the underlying data the report drew from, and no clear UX affordance signaling "this conversation is about this report." Users want to:

- Ask follow-up questions ("did you check Q4 buybacks?", "what's the source for that revenue figure?")
- Point out errors or omissions ("you missed the segment-level breakdown for AI services")
- Request live updates ("what's changed in the news since you wrote this?")
- Later, consolidate the discussion into a revised final report (this is plan 2, separate spec)

The structural primitives already exist in the server (`_attach_report_as_context`, chat session machinery, tool dispatcher), but they aren't surfaced as a feature. This spec elevates them and adds the missing pieces: persistent payload bundles, a chat ↔ report binding column, tool wiring, and the supporting UX.

## Goals

- **First-class "discuss this report" experience.** A clear UX entry point from the Repository view; existing chats that generated a report continue as the discussion thread for it.
- **RAG-style context retrieval.** Base context is the rendered report (small, cached); the model has tools to fetch deeper data, search the web, or call live data tools when the question demands.
- **One-report-per-thread enforcement.** Generating a new report in a bound chat opens a new thread automatically — clean separation between discussions.
- **Backward compatible.** Existing chat sessions and report generation flows continue to work unchanged. The feature is additive.

## Non-goals (deferred)

- **Evidence log** — a structured record of what the generation phase decided and why (`read_evidence_log` tool). Deferred to v2 once we see what questions users actually ask.
- **Multi-report conversations** — a chat that holds multiple reports in active context for cross-report analysis. Hard-scoped out in favor of one-report-per-thread.
- **Revision pass** — taking the original report + chat history and producing a new ReportSchema. This is plan 2, a separate spec.
- **Chat-driven report regeneration** — modifying the original report in place from chat. Tombstone+regenerate is the existing pattern; we don't add a new path.

## Dependencies

This feature ships after the **subagent report architecture** (`docs/superpowers/specs/2026-05-16-subagent-report-architecture-design.md`). The persistence model in §1 reuses the subagent runner's `ReportPlan`, `fetched_data`, and `SectionDraft` structures. Shipping before that runner would require building parallel persistence infrastructure for the classic ReportRunner — explicitly out of scope.

---

## Architecture overview

```
Report generation (SubagentReportRunner.run)
  ├─ ... existing pipeline ...
  └─ on ReportComplete:
        persist_report_context_bundle(report_id, plan, fetched_data, section_drafts, payload_refs)
            └─ writes ~/.openlia/report_bundles/{report_id}.json.gz  (5MB cap, gzipped)

Chat session lifecycle (existing infra + new binding column)
  ├─ chat_sessions.attached_report_id TEXT NULL          (NEW column, soft FK to reports)
  ├─ Explicit binding:  POST /chat/sessions {attached_report_id} → creates+seeds
  └─ Implicit binding:  report generated in chat with NULL attached_report_id →
                        chat_sessions.attached_report_id ← new_report_id  (UPDATE on completion)

Chat request handling (existing ChatRunner)
  ├─ Load bundle from disk if attached_report_id set
  │   └─ If missing/tombstoned: lock chat (banner + disabled composer)
  ├─ Seed ToolDispatcher._payload_store from bundle.payload_refs
  ├─ Register read_payload tool (alongside existing chat tools)
  └─ Standard chat turn with rendered report as the seed user message

Report-generation request from a chat session (NEW routing)
  ├─ If source session has NULL attached_report_id:
  │    Generate report → set source_session.attached_report_id = new_report_id (implicit binding)
  └─ If source session already has attached_report_id:
       Create new chat session → generate report into it → return new_session_id
       Frontend shows toast in source chat offering navigation
```

---

## Section 1 — Persistence model

When the SubagentReportRunner completes a report, a `ReportContextBundle` is written alongside the report so the chat can query it later.

### Bundle shape

```python
class ReportContextBundle:
    """Persisted alongside the report at completion time. Provides the
    chat with everything it needs to answer follow-ups via read_payload
    without re-fetching from external APIs."""

    plan: ReportPlan                          # the validated ReportPlan that drove generation
    fetched_data: dict[str, Any]              # eager-fetched payloads keyed by f"{tool}({args}):{path}"
    section_drafts: list[SectionDraft]        # raw subagent outputs (pre-editor)
    payload_refs: dict[str, dict[str, Any]]   # ref → raw-payload map; kept full so chat can slice paths the plan did not
    generation_meta: dict[str, Any]           # model_id, total_input_tokens, total_output_tokens, web_search_count, schema_version
```

### Storage location

`~/.openlia/report_bundles/{report_id}.json.gz` — gzipped JSON on the filesystem. SQLite stays clean. Easy to inspect. The retention machinery (tombstones + scheduler sweep from PR #120) deletes the bundle file when the report is hard-deleted.

### When it is written

In `SubagentReportRunner.run()`, immediately before the `ReportComplete` event is yielded. If the bundle write fails (disk full, permissions), the runner logs a warning, emits a `report.warning.bundle_persist_failed` dev event, and yields `ReportComplete` anyway — the report is still valid; only the chat-followup capability is lost for that report.

### Size budget

Soft cap: **5MB compressed per bundle**. If the bundle would exceed 5MB after gzip:
- `plan` and `section_drafts` are always kept (they are small)
- `fetched_data` and `payload_refs` are truncated by removing the largest entries first
- A `bundle_truncated: list[str]` metadata field records which refs were dropped
- The truncation is logged as `report.warning.bundle_truncated` so it is observable

### Bundle loading

Lazy: loaded by the chat session route on the first request to a bound session. Cached in-process for the duration of the request. Subsequent turns re-read from disk (consistent with the rest of the chat service being stateless across requests).

---

## Section 2 — Chat-report binding

### DB migration

```sql
ALTER TABLE chat_sessions ADD COLUMN attached_report_id TEXT NULL;
CREATE INDEX IF NOT EXISTS idx_chat_sessions_attached_report_id
    ON chat_sessions (attached_report_id);
-- Soft FK: no CASCADE. Reports use tombstone soft-delete; a session
-- pointing at a tombstoned report still loads (read-only fallback).
```

Existing sessions get `NULL` — backward compatible.

### Binding paths

**Explicit (from Repository view).** User clicks "Discuss" on a report card. Frontend POSTs `/chat/sessions {attached_report_id}`. Server checks for an existing session with the same `(user_id, attached_report_id)` — if found, returns that session id (idempotent reuse). Otherwise creates a new session, sets `attached_report_id`, runs the existing `_attach_report_as_context` helper to seed the first message, returns the session id.

**Implicit (within a chat that generates a report).** User in an unbound chat (e.g., the always-on Equity Research chat) generates a report. Existing report-generation flow runs. On `ReportComplete`, the report route runs an `UPDATE chat_sessions SET attached_report_id = ? WHERE id = ? AND attached_report_id IS NULL`. The conditional `AND attached_report_id IS NULL` prevents accidental overwrites in the race-condition path (handled in §4).

### Session title derivation (frontend)

When a session has `attached_report_id` non-null, the chat list shows `Discussion: {report.title}` with a 📎 icon. Frontend computes this from the report fetch; no DB denormalization.

### Tombstoned-report / missing-bundle handling

If a chat session loads and either (a) the attached report is tombstoned/deleted, or (b) the bundle file is missing from disk:
- The chat opens with messages visible (history scrollable)
- The composer is **disabled**
- A prominent banner reads: *"The report this discussion was about can no longer be fetched. I'm unable to answer any questions about it."*
- No "fix it" affordance; the user understands the report is gone

---

## Section 3 — Tool wiring in chat

### Tools available in a report-bound chat

| Tool | When | Purpose |
|---|---|---|
| `read_payload` | Always (when bundle loaded) | Query the persisted bundle for cheap re-use of already-fetched data |
| `web_search` | Per existing session toggle (default per department) | "What's changed since the report was generated?" |
| `eodhd__*`, `fmp__*`, etc. | Per department configuration | Live data fetching for "you didn't include X, can you pull it?" — full generation-time toolset |
| Existing skill tools | Per existing session preferences | No change from today |
| Department `chat:` mode tools | Per existing session preferences | No change from today |

### Tools explicitly NOT available in v1

- `read_evidence_log` — deferred to v2
- Anything that triggers a new report generation from inside the chat without going through the §4 routing — generation requests follow §4

### Tool wiring mechanics

The existing `ToolDispatcher` constructor already accepts the tool list. When a bound chat session loads:
1. Server loads `ReportContextBundle` from disk (or fails into the locked-chat path)
2. Server seeds `ToolDispatcher._payload_store` with `bundle.payload_refs`
3. Server registers `read_payload` in the tool list alongside the chat's existing tools

`read_payload` works exactly as it does during report generation today — same arguments, same behavior, same cap (`READ_PAYLOAD_CAP_CHARS = 50_000`). The only difference is that the payload_store is pre-seeded from the bundle instead of accumulated through the run.

### Base context per chat turn

- The chat's existing department system prompt (e.g., `equity_research.yaml::chat.system`) — sits above cache breakpoint, cached
- The seed user message inserted by `_attach_report_as_context`: report title + rendered report text + citations list — sits above cache breakpoint, cached
- The user's actual follow-up message — varies per turn

Estimated base context: 10-20K tokens. Cached after turn 1. Per-turn marginal cost dominated by tool-call cycles, which only fire when the model needs more than what the rendered report shows.

---

## Section 4 — One-report-per-thread enforcement

### Server-side routing

```python
# In the report-generation route handler (sketch):
def handle_report_generation_request(source_session_id, request, user):
    with serialize_per_session(source_session_id):  # per-session lock
        source_session = db.get(ChatSession, source_session_id)
        if source_session.attached_report_id is None:
            # Implicit-binding path — generate into the source session.
            report_id = generate_report(request, user)
            db.execute(
                "UPDATE chat_sessions SET attached_report_id = :rid "
                "WHERE id = :sid AND attached_report_id IS NULL",
                {"rid": report_id, "sid": source_session_id},
            )
            return {"session_id": source_session_id, "report_id": report_id, "redirect": False}
        else:
            # Source already bound — create a new thread for the new report.
            new_session = create_chat_session(
                department=source_session.department, user=user
            )
            report_id = generate_report(request, user)
            db.execute(
                "UPDATE chat_sessions SET attached_report_id = :rid WHERE id = :sid",
                {"rid": report_id, "sid": new_session.id},
            )
            return {"session_id": new_session.id, "report_id": report_id, "redirect": True}
```

### Race-condition handling

Per-source-session serialization (via row-level lock or in-process mutex keyed by `source_session_id`) ensures two back-to-back generation requests from the same source chat don't both try to implicit-bind. The second request sees the binding from the first (since the lock serializes the check), takes the "already bound" branch, and routes to a third new thread.

### Source session never re-anchors

Once a chat session has an `attached_report_id`, that value is **immutable** for the lifetime of the session. New reports requested from the chat always spawn into a new thread. Rationale: a chat's identity is "the discussion of report X" — re-anchoring would erase the user's mental model.

### Frontend behavior on `redirect: true`

The frontend receives the response with `redirect: true` and shows a toast in the source chat:

```
🆕 Generating new report in a separate thread → [Open]
```

The toast is dismissable. The new thread exists in the sidebar regardless of whether the user clicks. If they dismiss, they can find it later in the chat list.

---

## Section 5 — Frontend touchpoints

### Repository view — "Discuss" button on report cards

`ReportCard.tsx` gets a new action: *"Discuss"*. Sits with the existing actions (Open, Download, Delete). Clicking POSTs to `/chat/sessions` with `attached_report_id`. Server returns either an existing session id (idempotent reuse) or a new one. Frontend navigates to the chat route.

### Chat list (sidebar)

Sessions with `attached_report_id`:
- Title: `Discussion: {report.title}` (computed frontend-side via report fetch)
- Small 📎 icon distinguishing from regular department chats
- Hover preview shows `report.cover.tagline` if available

### Chat header banner

When viewing a chat with `attached_report_id`, the header shows:

```
📎 Discussing report: {report.title}  →  [Open report]
```

`[Open report]` navigates to the report viewer (new tab or split-pane, matching existing patterns).

### Locked-chat state

When the attached report is tombstoned or the bundle is missing:
- Header banner replaced with the locked message: *"The report this discussion was about can no longer be fetched. I'm unable to answer any questions about it."*
- Composer disabled (grayed input, send button hidden)
- Existing messages render normally for scroll-back
- No retry/regenerate affordance — the report is gone

### Report-generation redirect toast

When a new report spawns into a separate thread from a bound chat:

```
🆕 Generating new report in a separate thread → [Open]
```

Dismissable. Doesn't auto-navigate. The new thread is findable in the sidebar regardless.

### Implicit-binding one-time toast

The first time a chat gets bound via implicit binding (a user generates a report from an unbound chat), a one-time toast appears after the report completes:

```
ℹ️ This chat is now discussing '{report.title}'. New report
   requests will open a separate thread.
```

User-dismissable; preference persisted so it doesn't repeat for the same user.

### What does NOT change

- Existing chat composer, message rendering, tool-call chip rendering — unchanged
- Existing Repository view layout — only the action button is new
- Existing report viewer — unchanged (the "Discuss" button is the entry point, not a viewer modification)

---

## Configuration surfaces

| Env var | Default | Purpose |
|---|---|---|
| `OPENLIA_REPORT_BUNDLE_DIR` | `~/.openlia/report_bundles` | Where bundles are written |
| `OPENLIA_REPORT_BUNDLE_MAX_BYTES` | `5_242_880` (5 MiB) | Soft cap on per-bundle compressed size |
| `OPENLIA_REPORT_CHAT_ENABLED` | `0` | Feature flag — when `1`, the "Discuss" button + implicit binding are active |

Defaults are conservative. Flag stays OFF until the subagent runner has shipped and bundles are reliably being written.

---

## File layout

### New files

```
packages/core/src/openlia/llm/runtime/
  report_context_bundle.py        # ReportContextBundle dataclass + load/persist helpers (gzipped JSON)

packages/server/src/openlia_server/services/
  report_chat_context.py          # Loads bundle, seeds payload_store, registers read_payload for chat sessions

packages/server/src/openlia_server/tests/
  test_report_chat_context.py
  test_chat_report_binding.py
  test_report_thread_routing.py   # Section 4 routing

packages/core/tests/test_llm/test_runtime/
  test_report_context_bundle.py
```

### Modified files

- `packages/core/src/openlia/llm/runtime/subagent_runner.py` — write the bundle on `ReportComplete`
- `packages/server/src/openlia_server/db/models/content.py` — add `attached_report_id` column to `ChatSession`
- `packages/server/src/openlia_server/db/migrations/` — Alembic migration for the new column + index
- `packages/server/src/openlia_server/routes/chat_sessions.py` — bundle-loading on session load, read_payload tool registration when bound, idempotent reuse on `POST /chat/sessions {attached_report_id}`
- `packages/server/src/openlia_server/routes/reports.py` (or equivalent) — implement §4 routing (implicit binding + new-thread redirect)
- `packages/server/src/openlia_server/services/scheduler.py` (or equivalent tombstone sweep) — delete bundle file when report is hard-deleted
- `frontend/src/components/equity-research/ReportCard.tsx` — "Discuss" button
- `frontend/src/components/chat/ChatList.tsx` (or equivalent sidebar component) — title swap + 📎 icon
- `frontend/src/components/chat/ChatHeader.tsx` (or equivalent) — bound-report header banner + locked-chat banner + composer disable
- `frontend/src/components/chat/ChatComposer.tsx` (or equivalent) — disabled state
- `frontend/src/api/chat.ts` and `frontend/src/api/reports.ts` — the redirect: true response shape

### Untouched

- Existing `ChatRunner` (`packages/core/src/openlia/llm/runtime/chat.py`) — no changes
- Existing report viewer
- Existing `_attach_report_as_context` helper (reused as-is for seed-message content)
- All other report departments — same wiring works for any department that uses SubagentReportRunner

---

## Test plan (vertical slices, TDD)

| # | Slice | RED test |
|---|---|---|
| 1 | `ReportContextBundle` serialization | round-trip gzipped JSON; verify size cap truncation logic drops largest payload_refs first |
| 2 | `SubagentReportRunner` writes bundle on complete | mock disk; assert file written with correct shape after `ReportComplete` |
| 3 | `SubagentReportRunner` continues on bundle write failure | mock disk failure; assert `ReportComplete` still yielded + warning event recorded |
| 4 | DB migration adds `attached_report_id` column | apply migration; verify column + index present; existing rows have NULL |
| 5 | `POST /chat/sessions {attached_report_id}` creates bound session | hit endpoint; verify session created with column set |
| 6 | `POST /chat/sessions` is idempotent for same (user, report) | hit endpoint twice with same args; verify same session_id returned |
| 7 | Chat session load registers `read_payload` when bound | mock bundle; assert ToolDispatcher tool list contains read_payload |
| 8 | Chat session load locks on tombstoned report | tombstone report; assert chat response includes locked: true marker |
| 9 | Chat session load locks on missing bundle file | delete bundle from disk; assert locked: true |
| 10 | Implicit binding sets attached_report_id on report complete | generate report in unbound chat; assert column populated after ReportComplete |
| 11 | Implicit binding does not overwrite existing attached_report_id | pre-set column; generate report; assert column unchanged + redirect path taken |
| 12 | Report-gen request to bound chat returns redirect with new session_id | hit endpoint with bound source; verify redirect: true + new session id |
| 13 | Per-source-session serialization prevents double-bind race | fire two parallel report-gen requests against unbound chat; assert exactly one bound, one redirected |
| 14 | Source session's attached_report_id is immutable across redirects | bind source to report A; route to new thread for report B; assert source still points at A |
| 15 | Tombstone sweep deletes bundle file when report hard-deleted | hard-delete report; run sweep; verify bundle file gone |

---

## Rollout plan

| Phase | Trigger | Action |
|---|---|---|
| v1 ship | Subagent runner has shipped and is the default for equity_research; this branch merges | `OPENLIA_REPORT_CHAT_ENABLED=0`. Bundles are written but no UI surface yet. |
| Author validation | Author generates 3-5 reports, manually flips the flag, tests Discuss + implicit binding + live tool usage in chat | Confirm bundle loads, tools register, locked-chat behavior on a manually tombstoned report |
| Soft launch | Validation passes | Flip flag default ON for self-hosted personal-mode deployments; document in changelog |
| Expansion | Soft launch stable for a week | Consider promoting feature to other report departments (earnings_update, morning_briefing) — same code paths work, no new infrastructure |
| v2 features | After expansion | Evidence-log tool, possibly multi-report contexts, possibly DB-backed bundles for production scale |

---

## Open questions

None. All design decisions locked. Implementation plan to follow via writing-plans skill after the subagent runner ships and is validated.

---

## Acceptance criteria (v1)

- [ ] `OPENLIA_REPORT_CHAT_ENABLED=1` exposes the "Discuss" button on report cards; clicking creates an idempotent bound chat session
- [ ] Generating a report from an unbound chat sets `attached_report_id` automatically on `ReportComplete`
- [ ] Generating a report from a bound chat returns a new thread; source chat shows the redirect toast; source chat's `attached_report_id` is unchanged
- [ ] In a bound chat, `read_payload` works against the persisted bundle; `web_search` and live data tools work as in regular department chats
- [ ] Tombstoning the attached report or deleting the bundle file produces the locked-chat state (banner + disabled composer + messages still scrollable)
- [ ] All 15 tests in the test plan pass
- [ ] Existing chat sessions without `attached_report_id` behave identically to today (regression)
- [ ] Bundle size cap (5MB) enforced with truncation + warning event on overflow
