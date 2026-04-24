# Phase 12 — Shared Chat Components fix plan (→ 100%)


**Current:** ~90% shipped. **Root cause:** IMPLEMENTER (type narrowing + missing service layer + zero vitest).

**Gap summary:** Chat, file viewer, save-to-repo UX all shipped functionally, but `Department` union only covers 2 of 7 departments; `services/files.py` missing; zero frontend vitests; FileViewer click-to-open on repo rows missing (P1-09 blamed on Phase 22 but Phase 12 owns the FileViewer contract).

**Tasks (in execution order):**

1. **P1-02 — Widen `Department` union to all 7 departments via shared literal.**
   - Files: `frontend/src/api/chat.ts:3` — replace inline union with `import type { DepartmentSlug } from "@/api/departments"`. Create `frontend/src/api/departments.ts` exporting `DepartmentSlug` union + runtime `DEPARTMENT_SLUGS` array.
   - Spec ref: ChatInterfaceSpec, ChatHistorySpec.
   - Acceptance: vitest — filtering drawer by each of the 7 slugs returns matching sessions; tsc clean.

2. **P1-09 — FileViewer click-to-open from Repository rows.**
   - Files: `frontend/src/pages/Repository.tsx` — add row `onClick={() => openInViewer(item)}`; import `useFileViewer` context.
   - Spec ref: FileViewerSpec §"Open from Repository"; SaveToRepoSpec §"Open saved report".
   - Acceptance: vitest clicks a repo row, asserts FileViewer context state transitions to `open: true`.

3. **P2-16 — Extract `services/files.py`.**
   - Files: create `packages/server/src/openlia_server/services/files.py` — move file-resolution, size check, mime sniff out of `routes/files.py`.
   - Acceptance: `routes/files.py` has only request/response glue.

4. **P2-17 — Frontend vitests smoke suite.**
   - Files: create `ChatInterface.test.tsx`, `ChatInput.test.tsx`, `MessageList.test.tsx`, `AssistantMessage.test.tsx`, `SaveToRepoButton.test.tsx`, `FileDownloadButton.test.tsx`, `FileViewer.test.tsx`.
   - Spec ref: ChatInterfaceSpec, FileViewerSpec, FileDownloadSpec, SaveToRepoSpec.
   - Acceptance: `cd frontend && npm run test` runs ≥7 new specs.

5. **NEW-12-01 — Verify FileDownloadSpec PDF + DOCX dropdown contract.** Why new: P1-20 covers ReportCard-level (Phase 14); FileDownloadSpec applies to shared `FileDownloadButton`.
   - Files: `frontend/src/components/chat/FileDownloadButton.tsx`.
   - Acceptance: vitest asserts dropdown with "PDF" and "DOCX" items.

6. **NEW-12-02 — Verify SaveToRepoSpec toast + idempotency contract.** Why new: spec mandates post-save toast + "Already saved" state.
   - Files: `SaveToRepoButton.tsx`, `routes/repo.py`.
   - Acceptance: vitest — second save click shows "Already in repo" state.

7. **NEW-12-03 — Verify ChatInterfaceSpec cancellation + streaming-cursor behavior.** Why new: spec §Streaming cursor + §Cancellation mandate inline `▌` cursor and `stopped_at` persistence.
   - Files: `useChatStream.ts`, `AssistantMessage.tsx`.
   - Acceptance: vitest simulates SSE stream; cursor present mid-stream, removed on `done`; cancel button calls `AbortController.abort()`.

**Verification:** `uv run pytest packages/server/tests/test_services/test_files.py packages/server/tests/test_routes/test_repo.py` + `cd frontend && npm run test -- chat viewer` all green; manual: open Morning Briefing chat history drawer — non-empty session list appears.
