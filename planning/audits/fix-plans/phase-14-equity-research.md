# Phase 14 — Equity Research fix plan (→ 100%)


**Current:** ~83% shipped. **Root cause:** IMPLEMENTER.

**Gap summary:** Report SSE pipeline, config service, suggestion chips, and ReportCard ship, but Active-state layout diverges from spec, suggestion chips don't auto-submit, Download is two flat buttons, `POST /chat` drops `session_id`, and backend route/config tests are missing.

**Tasks (in execution order):**

1. **P1-03 — Thread `session_id` through `POST /departments/equity-research/chat`.**
   - Files: `routes/departments/equity_research.py:152–177` — accept `payload.session_id`, pass to `runner.run(session_id=...)`; mirror the `/report` route's pattern at lines 140–141.
   - Spec ref: EquityResearchPageSpec "Active State" — follow-up questions in the same conversation.
   - Acceptance: `test_equity_research_chat_route.py` asserts second `/chat` call with same `session_id` appends to existing session (not a new row).

2. **P1-19 — Make suggestion chips populate AND submit input.**
   - Files: `frontend/src/components/equity-research/SuggestionChips.tsx:9–25` — change `onSelect` contract to `(value, {submit: true})`; `EquityResearch.tsx:26–29` — replace `onChipSelect` so it sets input AND invokes `onSend`.
   - Spec ref: EquityResearchPageSpec "Welcome State" — "immediately populate the input and submit."
   - Acceptance: vitest — click "AAPL" triggers both `setInput("AAPL")` and `onSend` exactly once.

3. **P1-20 — Convert `ReportCard` Download to PDF+DOCX dropdown and add DOCX export backend.**
   - Files: `ReportCard.tsx:65–88` — replace flat button with `<DownloadMenu>` (PDF / DOCX); `frontend/src/api/reports.ts` add `reportDocxUrl(id)`; `routes/reports.py` add `GET /reports/{id}/docx` using `python-docx` (new `services/report_export.py::export_report_docx`).
   - Plan ref: Phase 14 Task 15 + Phase 13 Task 7.
   - Spec ref: EquityResearchPageSpec "Report Thumbnail Card" — `[Download ▾]` dropdown.
   - Acceptance: vitest — click ▾ shows two items; clicking DOCX opens `/reports/<id>/docx`; backend test downloads valid `.docx` zip.

4. **NEW-14-01 — Restore spec-compliant Active-state layout: chat below header, `ReportCard` as inline chat block, FileViewer-on-click.** Why new: tracker flags "active layout diverges" in summary only; current file is split-panel, spec requires single-column chat.
   - Files: `EquityResearch.tsx:145–198` — delete split-panel; render `<ChatInterface>` full-width and inject `<ReportCard>` as a message entry when `reportState.status === "complete"`; wire `onOpen` to global `FileViewerContext`.
   - Spec ref: EquityResearchPageSpec "Active State" ASCII layout.
   - Acceptance: E2E — after first report generates, chat shows streamed assistant message followed by ReportCard; `Open Report` opens shared FileViewer drawer, not a half-pane.

5. **P2-TESTS-14 — Add missing backend tests.**
   - Files: create `test_equity_research_config_route.py`, `test_equity_research_report_route.py`, `test_equity_research_chat_route.py`, `test_equity_research_config.py`.
   - Acceptance: `uv run pytest packages/server/tests -k equity_research` shows ≥4 new files passing.

6. **NEW-14-02 — `FromPortfolioPicker` renders as popover listing Portfolio tickers.** Why new: spec requires scrollable list rows; not flagged in tracker.
   - Files: `frontend/src/components/equity-research/FromPortfolioPicker.tsx` — fetch from `/portfolio/tickers`; render popover.
   - Acceptance: click chip → popover lists portfolio tickers; selecting one populates input and submits.

**Verification:** `uv run pytest packages/server/tests -k equity_research && npm --prefix frontend test -- equity-research`.
