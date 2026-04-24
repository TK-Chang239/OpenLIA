# Phase 16 — Morning Briefing fix plan (→ 100%)


**Current:** ~82% shipped. **Root cause:** mixed (IMPLEMENTER drift on prompt/builder contract, DEFERRED atomic components).

**Gap summary:** Prompt/builder JSON-blob mismatch silently drops `section_topics` and `reference_portfolio` at render time; monolithic `MBSettingsView` collapsed six atomic components into inline JSX; P0-09 residual (`mb_user_configs` migration exists, but verify on fresh Postgres boot); frontend lacks vitests for Archive + Settings flows.

**Tasks (in execution order):**

1. **P1-04 — Fix MB prompt/builder JSON-blob mismatch.**
   - Files: `services/mb_request_builder.py` (remove `MB_EXTRAS_JSON` stuffing at ~lines 51-65; pass `section_topics`, `custom_sections`, `reference_portfolio`, `enabled_sections` as top-level fields); `packages/core/src/openlia/prompts/morning_briefing.yaml` (confirm Jinja reads variables at the template root).
   - Spec ref: MorningBriefingsPageSpec "Section topics" + "Reference Portfolio toggle".
   - Acceptance: `test_morning_briefing_prompt.py` + `test_mb_request_builder.py` pass; manual on-demand briefing with two topic keywords + reference_portfolio=on renders both into LLM user prompt.

2. **P0-09 (phase-16 slice) — Verify `mb_user_configs` migration applies cleanly on Postgres.**
   - Files: `packages/server/src/openlia_server/db/migrations/versions/2026-04-23-2100_mb_user_configs.py` (audit columns).
   - Acceptance: `alembic upgrade head` on fresh Postgres creates `mb_user_configs` with all seven columns; EXPECTED_TABLES includes it.

3. **P2-15 — Decompose `MBSettingsView` into six atomic components.**
   - Files: create `SectionRow.tsx`, `TopicChip.tsx`, `NotesPopover.tsx`, `CustomSectionRow.tsx`, `ScheduleRow.tsx`, `AddScheduleModal.tsx`; refactor `MBSettingsView.tsx` to compose them.
   - Plan ref: Phase 16 plan Tasks 17, 18, 19.
   - Spec ref: MorningBriefingsPageSpec "Settings View / Coverage List" + "Schedule editor".
   - Acceptance: each exports independently; one vitest per component.

4. **NEW-16-01 — Add Archive + Settings + OnDemand frontend vitests.**
   - Files: `MBArchiveView.test.tsx`, `MBSettingsView.test.tsx`, `OnDemandBriefingButton.test.tsx`.
   - Why new: tracker lists only umbrella P2-TESTS debt; no Phase-16-specific frontend-test ticket.
   - Acceptance: three suites green.

5. **NEW-16-02 — Add `useMbChatSession` resolve-or-create test + endpoint-contract matrix row.**
   - Files: `useMbChatSession.test.ts`; add row for `POST /api/departments/morning-briefing/chat/session` in `endpoint-contract-matrix.md`.
   - Why new: matrix-row verification (P2-21) is generic; this pins the Phase 16 row.
   - Acceptance: matrix contains the row; hook test covers both existing-session and create-new-session paths.

**Verification:** `uv run pytest packages/server/tests/test_services/test_mb_request_builder.py packages/core/tests/prompts/test_morning_briefing_prompt.py && cd frontend && npm run test -- morning-briefing`; then manual: MB config with 2 topic keywords + reference_portfolio=on renders both in generated report.
