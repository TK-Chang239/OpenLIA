# Phase 12 — Shared Chat Components fix plan (→ 100%)

**Current:** ~90% shipped against plan; ~70% against spec. **Root causes:** IMPLEMENTER (Department type, drawer scope, services/files split, chat markdown, helper microcopy) + SPEC_DRIFT (FileDownload/SaveToRepo feedback details, chat history search/archive).

**Scope clarifications (supersede prior fix-plan):**

- Vitests are **not** absent. `frontend/src/components/chat/__tests__/` ships 11 specs and `components/viewer/__tests__/FileViewer.test.tsx` ships 4. The master-tracker "zero vitests" line (§5) is stale; what is missing are **targeted** specs for the gaps below, not a greenfield suite. P2-17 is folded into per-item acceptance clauses.
- Existing fix-plan NEW-12-01 asserts a "PDF + DOCX dropdown" — **FileDownloadSpec explicitly rejects that**: one click, no dropdown, no modal, browser-native download. Rewritten below as button-feedback contract.
- Existing fix-plan NEW-12-02 asserts a post-save toast — **SaveToRepoSpec explicitly says no toast; feedback stays inside the button**. Rewritten below as aria-live + idempotency contract.
- P1-09 (Repository row click → FileViewer) is owned by Phase 22; Phase 12 owns the FileViewerContext contract it consumes. Cross-referenced only.

---

## Tasks (in execution order)

### 1. **P1-02 — Widen `Department` union to all 7 departments.**
- Bug: `frontend/src/api/chat.ts:3` declares `export type Department = "secretary" | "equity_research"`. Drawer filter `items.filter((i) => i.department === department)` (ChatHistoryDrawer.tsx:32) silently returns empty for the other 5 slugs; callers passing `"morning_briefing" | "earnings_update" | "retail_sentiment" | "macro_research" | "panic_thermometer"` don't even type-check against the server enum.
- Files:
  - Create `frontend/src/api/departments.ts` exporting `DepartmentSlug` union (`"secretary" | "equity_research" | "earnings_update" | "morning_briefing" | "retail_sentiment" | "macro_research" | "panic_thermometer"`) + runtime `DEPARTMENT_SLUGS: readonly DepartmentSlug[]`.
  - Edit `frontend/src/api/chat.ts` — replace line-3 inline union with `import type { DepartmentSlug as Department } from "./departments"; export type { DepartmentSlug as Department } from "./departments";`.
  - Verify all call sites: `frontend/src/components/chat/ChatHistoryDrawer.tsx`, `frontend/src/pages/*Page.tsx`, `frontend/src/hooks/useMbChatSession.ts` still compile.
- Plan ref: File Structure §Frontend chat layer (typed clients).
- Spec ref: ChatHistorySpec §Database References (allowed slugs), ChatInterfaceSpec §Overview (Secretary + ER today; MB chat added Phase 16 lands on same type).
- Acceptance: vitest — render `<ChatHistoryDrawer department={d} …/>` once per slug, assert matching session renders; `tsc --noEmit` clean; `rg "\"secretary\" \\| \"equity_research\"" frontend/src` returns zero hits.
- Verification: `cd frontend && npm run test -- ChatHistoryDrawer && npx tsc -p tsconfig.json --noEmit`.

### 2. **NEW-12-04 — ChatHistoryDrawer: scope list to department + include archived filter.**
- Bug: `listSessions()` in `ChatHistoryDrawer.tsx:30` calls the server with no `department` param and with `include_archived` defaulted false, then filters client-side. Wasteful and incorrect once per-department indexes matter; archived sessions are silently unreachable (no Archived section — spec §Key Behaviors requires archive visibility).
- Files:
  - Edit `frontend/src/api/chat.ts` — extend `listSessions(opts?: { department?: DepartmentSlug; include_archived?: boolean })` to build `?department=…&include_archived=true` query.
  - Edit `frontend/src/components/chat/ChatHistoryDrawer.tsx` — call `listSessions({ department, include_archived: true })`; split `items` into `pinned`, `recent` (active & not archived), `archived` sections; render an `Archived` collapsible group.
  - Edit `packages/server/src/openlia_server/routes/chat_sessions.py` — accept `department` query filter on `GET /chat/sessions`.
- Plan ref: Task 1 "Chat sessions service + routes (GET /chat/sessions)".
- Spec ref: ChatHistorySpec §Key Behaviors — "Pin / archive / delete sessions", "Session list in sidebar, sorted by last activity".
- Acceptance: vitest — drawer calls `listSessions` with `{ department, include_archived: true }`; archived row appears under an `Archived` heading and is visually muted; unarchive via the same pencil-row action row restores to Recent.
- Verification: `cd frontend && npm run test -- ChatHistoryDrawer`; `uv run pytest packages/server/tests/test_routes/test_chat_sessions_routes.py -k department_filter`.

### 3. **NEW-12-05 — ChatHistoryDrawer: add session search.**
- Bug: ChatHistorySpec §Key Behaviors mandates "Search across session titles and message content". Drawer has no search input.
- Files:
  - Edit `frontend/src/components/chat/ChatHistoryDrawer.tsx` — add a `<input type="search">` under the header; debounce ≥250ms; filter in-memory by title (v1) with an inline "search messages" future hook.
  - Create `packages/server/src/openlia_server/routes/chat_sessions.py` — accept `q` query on `GET /chat/sessions` filtering by title prefix.
- Plan ref: Task 11 "ChatHistoryDrawer".
- Spec ref: ChatHistorySpec §Key Behaviors bullet 2.
- Acceptance: vitest — type "foo" → only sessions whose title includes "foo" remain visible.
- Verification: `cd frontend && npm run test -- ChatHistoryDrawer`.

### 4. **NEW-12-06 — Chat input helper microcopy + a11y description.**
- Bug: `ChatInput.tsx:64` renders `⌘ + ENTER` inside the pill. ChatInterfaceSpec §Helper Text mandates "Enter to send · Shift+Enter for new line"; additionally spec §Input Field requires textarea `aria-label` describing its purpose (present) AND helper text below the input (spec §Helper Text `mt-2 text-xs text-center`). Neither shipped: the helper is inline-right and says something different.
- Files:
  - Edit `frontend/src/components/chat/ChatInput.tsx` — move helper outside the border, below the input row, `mt-2 text-xs text-[--color-text-tertiary] text-center select-none`; copy: "Enter to send · Shift+Enter for new line". Link via `aria-describedby` on textarea.
- Plan ref: Task 8 "ChatInput".
- Spec ref: ChatInterfaceSpec §Helper Text, §Input Field (Placeholder row), §Accessibility.
- Acceptance: vitest — helper element with exact copy exists outside the border wrapper; textarea has `aria-describedby` pointing to its id.
- Verification: `cd frontend && npm run test -- ChatInput`.

### 5. **NEW-12-07 — AssistantMessage: markdown rendering + code highlighting.**
- Bug: `AssistantMessage.tsx:21` renders `{content}` as `whitespace-pre-wrap` plain text. ChatInterfaceSpec §Assistant Message doesn't mandate markdown in so many words, but FileViewerSpec §Plain Text / Markdown and MB/ER specs require LLM output rendered with headings, lists, code fences, and tables (GFM). Observation ties this to Phase 14 ER chat follow-ups displaying raw backticks today.
- Files:
  - Edit `frontend/src/components/chat/AssistantMessage.tsx` — wrap `content` in `<ReactMarkdown remarkPlugins={[remarkGfm]} components={{ code: CodeBlock }}>` with a syntax-highlighter (`highlight.js` or `shiki` already bundled via MarkdownRenderer path); keep the inline streaming cursor after the rendered body.
  - Add `frontend/src/components/chat/CodeBlock.tsx` shared between AssistantMessage and MarkdownRenderer.
- Plan ref: Design Rules §7 (design tokens) + Tech Stack (`react-markdown + remark-gfm`).
- Spec ref: ChatInterfaceSpec §2 Assistant Message; reuse of markdown component noted in FileViewerSpec §Plain Text / Markdown "same markdown component as chat messages".
- Acceptance: vitest — `content="# Heading\n\n\`\`\`py\nx=1\n\`\`\`"` renders an `<h1>` and a `<code class="language-py">` block; streaming cursor still appears after the rendered tree when `streaming=true`.
- Verification: `cd frontend && npm run test -- AssistantMessage`.

### 6. **NEW-12-08 — WelcomeOverlay entry animation + reduced-motion.**
- Bug: `WelcomeOverlay.tsx:17` sets only `exit`; no `initial`/`animate` per ChatInterfaceSpec §Welcome State "Chip entry Staggered; first chip starts at 200ms delay" is present on chips but the overlay itself has no entry transition, and Design Rule §10 mandates `prefers-reduced-motion` handling (no-op when reduced). Neither overlay nor chips respect the media query.
- Files:
  - Edit `frontend/src/components/chat/WelcomeOverlay.tsx` — add `useReducedMotion` from framer-motion; when true, set all durations to 0 and remove stagger. Add overlay `initial={{opacity:0}} animate={{opacity:1}}` consistent with spec.
- Plan ref: Design Rule §10.
- Spec ref: ChatInterfaceSpec §Welcome State, §Animation Summary.
- Acceptance: vitest with `matchMedia('(prefers-reduced-motion: reduce)')` stubbed true; chip buttons have zero `transition.duration`.
- Verification: `cd frontend && npm run test -- WelcomeOverlay`.

### 7. **NEW-12-03 — ChatInterface: inline `chat.report_thumbnail` + `stopped_at` persistence.**
- Bug: useChatStream accumulates `reportThumbnails` into a flat array (useChatStream.ts:44) but there is no code path that re-anchors them at the token index where the event arrived. ChatInterfaceSpec event table says "Render a report thumbnail card inline at the current position in the assistant message"; observed UX today places thumbs after the message. Also, cancellation path stores `stopped_at` server-side per ChatHistorySpec but the frontend sends no explicit "stopped" signal — the disconnect is the signal — so verify the server writes `chat_messages.stopped_at` on EOF; otherwise the stopped label appears ephemerally but rehydrates as a normal assistant turn.
- Files:
  - Edit `frontend/src/components/chat/useChatStream.ts` — change `message: string` to `chunks: Array<{ type: "text"; text: string } | { type: "thumbnail"; report_id: string; filename: string }>`; `chat.token` appends/merges into last text chunk; `chat.report_thumbnail` pushes a thumbnail chunk.
  - Edit `frontend/src/components/chat/AssistantMessage.tsx` to render chunks in order (text with markdown, thumbnails inline).
  - Verify `packages/server/src/openlia_server/routes/chat_stream.py` (or equivalent) writes `ChatMessage.stopped_at = now()` on disconnect without terminal event; add test.
- Plan ref: Design Rules §1–§4 (event-stream authoritative); Task 5.
- Spec ref: ChatInterfaceSpec §Event Handling table (`chat.report_thumbnail` row, connection-closed row); ChatHistorySpec §Key Behaviors "Partial message persistence on cancellation (`stopped_at` marker)".
- Acceptance: vitest — send stream `token("intro ")`, `report_thumbnail({id,fn})`, `token(" outro")` → rendered DOM order: text "intro ", thumbnail card, text " outro"; server test asserts `stopped_at IS NOT NULL` after disconnect.
- Verification: `cd frontend && npm run test -- useChatStream AssistantMessage`; `uv run pytest packages/server/tests/test_routes/test_chat_stream.py -k stopped_at`.

### 8. **NEW-12-09 — FileViewer: focus-move-on-open + focus-return-on-close + mobile full-screen.**
- Bug: `FileViewer.tsx:38` renders `motion.aside` with `tabIndex={-1}` but never calls `.focus()` on open; Escape handler requires focus to already be within the panel, so keyboard users cannot close with Esc unless they tab in first. FileViewerSpec §Accessibility: "Focus should move into the panel when it opens"; "Escape key closes and returns focus to the triggering chip". Mobile breakpoint (<768px) needs full-screen overlay + back/swipe — not implemented (panel width rule `min 360px` breaks on 320px phones).
- Files:
  - Edit `frontend/src/components/viewer/FileViewer.tsx` — `useEffect` on `current`: focus the close button; stash `document.activeElement` into a ref; on unmount, restore it. Add a `matchMedia("(max-width: 767px)")` branch that renders full-viewport overlay.
  - Edit `frontend/src/components/viewer/FileViewerContext.tsx` — retain `lastTrigger: HTMLElement | null` on `open()`.
- Plan ref: Design Rule §9 "Accessibility first"; Task 13.
- Spec ref: FileViewerSpec §Accessibility, §Responsive Behavior.
- Acceptance: vitest — open viewer, assert `document.activeElement` matches Close button; press Esc, assert focus returns to chip; render at viewport 360px → panel is full-width (`100vw`).
- Verification: `cd frontend && npm run test -- FileViewer`.

### 9. **NEW-12-10 — FileViewer: scroll-position preservation across chip swaps.**
- Bug: FileViewerSpec §Multi-file: "Content area fades out then fades in with new content"; §Scroll: "Scroll position is preserved within the session if the user clicks away and returns to the same file". Today clicking a second chip calls `setCurrent(newTarget)` and the scroll container unmounts/remounts, losing position.
- Files:
  - Edit `frontend/src/components/viewer/FileViewerContext.tsx` — cache `{ [filename: string]: number }` of `scrollTop`.
  - Edit `frontend/src/components/viewer/FileViewer.tsx` — on `current` change apply stashed scroll; on unmount write current `scrollTop`; wrap content swap in `AnimatePresence` with the spec's fade timings (100ms out, 150ms in).
- Plan ref: Task 13.
- Spec ref: FileViewerSpec §Multi-file, §Scroll.
- Acceptance: vitest — open file A, scroll to `500`, open file B, re-open A → scrollTop === 500 (mock `scrollTo`).
- Verification: `cd frontend && npm run test -- FileViewer`.

### 10. **NEW-12-11 — CsvRenderer + PdfRenderer + MarkdownRenderer: error + retry states.**
- Bug: FileViewerSpec §States table requires an **Error** state with `AlertCircle` + "Try again" link. `MarkdownRenderer.tsx:18` only renders raw error text; `PdfRenderer.tsx` never reaches its error branch (no `.catch`); Csv/Image/Code renderers have no error state. Empty state ("This file is empty.") also missing across all renderers.
- Files:
  - Edit each renderer in `frontend/src/components/viewer/renderers/*.tsx` — add unified `useFileFetch(source)` hook returning `{status: "loading"|"loaded"|"error"|"empty"; data}`; render error + retry; render empty state.
  - Extract shared hook to `frontend/src/components/viewer/renderers/useFileFetch.ts`.
- Plan ref: Task 15.
- Spec ref: FileViewerSpec §States (Error, Empty, Loading).
- Acceptance: vitest per renderer — failed fetch → "Failed to load file." + a clickable "Try again" that re-issues fetch; empty 200 response → "This file is empty.".
- Verification: `cd frontend && npm run test -- MarkdownRenderer PdfRenderer CsvRenderer`.

### 11. **P2-16 / NEW-12-12 — Extract `services/files.py`.**
- Bug: `packages/server/src/openlia_server/routes/files.py` contains report path resolution, auth hops (attachment → message → session), filename sanitization, and existence checks. Violates Design Rule: "business logic belongs in core/services, routes are glue". Also, the current implementation serves **`.md`** for report downloads by fabricating a filename (`{title}.md`) but FileDownloadSpec requires "the original filename including extension" — reports should round-trip through `ReportExportService` to produce the spec-agreed PDF/DOCX via format param.
- Files:
  - Create `packages/server/src/openlia_server/services/files.py` with `resolve_report_download(db, user_id, report_id, format) -> FileStream` and `resolve_attachment_download(db, user_id, attachment_id) -> FileStream`.
  - Edit `packages/server/src/openlia_server/routes/files.py` — route contains only request parsing + `StreamingResponse` wrapping.
  - Accept `?format=pdf|docx|md` query on `GET /reports/{id}/download`; default to the stored export format.
  - Edit `frontend/src/api/files.ts` — `downloadUrlForReport(reportId, format?)`.
- Plan ref: File Structure §Backend — `services/files.py` line; Design Rule "business logic in services".
- Spec ref: FileDownloadSpec §Functionalities "Filename Preservation"; §Non-Goals "no format conversion" — so keep original format; the `format` param applies only when multiple exports exist.
- Acceptance: `uv run pytest packages/server/tests/test_services/test_files.py` passes; `routes/files.py` ≤ 40 LOC.
- Verification: `uv run pytest packages/server/tests/test_services/test_files.py packages/server/tests/test_routes/test_files.py`.

### 12. **NEW-12-01 (rewritten) — FileDownloadButton: spec-accurate feedback contract.**
- Bug: FileDownloadSpec §Download Feedback specifies ✓-for-1.5s on success, ⚠-for-2s on error, no toast, no modal, no dropdown (original NEW-12-01 said "dropdown — PDF + DOCX" which contradicts spec). The shipped component gets timing right but: (a) viewer-header variant label does not flip to "Downloaded" for 1.5s post-success or "Failed" on error, (b) no `aria-live` region for screen-reader announcement, (c) no disabled+tooltip "File no longer available" state, (d) no 400ms tooltip delay.
- Files:
  - Edit `frontend/src/components/chat/FileDownloadButton.tsx` — header variant label: "Download" → "Downloaded" (success 1.5s) / "Failed" (error 2s); add hidden `aria-live="polite"` span announcing "Download started" / "Download failed"; accept optional `disabled?: boolean; disabledReason?: string` and render `aria-disabled="true"` + tooltip (use `title` for v1, dedicated Tooltip component in v2).
- Plan ref: Task 19 "FileDownloadButton".
- Spec ref: FileDownloadSpec §Download Feedback table, §File Expiry Handling, §Accessibility, §Tooltip (400ms delay).
- Acceptance: vitest — header variant after success shows text "Downloaded" for 1500ms, then reverts; after error shows "Failed" for 2000ms; `aria-live` region contains status text; passing `disabled` renders `aria-disabled="true"` and keeps focusability.
- Verification: `cd frontend && npm run test -- FileDownloadButton`.

### 13. **NEW-12-02 (rewritten) — SaveToRepoButton: saved-state visuals + idempotency + aria-live.**
- Bug: SaveToRepoSpec §Save Feedback and §States mandate (a) filled bookmark + success border token in saved state, (b) hovering the saved button shows "Remove" label + error tint, (c) chip-variant button stays at full opacity in saved state even when chip not hovered, (d) aria-live announces "Report saved to Repository" / "Report removed from Repository" / error copy, (e) API is idempotent (spec §Conflict Handling). Today `SaveToRepoButton.tsx` flips icon only (no border color / no hover-to-Remove label); chip visibility is `opacity-0 group-hover:opacity-100` always (breaks spec persistent saved chip); aria-live only fires on error; frontend-to-backend: server `DELETE /repo/items?report_id=X` does not return success when the row is already absent (verify `svc.unsave_from_repo` is a no-op — if it raises 404, surface bubble up).
- Files:
  - Edit `frontend/src/components/chat/SaveToRepoButton.tsx` — add `saved` class variants with `--color-feedback-success` border, "Save"/"Saved"/"Remove" label cycle in viewer-header; aria-live announcements on every state transition; prop `initialSaved` drives hover-overrides.
  - Edit `frontend/src/components/chat/AttachmentChip.tsx` — when `SaveToRepoButton` reports `saved=true`, stop applying `opacity-0` gating via a `data-saved` attribute + CSS rule; expose `onChange` callback.
  - Edit `packages/server/src/openlia_server/services/repo.py` + `routes/repo.py` — confirm `unsave` is idempotent (204 on already-absent); confirm `save` is idempotent (201 or 200 on existing uniq (user_id, report_id)).
- Plan ref: Task 18 "SaveToRepoButton".
- Spec ref: SaveToRepoSpec §Save Feedback, §Conflict Handling, §Attachment Chip Button Design (saved always full opacity), §Accessibility (aria-live announcements).
- Acceptance: vitest — click Save twice in rapid succession → one POST request, UI lands on saved; click Save on an already-saved `initialSaved=true` report (simulate POST returning 200) → no error state. Chip-variant `initialSaved=true` rendered without hover → `opacity: 1`. Backend test: POST /repo/items twice returns 2xx both times; DELETE twice returns 2xx both times.
- Verification: `cd frontend && npm run test -- SaveToRepoButton AttachmentChip`; `uv run pytest packages/server/tests/test_routes/test_repo_routes.py -k idempot`.

### 14. **NEW-12-13 — ChatHistoryDrawer: delete-confirm dialog a11y + undo.**
- Bug: `ChatHistoryDrawer.tsx:121` uses `window.confirm("Delete …")`. ChatHistorySpec and the master design-rules forbid native dialogs (not styleable, no a11y announcement). Undo is not spec-mandated but the chat-history micro-interactions section implies soft-delete semantics.
- Files:
  - Edit `frontend/src/components/chat/ChatHistoryDrawer.tsx` — replace `window.confirm` with a promise-returning `<ConfirmDialog>` from `components/primitives`, focus-trapped, `role="alertdialog"`.
- Plan ref: Task 11.
- Spec ref: ChatHistorySpec §Key Behaviors ("Pin / archive / delete sessions"), Design Rule §9.
- Acceptance: vitest — click Delete → modal appears with focus trapped on Cancel; Esc dismisses; Enter on Confirm triggers `deleteSession`.
- Verification: `cd frontend && npm run test -- ChatHistoryDrawer`.

### 15. **NEW-12-14 — ChatHistoryDrawer: auto-titles from first user message.**
- Bug: `createSession` posts `title: "New chat"` literal (`ChatHistoryDrawer.tsx:39`). ChatHistorySpec §Key Behaviors: "Session auto-title generation (first user message or LLM summary)". Server `services/chat_sessions.create_session` accepts `title` but there is no post-first-message auto-rename hook.
- Files:
  - Edit `packages/server/src/openlia_server/services/chat_sessions.py` — add `ensure_titled(session_id, first_user_text)` that sets title to first 48 chars of first user message if current title == "New chat".
  - Hook into `chat_stream.py` (or the SSE entry point) after the first user message persists.
- Plan ref: Task 1; Task 5.
- Spec ref: ChatHistorySpec §Key Behaviors.
- Acceptance: backend test — create session with default title, send message "What moved markets today?", assert session title in DB == "What moved markets today?" (truncated).
- Verification: `uv run pytest packages/server/tests/test_services/test_chat_sessions.py -k auto_title`.

### 16. **NEW-12-15 — SSE error taxonomy + reconnect policy.**
- Bug: `useChatStream.ts:157` maps the `error` DOM event onto a synthetic `chat.error` with fixed copy "Connection lost. Please try again." This collides with the terminal-event semantics (Design Rule §2 "terminal events are mutually exclusive" — an underlying transport drop is **not** a terminal event per spec; it should render "Response stopped."). Per ChatInterfaceSpec §Event Handling last row: "Connection closed without a terminal event → render 'Response stopped.'" Today users see a false "Connection lost" error for the cancellation case.
- Files:
  - Edit `frontend/src/components/chat/useChatStream.ts` — differentiate: if `readyState === EventSource.CLOSED` due to stop() → already `stopped`; if without any tokens arriving → `error` with retry; if partial content arrived → `stopped`. Add 1 auto-reconnect attempt for transient network drops before surfacing error.
- Plan ref: Design Rules §2–§4.
- Spec ref: ChatInterfaceSpec §Event Handling "Connection closed without a terminal event".
- Acceptance: vitest — open stream, emit `chat.token("hi")`, simulate transport error → state transitions to `stopped` (not `error`); no tokens + transport error → state `error`.
- Verification: `cd frontend && npm run test -- useChatStream`.

### 17. **NEW-12-16 — AbortController for send (replace EventSource where server supports POST SSE).**
- Bug: `EventSource` cannot send a request body; `useChatStream.send` uses `?q=...` in querystring (useChatStream.ts:130), which breaks long prompts at ~2KB depending on proxy limits. Plan Architecture says "the `useChatStream` hook owns the SSE event-stream state machine" and Plan Tech Stack cites abort via `AbortController`; the shipped hook closes the EventSource but can't pass an abort signal to the backend for graceful tool-call cancellation.
- Files:
  - Edit `frontend/src/components/chat/useChatStream.ts` — replace EventSource with `fetch(url, { method: "POST", body: JSON, signal })` + SSE parser (`eventsource-parser` pkg) so (a) prompts go in POST body, (b) `AbortController.abort()` on Stop closes the server stream cleanly.
- Plan ref: Design Rule §4 "Client-side cancellation = connection close"; Tech Stack.
- Spec ref: ChatInterfaceSpec §Event Handling (state-machine semantics).
- Acceptance: vitest — call `stop()` → `AbortController.abort` invoked; network request method === "POST"; long 5KB prompt succeeds.
- Verification: `cd frontend && npm run test -- useChatStream`.

### 18. **NEW-12-17 — AttachmentChip: keyboard focus reveals actions + aria wiring.**
- Bug: `AttachmentChip.tsx:70` reveals action buttons via `opacity-0 group-hover:opacity-100 group-focus-within:opacity-100`. `focus-within` only matches on an interactive descendant receiving focus, but the buttons themselves are hidden (pointer-events via opacity — Tailwind does not auto-apply `pointer-events-none`); so Tab skips over them. FileDownloadSpec §Accessibility: "show the button when the chip or button itself is focused". Also chip's `role="button" tabIndex={0}` clashes with internal `<button>` children (nested interactive elements).
- Files:
  - Edit `frontend/src/components/chat/AttachmentChip.tsx` — wrap chip in a keyboard-navigable `<div role="group">` (not button), with a primary `<button>` inside for "Open file viewer: {filename}"; action buttons siblings of that button. Use CSS `:focus-within` with `pointer-events: auto` reliably. Add `pointer-events-none` to the hover-gated wrapper when inactive.
- Plan ref: Task 12.
- Spec ref: FileViewerSpec §Entry Point: Attachment Chip, §Accessibility; FileDownloadSpec §Accessibility; SaveToRepoSpec §Accessibility.
- Acceptance: vitest — Tab through chip → open button, then save button, then download button, each visible; arrow-keys do not trap.
- Verification: `cd frontend && npm run test -- AttachmentChip`.

### 19. **NEW-12-18 — P1-09 cross-ref: Repository row → FileViewer open (owned by Phase 22).**
- Bug: `frontend/src/pages/Repository.tsx` does not consume `useFileViewer`. Phase 22 owns the row-onClick wiring; Phase 12 owns the `FileViewerContext` contract the row will call (`open({filename, kind, metadata, source: {kind:"report", reportId}, initialSaved:true})`). Must ensure `FileViewerProvider` is mounted at AppShell level so Repository page can consume it.
- Files:
  - Verify `frontend/src/components/shell/AppShell.tsx` wraps routes in `<FileViewerProvider>`; if not, add it.
- Plan ref: Design Rule §6 "FileViewer is a singleton".
- Spec ref: FileViewerSpec §"Open from Repository" (cross-spec: Repository page opens viewer).
- Acceptance: rendering any route, `useFileViewer()` does not throw; Phase 22 fix plan can then wire row click.
- Verification: `cd frontend && npm run test -- AppShell`.

### 20. **NEW-12-19 — Prefers-reduced-motion across chat + viewer animations.**
- Bug: Design Rule §10 requires `prefers-reduced-motion` short-circuit across all Framer Motion uses. Shipped: `MessageList` respects it for scroll (ok); nothing else does (AssistantMessage/UserBubble entry, ThinkingIndicator dots, ToolCallChip, FileViewer slide, ViewerHeader, WelcomeOverlay).
- Files:
  - Create `frontend/src/hooks/useReducedMotion.ts` if not present (framer-motion exports one; alias).
  - Edit every `motion.*` / `framer-motion` user in `components/chat/**` and `components/viewer/**` to set `transition.duration: 0` when reduced.
- Plan ref: Design Rule §10.
- Spec ref: ChatInterfaceSpec §Accessibility + §Animation Summary (implied by WCAG 2.3.3).
- Acceptance: vitest — with matchMedia mocked reduced, assert `motion.*` components rendered with zero transition duration (snapshot on `transition` prop).
- Verification: `cd frontend && npm run test -- --grep reduced`.

### 21. **NEW-12-20 — Session rename concurrency guard.**
- Bug: `ChatHistoryDrawer.tsx:63` commits rename on `onBlur` without debounce or ETag; if server PATCH 409s (stale lastActivity on the row) the UI silently keeps the new title.
- Files:
  - Edit `frontend/src/components/chat/ChatHistoryDrawer.tsx` — on PATCH failure revert local title; show inline red underline + toast.
- Plan ref: Task 11.
- Spec ref: ChatHistorySpec §Key Behaviors "Rename session title inline".
- Acceptance: vitest — mock `patchSession` to reject → UI reverts to prior title.
- Verification: `cd frontend && npm run test -- ChatHistoryDrawer`.

### 22. **NEW-12-21 — Targeted vitest gaps (supersedes P2-17).**
- Bug: Existing suites cover the happy path but miss: CodeRenderer syntax mode fallback, CsvRenderer large-file virtualization (spec says table sticky header — no test), ImageRenderer click-to-zoom lightbox, UnsupportedRenderer "Download the file to view it" link, UserBubble max-width truncation, ThinkingIndicator `aria-live="polite"`, ToolCallChip running→done transitions, ErrorMessage retry dispatch, ReportThumbnail renders inline with proper `kindFromFilename`, useFileViewer guard (throws if provider absent), drawer `department` prop swap resets session list.
- Files:
  - Add targeted tests under `frontend/src/components/chat/__tests__/` and `components/viewer/__tests__/`.
- Plan ref: Task 20 "Smoke test".
- Spec ref: per spec section cited above (one test per cited behavior).
- Acceptance: `cd frontend && npm run test` passes and new specs count ≥ 12 new tests.
- Verification: `cd frontend && npm run test`.

---

## Verification roll-up

```bash
# Backend
uv run pytest \
  packages/server/tests/test_services/test_chat_sessions.py \
  packages/server/tests/test_services/test_files.py \
  packages/server/tests/test_services/test_repo.py \
  packages/server/tests/test_routes/test_chat_sessions_routes.py \
  packages/server/tests/test_routes/test_chat_stream.py \
  packages/server/tests/test_routes/test_files.py \
  packages/server/tests/test_routes/test_repo_routes.py

# Frontend
cd frontend && npm run test
cd frontend && npx tsc -p tsconfig.json --noEmit

# Manual
# 1. Open /secretary, /equity-research, /morning-briefing (add slug)
#    → ChatHistoryDrawer shows sessions for each.
# 2. Save a report twice, unsave, save again → no errors; button cycles.
# 3. Open a file, resize panel, open a 2nd chip → fade + scroll preserved.
# 4. Stop a streaming response → "Response stopped." persists after reload.
```

---

## Master-tracker reconciliations

- **P1-02** — task 1 above.
- **P1-09** — cross-ref only (task 19); owned by Phase 22 fix plan.
- **P2-16** — task 11 above.
- **P2-17** — superseded by task 22 (targeted vitest gaps, not a greenfield "zero vitests" claim).
- **NEW-12-01 / NEW-12-02 / NEW-12-03** — rewritten with spec-accurate contracts (tasks 12, 13, 7).
- **NEW-12-04 … NEW-12-21** — new gaps minted by this deep audit; add to §11 of master tracker when merged.
