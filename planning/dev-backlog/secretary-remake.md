# Secretary Page Remake — Backlog

Tracks deferred work from the UI remake on `ui-remake` branch. Source design: `~/Downloads/OpenLIAv3/app/index.html`. Decisions captured in the conversation that produced commits on this branch.

---

## Decisions locked (for reference)

| # | Topic | Choice |
|---|-------|--------|
| 1 | Pixel-match scope | Visual + every primitive reachable; content stays dynamic |
| 2 | FileViewer | Slide-in (kept current); default open width snaps to ~40% of viewport |
| 3 | Empty state | Keep existing `WelcomeOverlay` |
| 4 | Greeting + macro strip at top of populated thread | Dropped both |
| 5 | Topbar on Secretary | Time stamp only (no LIVE pill, no CONGRESS_ACTIVE stamp) |
| 6 | Composer left pill | ModelPicker restyled to design's bordered mono pill |
| 7 | Source chips | Restyled `ToolCallChip`; click opens artifact in FileViewer |
| 8 | In-bubble KPI grid | New `DataBlock` primitive parsed from `\`\`\`databloc` fence |
| 9 | Pull-quote | New `PullQuoteBlock`; emit from report runner + chat fence |
| 10 | Assistant message tag | Department · tokens · latency above each bubble |
| 11 | Composer attach button | Full UX in frontend; backend upload deferred |
| 12 | Kbd binding | Kept current Enter-sends + helper text (diverges from design's `⌘ + ENTER`) |
| 13 | FileViewer tabs | Preview + Raw only (Sources deferred) |
| 14 | Motion | Tasteful entry choreography (opacity+y on new content, stagger on chips/cards) |

---

## Deferred / pending items

### Backend — chat attachments upload
- **What**: `POST /api/chat/sessions/:id/attachments` for uploading user-supplied files into a chat session.
- **Why deferred**: User explicitly scoped this session to frontend-only. Backend follow-up.
- **Frontend state**: Paperclip button + OS file picker + `AttachmentChip` rendering ship in this branch. Files are held in client memory; the upload call site is marked with `// TODO: backend upload pending` and either no-ops or POSTs to a placeholder route that 404s gracefully.
- **Schema sketch**: `{ filename, content_type, size_bytes, blob }` → returns `{ attachment_id, repo_id?, url? }`. Attachments may be auto-promoted to Repository items when worth keeping.

### Backend — report runner `pull_quote` block kind
- **What**: Add `pull_quote` to the union of block kinds in the `reports` JSON schema and to the LLM's system prompt for ReportRunner so it can emit executive/analyst quote callouts.
- **Why deferred**: Frontend renderer (`PullQuoteBlock`) lands first; backend schema bump can land independently.
- **Shape**: `{ type: "pull_quote", text: string, attribution?: string, source?: string, timestamp?: string }`.

### Topbar — LIVE_FEED_ACTIVE pill on Secretary
- **What**: Design shows a green pulsing `LIVE_FEED_ACTIVE` pill in the Secretary topbar. We dropped it because Secretary is a chat surface, not a data feed.
- **Reconsider when**: A real "Secretary has live signals" state exists (e.g., scheduled briefings, watchlist alerts). Then turn the pill on conditionally.

### Topbar — CONGRESS_ACTIVE stamp
- **What**: Design shows `CONGRESS_ACTIVE: 119` as a topbar stamp. We dropped it; no source connects "Congress activity" to a Secretary chat.
- **Reconsider when**: A macro/political-context surface lands that genuinely tracks legislative session state.

### Greeting + macro strip at top of populated chat thread
- **What**: Design shows `Good morning, TK. / S&P FUT +0.34 · VIX 14.2 · 10Y 4.28 · DXY 103.1` at the top of the chat scroll. Dropped both because we have no live macro feed and a hardcoded placeholder feels like demo content.
- **Reconsider when**: A `/api/macro/quotes` (or similar) endpoint lands with real S&P/VIX/10Y/DXY values. Then add the strip back.

### FileViewer — Sources tab
- **What**: Design's right pane has three tabs: Preview / Sources / Raw. Sources omitted; Preview + Raw shipped.
- **Why deferred**: Sources tab requires a `sources: [{ label, url|repo_id, kind }]` field on every report — the schema isn't decided yet.
- **Reconsider when**: The report runner standardizes a sources payload (likely tied to the `pull_quote` work above — sources cluster naturally with citations).

### Composer — `Cmd + Enter` keybinding
- **What**: Design shows `⌘ + ENTER` as the send hint. We kept Enter-sends because every chat surface users have used (Slack, ChatGPT, Claude.ai, iMessage) uses Enter-sends, and switching breaks muscle memory.
- **Reconsider when**: User feedback indicates they want editor-style binding for long-form prose. Could become a setting under `Settings → Account → Composer behavior`.
