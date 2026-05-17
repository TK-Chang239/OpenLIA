# Background Report Generation — Design

**Date:** 2026-05-17
**Status:** Draft — pending implementation plan
**Branch:** new branch to be created from `feat/subagent-report-architecture` (or from main, after that branch ships)
**Spec siblings:**
- `docs/superpowers/specs/2026-05-16-subagent-report-architecture-design.md` (the runner this builds on)
- `docs/superpowers/specs/2026-05-17-report-chat-followup-design.md` (independent feature; can ship before/after this one)

---

## Problem

Today, equity research report generation streams server-side events to the page that initiated the request. The SSE connection is bound to the page. Navigating away from the equity_research page drops the SSE connection — and with it, the report generation cancels (the wrapper coroutine sees its consumer disappear and aborts).

This is a poor fit for a 6-minute generation. The user wants to kick off a report and walk away — get notified when it's done, navigate freely in the meantime. Multiple reports should be able to run in parallel (e.g., kick off MSFT, navigate to portfolio, kick off AAPL).

## Goals

- **Fire and forget UX.** Kick off a report, navigate anywhere in OpenLIA, completion notifies the user via toast wherever they are.
- **Unbounded parallel.** No cap on concurrent reports.
- **Re-attachable live progress.** Navigating back to the equity_research page (or clicking a generating-state card from the Repository) re-attaches to the live SSE stream as if the user never left.
- **Auto-cancel on browser close.** Closing all OpenLIA tabs for 90+ seconds cancels in-flight generations — avoids "I forgot I had this running" cost surprises.
- **Resilient to server restart.** In-flight reports caught by a restart are marked failed with a clear reason; a one-click Retry button re-submits the original request.

## Non-goals (deferred)

- **Retroactive notifications.** If the user is offline when completion fires, no "ding" pops up next time. They see the completed report in the Repository normally. (v2 adds an unread-notification queue.)
- **Multi-process deployments.** The in-process task registry assumes a single uvicorn worker. v2 would swap for Redis/Postgres pub-sub.
- **Resume-from-checkpoint.** Restart-orphaned reports get marked failed; no partial-progress resume.
- **Concurrency cap.** Unbounded by design. v2 could add a per-user soft cap.
- **Background notifications for other report departments.** v1 ships for equity_research only; expansion to other report departments comes later (same code paths work).

---

## Architecture overview

```
POST /reports/generate
  ├─ Insert reports row with status='generating', original_request=<json>
  ├─ registry.submit(report_id, runner_coroutine, user_id)
  │   └─ asyncio.create_task(_wrapper(runner, report_id, user_id))
  └─ Return immediately with {"report_id": ..., "status": "generating"}

Background _wrapper coroutine (in-process):
  ├─ for event in runner.run():
  │    event_ring.append(event)
  │    for queue in subscriber_queues: queue.put_nowait(event)
  │    persist event side-effects (status updates, report payload on complete)
  └─ on done: fanout {type:report.complete|failed|cancelled} to presence channel

GET /reports/{report_id}/stream
  ├─ Look up task in registry
  ├─ If found: replay event_ring → attach as new subscriber queue → tail live
  └─ If not found: synthesize terminal event from DB row → end stream

GET /notifications/stream (app-shell SSE, opened once per browser session)
  └─ presence registry attaches queue, fanout receives report.complete etc.

DELETE /reports/{report_id}
  ├─ Mark row status='cancelled'
  └─ asyncio.cancel() on the task

App-shell beforeunload → POST /notifications/presence-close (sendBeacon)
  └─ Speeds up presence-disconnect detection (auto-cancel sweep still fires after grace)

Background auto-cancel sweep (asyncio task, runs every 15s):
  └─ For each user with no presence connections for >90s, cancel all their in-flight reports
```

**Why this hits the targets:**

| Goal | Mechanism |
|---|---|
| Fire and forget | POST returns immediately; background task survives client disconnect |
| Unbounded parallel | No concurrency primitive constrains task submission |
| Re-attachable live progress | event_ring replay + fan-out queues |
| Auto-cancel on browser close | Presence registry + grace-period sweep |
| Resilient to server restart | startup sweep marks orphans failed; original_request enables Retry |

---

## Section 1 — Background task registry + lifecycle

### Data structures

```python
@dataclass
class BackgroundReportTask:
    """One running report generation. Wraps the asyncio task and the
    fan-out queues that SSE subscribers attach to."""
    report_id: str
    user_id: str
    asyncio_task: asyncio.Task
    subscriber_queues: set[asyncio.Queue]    # each open SSE attaches one
    event_ring: deque                         # last 200 events for late subscribers
    started_at: datetime
    cancelled: bool = False                   # set True by DELETE handler

class BackgroundReportRegistry:
    """Per-process singleton. Lives on app state."""
    _by_report_id: dict[str, BackgroundReportTask]
    _by_user_id: dict[str, set[str]]          # user_id → set of report_ids

    def submit(self, *, user_id: str, report_id: str, runner_coro) -> BackgroundReportTask: ...
    def get(self, report_id: str) -> BackgroundReportTask | None: ...
    def cancel(self, report_id: str) -> bool: ...
    def cancel_user(self, user_id: str) -> list[str]: ...   # returns cancelled report_ids
    def list_active(self, user_id: str) -> list[BackgroundReportTask]: ...
    def forget(self, report_id: str) -> None: ...           # called by wrapper finally clause
```

### Wrapper coroutine

The wrapper is what `registry.submit` schedules. It owns the lifecycle: persists state changes, fans out events, handles cancellation.

```python
async def _wrapper(
    runner_coro,
    *,
    report_id: str,
    user_id: str,
    db_session_factory,
    presence: UserPresenceRegistry,
    registry: BackgroundReportRegistry,
) -> None:
    task = registry.get(report_id)
    try:
        async for event in runner_coro:
            task.event_ring.append(event)
            for queue in list(task.subscriber_queues):
                try:
                    queue.put_nowait(event)
                except asyncio.QueueFull:
                    try:
                        queue.get_nowait()  # drop oldest
                        queue.put_nowait(event)
                    except Exception:
                        pass
            if isinstance(event, ReportComplete):
                _persist_complete(db_session_factory, report_id, event.schema)
                presence.fanout(user_id, {
                    "type": "report.complete",
                    "report_id": report_id,
                    "title": event.schema.get("cover", {}).get("title", ""),
                })
            elif isinstance(event, ReportError):
                _persist_failed(db_session_factory, report_id, event.message)
                presence.fanout(user_id, {
                    "type": "report.failed",
                    "report_id": report_id,
                    "failure_reason": event.message,
                })
    except asyncio.CancelledError:
        _persist_cancelled(db_session_factory, report_id, "user_cancelled")
        presence.fanout(user_id, {"type": "report.cancelled", "report_id": report_id})
        raise
    finally:
        registry.forget(report_id)
```

### Fan-out semantics

- Each open SSE subscriber gets its own `asyncio.Queue(maxsize=512)`
- Producer (wrapper) `put_nowait` to all queues per event
- On `QueueFull`: drop the queue's oldest event, then push new (slow-consumer policy is drop-oldest, not block-producer)
- Late subscribers (joining mid-generation) drain `event_ring` first, then start receiving live events
- `event_ring` size: **200 events**, covers typical 14-section run end-to-end

### App-shutdown handling

FastAPI `lifespan` shutdown hook iterates the registry, cancels each task with a short timeout, persists `failed/server_shutdown`. The startup sweep (§2) catches anything that wasn't fully persisted.

---

## Section 2 — Persistence (status, original_request, startup sweep)

### DB migration

```sql
ALTER TABLE reports ADD COLUMN status TEXT NOT NULL DEFAULT 'complete';
-- Values: 'generating' | 'complete' | 'failed' | 'cancelled'
-- Existing rows backfill as 'complete' (they're all finished).

ALTER TABLE reports ADD COLUMN failure_reason TEXT NULL;
-- Populated on failed/cancelled. Examples: 'server_restart_interrupted',
-- 'server_shutdown', 'user_cancelled', 'session_disconnected',
-- 'provider_error: ...'

ALTER TABLE reports ADD COLUMN original_request JSON NULL;
-- Persisted ReportRequest at submit time (department, mode, user_input,
-- enabled_sections, custom_sections, length). Used by the Retry button.

ALTER TABLE reports ADD COLUMN started_at DATETIME NULL;
-- When generation began (distinct from row created_at). Powers the
-- elapsed-time counter on the placeholder card.

CREATE INDEX IF NOT EXISTS idx_reports_status ON reports (status);
```

### Status transitions

```
                       ┌──────────────┐
   POST /generate ────→│  generating  │
                       └──────┬───────┘
              ┌───────────────┼───────────────┐
              ↓               ↓               ↓
        ┌──────────┐    ┌──────────┐    ┌──────────┐
        │ complete │    │  failed  │    │cancelled │
        └──────────┘    └──────────┘    └──────────┘
            ↑                ↑               ↑
       runner done     runner raised    DELETE /reports/{id}
                       or restart sweep  or auto-cancel sweep
```

### Server startup sweep

In the FastAPI `lifespan` startup hook:

```python
async def sweep_orphaned_generating_reports(db_session_factory) -> None:
    """Any reports still marked 'generating' at startup are orphans
    from a previous process. Mark them failed; the Retry button
    (using original_request) lets the user re-submit."""
    with db_session_factory() as session:
        orphans = session.query(Report).filter(Report.status == "generating").all()
        for row in orphans:
            row.status = "failed"
            row.failure_reason = "server_restart_interrupted"
        session.commit()
        log.info("startup sweep marked %d orphaned reports failed", len(orphans))
```

Runs once. Idempotent. After it completes, the in-process registry is empty.

### Retry flow

```
Frontend: user clicks "Retry" on a failed/cancelled card
  └─ POST /reports/{id}/retry
       Server reads original_request from the failed row
       Submits a NEW generation with that request
       Returns the new report_id
       Old failed row stays in the Repository as audit trail
```

Retry creates a **new** row — never mutates the failed row. Preserves audit history; avoids dangling-reference issues for chat sessions bound to the old id.

---

## Section 3 — SSE re-subscription

### The endpoint

```
GET /reports/{report_id}/stream
  → SSE stream of named events (same frame format as today's report SSE)
```

Frame shape is unchanged: `ReportStart`, `ReportPhase`, `ReportSectionStart`, `ReportSectionComplete`, `ReportToolCall`, `ReportToolCallStart`, `ReportComplete`, `ReportError`, etc. Existing `useReportStream.ts` parser works unchanged.

### Handler

```python
@router.get("/{report_id}/stream")
async def stream_report(
    report_id: str,
    user=Depends(get_current_user),
    registry: BackgroundReportRegistry = Depends(get_registry),
    db: Session = Depends(get_db),
) -> StreamingResponse:
    row = db.get(Report, report_id)
    if row is None or row.user_id != user.id:
        raise HTTPException(404)

    task = registry.get(report_id)

    async def event_generator():
        if task is None:
            # Generation already finished — synthesize a terminal event
            # from the persisted row.
            yield _to_sse_frame(_synthesize_terminal_event(row))
            return

        # Live attachment: replay ring, then tail.
        queue: asyncio.Queue = asyncio.Queue(maxsize=512)
        task.subscriber_queues.add(queue)
        try:
            for ev in list(task.event_ring):
                yield _to_sse_frame(ev)
            while True:
                ev = await queue.get()
                yield _to_sse_frame(ev)
                if isinstance(ev, (ReportComplete, ReportError)):
                    return
        finally:
            task.subscriber_queues.discard(queue)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


def _synthesize_terminal_event(row: Report):
    if row.status == "complete":
        return ReportComplete(report_id=row.id, schema=json.loads(row.report_schema_json))
    if row.status == "cancelled":
        return ReportError(report_id=row.id, code="cancelled",
                           message=row.failure_reason or "Cancelled")
    # 'failed' or unexpected
    return ReportError(report_id=row.id, code="failed",
                       message=row.failure_reason or "Generation failed")
```

### Authorization

- Report row exists
- Report's `user_id` matches the requesting user

### Unification with the originating page

The originating page (the one that clicked "Generate") uses the same `GET /reports/{id}/stream` endpoint as any revisit. The new flow:

1. POST `/reports/generate` → returns `{report_id}` in <500ms
2. Frontend opens `GET /reports/{id}/stream` → SSE consumer (identical to revisit path)

The old POST-based SSE on `useReportStream.ts` is replaced by the new GET endpoint. No special case between "first viewer" and "revisitor."

---

## Section 4 — Presence channel + auto-cancel + completion notifications

### The notifications SSE

Opened by the app shell when the React app loads. Stays open across page navigation. Closes only on tab close or logout.

```
GET /notifications/stream
  → SSE stream of named events for this user
  Events:
    - report.complete   { report_id, title }
    - report.failed     { report_id, failure_reason }
    - report.cancelled  { report_id }
    - report.heartbeat  (every 30s — proxy keepalive)
```

### Presence registry

```python
class UserPresenceRegistry:
    _user_connections: dict[str, set[asyncio.Queue]]
    _last_disconnect_at: dict[str, datetime]

    def attach(self, user_id: str) -> asyncio.Queue:
        queue = asyncio.Queue(maxsize=64)
        self._user_connections.setdefault(user_id, set()).add(queue)
        self._last_disconnect_at.pop(user_id, None)
        return queue

    def detach(self, user_id: str, queue: asyncio.Queue) -> None:
        conns = self._user_connections.get(user_id, set())
        conns.discard(queue)
        if not conns:
            self._user_connections.pop(user_id, None)
            self._last_disconnect_at[user_id] = datetime.now(UTC)

    def fanout(self, user_id: str, event: dict) -> None:
        for queue in self._user_connections.get(user_id, set()):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                pass

    def users_with_no_connections(self) -> dict[str, datetime]:
        return dict(self._last_disconnect_at)
```

### Auto-cancel sweep

Background asyncio task started at app launch:

```python
async def auto_cancel_sweep(
    *,
    presence: UserPresenceRegistry,
    registry: BackgroundReportRegistry,
    db_session_factory,
    grace_seconds: int = 90,
    poll_seconds: int = 15,
) -> None:
    while True:
        await asyncio.sleep(poll_seconds)
        now = datetime.now(UTC)
        for user_id, last_seen in presence.users_with_no_connections().items():
            if (now - last_seen).total_seconds() >= grace_seconds:
                cancelled_ids = registry.cancel_user(user_id)
                if cancelled_ids:
                    with db_session_factory() as session:
                        for rid in cancelled_ids:
                            row = session.get(Report, rid)
                            if row and row.status == "generating":
                                row.status = "cancelled"
                                row.failure_reason = "session_disconnected"
                        session.commit()
                    log.info("auto-cancelled %d reports for user %s", len(cancelled_ids), user_id)
```

Grace period: **90 seconds** (tunable via `OPENLIA_AUTO_CANCEL_GRACE_SECONDS`). Poll interval: **15 seconds** (tunable via `OPENLIA_AUTO_CANCEL_POLL_SECONDS`).

### Completion notification delivery

The wrapper coroutine (§1) calls `presence.fanout(user_id, {...})` on terminal events. If the user has an open notification SSE, the event arrives in ms and the toast fires. If they don't, the event is dropped — they see the completed report in the Repository next time they're online (no retroactive toast in v1).

### Heartbeat

Every 30 seconds, the server emits `report.heartbeat` to all open notification SSEs. Standard SSE keepalive prevents proxy timeouts during quiet periods.

### `POST /notifications/presence-close` (best-effort hint)

App shell `beforeunload` handler pings this with `navigator.sendBeacon`. Server fast-forwards the user's `_last_disconnect_at` so the auto-cancel sweep picks them up on the next cycle (instead of waiting the SSE close timeout + 90s grace).

```python
@router.post("/presence-close")
def presence_close(user=Depends(get_current_user), presence: UserPresenceRegistry = Depends(...)) -> dict:
    # Force the user's last_disconnect to "now - grace_seconds + small_margin"
    # so the next sweep tick will catch them. Idempotent; safe to call even
    # if the user still has other tabs open (those tabs' SSE connections
    # will reset the timestamp on their next event).
    presence.set_imminent_disconnect(user.id)
    return {"ok": True}
```

Best-effort: if the beacon doesn't fire, the standard SSE close detection + 90s sweep still does the right thing.

---

## Section 5 — Frontend touchpoints

### App shell — notifications SSE consumer

```ts
// frontend/src/app/useNotificationsStream.ts (new)
export function useNotificationsStream(): void {
  useEffect(() => {
    const es = new EventSource("/notifications/stream");
    es.addEventListener("report.complete", (e) => {
      const { report_id, title } = JSON.parse((e as MessageEvent).data);
      toast.success(`Report ready: ${title}`, {
        action: { label: "Open", onClick: () => navigate(`/reports/${report_id}`) },
      });
    });
    es.addEventListener("report.failed", (e) => {
      const { report_id, failure_reason } = JSON.parse((e as MessageEvent).data);
      toast.error(`Report failed: ${failure_reason}`, {
        action: { label: "Open", onClick: () => navigate(`/reports/${report_id}`) },
      });
    });
    es.addEventListener("report.cancelled", (e) => {
      const { report_id } = JSON.parse((e as MessageEvent).data);
      toast.info("Report cancelled", {
        action: { label: "Open", onClick: () => navigate(`/reports/${report_id}`) },
      });
    });
    return () => es.close();
  }, []);
}
```

Called once in the top-level `App.tsx`.

### Repository view — status-aware report cards

```tsx
function ReportCard({ report }: { report: Report }) {
  switch (report.status) {
    case "generating":
      return <GeneratingPlaceholderCard report={report} />;
    case "complete":
      return <CompletedReportCard report={report} />;
    case "failed":
    case "cancelled":
      return <FailedReportCard report={report} />;
  }
}
```

- **GeneratingPlaceholderCard**: title (from `original_request.user_input`), spinner, `started_at`-derived elapsed counter, Cancel button. Click navigates to `/equity-research?report_id={id}` so the page re-attaches.
- **CompletedReportCard**: today's card (Open/Download/Delete/Discuss).
- **FailedReportCard**: greyed, error icon, failure_reason text, Retry + Delete buttons.

### Cancel button on generating cards

```tsx
async function handleCancel(report_id: string) {
  if (!confirm("Cancel this report? Partial progress will be discarded.")) return;
  await fetch(`/reports/${report_id}`, { method: "DELETE" });
  // Notification SSE delivers the cancelled event; Repository view re-renders.
}
```

### Retry button on failed/cancelled cards

```tsx
async function handleRetry(failed_report_id: string) {
  const resp = await fetch(`/reports/${failed_report_id}/retry`, { method: "POST" });
  const { report_id } = await resp.json();
  navigate(`/equity-research?report_id=${report_id}`);
}
```

### Equity research page — re-attach on mount

```tsx
// On user kickoff: POST then attach.
async function handleGenerate(request: ReportRequest) {
  const { report_id } = await api.reports.generate(request);
  attachToReport(report_id);
}

// On page mount with ?report_id query: attach to existing stream.
useEffect(() => {
  const id = searchParams.get("report_id");
  if (id) attachToReport(id);
}, [searchParams.get("report_id")]);

function attachToReport(report_id: string) {
  const es = new EventSource(`/reports/${report_id}/stream`);
  // existing event handlers from useReportStream.ts, unchanged
  // (the SSE protocol is identical)
  return () => es.close();
}
```

The unification (§3) means **one code path** for live progress: the SSE consumer. No special case for "originating page" vs "revisit."

### `beforeunload` beacon for fast presence-close

```tsx
useEffect(() => {
  function onBeforeUnload() {
    navigator.sendBeacon("/notifications/presence-close");
  }
  window.addEventListener("beforeunload", onBeforeUnload);
  return () => window.removeEventListener("beforeunload", onBeforeUnload);
}, []);
```

Best-effort. If the beacon doesn't arrive, the 90s sweep still works.

### What does NOT change

- Existing `useReportStream.ts` event handlers (the SSE protocol is unchanged; only the URL changes from POST-based to GET endpoint)
- Report viewer pages
- Existing chat infrastructure
- Existing report-bundle generation (chat-followup feature stays independent)

---

## Configuration surfaces

| Env var | Default | Purpose |
|---|---|---|
| `OPENLIA_BACKGROUND_REPORTS_ENABLED` | `0` | Feature flag — when `1`, the new background path is active. When `0`, existing POST-based SSE behavior continues. |
| `OPENLIA_EVENT_RING_SIZE` | `200` | Per-task event ring capacity for late-subscriber replay |
| `OPENLIA_AUTO_CANCEL_GRACE_SECONDS` | `90` | Time after last presence disconnect before auto-cancel fires |
| `OPENLIA_AUTO_CANCEL_POLL_SECONDS` | `15` | How often the auto-cancel sweep runs |
| `OPENLIA_NOTIFICATIONS_HEARTBEAT_SECONDS` | `30` | Notifications SSE heartbeat interval |

---

## File layout

### New files

```
packages/server/src/openlia_server/services/
  background_report_registry.py     # BackgroundReportTask + BackgroundReportRegistry
  user_presence_registry.py         # UserPresenceRegistry
  auto_cancel_sweep.py              # The asyncio background sweep task
  report_wrapper.py                 # _wrapper coroutine (lifecycle, fan-out, persist)

packages/server/src/openlia_server/routes/
  reports_stream.py                 # GET /reports/{id}/stream + DELETE /reports/{id} + POST /reports/{id}/retry
  notifications_stream.py           # GET /notifications/stream + POST /notifications/presence-close

packages/server/tests/
  test_background_report_registry.py
  test_user_presence_registry.py
  test_auto_cancel_sweep.py
  test_report_wrapper.py
  test_reports_stream.py
  test_notifications_stream.py
  test_retry_flow.py
  test_startup_sweep.py

frontend/src/app/
  useNotificationsStream.ts         # App-shell SSE consumer + toasts
  useBeforeUnloadBeacon.ts          # presence-close ping

frontend/src/components/equity-research/
  GeneratingPlaceholderCard.tsx     # status="generating" card variant
  FailedReportCard.tsx              # status="failed"|"cancelled" card variant
```

### Modified files

- `packages/server/src/openlia_server/app.py` (or lifespan setup) — wire registry, presence, auto-cancel sweep, startup sweep
- `packages/server/src/openlia_server/db/models/content.py` — add 4 new columns to Report model
- `packages/server/src/openlia_server/db/migrations/versions/` — Alembic migration
- `packages/server/src/openlia_server/routes/reports.py` (or wherever generate lives) — POST returns immediately, spawns registry task instead of streaming
- `frontend/src/components/equity-research/ReportCard.tsx` — switch by `status`
- `frontend/src/components/report/useReportStream.ts` — change URL from POST-based to `GET /reports/{id}/stream`
- `frontend/src/pages/EquityResearchPage.tsx` (or equivalent) — handle `?report_id` query
- `frontend/src/App.tsx` — install `useNotificationsStream` + `useBeforeUnloadBeacon`

### Untouched

- `SubagentReportRunner` itself — the runner is consumed as an async iterator; backgrounding wraps the iterator without changing it
- Report viewer pages
- Report content schema and validator
- All other report departments (the background path ships behind a flag, gated to equity_research)

---

## Test plan (vertical slices, TDD)

| # | Slice | RED test |
|---|---|---|
| 1 | `BackgroundReportRegistry.submit/get/cancel` | create + retrieve + cancel; verify task ends and forget() called |
| 2 | `BackgroundReportRegistry.cancel_user` | cancel multiple tasks for one user, leave another user's task alone |
| 3 | `event_ring` truncates at 200 | submit > 200 events; assert ring stays bounded |
| 4 | Fan-out drops oldest on QueueFull | fill a queue past maxsize; assert oldest dropped |
| 5 | `_wrapper` persists `complete` status + payload on ReportComplete | mock runner yields ReportComplete; verify DB row updated |
| 6 | `_wrapper` persists `failed` status on ReportError | mock runner yields ReportError; verify DB updated with failure_reason |
| 7 | `_wrapper` persists `cancelled` status on asyncio.CancelledError | cancel task; verify DB updated with user_cancelled |
| 8 | DB migration adds 4 columns + index | apply migration; verify schema |
| 9 | POST /reports/generate returns report_id immediately | hit endpoint; assert response time < 1s + report_id present + row exists with status=generating + original_request stored |
| 10 | GET /reports/{id}/stream attaches as new subscriber to live task | mock task with events; subscribe via SSE; assert events received |
| 11 | GET /reports/{id}/stream synthesizes terminal event for finished report | finish a task; subscribe AFTER finish; assert one synthetic ReportComplete frame + stream ends |
| 12 | GET /reports/{id}/stream 404 for other users | request stream as user B for user A's report; expect 404 |
| 13 | DELETE /reports/{id} cancels the task | submit task; DELETE; assert task ends + row marked cancelled |
| 14 | POST /reports/{id}/retry creates new generation from original_request | submit + fail; POST retry; assert new report_id, new row generating, same original_request |
| 15 | GET /notifications/stream attaches to presence registry | open SSE; verify registry has the user; close; verify last_disconnect timestamp set |
| 16 | presence.fanout delivers to all open notification SSEs | open 2 SSEs for same user; fanout; assert both receive |
| 17 | Auto-cancel sweep cancels tasks for users disconnected > grace_seconds | drop user's last connection; advance time past grace; run sweep; assert cancel_user called |
| 18 | Auto-cancel sweep ignores users with open connections | keep connection open; assert nothing cancelled |
| 19 | POST /notifications/presence-close fast-forwards disconnect | open SSE; close connection; POST presence-close; assert sweep cancels on next tick |
| 20 | Startup sweep marks orphaned generating rows failed | seed generating row; restart-style startup hook; assert row updated |
| 21 | Heartbeat fires every 30s on notification SSE | open SSE; wait > 30s; assert heartbeat event received |
| 22 | Reports list endpoint returns status column | seed reports of each status; assert list includes status field |

---

## Rollout plan

| Phase | Trigger | Action |
|---|---|---|
| v1 ship | branch merges | `OPENLIA_BACKGROUND_REPORTS_ENABLED=0`. Existing POST-based SSE flow unchanged. New routes exist but frontend doesn't use them. |
| Author validation | Manually flip flag; generate 3-5 reports; test navigate-away + revisit + auto-cancel + retry | Confirm fire-and-forget works, no orphan tasks after restart, toast fires, auto-cancel triggers within ~90s of tab close |
| Soft launch | Validation passes | Flip flag default `1` for self-hosted personal-mode deployments; update changelog |
| Expansion | Soft launch stable for a week | Extend to other report departments (morning_briefing, earnings_update) — same code paths work, just register their runners with the same registry |
| v2 features | After expansion | Retroactive notifications (unread queue), multi-process broker (Redis/Postgres pub-sub), resume-from-checkpoint, per-user concurrency cap |

---

## Open questions

None. All design decisions locked. Implementation plan to follow via the writing-plans skill.

---

## Acceptance criteria (v1)

- [ ] `OPENLIA_BACKGROUND_REPORTS_ENABLED=1` routes report generation through the background registry; POST returns within 1s with the new report_id
- [ ] Navigating away from the equity_research page during generation does NOT cancel the report; it continues to completion
- [ ] Navigating back to the equity_research page with `?report_id={id}` (or clicking a generating card) attaches to the live stream with no event loss
- [ ] Multiple reports can run in parallel (no concurrency cap)
- [ ] Closing all OpenLIA tabs causes in-flight reports to be cancelled within 90-105 seconds (presence sweep)
- [ ] `POST /notifications/presence-close` from the `beforeunload` beacon speeds up the cancel to the next sweep tick (~15s instead of waiting for SSE close detection)
- [ ] Restarting the server while reports are in flight: on restart, those rows are marked `failed/server_restart_interrupted`; Retry button works
- [ ] DELETE on a generating report cancels the task and updates the row to `cancelled/user_cancelled`
- [ ] Retry button creates a new generation from the persisted `original_request`; old failed row remains as audit trail
- [ ] Completion fires a toast in the app shell via the notifications SSE
- [ ] All 22 tests in the test plan pass
- [ ] Flag OFF: every existing report path generates identically to pre-merge (backward compat)
