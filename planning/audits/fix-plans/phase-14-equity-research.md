# Phase 14 — Equity Research fix plan (deep audit, → 100%)

**Current:** ~70% shipped (down-revised from 83% after deep audit). **Root cause:** IMPLEMENTER + PLANNER. Many UI behaviors quietly diverge from `EquityResearchPageSpec.md`; runtime emits no per-section events although the spec advertises mode-specific 13/7/8 section flows; backend route tests are partial; chat route drops `session_id` (master tracker P1-03).

**Verified-against-code summary of gaps:**

- **Runtime/SSE:** `packages/core/src/openlia/llm/runtime/events.py:77–113` only defines `ReportStart`, `ReportPhase`, `ReportToolCall`, `ReportComplete`, `ReportError`. No per-section events (`report.section.start` / `report.section.chunk` / `report.section.complete`). The runner streams a single monolithic complete payload — incompatible with spec's section-level progress UI for 13/7/8 section modes.
- **Active layout:** `frontend/src/pages/departments/EquityResearch.tsx:145–198` renders a 360px split panel with a status panel + chat on right; spec L122–135 mandates a single-column scrollable chat with the `ReportCard` injected as an inline assistant message. FileViewer is rendered inline in the right pane instead of opening the global FileViewer drawer/route.
- **`POST /chat` drops `session_id`:** `routes/departments/equity_research.py:152–177` — `ChatPayload.session_id` is declared (line 53) but never threaded into `runner.run(...)` (line 164). New chat session created on every turn. Master tracker P1-03.
- **Suggestion chips don't auto-submit:** `EquityResearch.tsx:26–29` `onChipSelect` only calls `setInput` + `focus`; spec L159 requires "immediately populate the input and submit." Test `EquityResearch.test.tsx:42` actually pins the broken behavior.
- **`ReportCard` Download is a single PDF button:** `ReportCard.tsx:73–79` renders a flat "Download PDF" button. Spec L198 / L239 specify `[Download ▾]` dropdown with PDF / DOCX. Component prop `onDownload(id, format)` exists but is never wired to a DOCX backend.
- **No DOCX export route:** `services/report_export.py` and `routes/reports.py` only ship PDF. No `python-docx` codepath.
- **No chat assistant streaming wired to ER chat route:** `ChatInterface` is mounted (line 188) but the chat SSE comes through the generic `/chat/stream` runner, not the ER-specific `/departments/equity-research/chat` route. The ER chat route exists but is unused by the page.
- **`ReportCard.onSave` is a no-op:** `EquityResearch.tsx:163–166` comment "handled by Phase 12 SaveToRepoButton inside the viewer" — but viewer is not opened from card click in this layout, so saving from the card is impossible.
- **Per-section retry / regenerate:** Not implemented anywhere (no events, no UI control). Plan does not provide it; spec doesn't explicitly require it but it's expected for a 13-section flow. Treat as PLANNER gap → mark not-required for v1, file as future.
- **Mode toggle on Welcome screen:** Spec assumes mode picker is only inside Report Settings modal — verified, OK. Active mode is shown nowhere on the page header (small spec drift but not blocking).
- **Loading skeleton / stream phases:** `useReportStream.ts` parses `report.phase`, `report.tool_call`, `report.complete`, `report.saved`, `report.error` (verified L8–16). Spec L348 ("Generating: typing indicator", L349 "Streaming: token-by-token reveal") has no token-level reveal for the report itself because runtime emits no token deltas — acceptable, but the streaming "Writing…" UI must show section progress; current sectionTitles list comes from `report.start`, never updates per-section.
- **Error state:** `ReportStatusPanel` shows error but no "Try again" `RotateCcw` retry button (spec L352).
- **`er_user_configs` table:** Migration `2026-04-17-2100_er_user_configs.py` and model `db/models/departments.py:27–53` exist and validated — no fix needed. **No `er_section_progress` table** exists; if per-section streaming is added, decide whether to persist intermediate sections or stream-only.
- **Tests:**
  - Backend: `test_equity_research_runner.py` (1-line stub — file truncated to `from __future__ import annotations`). `test_equity_research_chat_route.py` exists but has zero `session_id` coverage. `test_equity_research_config_route.py` and `test_equity_research_report_route.py` exist but small (70/87 lines).
  - Frontend: `EquityResearch.test.tsx` has 3 trivial tests; no test for SSE happy path, error state, ReportCard rendering on `report.saved`, no DOCX, no FromPortfolio popover behavior.
  - No `ReportCard.test.tsx` coverage of DOCX dropdown, no `useReportStream.test.ts` integration.
- **Spec drift on mode labels:** Modal heading uses "Sections (Stock Initiation Report)" — verified L128 `${MODE_LABELS[mode]} Report` matches spec L281.
- **Framework JSON shape:** Verified all 3 frameworks ship correct section counts (13/7/8); section ids consistent with `_framework_section_ids`. OK.
- **Tier mapping:** `_TIER_BY_MODE` sets `stock_update` → `everyday`, others → `thinking`. Plan-aligned.

---

## Tasks (in execution order)

### 1. **P1-03 — Thread `session_id` through `POST /departments/equity-research/chat`**

- **Files:**
  - `packages/server/src/openlia_server/routes/departments/equity_research.py:152–177` — pass `session_id=payload.session_id` into `runner.run(...)`. Pattern mirrors `/report` route at L141. Note: generic `ChatRunner.run` signature must accept it; check `packages/core/src/openlia/llm/runtime/chat.py` and align (most other dept routes use this same signature).
- **Spec ref:** EquityResearchPageSpec "Active State" — follow-up questions land in the same conversation.
- **Acceptance:**
  - `test_equity_research_chat_route.py` adds two new tests: (a) call with `session_id="abc"` records that ChatRunner received `session_id="abc"`; (b) two consecutive calls with same `session_id` append to one session row, not two.

### 2. **NEW-14-01 — Wire ER chat route into `ChatInterface`, drop generic `/chat/stream` for ER**

- **Why:** Current page mounts `ChatInterface` which calls `/chat/stream`. ER prompts in `prompts/equity_research.yaml` go unused for chat replies. ER-specific tools/persona never apply.
- **Files:**
  - `frontend/src/pages/departments/EquityResearch.tsx:188–195` — replace `ChatInterface` with a thin variant that POSTs to `/api/departments/equity-research/chat` with `{message, session_id}` and parses `chat.start/token/done/error` SSE events.
  - Or: extend `ChatInterface` to accept a `streamUrl` + `bodyExtras` prop and pass `{session_id}` through.
- **Acceptance:**
  - Vitest renders page in active state, types follow-up, asserts request goes to `/api/departments/equity-research/chat` with `session_id`.

### 3. **NEW-14-02 — Restore spec-compliant Active layout (single-column chat + inline ReportCard)**

- **Why:** `EquityResearch.tsx:145–198` ships split-panel; spec L122–135 says single-column chat, ReportCard appears inline as an assistant message, Open Report opens the global FileViewer.
- **Files:**
  - `EquityResearch.tsx` — delete the `<div className="flex flex-1 min-h-0">` block; render a single `<ChatInterface>` (or its replacement from NEW-14-01) full-width and inject a synthetic assistant message containing `<ReportCard>` as soon as `reportState.status === "complete"` and schema is loaded.
  - Wire `onOpen={(id) => fileViewerCtx.open(id)}` (Phase 12 FileViewer drawer) — verify import path under `frontend/src/components/viewer/`.
  - Move `ReportStatusPanel` content into a transient assistant placeholder bubble that lives in the chat thread until the card replaces it.
- **Spec ref:** Spec L122–135, L183–241.
- **Acceptance:**
  - E2E (or vitest with mocked SSE): after first `/report` call completes, chat shows phase placeholder → replaced by `ReportCard`; `Open Report` opens shared FileViewer (drawer or route), not a half-pane within the page.

### 4. **NEW-14-03 — Make suggestion chips populate AND submit input**

- **Files:**
  - `frontend/src/components/equity-research/SuggestionChips.tsx:9–25` — change `onSelect` callers to invoke a single handler that fills + submits.
  - `EquityResearch.tsx:26–29` — replace `onChipSelect`: `setInput(value)` then call `onSend()` after one render tick (use `useEffect` keyed on a `pendingSubmit` flag, or accept submit value directly into `onSend`).
- **Spec ref:** Spec L159 — "immediately populate the input and submit."
- **Acceptance:** Vitest — clicking AAPL fires `setInput("AAPL")` AND triggers `/api/departments/equity-research/report` POST exactly once. Update existing `EquityResearch.test.tsx:42` which currently asserts only the populated value.

### 5. **NEW-14-04 — `ReportCard` Download → PDF + DOCX dropdown; ship DOCX backend**

- **Frontend:**
  - `frontend/src/components/equity-research/ReportCard.tsx:65–88` — replace single PDF button with a dropdown using `@radix-ui/react-dropdown-menu` (already in dep tree per other components) showing "Download as PDF" / "Download as DOCX". Use the existing `onDownload(id, format)` prop signature.
  - `frontend/src/api/reports.ts` — add `reportDocxUrl(id) => '/api/reports/${id}/docx'`.
  - `EquityResearch.tsx:163` — pass real `onDownload`: `(id, fmt) => window.open(fmt === 'pdf' ? reportPdfUrl(id) : reportDocxUrl(id))`.
- **Backend:**
  - `packages/server/src/openlia_server/services/report_export.py` — add `export_report_docx(schema) -> bytes` using `python-docx`. Map cover, sections, blocks (paragraph, list, table, image-skip).
  - `packages/server/src/openlia_server/routes/reports.py` — add `GET /reports/{id}/docx` returning `application/vnd.openxmlformats-officedocument.wordprocessingml.document`.
  - `pyproject.toml` (core OR server) — add `python-docx` to dependencies (ensure it lives in server, not core, since it's an export concern).
- **Spec ref:** Spec L198, L239.
- **Acceptance:**
  - Vitest: clicking ▾ opens menu with two items; clicking DOCX calls window.open with `/api/reports/<id>/docx`.
  - Pytest: `test_reports.py` adds DOCX download test asserting a valid `.docx` zip header (`PK\x03\x04`) and HTTP 200 with correct content-type.

### 6. **NEW-14-05 — Wire `ReportCard.onSave` to repo via Save-to-Repo from the card**

- **Why:** Card prop exists, current handler is a no-op; spec L240 lists Save to Repo as a card action.
- **Files:**
  - Reuse the Phase 12 `SaveToRepoButton` inline behavior; new helper `saveReportToRepo(reportId)` in `frontend/src/api/repo.ts` (verify existing helper presence).
  - `EquityResearch.tsx:164–166` — call `saveReportToRepo(id)` then toggle a "saved" state on the card (filled `Bookmark` icon per spec).
- **Acceptance:** Vitest mocks the API and asserts POST happens; bookmark icon flips to filled.

### 7. **NEW-14-06 — Per-section streaming events (runtime + UI)**

- **Why:** Spec advertises mode-specific 13/7/8-section flows. Without per-section events the user only sees a generic spinner for what may take 60–120s.
- **Backend (core):**
  - `packages/core/src/openlia/llm/runtime/events.py` — add `ReportSectionStart`, `ReportSectionComplete`, optional `ReportSectionChunk` dataclasses with TYPEs `report.section.start|chunk|complete`. Extend `to_wire`.
  - `packages/core/src/openlia/llm/runtime/report.py` — emit `ReportSectionStart(section_id, title, idx, total)` before each section LLM call; emit `ReportSectionComplete(section_id, blocks)` after the section validates. Persist nothing intermediate (no new table required for v1).
- **Server runner:** `services/equity_research_runner.py` re-yields these events transparently (it already passes through arbitrary events — verify L80–87).
- **Frontend:**
  - `frontend/src/components/report/useReportStream.ts` — extend reducer to track `sections: { id, title, status: 'pending'|'writing'|'done' }[]`.
  - `EquityResearch.tsx` — placeholder bubble shows live section checklist (✓ Company Overview, … ⏳ Industry Overview, …). Replaces current static `sectionTitles` list.
- **Acceptance:**
  - Backend unit test (`packages/core/tests/test_runtime_report.py`): scripted runner emits start + 3 sections + complete; wire format includes `report.section.start` and `report.section.complete`.
  - Frontend test: useReportStream reducer transitions section status correctly.

### 8. **NEW-14-07 — Error state with retry button**

- **Files:**
  - `EquityResearch.tsx` — when `reportState.status === "error"`, render an inline error bubble in chat with `[Try again]` button (`RotateCcw` icon). Click re-issues the last `startReport({...})` with same body.
  - For chat errors: `ChatInterface` already handles per-message error UI — verify retry calls into ER chat route (post NEW-14-01).
- **Spec ref:** Spec L352.
- **Acceptance:** Vitest forces `report.error` event, asserts retry button appears and re-fires fetch.

### 9. **NEW-14-08 — Loading skeleton on initial config load**

- **Why:** Current `if (loading || !config) return <div>Loading…</div>` (L77–79) violates spec design quality bar. Other dept pages use `<PageSkeleton>`.
- **Files:** `EquityResearch.tsx:77` — replace with a header skeleton + chip skeleton row.
- **Acceptance:** Visual check + vitest snapshot.

### 10. **P2-TESTS-14 — Backend test gap closure**

- **Files (create / extend):**
  - `packages/server/tests/test_services/test_equity_research_runner.py` — currently a 1-line stub. Add: happy-path `run_report` with scripted inner runner emits `report.start`, `report.complete`, then `report.saved` with persisted report; mode validation raises on bad mode; resolve_active threads `report_length` correctly.
  - `packages/server/tests/test_services/test_equity_research_config.py` — NEW. Cover defaults seeding, partial PUT (only `report_length`), unknown section id raises 400, custom-section round trip per mode, `resolve_active` returns expected `ActiveReportConfig`.
  - `test_equity_research_chat_route.py` — extend with `session_id` threading + reuse-session test (P1-03 acceptance).
  - `test_equity_research_report_route.py` — extend with: invalid mode 400; SSE includes `report.saved` event; auth required.
  - `test_equity_research_config_route.py` — extend with: unknown mode 400; unknown section id 400; PUT then GET round-trip.
- **Acceptance:** `uv run pytest packages/server/tests -k equity_research` runs ≥10 tests across 5 files, all pass.

### 11. **P2-TESTS-FE-14 — Frontend test gap closure**

- **Files:**
  - `frontend/src/pages/departments/EquityResearch.test.tsx` — extend: chip-click submits (NEW-14-03 acceptance), report SSE happy path renders ReportCard inline (mock EventSource/fetch), error state shows retry, follow-up chat hits ER chat URL with session_id.
  - `frontend/src/components/equity-research/ReportCard.test.tsx` — extend: dropdown shows two items; DOCX click opens DOCX URL.
  - `frontend/src/components/equity-research/FromPortfolioPicker.test.tsx` — NEW. Renders portfolio holdings; selecting a row calls `onSelect`.
  - `frontend/src/components/report/__tests__/useReportStream.test.ts` — NEW or extend. Cover section.start/complete reducer transitions (NEW-14-06).
- **Acceptance:** `npm --prefix frontend test -- equity-research` runs ≥6 test files, all pass.

### 12. **NEW-14-09 — Plan/spec doc reconciliation**

- **Why:** Implementation plan (3664 lines) mentions split-panel reportcard variants in Task 13; spec mandates single-column inline. Plan must be updated to match spec, since spec is source of truth.
- **Files:**
  - `planning/implementation-plans/2026-04-17-phase-14-equity-research.md` — append a "Post-audit corrections (2026-04-24)" section listing: single-column active layout; chip auto-submit; DOCX export; ER chat session_id; per-section events; retry button. Mark superseded sections.
- **Acceptance:** Plan and spec align on Active-state layout and chat routing.

---

## Verification

```bash
uv run pytest packages/core/tests -k "report or equity_research"
uv run pytest packages/server/tests -k equity_research
npm --prefix frontend test -- equity-research
npm --prefix frontend test -- useReportStream
```

All must pass. Manual smoke: load `/departments/equity-research`, click `AAPL` chip → report streams with section checklist → ReportCard appears inline → click `Download ▾` → DOCX downloads → click `Open Report` → global FileViewer opens → ask follow-up → assistant streams in same `session_id`.
