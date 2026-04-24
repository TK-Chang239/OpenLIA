# Phase 13 — Report Pipeline & Secretary fix plan (→ 100%)


**Current:** ~75% shipped. **Root cause:** IMPLEMENTER.

**Gap summary:** Report pipeline core + PDF export shipped, but the Secretary HTTP route/service was never wired, the PDF block renderer reads wrong schema field names for `metric_cards`/`table`, and the spec's Redirect Suggestion Card chat block was never built on the frontend.

**Tasks (in execution order):**

1. **P0-01 — Create Secretary HTTP route + chat runner service + frontend client and mount in app.**
   - Files: create `routes/departments/secretary.py` (`build_secretary_router`, `POST /departments/secretary/chat` SSE); `services/secretary_chat_runner.py` (wraps `ChatRunner`); `frontend/src/api/secretary.ts`; modify `app.py:48–78` to import `build_secretary_router` and mount around line 347.
   - Plan ref: Phase 13 Tasks 9 + 10.
   - Spec ref: SecretaryPageSpec "Functions", "Message Input", "Response Interruption".
   - Acceptance: `curl -N .../departments/secretary/chat -d '{"message":"hi","session_id":"s1"}'` streams `message.delta` events.

2. **P1-01 — Fix PDF block renderer field-name bugs for `metric_cards` and `table`.**
   - Files: `routes/reports.py:42–65` — `metric_cards` reads `block.get("metrics", [])`; `table` reads `block.get("headers", [])` and iterates rows by header `key`.
   - Plan ref: Phase 13 Tasks 8 + 1.
   - Spec ref: `report-rendering-pipeline-design.md` block definitions.
   - Acceptance: `test_reports.py` asserts PDF HTML contains metric labels/values and table headers/rows for fixture reports.

3. **NEW-13-01 — Build `RedirectCard` chat block component and wire into Secretary message stream.** Why new: SecretaryPageSpec "Redirect Suggestion Card" is a first-class chat block; tracker covers only the route.
   - Files: create `frontend/src/components/secretary/RedirectCard.tsx`; modify `frontend/src/pages/SecretaryPage.tsx:31–62` to subscribe to a `redirect_suggestion` SSE event; extend `services/secretary_chat_runner.py` to emit that event.
   - Spec ref: SecretaryPageSpec "Redirect Suggestion Card" + "Redirect Routing Logic" table.
   - Acceptance: vitest renders `RedirectCard` with dept=equity_research; clicking "Go to Equity Research" calls `router.push('/equity-research?prompt=<text>')`.

4. **NEW-13-02 — Implement Welcome-state animations, stop button, and "Response stopped" label on SecretaryPage.** Why new: spec "Welcome State Layout Details" + "Response Interruption" not implemented beyond a boolean toggle.
   - Files: `frontend/src/pages/SecretaryPage.tsx:31–62`; surface stop-stream callback in `ChatInterface`.
   - Spec ref: SecretaryPageSpec "Welcome State Layout Details", "States" table.
   - Acceptance: sending first chip message transitions welcome overlay out (200ms); mid-stream stop emits "Response stopped" line.

5. **P2-10 — Remove orphaned `system` / `user` top-level keys from `secretary.yaml`** (see Phase 5 entry — same file).

6. **NEW-13-03 — Backend tests for Secretary route + redirect emission.**
   - Files: create `packages/server/tests/routes/departments/test_secretary.py`.
   - Acceptance: `uv run pytest packages/server/tests/routes/departments/test_secretary.py` green.

**Verification:** `uv run pytest packages/server/tests/routes/test_reports.py packages/server/tests/routes/departments/test_secretary.py && curl -sN .../departments/secretary/chat -d '{"message":"write a full AAPL research report","session_id":"s1"}' | grep redirect_suggestion`.
