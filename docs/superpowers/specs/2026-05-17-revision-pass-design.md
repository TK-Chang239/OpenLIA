# Revision Pass — Design

**Date:** 2026-05-17
**Status:** Draft — pending implementation plan
**Branch:** to be created from the merged `main` after both `feat/subagent-report-architecture` AND `feat/report-chat-followup` ship
**Spec siblings:**
- `docs/superpowers/specs/2026-05-16-subagent-report-architecture-design.md` (provides `EditorClient`, `_finalize_submit_payload`, `BackgroundReportRegistry`-compatible runner shape)
- `docs/superpowers/specs/2026-05-17-report-chat-followup-design.md` (provides the chat thread, `attached_report_id` column, the `ReportContextBundle` — **this spec amends §3 and §4 of that one**)
- `docs/superpowers/specs/2026-05-17-background-report-generation-design.md` (provides `BackgroundReportRegistry`, notification SSE, retry/cancel affordances)

---

## Problem

After a user generates an equity research report and discusses it in the chat-followup feature (specced separately), they want to consolidate the discussion into a revised final report. Today there's no path — the user can edit the chat but the original report stays unchanged.

The user wants: in the same chat thread that's been discussing the report, ask the AI to "consolidate this into a final version." A new revised report appears, saved as a separate Repository entry. The chat thread continues — now discussing the revised version. Subsequent revisions iterate the same way (discussion → revision → discussion → revision).

## Goals

- **LLM-triggered revisions.** The chat LLM calls a `revise_report` tool when the user expresses revision intent in natural language ("consolidate this", "final version", "revised report"). No new button or slash command.
- **Editor-only revision pass.** Take the original ReportSchema + the chat transcript + the bundle's `read_payload` access; produce a new ReportSchema in one editor pass. Fast (~30s), cheap (~$0.20).
- **Same chat thread, re-anchor on success.** The chat that produced the original keeps discussing — its `attached_report_id` re-points to the revised report when revision completes successfully. The thread accumulates a history of all iterations.
- **Revised report is independently discussable.** Bundle inherited via file copy so chat-followup's `read_payload` works on the revised report immediately.
- **One-ticker-per-thread.** Chat-followup's "one-report-per-thread" rule generalizes to "one-ticker-per-thread" — same ticker stays in the thread (re-anchors); different ticker spawns a new thread.

## Non-goals (deferred)

- **Provenance link / "Revised from" badge.** Revised reports stand on their own merits; no formal link back to source. (v2 could add provenance if needed for audit.)
- **In-place report editing.** Revisions always produce a new row; original is preserved.
- **Live data fetching during revision.** Editor-only with `read_payload` over the original bundle. If the chat surfaced data via live tools, that data is in the chat transcript and the editor consumes it from there. (For new live data, the user can keep discussing — live tools work in chat — then revise.)
- **Cross-thread report merging.** A revision draws from ONE chat's discussion of ONE source report; can't merge multiple chats into one revised report.
- **Section-level revisions.** Each revision is a full-report rewrite. (`sections_to_focus` is a hint to the editor, not a structural cap on what it can touch.)

## Dependencies

This feature ships **after** both:
1. The subagent report architecture (`feat/subagent-report-architecture`) — provides `EditorClient`, `_finalize_submit_payload`, the `ReportContextBundle` shape
2. The chat follow-up feature (`feat/report-chat-followup`) — provides the chat thread, `attached_report_id` column, bundle persistence

Both must be merged before this work begins. Background generation can ship before or after — they are independent.

---

## Architecture overview

```
Chat LLM in a bound chat session decides to call revise_report
  └─ Chat-route intercepts the tool call (does NOT dispatch through ToolDispatcher)
      └─ POST /reports/{source_report_id}/revise
          Body: {chat_session_id, revision_brief, sections_to_focus}
  └─ Server creates new report row (status=generating, original_request marks "revision")
  └─ Server submits RevisionRunner.run() into BackgroundReportRegistry
  └─ Server returns {new_report_id, status:generating}
  └─ Chat returns synthetic tool result to the model:
       {"status": "revision_started", "new_report_id": "...", "estimated_seconds": 30}

RevisionRunner.run() (async iterator, background-task-compatible):
  ├─ Phase("loading_context")
  │   Load source ReportSchema, source ReportContextBundle, chat transcript
  ├─ Phase("editing")
  │   EditorClient.compose(EditorRequest with:
  │     - revision_brief, sections_to_focus, chat_transcript_excerpt
  │     - role_prompt = shared/revision_editor_role.yaml.j2
  │     - section_drafts = synthesized from source report's sections
  │     - read_payload tool seeded from source bundle's payload_refs)
  └─ Phase("finalizing")
      _finalize_submit_payload → validate_report_payload
      shutil.copy2(source_bundle, revised_bundle)  # bundle inheritance
      ReportComplete(report_id=new_revised_report_id, schema=final_payload)

run_wrapped_revision (post-Background wrapper extension):
  On successful ReportComplete:
    UPDATE chat_sessions SET attached_report_id = new_revised_report_id
                        WHERE id = source_chat_session_id
    presence.fanout(user_id, {type: "chat.attached_report_changed",
                              session_id, new_report_id})

Frontend chat:
  Receives chat.attached_report_changed via notifications SSE
  → re-fetches the session
  → chat header banner updates to point at revised report
  Standard report.complete toast also fires (from background-gen spec)
```

---

## Section 1 — `revise_report` tool + ticker-keyed chat binding

### The tool

Registered in the chat tool list whenever the session has `attached_report_id` set (alongside `read_payload` and live data tools from chat-followup §3).

```python
revise_report = ToolSchema(
    name="revise_report",
    description=(
        "Consolidate the original report and this discussion into a revised "
        "report. Call this when the user explicitly asks for a 'final', "
        "'revised', 'consolidated', 'updated', or 'final version' of the "
        "report. Do NOT call this for summary or recap requests — only "
        "when the user wants a NEW report saved."
    ),
    parameters={
        "type": "object",
        "additionalProperties": False,
        "required": ["revision_brief"],
        "properties": {
            "revision_brief": {
                "type": "string",
                "description": (
                    "2-4 sentence summary derived from the chat discussion: "
                    "what's wrong with the original, what's missing, what "
                    "structural changes the user asked for. The editor uses "
                    "this to guide the rewrite."
                ),
            },
            "sections_to_focus": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Optional section_ids the editor should pay extra "
                    "attention to. Omit when revision is broad."
                ),
            },
        },
    },
)
```

### Chat-route interception

When the chat LLM emits a `revise_report` tool call, the chat-message handler intercepts BEFORE the normal `ToolDispatcher` path. Logic:

```python
# In the chat message handler, after the LLM response:
for call in response.tool_calls:
    if call.name == "revise_report":
        # Don't dispatch through the regular tool dispatcher.
        result = await _trigger_revision(
            db=db,
            chat=chat_session,
            args=call.arguments,
            user=user,
        )
        # Inject synthetic tool result back into the conversation so the
        # model can continue (and produce a graceful "started" message).
        synthetic_result = {
            "status": "revision_started",
            "new_report_id": result["report_id"],
            "estimated_seconds": 30,
        }
        # ... append assistant tool_calls message + tool result message ...
        continue  # don't fall through to ToolDispatcher.dispatch
```

`_trigger_revision` POSTs internally to the `POST /reports/{source_report_id}/revise` endpoint (defined in §3) — or, equivalently, calls the same service function the route handler uses.

### Ticker-keyed chat binding (amends chat-followup spec)

The chat-followup spec §4 currently checks `attached_report_id is None` to decide between implicit-bind and new-thread routing. We generalize this to subject-keyed comparison:

```python
def handle_report_generation_request(source_session, request, user):
    if source_session.attached_report_id is None:
        # Implicit-binding (unchanged): no existing binding.
        report_id = generate_report(request, user)
        source_session.attached_report_id = report_id
        return {"session_id": source_session.id, "report_id": report_id, "redirect": False}

    bound_report = db.get(Report, source_session.attached_report_id)
    bound_subject = _normalize_subject(
        (bound_report.original_request or {}).get("user_input", "")
    )
    new_subject = _normalize_subject(request.user_input)
    if bound_subject == new_subject:
        # Same ticker — re-anchor in this thread.
        report_id = generate_report(request, user)
        source_session.attached_report_id = report_id
        db.commit()
        return {"session_id": source_session.id, "report_id": report_id, "redirect": False}

    # Different ticker — new thread.
    new_session = create_chat_session(department=source_session.department, user=user)
    report_id = generate_report(request, user)
    new_session.attached_report_id = report_id
    db.commit()
    return {"session_id": new_session.id, "report_id": report_id, "redirect": True}


def _normalize_subject(raw: str) -> str:
    """Lowercase + whitespace-trim. v1 does NOT smooth ticker-exchange
    variants ('MSFT.US' vs 'MSFT.NASDAQ' count as different)."""
    return (raw or "").strip().lower()
```

This is a small behavioral change to chat-followup §4: `attached_report_id` is no longer strictly immutable. It re-anchors when the same ticker generates again (or when a revision completes — see §3).

### Revisions bypass the subject check

Revisions don't go through `POST /reports/generate`'s routing — they have their own `/revise` endpoint (§3). By construction, a revision shares the source's ticker; the revise endpoint re-anchors the source chat directly on success.

---

## Section 2 — `RevisionRunner` module

A new lightweight runner alongside `SubagentReportRunner`. Same `AsyncIterator[SseEvent]` shape so the background-task registry and SSE re-subscription endpoint work without changes.

### Class

```python
# packages/core/src/openlia/llm/runtime/revision_runner.py

class RevisionRunner:
    """One editor pass producing a revised report.

    Inputs: source ReportSchema, source ReportContextBundle, chat transcript.
    Output: a new ReportSchema yielded via ReportComplete.
    """

    def __init__(
        self,
        *,
        prompts: PromptLoader,
        resolve: ResolveFn,
        registry: Any,
        flagship_provider_factory: ProviderFactory,
        report_id_factory: Callable[[], str] | None = None,
        bundle_dir: Path | None = None,
        chat_repo: ChatSessionRepo,
        report_repo: ReportRepo,
    ) -> None: ...

    async def run(
        self,
        *,
        department_id: str,
        user_id: str | None,
        source_report_id: str,
        chat_session_id: str,
        revision_brief: str,
        sections_to_focus: list[str] | None,
    ) -> AsyncIterator[SseEvent]: ...
```

### Run flow

```
ReportStart(report_id=new_revised_report_id)
  └─ Phase("loading_context")
      Load source ReportSchema + source ReportContextBundle + chat transcript
      Fail loud (ReportError) if source bundle is missing
  └─ Phase("editing")
      EditorClient.compose(EditorRequest with revision fields)
      → revised ReportSchema
  └─ Phase("finalizing")
      _finalize_submit_payload (existing: server fields + normalize + meta_stats)
      validate_report_payload
      Copy source bundle to new bundle path
  └─ ReportComplete(report_id=new_revised_report_id, schema=final_payload)
```

### `EditorClient` extension

The existing `EditorClient` (from subagent runner spec) accepts an `EditorRequest`. For revision, we extend the request:

```python
class EditorRequest(BaseModel):
    # ... existing fields ...
    revision_brief: str | None = None             # NEW
    sections_to_focus: list[str] | None = None    # NEW
    chat_transcript_excerpt: str | None = None    # NEW
```

`EditorClient.compose` picks the role prompt by checking `revision_brief is not None`:

- `revision_brief is None` → `shared/editor_role.yaml.j2` (existing, original-report editor)
- `revision_brief is not None` → `shared/revision_editor_role.yaml.j2` (NEW)

### `revision_editor_role.yaml.j2` (new partial)

Same shape as `editor_role.yaml.j2` but reframes the responsibilities:

1. Preserve everything from the original that the discussion did NOT object to
2. Apply `revision_brief` faithfully — don't add or remove things the user didn't ask about
3. Reference `chat_transcript_excerpt` for facts and corrections the user surfaced; trust the user's corrections over the original's claims
4. Use `read_payload` for any data point the original underrepresented (`sections_to_focus` is a hint, not a hard scope)
5. Output the same `submit_report` payload — same schema, same strictness

### Chat-transcript compression

The chat transcript can be long. Deterministic compression (no LLM call) before passing to the editor:

```python
def compress_chat_transcript(messages: list[ChatMessage], cap_chars: int = 30_000) -> str:
    """Build a compact representation:
      - Every user message: verbatim
      - Every assistant message: verbatim
      - Every tool call + result: '[tool] read_payload(ref=..., path=...) → 1213 chars'
      Capped to ~30K chars (most recent kept; older trimmed with marker).
    """
    ...
```

The editor sees a structured summary — not the raw blow-by-blow.

### Bundle inheritance

After the editor produces a valid payload, before yielding `ReportComplete`:

```python
import shutil

source_bundle_path = self._bundle_dir / f"{source_report_id}.json.gz"
new_bundle_path = self._bundle_dir / f"{new_revised_report_id}.json.gz"
if source_bundle_path.exists():
    shutil.copy2(source_bundle_path, new_bundle_path)
else:
    # Source bundle missing → revision should have already failed at loading_context phase.
    # If we reach here, something's wrong. Log warning; revised report ships without a bundle.
    self._trace(
        "report.warning.revision_bundle_missing",
        "Source bundle missing; revised report has no bundle.",
        {"source_report_id": source_report_id, "new_report_id": new_revised_report_id},
    )
```

### Source-bundle-missing handling

If the source bundle is missing at the start (loading_context phase), the runner yields a `ReportError` immediately and aborts. The user sees a failed-card in the Repository: *"Could not revise — the original report's context bundle is no longer available."* No retry is offered (retrying won't help — the bundle is gone).

---

## Section 3 — Server route + chat re-anchor

### The endpoint

```
POST /reports/{source_report_id}/revise
  Body: {
    "chat_session_id": "sess_xxx",
    "revision_brief": "...",
    "sections_to_focus": ["risk_analysis", "financial_projections"] | null
  }
  Returns: {"report_id": "r_new", "status": "generating"}
```

### Handler

```python
@router.post("/{source_report_id}/revise")
async def revise_report_ep(
    source_report_id: str,
    body: ReviseReportIn,
    user=Depends(get_current_user),
    db: Session = Depends(get_db),
    registry: BackgroundReportRegistry = Depends(get_registry),
    presence: UserPresenceRegistry = Depends(get_presence),
) -> dict:
    # Auth.
    source_row = db.get(Report, source_report_id)
    if source_row is None or source_row.user_id != user.id:
        raise HTTPException(404)
    chat = db.get(ChatSession, body.chat_session_id)
    if chat is None or chat.user_id != user.id or chat.attached_report_id != source_report_id:
        raise HTTPException(400, "chat session is not bound to this report")

    # Per-chat-session lock to prevent racey re-anchors.
    async with _SOURCE_CHAT_LOCKS[body.chat_session_id]:
        # Build the new report row up-front.
        new_report_id = f"r_{uuid.uuid4().hex[:12]}"
        new_row = Report(
            id=new_report_id,
            user_id=user.id,
            department=source_row.department,
            status="generating",
            started_at=datetime.now(UTC),
            original_request={
                "kind": "revision",
                "source_report_id": source_report_id,
                "chat_session_id": body.chat_session_id,
                "revision_brief": body.revision_brief,
                "sections_to_focus": body.sections_to_focus,
            },
        )
        db.add(new_row)
        db.commit()

    # Build the RevisionRunner coroutine.
    runner_coro = RevisionRunner(...).run(
        department_id=source_row.department,
        user_id=user.id,
        source_report_id=source_report_id,
        chat_session_id=body.chat_session_id,
        revision_brief=body.revision_brief,
        sections_to_focus=body.sections_to_focus,
    )

    # Submit to background registry (same machinery as primary generation).
    task = registry.submit(user_id=user.id, report_id=new_report_id, runner_coro=runner_coro)

    # Wrapper coroutine handles standard persistence PLUS chat re-anchor on success.
    asyncio.create_task(run_wrapped_revision(
        runner_coro=_subscribe_via_queue(task),
        new_report_id=new_report_id,
        source_chat_session_id=body.chat_session_id,
        user_id=user.id,
        db_session_factory=get_session_factory(),
        presence=presence,
        registry=registry,
    ))

    return {"report_id": new_report_id, "status": "generating"}
```

### Revision-specific wrapper

```python
async def run_wrapped_revision(
    *,
    runner_coro,
    new_report_id: str,
    source_chat_session_id: str,
    user_id: str,
    db_session_factory,
    presence,
    registry,
) -> None:
    # First, the standard wrapper handles persistence + notifications.
    await run_wrapped_report(
        runner_coro=runner_coro,
        report_id=new_report_id,
        user_id=user_id,
        db_session_factory=db_session_factory,
        presence=presence,
        registry=registry,
    )
    # If we reach here (not raised CancelledError), the report finished
    # either successfully or via ReportError. Re-anchor only on success.
    with db_session_factory() as session:
        row = session.get(Report, new_report_id)
        if row and row.status == "complete":
            chat = session.get(ChatSession, source_chat_session_id)
            if chat:
                chat.attached_report_id = new_report_id
                session.commit()
                presence.fanout(user_id, {
                    "type": "chat.attached_report_changed",
                    "session_id": source_chat_session_id,
                    "new_report_id": new_report_id,
                })
```

### Race-condition handling

Module-level `dict[chat_session_id, asyncio.Lock]` serializes revision requests per source chat. Two simultaneous `revise_report` tool calls (rare in practice) are processed sequentially. The first acquires the lock; the second waits.

If the second's source_report_id is the now-stale one (the first revision re-anchored), the second's auth check (`chat.attached_report_id != source_report_id`) returns HTTP 400, the chat handler returns a synthetic tool error to the model: `{"status": "stale_source", "message": "Source report no longer bound; revision skipped."}`. The model can apologize and continue.

### Retry semantics

The Retry button (from background-gen spec) on a failed/cancelled revision row reads `original_request.kind == "revision"` and routes through this `/revise` endpoint (not `/reports/generate`) using the persisted source_report_id + chat_session_id + revision_brief + sections_to_focus. A small amendment to the background-gen retry handler:

```python
@router.post("/{report_id}/retry")
async def retry_report_ep(report_id, ...):
    row = db.get(Report, report_id)
    if row.original_request.get("kind") == "revision":
        # Route to revision endpoint.
        return await revise_report_ep(
            source_report_id=row.original_request["source_report_id"],
            body=ReviseReportIn(
                chat_session_id=row.original_request["chat_session_id"],
                revision_brief=row.original_request["revision_brief"],
                sections_to_focus=row.original_request.get("sections_to_focus"),
            ),
            user=user, db=db, registry=registry, presence=presence,
        )
    # Otherwise, existing /generate retry path.
    ...
```

---

## Section 4 — Frontend touchpoints

### Revision-in-progress chip in the chat

When the chat handler intercepts a `revise_report` tool call, it inserts a special-styled assistant chip into the thread:

```
[chip] 🔄 Revising the report based on our discussion...  [Cancel revision]
```

The chip is dismissable; the [Cancel revision] button DELETEs `/reports/{new_report_id}` which cancels the registry task. The chat continues to function — read_payload still works against the ORIGINAL bundle, live tools work, user can keep asking questions.

The synthetic tool result returned to the LLM lets it respond gracefully: *"Started the revision; I'll let you know when it's done."*

### Notification toast on completion

Already wired in the background-gen spec §5 (`useNotificationsStream`). The standard `report.complete` toast fires for the revised report. Clicking opens the new report.

### `chat.attached_report_changed` event handling

New event type delivered via the notifications SSE. The chat page subscribes to this and, on receipt:

```ts
es.addEventListener("chat.attached_report_changed", (e) => {
  const { session_id, new_report_id } = JSON.parse(e.data);
  if (currentChatSessionId === session_id) {
    refetchChatSession();  // re-loads the session, including the new attached_report_id
    // The chat header banner re-renders against the new report.
    // The chat-followup tool wiring (read_payload now bound to the new bundle)
    // updates on the next message.
  }
});
```

### Revised report in Repository

The Repository view's reports list endpoint returns the revised report as a standard row with `status="complete"`. It renders via the status-aware card dispatcher (background-gen §5) — no special badge. Per Q4a, no provenance link to the source.

### Failed-revision handling

Standard `report.failed` toast (from background-gen). The Repository shows a failed-card with `failure_reason` from `original_request.revision_brief` truncated. Retry button works (re-routes through the revise endpoint per §3).

The source chat stays anchored to the original on failure — the chat thread shows the synthetic "revision started" exchange plus an assistant follow-up: *"The revision failed: {failure_reason}. You can retry from the Repository."* (The assistant message comes from the runtime; the model doesn't know the revision failed until informed via a subsequent message.)

### What does NOT change

- `useReportStream`, `useNotificationsStream`, `useBeforeUnloadBeacon` from background-gen — all unchanged
- Chat message rendering (except the new status-chip variant)
- Repository view (except the revision-failure card uses the existing failed-card)
- Toast machinery

---

## Configuration surfaces

| Env var | Default | Purpose |
|---|---|---|
| `OPENLIA_REVISION_PASS_ENABLED` | `0` | Feature flag — when `1`, `revise_report` is registered in bound chats; the `/revise` endpoint accepts requests |
| `OPENLIA_REVISION_TRANSCRIPT_CAP_CHARS` | `30000` | Cap on chat-transcript compression |

---

## File layout

### New files

```
packages/core/src/openlia/llm/runtime/
  revision_runner.py                       # RevisionRunner + run_wrapped_revision
  chat_transcript_compressor.py            # deterministic chat-transcript compression

packages/core/src/openlia/prompts/shared/
  revision_editor_role.yaml.j2             # Editor role prompt for revisions

packages/server/src/openlia_server/routes/
  reports_revise.py                        # POST /reports/{source_id}/revise

packages/server/tests/
  test_revision_runner.py
  test_chat_transcript_compressor.py
  test_reports_revise_endpoint.py
  test_revision_race_lock.py
  test_revision_retry_routing.py
  test_chat_attached_report_changed_event.py

packages/core/tests/test_llm/test_runtime/
  test_revision_editor_role_prompt.py
  test_revision_runner_e2e.py

frontend/src/components/chat/
  RevisionInProgressChip.tsx
  RevisionInProgressChip.test.tsx
```

### Modified files

- `packages/core/src/openlia/llm/runtime/editor_client.py` — add `revision_brief`, `sections_to_focus`, `chat_transcript_excerpt` to `EditorRequest`; switch role prompt based on whether `revision_brief` is set
- `packages/server/src/openlia_server/routes/chat_sessions.py` — intercept `revise_report` tool calls before `ToolDispatcher.dispatch`; subscribe to `chat.attached_report_changed`
- `packages/server/src/openlia_server/routes/reports.py` — adapt retry handler to route revision retries through `/revise`
- `packages/server/src/openlia_server/services/report_chat_context.py` — register `revise_report` in the tool list for bound sessions
- `packages/server/src/openlia_server/routes/notifications_stream.py` — emit `chat.attached_report_changed` events
- `frontend/src/components/chat/ChatThread.tsx` — render `RevisionInProgressChip` for revision-tool messages; subscribe to `chat.attached_report_changed`
- `frontend/src/app/useNotificationsStream.ts` — handle `chat.attached_report_changed` event
- `docs/superpowers/specs/2026-05-17-report-chat-followup-design.md` — §3 + §4 amendments noting ticker-keyed binding + mutable `attached_report_id`

### Untouched

- `SubagentReportRunner` — entirely independent code path
- Background-generation registry, presence, sweep machinery — reused as-is
- Other report departments — revisions are equity_research only in v1; expanding requires per-department style guides and editor role prompts

---

## Test plan (vertical slices, TDD)

| # | Slice | RED test |
|---|---|---|
| 1 | `compress_chat_transcript` — verbatim user/assistant + tool-call summary, capped | feed long transcript; assert ≤30K chars, structure preserved |
| 2 | Ticker normalization | `_normalize_subject("MSFT")` == `_normalize_subject(" msft ")` |
| 3 | `EditorClient.compose` picks revision role when `revision_brief` set | fake provider; verify system prompt contains revision-role text |
| 4 | `revision_editor_role.yaml.j2` prompt content | render partial; assert references to "revision_brief", "chat transcript", "preserve original" |
| 5 | `RevisionRunner` happy path E2E | fake editor + source bundle on disk; verify ReportComplete + bundle copied |
| 6 | `RevisionRunner` fails when source bundle missing | delete source bundle; assert ReportError emitted, ReportComplete not |
| 7 | `RevisionRunner` writes new bundle as a copy of source | assert source and new bundle bytes identical |
| 8 | `POST /reports/{id}/revise` auth: 404 for other user's source | hit endpoint as user B with user A's report; expect 404 |
| 9 | `POST /reports/{id}/revise` auth: 400 when chat not bound to source | unbound chat or mismatched binding; expect 400 |
| 10 | `POST /reports/{id}/revise` returns new report_id + status=generating fast (<1s) | hit endpoint; verify fast response shape |
| 11 | Per-source-chat-session lock serializes revisions | fire two parallel revisions on same chat; assert one wins + second sees stale source |
| 12 | `run_wrapped_revision` re-anchors chat on success | run to completion; verify `chat_sessions.attached_report_id` updated |
| 13 | `run_wrapped_revision` does NOT re-anchor on failure | runner emits ReportError; verify chat still bound to original |
| 14 | `chat.attached_report_changed` event fanout | spy on presence; verify event emitted on successful completion |
| 15 | Chat-route intercepts `revise_report` tool calls (not dispatched) | mock dispatcher; verify dispatch NOT called for revise_report |
| 16 | Synthetic tool result returned to LLM is `revision_started` | inspect conversation after intercept; assert correct synthetic shape |
| 17 | Subject-keyed binding: same ticker re-anchors instead of new thread | bound chat to MSFT; generate MSFT again; verify same chat session_id returned, attached_report_id updated |
| 18 | Subject-keyed binding: different ticker spawns new thread | bound chat to MSFT; generate AAPL; verify new session id + redirect:true |
| 19 | Retry on revision routes through `/revise` not `/generate` | seed failed revision row; hit `/retry`; assert revise route hit (mock + assert) |
| 20 | Frontend: RevisionInProgressChip renders + Cancel button DELETEs | render with mock report_id; click Cancel; assert fetch called with DELETE |
| 21 | Frontend: chat re-fetches on `chat.attached_report_changed` | dispatch event; assert chat refetch called |

---

## Rollout plan

| Phase | Trigger | Action |
|---|---|---|
| v1 ship | Branch merges (after subagent runner AND chat-followup both merged) | `OPENLIA_REVISION_PASS_ENABLED=0`. `revise_report` not registered; `/revise` route exists but rejects when flag off. |
| Author validation | Manually flip flag; generate MSFT report, discuss, ask for "final version" | Confirm revision fires, completes within ~30s, chat re-anchors, revised report appears in Repository, ticker-keyed binding works for "now generate AAPL" |
| Soft launch | Validation passes | Flip flag default `1`; document in changelog |
| Expansion | Soft launch stable for a week | Extend `revision_editor_role.yaml.j2` to other report departments (earnings_update, morning_briefing) |
| v2 features | After expansion | Provenance link if users request, section-level revisions (replace just one section), cross-thread merging if a use-case emerges |

---

## Open questions

None. All design decisions locked. Implementation plan to follow via writing-plans skill.

---

## Acceptance criteria (v1)

- [ ] `OPENLIA_REVISION_PASS_ENABLED=1` registers `revise_report` in the tool list for bound chat sessions
- [ ] LLM-triggered revision creates a new report row (status=generating) within ~1s and returns immediately to the model with `revision_started`
- [ ] RevisionRunner completes in ~30s for a standard 14-section report at ~$0.20 cost
- [ ] On success, source chat's `attached_report_id` re-points to the new revision; chat header banner updates; new bundle is on disk for the revised report
- [ ] On failure, source chat stays bound to original; failed-card appears in Repository; Retry button works (re-routes through `/revise`)
- [ ] Source bundle missing → revision fails loud with the right error message
- [ ] Ticker-keyed binding: generating MSFT again from a MSFT-bound chat stays in the thread; generating AAPL spawns a new thread
- [ ] Per-chat-session lock prevents racey re-anchors
- [ ] All 21 tests in the test plan pass
- [ ] Flag OFF: chat-followup behavior unchanged from its v1 baseline (no `revise_report` in tool list, no ticker-keyed re-anchor — strict per-report immutability)

> **Spec amendment dependency:** This spec amends `docs/superpowers/specs/2026-05-17-report-chat-followup-design.md` §3 and §4. The amendments are GATED on `OPENLIA_REVISION_PASS_ENABLED=1` — when the flag is off, chat-followup behaves exactly as its standalone spec describes (strict immutability of `attached_report_id`, per-report thread). When the flag is on, ticker-keyed re-anchoring is active.
