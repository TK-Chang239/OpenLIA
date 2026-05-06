# Morning Briefing — Dev Backlog

Open work for the Morning Briefing department. Items are scoped to MB but several
have cross-cutting fixes that benefit other report departments (Equity Research,
Earnings Update, Macro Research). Each item lists where the issue lives and a
hint at the fix shape.

Last updated: 2026-05-05

---

## P0 — User-visible breakage

### MB-1. Report writing turn truncates on long briefings (PARTIAL FIX 2026-05-05)
- Symptom: `LLM returned non-JSON response: Expecting ',' delimiter: line N column 8 (char ~16k)`.
- Fix shipped: writing-phase `max_tokens` now uses
  `min(resolved.capabilities.max_output_tokens, 16384)` with a 4096 floor
  (`packages/core/src/openlia/llm/runtime/report.py`).
- Still open:
  - For models capped at 4096 output tokens (Haiku, GPT-5.4-mini), a long
    briefing can still hit the cap. Need either per-section streaming
    (one LLM call per section, accumulated into final schema) or a
    "continue" pass that asks the model to resume the JSON.
  - Hard-stop on truncation should produce a clearer user-facing message
    than "Expecting , delimiter" — detect `finish_reason == "length"`
    and surface "Report exceeded model output limit".

### MB-2. Anthropic adapter ignores `response_format=json_schema`
- File: `packages/core/src/openlia/llm/adapters/anthropic.py`.
- Today the adapter never forwards `response_format` to the API, so MB
  relies on prompt instructions ("Emit only the ReportSchema JSON")
  to coerce JSON output. Models routinely return markdown-fenced JSON
  or prose preambles. We added prose/fence-tolerant parsing in
  `report.py::_extract_json_object` as a backstop, but the right fix
  is provider-level enforcement.
- Options:
  1. Anthropic-native tool-use: define a single `submit_report` tool
     whose `input_schema` is the ReportSchema; force `tool_choice` to
     it. The model's `tool_use` block is the structured payload.
  2. Pre-fill the assistant turn with `{` so Anthropic continues from
     the opening brace.
- Preferred: option 1 — converges with how OpenAI/Gemini structured
  output already works.

---

## P1 — Correctness / robustness

### MB-3. Framework JSON is not a valid JSON Schema
- Files: `packages/core/src/openlia/reports/frameworks/morning_briefing.json` (and
  every other `*_framework.json`).
- Today the framework dict is passed directly as
  `ResponseFormat(kind="json_schema", json_schema=framework)`. It's a
  content template (with `cover`, `sections[]`, `instructions` strings),
  not a JSON Schema (`type`, `properties`, `required`).
- OpenAI strict mode rejects this; Anthropic ignores it; Gemini is lenient
  but does not enforce.
- Fix: split into two artifacts per report mode:
  - `<mode>.schema.json` — true JSON Schema describing the output shape.
  - `<mode>.template.json` — content stub + `instructions` for the prompt.
- Pass `schema.json` to providers; pass `template.json` to the user prompt.

### MB-4. Report runner can run with zero tools
- File: `packages/core/src/openlia/llm/runtime/report.py` — when
  `ToolDispatcher.build()` returns `[]`, the tool loop is `range(0)` and
  the model goes straight to writing with no data.
- Mitigation shipped 2026-05-05: prompt now anchors today's date and
  the `has_tools=False` branch instructs the model to leave numerics
  null and write "Data unavailable." instead of refusing.
- Better fix: connector setup wizard should not let a department be
  marked "ready" without at least one mapped requirement tool. Surface a
  blocker banner on the MB page with a "Set up connectors" CTA when
  `dept-health` reports MB as blocked.

### MB-5. `current_date` is UTC, not user timezone
- File: `packages/core/src/openlia/llm/runtime/report.py:219`.
- Around the UTC date boundary a user in PT sees yesterday's date in
  their briefing. The MB schedule does already store a timezone
  (`MbSchedule.timezone`) — plumb it into `ReportRequest` and use it in
  the report runner. For on-demand runs, fall back to the user's
  account timezone or the schedule's timezone.

### MB-6. No retry on truncation
- File: `packages/core/src/openlia/llm/runtime/report.py:316-336`.
- A truncated JSON response (finish_reason="length") is fatal. Once
  per-section streaming (MB-1) lands, retry-on-truncation becomes
  natural — re-ask only for the failed section.

### MB-7. Frontend API contract drift across departments
- Fix shipped 2026-05-05: `frontend/src/api/morning-briefing.ts::fetchReports`
  now maps server's `{items: [...]}` to the frontend's `{reports: [...]}`
  (root cause of the `TypeError: Cannot read properties of undefined
  (reading 'length')` crash on the MB page).
- Backlog: audit all other department API clients
  (`earnings-update.ts`, `macro-research.ts`, `equity-research.ts`,
  ...) for similar assumptions about response field names. Consider
  introducing a shared `RecentReportsResponse` type that mirrors the
  server's `ReportListOut.items` directly so the mismatch can't recur.

---

## P2 — UX

### MB-8. No progressive rendering of report sections
- The runner emits `ReportSectionStart` events but the actual content
  arrives as one `ReportComplete` schema at the very end. The UI shows
  "Loading briefing…" for the entire generation duration.
- Wire per-section content delta events from the runner once
  per-section LLM calls (MB-1) are in.

### MB-9. Empty-state CTA on Archive view
- `frontend/src/components/morning-briefing/MBArchiveView.tsx` — the
  empty state shows "No reports yet" with a "Go to Settings" link. If
  the user has no schedule and no connectors, the better CTA is
  "Generate one now" or "Set up connectors". Tie copy to
  `dept-health` status.

### MB-10. Schedule label hardcoded ("Pre-Market" / "Post-Market")
- `packages/core/src/openlia/reports/frameworks/morning_briefing.json`
  cover instructions assume Pre-Market/Post-Market. For users running
  on-demand, the schedule label should auto-derive from the run time
  vs. market hours, or be omittable.

### MB-11. Follow-up chat chips are static
- `frontend/src/pages/departments/MorningBriefing.tsx::FOLLOW_UP_CHIPS`
  is hardcoded. Generate from the latest briefing's section ids and
  key findings so chips reference today's content.

---

## P3 — Test gaps

### MB-12. Truncated-output path
- Add a test in `packages/core/tests/test_llm/test_runtime/test_report.py`:
  provider returns a JSON prefix only (simulating finish_reason="length").
  Assert the error message names truncation, not "Expecting , delimiter".

### MB-13. Empty-tools render path
- Verify the writing-phase prompt is invoked when
  `tool_dispatcher.build()` returns `[]` and the user prompt contains
  the "Data unavailable" fallback block.

### MB-14. Anthropic structured output integration test
- After MB-2 ships, add an integration test that submits a
  `submit_report` tool spec and verifies the report runner extracts
  the structured input from `tool_calls[0].arguments` instead of from
  `response.text`.

### MB-15. Browser smoke for the live "generate now" button
- `OnDemandBriefingButton` posts to `/api/departments/morning-briefing/report`
  and streams SSE. Manual smoke this session uncovered MB-1, MB-7, and
  the prompt issues. Add Playwright coverage that walks the on-demand
  flow with a fake provider, asserting the report renders end-to-end.

---

## Tracking notes

- Bugs filed against MB during the 2026-05-05 session:
  - Frontend `TypeError: Cannot read properties of undefined (reading 'length')` — fixed (MB-7).
  - `LLM returned non-JSON response: Expecting value: line 1 column 1` (refusal) — fixed by prompt date injection (MB-4).
  - `LLM returned non-JSON response: Expecting value:` (markdown fences) — fixed by `_extract_json_object` (MB-2 backstop).
  - `Expecting ',' delimiter: line 284 column 8 (char 16223)` — partial fix via max_tokens bump (MB-1).
- Branch where fixes shipped: `fix/morning-briefings`.
