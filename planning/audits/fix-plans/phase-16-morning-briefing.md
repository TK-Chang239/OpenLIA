# Phase 16 — Morning Briefing fix plan (→ 100%)

**Current:** ~75% shipped. **Root cause:** mixed — IMPLEMENTER drift (prompt/builder contract silently severed by `MB_EXTRAS_JSON` hack; no prompt-render path can ever see `section_topics` or `reference_portfolio`); DEFERRED atomic components (6 of 8 settings subcomponents collapsed into 2 inline helpers in `MBSettingsView.tsx`); DEFERRED frontend vitests (0 of 4 expected suites shipped); DEFERRED microcopy/layout alignment with spec (header, date grouping, view toggles, notes popover, Add Schedule modal).

**Gap summary:**
- **Prompt/builder contract broken (P1-04, verified):** `services/mb_request_builder.py` lines 58-66 wrap `section_topics` + `reference_portfolio` into a JSON string inside `user_input`; `ReportRequest` has no keyword slot for these fields; `prompts/morning_briefing.yaml` lines 41-69 render top-level Jinja vars `section_topics` / `reference_portfolio` that are never supplied. Net effect: every scheduled and on-demand briefing loses topic keywords, notes, and reference-portfolio injection. Prompt tests pass only because they inject the vars directly at `render()` time, bypassing the builder.
- **P0-09 (mb_user_configs migration):** VERIFIED PRESENT at `db/migrations/versions/2026-04-23-2100_mb_user_configs.py` with 9 columns (id, user_id, report_length, enabled_section_ids, section_topics, custom_sections, reference_portfolio, created_at, updated_at) + FK + unique + check-constraint; `EXPECTED_TABLES` in `test_db/test_migrations.py` contains `mb_user_configs`. Fresh-Postgres alembic boot is clean. Residual risk: `server_default=sa.text("0")` for Boolean on Postgres should be `'false'` — requires fix.
- **Atomic components collapsed (P2-15):** Plan Tasks 17-19 specified 6 separate files (`SectionRow`, `TopicChip`, `NotesPopover`, `CustomSectionRow`, `ScheduleRow`, `AddScheduleModal`). Shipped: only `MBArchiveView.tsx`, `MBReportCard.tsx`, `MBSettingsView.tsx`, `OnDemandBriefingButton.tsx`. `TopicsEditor` + `ScheduleEditor` are inline helpers inside `MBSettingsView.tsx` — no standalone `TopicChip`/`NotesPopover`/`SectionRow`/`CustomSectionRow`/`ScheduleRow`/`AddScheduleModal` exists. The spec's Notes popover (click chip, not ×) is not implemented; notes edit via tiny inline input, not a popover textarea.
- **Frontend vitests absent:** Only `MorningBriefing.test.tsx` + `section-catalog.test.ts` exist. Zero per-component vitests for `MBArchiveView`, `MBSettingsView`, `MBReportCard`, `OnDemandBriefingButton`. `useMbChatSession` resolve-or-create has no hook test.
- **Frontend page composition drift (memory 1151):** Page ships a 3-tab nav (Archive / Chat / Settings) with a separate full-page viewer split (ReportRenderer + ChatInterface) when `viewing` is set. Spec mandates two views only (Archive + Settings) with no Chat tab; Chat is supposed to surface only when opening a specific report. Needs reconciliation — either (a) update spec to document the Chat tab + Viewer split addition, or (b) fold Chat into the viewer split and drop the top-level Chat tab.
- **Spec microcopy / layout drift:** (1) Header is spec'd 56px `h-14` with "← Back to Reports" text link; shipped header uses generic title + inline tab bar; (2) Archive is spec'd date-grouped with "Today — …", "Yesterday — …", "April 7" group headers — verify `MBArchiveView` implements; (3) Settings uses raw HTML `<input type=checkbox>` + plain buttons rather than Radix primitives (`Checkbox`, `Dialog`, `Popover`, `ToggleGroup`) listed in plan Tech Stack; (4) No "Add Schedule" modal; shipped `ScheduleEditor` is inline — spec requires modal with time picker, tz dropdown, day checkboxes, label field; (5) "+ Add Section" button missing on Custom Sections header; (6) No toast notification on save ("Settings saved."); (7) No empty-state with Sun icon + CTA in Archive.
- **Boolean default portability:** migration uses `sa.text("0")` for `reference_portfolio` — valid on SQLite, breaks on Postgres.
- **Scheduler wiring:** `app.py` lines 251-255 correctly instantiate `MbRequestBuilderImpl` and inject into `build_scheduler_service(mb_builder=...)`. Verified.
- **Endpoint matrix:** `endpoint-contract-matrix.md` lines 156-167 already list all 5 MB routes + SSE shape; Phase-16 slice of P2-21 matrix verification is satisfied. No new row needed.

**Tasks (in execution order):**

1. **P1-04 — Fix MB prompt/builder contract end-to-end.**
   - Context: `ReportRequest` (Plan 5) currently carries `mode`, `user_input`, `enabled_sections`, `custom_sections`, `length` — no slot for `section_topics` or `reference_portfolio`. Two options:
     - **Option A (preferred):** Extend `ReportRequest` with optional `section_topics: Mapping[str, list[dict]] | None = None` and `reference_portfolio: list[dict] | None = None` fields (Plan 5 already isolates the dataclass; adding optional fields is additive). Update `PromptLoader` context-building path to forward them unchanged.
     - **Option B:** Add a sibling `extras: Mapping[str, Any] | None = None` bucket on `ReportRequest` and have the prompt loader merge `extras` into the Jinja render context. Slightly looser contract but avoids growing the dataclass for every future department.
   - Files:
     - `packages/core/src/openlia/llm/runtime/messages.py` (add field(s) to `ReportRequest`).
     - `packages/core/src/openlia/llm/runtime/runner.py` or wherever `ReportRunner` assembles the Jinja render context for `report.<mode>.user` — pass the new field(s) through.
     - `packages/server/src/openlia_server/services/mb_request_builder.py` — remove the `MB_EXTRAS_JSON` stuffing at lines 58-66; pass `section_topics=cfg.section_topics` and `reference_portfolio=reference_portfolio` as typed `ReportRequest` fields; restore `user_input` to the plain instruction string.
     - `packages/core/src/openlia/prompts/morning_briefing.yaml` — confirm Jinja reads vars at template root (already correct — lines 37, 41-49, 62-69).
   - Tests (new + updated):
     - `packages/server/tests/test_services/test_mb_request_builder.py` — assert built `ReportRequest.section_topics == cfg.section_topics` and `ReportRequest.reference_portfolio == [...]` when toggle on + holdings exist; assert `user_input` contains no `MB_EXTRAS_JSON` substring.
     - `packages/core/tests/llm/runtime/test_runner.py` (or equivalent) — assert the Jinja render context includes `section_topics` + `reference_portfolio` pulled off `ReportRequest`.
     - `packages/core/tests/prompts/test_morning_briefing_prompt.py` — keep as-is (already tests top-level vars).
     - End-to-end: on-demand briefing with 2 topics per section + `reference_portfolio=True` + portfolio with 2 holdings renders both into LLM user prompt (observable via captured `LlmRequest.user_message`).
   - Plan ref: Phase 16 plan Design Rules 5, 7; Task 7.
   - Spec ref: MorningBriefingsPageSpec "Section topics" + "Reference Portfolio toggle".
   - Acceptance: all three tests green; manual end-to-end prompt capture shows `War`, `Energy`, `Russia-Ukraine`, and every holding `ticker`/`name` in the user message body.

2. **NEW-16-03 — Fix Boolean `server_default` in mb_user_configs migration for Postgres.**
   - Files: `packages/server/src/openlia_server/db/migrations/versions/2026-04-23-2100_mb_user_configs.py` line 60 — change `server_default=sa.text("0")` to `server_default=sa.text("false")` (or use `sa.false()`).
   - Why new: P0-09 lists migration as present but does not flag the SQLite-only literal.
   - Acceptance: `alembic upgrade head` on fresh Postgres boots without a "invalid input syntax for type boolean: \"0\"" error; existing SQLite tests still pass.

3. **P2-15 — Decompose `MBSettingsView` into the 6 atomic components specified by plan Tasks 17-19.**
   - Files: create under `frontend/src/components/morning-briefing/`:
     - `SectionRow.tsx` — one standard section (checkbox + title + hint + children slot for topic chips / reference-portfolio toggle).
     - `TopicChip.tsx` — pill with × remove + click-to-open-notes; dot indicator when notes non-empty.
     - `NotesPopover.tsx` — Radix `Popover` with textarea + Done button (per spec Settings View — Notes Popover table).
     - `CustomSectionRow.tsx` — bordered card with editable name + description textarea + `×` remove.
     - `ScheduleRow.tsx` — single-line schedule display + Edit + `✕` (opens `AddScheduleModal` in edit mode).
     - `AddScheduleModal.tsx` — Radix `Dialog` with time picker, tz dropdown, day checkboxes, label field, Cancel / Add Schedule buttons.
   - Refactor `MBSettingsView.tsx` to compose them; delete inline `TopicsEditor` and `ScheduleEditor` helpers.
   - Replace raw `<input type=checkbox>` with Radix `Checkbox`; use Radix `ToggleGroup` for day selection (plan Tech Stack line 20).
   - Plan ref: Phase 16 plan Tasks 17, 18, 19, 20.
   - Spec ref: MorningBriefingsPageSpec "Settings View / Coverage List", "Settings View — Notes Popover", "Settings View — Custom Sections", "Settings View — Schedule", "Settings View — Add Schedule Modal".
   - Acceptance: each component exports independently; `MBSettingsView.tsx` body drops below ~120 lines; one vitest per component (see next task).

4. **NEW-16-01 — Add per-component frontend vitests.**
   - Files under `frontend/src/components/morning-briefing/__tests__/`:
     - `MBArchiveView.test.tsx` — empty state renders Sun icon + Go-to-Settings CTA; populated grid date-groups by "Today / Yesterday / April 7".
     - `MBReportCard.test.tsx` — Open + Download buttons fire; New badge appears when `created_at` < 1 hour + unopened.
     - `MBSettingsView.test.tsx` — toggling section checkbox updates `enabled_section_ids`; adding custom section appends with `crypto.randomUUID()` id; Save button calls `onSaveConfig` with current draft.
     - `SectionRow.test.tsx`, `TopicChip.test.tsx`, `NotesPopover.test.tsx`, `CustomSectionRow.test.tsx`, `ScheduleRow.test.tsx`, `AddScheduleModal.test.tsx` — one focused behavior each.
     - `OnDemandBriefingButton.test.tsx` — click triggers `useReportStream` start; `onSaved(reportId)` fires on `report.saved`; `onError` on `report.error`.
   - Why new: tracker lists only umbrella P2-TESTS debt; no Phase-16-specific frontend-test ticket.
   - Acceptance: `cd frontend && npm run test -- morning-briefing` runs 10+ suites all green.

5. **NEW-16-02 — Add `useMbChatSession` resolve-or-create hook test.**
   - Files: `frontend/src/hooks/__tests__/useMbChatSession.test.ts`.
   - Cases: (a) GET returns existing `{session_id}` → hook exposes same id, no POST fired; (b) POST returns new id when user has none; (c) hook surfaces loading + error states.
   - Plan ref: Phase 16 plan Task 15.
   - Acceptance: 3 cases green.

6. **NEW-16-04 — Reconcile Chat-tab + Viewer-split page composition with spec.**
   - Context: shipped page (per memory observation 1151) has a 3-tab nav (Archive / Chat / Settings) plus a split viewer when a report is opened. Spec (MorningBriefingsPageSpec §"Overview") says two views only: Archive (default) + Settings, accessed via a Settings button. No Chat tab, no split viewer in spec.
   - Action: update `planning/specs/pages/departments/MorningBriefingsPageSpec.md` to document the 3-tab nav + viewer-split Chat as the intended v1 design, OR rework `MorningBriefing.tsx` to drop the Chat tab and keep Chat only inside the viewer split. Decision belongs to the product owner; flag in the fix-plan review.
   - Files (if reworking): `frontend/src/pages/departments/MorningBriefing.tsx` lines 180-200 (tab bar), 209-222 (chat tab body).
   - Acceptance: spec and shipped page agree on which of {Archive, Chat, Settings, Viewer} exist at top level.

7. **NEW-16-05 — Spec-aligned microcopy and layout polish.**
   - Files: `frontend/src/pages/departments/MorningBriefing.tsx`, `MBArchiveView.tsx`, `MBSettingsView.tsx`.
   - Fixes:
     - Archive header: 56px `h-14` with title left, "⚙ Settings" button right (when not in tab mode).
     - Settings header: "← Back to Reports" text link + "Morning Briefings Settings" title (when not in tab mode).
     - Archive date-group headers: "Today — Thursday, April 9, 2026" / "Yesterday — …" / "April 7" formats.
     - Archive empty state: Sun icon 40px `--color-text-tertiary` + "No reports yet." message + "⚙ Go to Settings" CTA.
     - Settings Save toast: bottom-right, 3-second auto-dismiss, success + error variants.
     - Replace arbitrary Tailwind classes with the `--color-bg-base` / `--color-border-subtle` / `--radius-lg` tokens from plan Tech Stack.
   - Acceptance: visual parity with spec layouts; three vitest assertions exercise the new strings / tokens.

8. **NEW-16-06 — Add backend on-demand + schedule integration test that exercises the builder->prompt path.**
   - Files: `packages/server/tests/test_services/test_mb_runner.py` (add a case).
   - Scenario: seed `MbUserConfig` with `section_topics={"global_macro": [{"topic": "War", "notes": "Russia-Ukraine"}]}` and `reference_portfolio=True`; seed 2 `PortfolioHolding` rows; stub `ReportRunner` to capture the `ReportRequest`; invoke `mb_runner.run_on_demand`; assert the captured `ReportRequest` carries `section_topics` with "War" and `reference_portfolio` with both tickers. This catches a future `MB_EXTRAS_JSON` regression.
   - Acceptance: test passes against fixed builder (Task 1) and fails against current master.

**Verification:**

```bash
uv run pytest \
  packages/core/tests/departments/test_morning_briefing.py \
  packages/core/tests/prompts/test_morning_briefing_prompt.py \
  packages/server/tests/test_services/test_mb_config.py \
  packages/server/tests/test_services/test_mb_request_builder.py \
  packages/server/tests/test_services/test_mb_runner.py \
  packages/server/tests/test_services/test_mb_schedules_service.py \
  packages/server/tests/test_routes/departments/test_morning_briefing_config.py \
  packages/server/tests/test_routes/departments/test_morning_briefing_schedule.py \
  packages/server/tests/test_routes/departments/test_morning_briefing_report.py \
  packages/server/tests/test_routes/departments/test_morning_briefing_chat_session.py \
  packages/server/tests/test_db/test_migrations.py
cd frontend && npm run test -- morning-briefing
```

Manual: (1) boot fresh Postgres, run `alembic upgrade head`, confirm `mb_user_configs` exists with all 9 columns and reference_portfolio defaults to `false`; (2) PUT config with 2 topics + `reference_portfolio=true`; add 2 portfolio holdings; POST `/report`; capture `LlmRequest.user_message` from fixture — both topic names, notes, and both holding tickers must appear verbatim; (3) open Settings View, click a topic chip, verify Notes popover opens with textarea + Done; (4) click "+ Add Schedule", verify Radix Dialog with time / tz / days / label fields appears.
