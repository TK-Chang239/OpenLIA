# Phase 13 — Report Pipeline & Secretary fix plan (→ 100%)

**Current:** ~70% shipped. **Root cause:** IMPLEMENTER.

**Gap summary:** Core `ReportSchema` (Pydantic), assembler, validator, frameworks loader, and SecretaryDepartment core class are shipped. Frontend report renderer (all 16 block/chart components plus cover/TOC/scroll tracker), `RedirectCard`, and `api/reports.ts` are shipped. What is missing or wrong:

1. No Secretary HTTP route nor chat-runner service — `routes/departments/secretary.py`, `services/secretary_chat_runner.py`, and the `build_secretary_router` mount in `app.py` are all absent.
2. The reports PDF fallback HTML renderer in `routes/reports.py` reads **wrong field names** for `metric_cards` (reads `cards`, schema is `metrics`) and `table` (reads flat `columns` and list-rows, schema is `headers[].key/label` + keyed-dict rows) — PDFs silently drop these blocks.
3. `_schema_to_html` omits most block types entirely (all 10 chart blocks, `key_finding` reads wrong `heading/body` fields, `rating_badge` reads wrong `label/value` fields, `group` ignores `columns`, `cover.key_metrics`/`stats_panel`/`ticker`/`page_furniture` not rendered, sections have no `id` anchor).
4. Two parallel report-persistence services with **conflicting schema contracts**: `services/report_store.py` has a stale `validate_report_schema` that requires `{heading, content}` sections (legacy markdown shape), while `services/reports.py` uses `validate_report_payload` against the canonical `ReportSchema`. `save_report` in the former rejects valid blocked schemas.
5. `api/secretary.ts` frontend client is missing (only `api/reports.ts` shipped).
6. No Secretary frontend wiring for `suggest_redirect` tool-call → `RedirectCard` (`RedirectCard.tsx` exists but is unused; `SecretaryPage.tsx` does not subscribe to chat tool-call events).
7. Secretary page lacks spec-mandated animations (welcome exit 200ms, chip stagger, card entry), stop-button + "Response stopped" label, and clicking a chip does not populate/submit input.
8. `secretary.yaml` has orphaned top-level `system` / `user` keys (legacy single-shot template) that are not consumed by `ChatRunner` — spec implies only the `chat.system` block is used. Tracked by P2-10 (Phase 5) — carry-over item.
9. No backend tests for `routes/departments/test_secretary.py`; `test_routes/test_reports.py` does not assert that PDF contains `metric_cards`/`table` content (only that bytes start with `%PDF`).

---

**Tasks (in execution order):**

---

### 1. P1-01 — Fix PDF block renderer field-name bugs in `_render_block` and `_schema_to_html`

`packages/server/src/openlia_server/routes/reports.py` lines 30–85 iterate over the wrong keys. Spec (`report-rendering-pipeline-design.md` §Block Types) is authoritative.

**Concrete bugs:**

| Block | Current (wrong) | Canonical (per `ReportSchema`) |
|---|---|---|
| `metric_cards` (line 42) | `block.get("cards", [])` | `block.get("metrics", [])` |
| `metric_cards` item | `c["label"] / c["value"]` | add optional `delta` + `delta_direction` colour class |
| `table` (line 54) | `block["columns"]` (list of strings) and `block["rows"]` (list of list) | `block["headers"]` (list of `{key,label,align,sortable,sparkline}`) and `block["rows"]` (list of dict keyed by header `key`) |
| `table` thead rendering | emits `<th>{col}</th>` | must emit `<th class="text-{align}">{label}</th>` |
| `table` tbody rendering | iterates row as list | must iterate headers and pull `row[header.key]`; apply `_row_style` + `cell_format` rules (directional/negative/positive/bold/muted) |
| `table` extra | none | render `title`, `footnotes`, and sparkline cells (SVG inline) per spec §Sparkline Table Extension |
| `key_finding` (line 34) | reads `heading` + `body` | schema has single `content` markdown field only |
| `rating_badge` (line 38) | reads `label` + `value` | schema has `rating` (required), `previous_rating`, `change_date`; render coloured pill (Buy/Hold/Sell palette) |
| `group` (line 63) | ignores `columns` | must render `<div class="group group-cols-N">…</div>` with inline `grid-template-columns` or flex so layout matches HTML view |
| Chart blocks (all 10) | single placeholder `<p>[Title]</p>` | must render static SVG/HTML representation so PDFs contain chart content, not a stub. Minimum v1: render the chart title + a pre-computed static SVG (ECharts SSR) — see Task 4 below |

**Cover / furniture / sections missing in `_schema_to_html`:**

- `cover.ticker` not rendered
- `cover.key_metrics` (row of stat cards) not rendered
- `cover.stats_panel` (bordered metadata grid) not rendered
- `page_furniture.header` / `footer` / `disclaimer` ignored — must be wired into Playwright `header_template` / `footer_template` via `export_report_pdf` which already accepts them (`services/report_export.py:42–60`); populate from `schema.page_furniture`
- `section.id` not emitted as HTML anchor (TOC links break in HTML-preview fallback)

**Acceptance:**
- `uv run pytest packages/server/tests/test_routes/test_reports.py::test_export_pdf_renders_all_block_types` (new — see Task 10) extracts PDF text via `pdfminer.six` and asserts every fixture label/value/cell/title appears.
- `_render_block({"type": "table", ...})` round-trips header labels, row cells keyed by `header.key`, and applies `_row_style` CSS class.

**Plan ref:** Phase 13 Task 8. **Spec ref:** `report-rendering-pipeline-design.md` §Block Types, §Cover Block, §Global Page Furniture.

---

### 2. P0-01 — Create Secretary HTTP route + chat-runner service + mount in app

Master tracker P0-01. Spec: `SecretaryPageSpec.md` §Functions, §Redirect Routing Logic, §Response Interruption. Plan Task 9.

**Files to create:**

1. `packages/server/src/openlia_server/services/secretary_chat_runner.py` — thin wrapper around `openlia.llm.runtime.chat.ChatRunner` with:
   - Department resolver pulls `SecretaryDepartment()` from `openlia.departments`
   - Loads prompt `secretary.yaml` (chat block) via existing Jinja loader
   - Registers mapped data tools (`stock_quote`, `company_profile`, `company_news`, `historical_prices`, `economic_events`) via `openlia_server.services.data_providers` user-scoped resolver
   - Registers `suggest_redirect` extra-tool (from `SecretaryDepartment.extra_tools`)
   - Accepts `CancellationToken` for stop-stream
   - Yields `ChatEvent`s (`chat.start`, `chat.token`, `chat.tool_call`, `chat.tool_call.result`, `chat.done`, `chat.error`, `chat.stopped`) in wire form via `to_wire`

2. `packages/server/src/openlia_server/routes/departments/secretary.py` — defines `build_secretary_router(*, db_session_factory, mode)`:
   - `POST /departments/secretary/chat` — SSE endpoint
     - Body: `{"message": str, "session_id": str | None}`
     - Auth via `build_require_auth`
     - Persists user + assistant messages to `chat_sessions` table (per cross-plan contract — same pattern as `equity_research.py:60+`)
     - Streams SSE events produced by `SecretaryChatRunner` via `StreamingResponse` w/ `media_type="text/event-stream"`
     - Honors `Request.is_disconnected()` to cancel stream
   - `GET /departments/secretary/chat?session_id=…` — optional EventSource GET variant matching `api/secretary.ts` spec contract (Plan Task 10 Step 3)

3. `packages/server/src/openlia_server/routes/departments/__init__.py` — re-export `build_secretary_router` alongside existing `build_equity_research_router` etc.

**Files to modify:**

- `packages/server/src/openlia_server/app.py` lines 50–68 — add import:
  ```python
  from openlia_server.routes.departments import (
      build_secretary_router,
      ...
  )
  ```
  and mount at line 346 (before `build_equity_research_router`):
  ```python
  app.include_router(build_secretary_router(db_session_factory=factory, mode=mode))
  ```

**Acceptance:**
- `curl -sN -H "accept: text/event-stream" -X POST .../departments/secretary/chat -d '{"message":"hi","session_id":"s1"}'` emits `data: {"type":"chat.start",...}` → `chat.token` → `chat.done`.
- Unauthed in company mode returns 401.
- Cancelling the HTTP request mid-stream cancels the `ChatRunner` and emits `chat.stopped`.

---

### 3. NEW-13-01 — Create `api/secretary.ts` typed client

Plan Task 10 shipped `api/reports.ts` but not `api/secretary.ts` (verified absent). Spec: plan doc Task 10 Step 3.

**File:** `frontend/src/api/secretary.ts`

```ts
export function secretaryChatUrl(sessionId?: string): string {
  const base = '/api/departments/secretary/chat';
  return sessionId ? `${base}?session_id=${encodeURIComponent(sessionId)}` : base;
}
```

Plus test `frontend/src/api/__tests__/secretary.test.ts` asserting both branches (with and without sessionId).

**Acceptance:** `npx vitest run src/api/__tests__/secretary.test.ts` passes.

---

### 4. NEW-13-02 — Replace chart-block placeholder with static SVG rendering in PDF path

`_render_block` currently falls through for every chart type to a `<p class="placeholder">[Title]</p>` line. PDF exports of real reports lose all charts. Spec §Charts in PDF says "ECharts in SVG rendering mode outputs vector graphics". Options:

- **Option A (preferred):** server uses Playwright to open the full React renderer URL `/reports/{id}/render?pdf=1` (fed from the React bundle) instead of the HTML fallback — the same React `ReportRenderer` runs, ECharts renders in SVG mode, PDF captures vectors. Requires a minimal Vite-served static bundle or an in-process SSR route.
- **Option B:** keep fallback HTML but call ECharts SSR via a Python-side JS bridge (deferred). Out of scope v1.

**Chosen:** Option A. Add a new route `GET /reports/{id}/render` in `routes/reports.py` that returns a stand-alone HTML page importing the compiled frontend `ReportRenderer` bundle with the report schema injected as `window.__REPORT_SCHEMA__`. `export_report_pdf_route` launches Playwright against that URL (same origin, forwarding auth cookie) instead of the hand-rolled HTML.

**Files:**
- `packages/server/src/openlia_server/routes/reports.py` — add `render_report_html` route; rewrite `export_report_pdf_route` to use `page.goto(f"http://127.0.0.1:{port}/reports/{id}/render", wait_until="networkidle")`.
- `frontend/src/main.tsx` — add `/reports/:id/render` route that mounts `<ReportRenderer schema={window.__REPORT_SCHEMA__} />` with animations disabled.
- `packages/server/src/openlia_server/services/report_export.py` — pass `schema.page_furniture.header/footer/disclaimer` as `header_html`/`footer_html` (already supported by `export_report_pdf`).

**Acceptance:** integration test generates a report containing every chart type and asserts resulting PDF byte count > 40 KB and `pdfminer` text contains chart titles.

---

### 5. NEW-13-03 — Reconcile `services/report_store.py` and `services/reports.py`

Two stores define overlapping APIs with contradictory schemas:

- `services/report_store.py:23–41` `validate_report_schema` requires sections of shape `{heading: str, content: str}` — this is the **legacy markdown** shape and will reject every `ReportSchema` produced by Phase 13 Task 3 assembler (`{id, title, blocks}`). `save_report` therefore cannot persist any valid v1 report.
- `services/reports.py:17–23` `get_report` and `create_report` use the canonical `validate_report_payload` against `ReportSchema`.

**Fix:**
- Delete `services/report_store.py::validate_report_schema` and rewrite `save_report` to call `openlia.reports.validator.validate_report_payload`, accepting a `ReportSchema` (or dict) and storing `content_structured = schema.model_dump(mode="json")`.
- Audit all callers. Currently `save_report` is imported by `services/equity_research_runner.py` and `services/mb_runner.py` (grep). Migrate them to use `services/reports.py::create_report` with the canonical `ReportSchema` object.
- Consolidate into a single module: move `get_report_for_user` + renamed `save_report` into `services/reports.py`, delete `report_store.py`.

**Acceptance:**
- `grep -r "from openlia_server.services.report_store" packages/` returns zero matches.
- `uv run pytest packages/server/tests/test_services/test_reports.py` green with canonical schema fixtures.

**Spec ref:** cross-plan contracts locked 2026-04-20 (reports table contract). **Plan ref:** Phase 13 Task 6.

---

### 6. NEW-13-04 — Wire Secretary tool-call events to `RedirectCard` in SecretaryPage

`RedirectCard.tsx` is implemented but never rendered. SecretaryPage only forwards a `sentOnce` flag; it does not subscribe to streaming tool-call events.

**Files:**
- `frontend/src/pages/SecretaryPage.tsx` — subscribe to `ChatInterface` tool-call events; when `chat.tool_call.result` with `tool_name === "suggest_redirect"` arrives, render `<RedirectCard department={...} reason={...} prefill={...} />` below the assistant message per spec §Redirect Suggestion Card.
- `frontend/src/components/chat/ChatInterface` — expose a `onToolCallResult` prop; emit tool-call results from the SSE stream into the prop.
- `frontend/src/components/chat/RedirectCard.tsx` — verify: on click, `router.push(/${dept}?prefill=${encodeURIComponent(prefill)})` (plus dept URL mapping table matching spec routing table).

**Acceptance:** Vitest — fire a `chat.tool_call.result` event for `suggest_redirect` with `department=equity_research, prefill=AAPL`; assert `<RedirectCard>` rendered with those props; click "Go to Equity Research →" calls `router.push('/equity-research?prefill=AAPL')`.

---

### 7. NEW-13-05 — Implement Welcome-state animations, chip-submit, stop-button, and "Response stopped" label on SecretaryPage

Spec §Welcome State Layout Details + §Response Interruption + §Message Input.

**Missing UI/behaviour:**
- Welcome greeting + sub-text entry animation `opacity 0→1, y 12→0, 250ms` (use Framer Motion).
- Chip row staggers in `40ms` apart after heading.
- Welcome exit animation `opacity 1→0, y 0→-8, 200ms` when first message sent.
- Clicking a suggestion chip must populate the input **and submit immediately** — currently chips are inert `<button>`s (lines 41–49).
- Stop button: replace send when `streaming === true`, dimensions `w-8 h-8`, `Square` icon, clicking cancels the SSE stream (posts to a cancel endpoint or closes the EventSource — `ChatInterface` already exposes stop via `useChatStream.stop()`; expose it through props).
- On stop, append a muted "Response stopped" label beneath the partial reply.
- Helper text beneath input: "Press Enter to send · Shift+Enter for new line".

**File:** `frontend/src/pages/SecretaryPage.tsx` + `frontend/src/components/chat/ChatInterface.tsx`.

**Acceptance:** Vitest — clicking chip submits message; welcome overlay unmounts with animation (measure transition); while streaming, send button replaced by Square-icon stop button; clicking stop emits `abort` and appends "Response stopped".

---

### 8. NEW-13-06 — Strip orphaned `system` / `user` top-level keys from `secretary.yaml`

Lines 1–24 of `packages/core/src/openlia/prompts/secretary.yaml` define `system:` and `user:` at the top level — a legacy single-shot template that predates the `chat:` block. The Secretary chat runtime loads only the `chat:` sub-tree; the top-level keys are dead code and contradict the spec (spec makes no mention of a non-chat mode for Secretary).

**Fix:** Delete lines 1–23; keep only the `chat:` block. Verify via `grep -rn "secretary" packages/core/src/openlia/llm/` that no loader path references `prompts/secretary.yaml::system`.

**Carries P2-10** (also referenced from Phase 5 fix-plan).

**Acceptance:** `uv run python -c "from openlia.prompts.loader import load_prompt; print(load_prompt('secretary')['chat']['system'][:40])"` prints the expected first chars; loader does not break on any department.

---

### 9. NEW-13-07 — Backend tests for Secretary route, chat runner, and redirect emission

**File:** `packages/server/tests/test_routes/departments/test_secretary.py`

Cases (per plan Task 9 Step 1 but expanded):
1. `test_secretary_chat_streams_start_token_done` — fake LLM emits plain text, assert event order `chat.start → chat.token+ → chat.done`.
2. `test_secretary_chat_emits_suggest_redirect_tool_call` — fake LLM emits tool call for `suggest_redirect(department=equity_research, reason=..., prefill=AAPL)`; assert `chat.tool_call.result` event carries those args.
3. `test_secretary_chat_requires_auth_in_company_mode` — 401 for `company_client_anon`.
4. `test_secretary_chat_persists_session_messages` — after a round trip, `chat_sessions` table contains one user + one assistant message for given `session_id`.
5. `test_secretary_chat_cancellation` — disconnect mid-stream; assert `ChatRunner` receives cancel and final event is `chat.stopped`.
6. `test_secretary_chat_tool_stock_quote` — LLM emits `stock_quote(AAPL)`; assert provider is invoked with user-scoped EODHD key and result flows back as `chat.tool_call.result`.

**Acceptance:** `uv run pytest packages/server/tests/test_routes/departments/test_secretary.py -v` green.

---

### 10. NEW-13-08 — Rendering tests per block type + PDF integration test

`test_routes/test_reports.py` currently only checks `%PDF` magic. Expand:

**File:** `packages/server/tests/test_routes/test_reports.py` (extend) and new `packages/server/tests/test_services/test_report_export.py`.

Cases:
1. `test_pdf_contains_metric_cards_labels_and_values` — fixture with a `metric_cards` block; extract PDF text via `pdfminer.six`; assert each label and value appear.
2. `test_pdf_contains_table_headers_and_rows_by_header_key` — fixture table with `headers=[{key:"m",label:"Metric"},{key:"v",label:"Value"}]` and `rows=[{m:"Revenue",v:"$124B"}]`; assert "Metric", "Value", "Revenue", "$124B" in PDF.
3. `test_pdf_renders_all_chart_types` (post NEW-13-02) — schema with line/bar/area/pie/candlestick/waterfall/scatter/heatmap/treemap/combo; PDF text includes every chart title.
4. `test_pdf_page_furniture_applied` — asserts `header.right` ("Secretary") and `footer.center` ("Page 1") appear on generated PDF.
5. `test_pdf_cover_renders_key_metrics_and_stats_panel` — asserts both cover zones appear.
6. `test_render_block_table_applies_row_style` — unit test on `_render_block`; passes a `_row_style: "subtotal"` row; asserts `class="row-subtotal"` appears.
7. `test_render_block_cell_format_directional` — negative value in directional-rule column renders with `class="fmt-negative"`; positive with `fmt-positive`.
8. `test_render_block_key_finding_uses_content_field` — uses `content`, not the old `heading/body`.
9. `test_render_block_rating_badge_uses_rating_field` — renders green badge for `rating: "Overweight"`, yellow for Hold, red for Sell.

**Acceptance:** `uv run pytest packages/server/tests/test_routes/test_reports.py packages/server/tests/test_services/test_report_export.py -v` green.

---

### 11. NEW-13-09 — Verify SaveToRepo for Secretary-initiated saves

`services/repo.py::save_to_repo` is wired (line 43) and `routes/repo.py` uses it for PDFs. But the SecretaryPageSpec §Functions mentions meta requests like "save this report to the repository". There is no Secretary tool today that performs that side-effect.

**Fix:** Add a `save_report_to_repo` extra-tool to `SecretaryDepartment.extra_tools` in `packages/core/src/openlia/departments/secretary.py`, with schema `{report_id: str}`. Implement the tool handler in `services/secretary_chat_runner.py` that calls `openlia_server.services.repo.save_to_repo(db, user_id=user.id, report_id=args["report_id"])` and returns `{ok: True, repo_item_id: ...}`.

**Acceptance:** Test `test_secretary_chat_save_report_to_repo_tool` — LLM emits `save_report_to_repo(report_id=<fixture>)`; assert `repo_items` row created, event payload carries `repo_item_id`.

**Spec ref:** SecretaryPageSpec §Functions "handle meta requests ('save this report to the repository')" and cross-plan contracts §repo_items table.

---

### 12. NEW-13-10 — Tool-call → block transformation rules documented in runner

Report generation pipeline (Equity Research, Earnings Update, Morning Briefing) produces data tool calls whose returned values must be embedded into the correct block type by the LLM. The spec §Content Decisions is explicit that the LLM decides, but the **assembler** should enforce:

- Tool calls classified as `quote_like` (stock_quote, fx_quote) may be transformed into `metric_cards` items.
- Tool calls classified as `historical_prices` may be transformed into `line_chart` or `candlestick_chart`.
- Tool calls classified as `statement_row` may be transformed into `table` rows.

`packages/core/src/openlia/reports/assembler.py` currently only strips instructions and injects furniture. It does not validate that tool-call results referenced by `{{ tool_call_ref }}` placeholders resolve. The LLM writes raw values today, so no transformation is required — but assembler should **reject** blocks referencing unknown tool-call ids if the framework introduces that feature.

**Fix:** Document and add a sentinel in `assembler.py`: if a block contains a string value matching `^\{\{tool\:.*\}\}$`, raise `ReportAssemblyError`. This is a guard, not a transformer — prevents silent publication of un-substituted placeholders.

**Acceptance:** `uv run pytest packages/core/tests/reports/test_assembler.py::test_rejects_unsubstituted_tool_placeholder` green.

---

**Verification (full phase):**

```bash
uv run pytest \
  packages/core/tests/reports/ \
  packages/server/tests/test_services/test_reports.py \
  packages/server/tests/test_services/test_report_export.py \
  packages/server/tests/test_routes/test_reports.py \
  packages/server/tests/test_routes/departments/test_secretary.py

cd frontend && npx vitest run \
  src/api/__tests__/secretary.test.ts \
  src/pages/__tests__/SecretaryPage.test.tsx \
  src/components/chat/__tests__/RedirectCard.test.tsx

# Live smoke:
uv run openlia serve &
curl -sN -H "accept: text/event-stream" \
  -X POST http://127.0.0.1:8000/api/departments/secretary/chat \
  -d '{"message":"write a full AAPL research report","session_id":"s1"}' \
  | grep -E '"type":"chat.(start|tool_call.result|done)"'
```

Expected: SSE stream shows `chat.start → chat.tool_call.result (suggest_redirect, department=equity_research) → chat.done`.

---

**Owner handoff:** IMPLEMENTER picks up Task 1 (PDF field-name fix) first — smallest blast radius, immediate effect on existing e2e fixture. Then Task 2 (Secretary route) to unblock P0-01 on master tracker. Tasks 3–7 in any order; Task 8 is a 30-second diff; Tasks 9–12 close out tests + docs.
