# EU v2 — Watchlist rename + Template/Instructions split — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Rename "Coverage" → "Watchlist", and make Template (forced output schema) and Instructions (free-form prompt) independently optional but never both empty.

**Architecture:** Mirror v3's `FREEFORM_TEMPLATE_ID` for the optional-template path; add a "not both empty" guard at settings-save, run-start, and the settings modal. Rename is a label/component change. Branch `feat/eu-v2-template-split` stacks on `feat/eu-v2-instructions` (PR #216).

**Tech Stack:** FastAPI/SQLAlchemy (server), report_eu engine (core, no change needed — freeform already supported), React/TS (frontend), pytest, i18next (en+zh-TW).

---

## Task 1: Backend — freeform template + not-both-empty guard

**Files:**
- Modify: `packages/server/src/openlia_server/services/eu_v2_run_service.py`
- Modify: `packages/server/src/openlia_server/routes/departments/earnings_update_v2.py` (settings PUT guard + run-start error mapping)
- Test: `packages/server/tests/test_services/test_eu_v2_run_service.py`, `packages/server/tests/test_routes/departments/test_earnings_update_v2*.py`

Reference: `equity_research_v3.py:90` `FREEFORM_TEMPLATE_ID = "freeform"` and `_freeform_template_spec()` (uses `TemplateSpec.model_construct(template_id="freeform", name=..., shape_description=..., ticker_anchored=True, default_length=..., sections=[])` — copy its construction so the v2.3 schema's section-min validation is bypassed).

- [ ] **Step 1: Write failing tests**

```python
# test_eu_v2_run_service.py
def test_build_run_request_freeform_template_with_instructions(db_session):
    # seed user + an instruction profile + settings(template_id="freeform", instructions_id=that)
    ...
    req = run_svc.build_run_request(db_session, user_id="local", ticker="SNOW",
        trigger_kind="on_demand", fiscal_period=None, report_date=None,
        release_timing=None, eps_estimate=None, revenue_estimate=None)
    assert req.template.sections == []          # freeform = no forced schema
    assert req.instructions == "Favor FCF."      # methodology drives it

def test_build_run_request_rejects_freeform_without_instructions(db_session):
    # settings(template_id="freeform", instructions_id=None)
    import pytest
    with pytest.raises(run_svc.EmptyBriefError):   # new error type
        run_svc.build_run_request(db_session, user_id="local", ticker="SNOW",
            trigger_kind="on_demand", fiscal_period=None, report_date=None,
            release_timing=None, eps_estimate=None, revenue_estimate=None)
```

- [ ] **Step 2: Run to verify fail** — `uv run pytest packages/server/tests/test_services/test_eu_v2_run_service.py -k freeform -v` → FAIL.

- [ ] **Step 3: Implement**

In `eu_v2_run_service.py`:
- Add `EU_FREEFORM_TEMPLATE_ID = "freeform"` and `_freeform_template_spec()` (copy v3's `model_construct` shape; `shape_description` e.g. "Free-form earnings update — structure designed by the analyst per the instructions.").
- Add `class EmptyBriefError(ValueError)` (a run needs a template or instructions).
- In `build_run_request`, after resolving `settings` and `instructions_text`:
  ```python
  if settings.template_id == EU_FREEFORM_TEMPLATE_ID:
      template = _freeform_template_spec()
  else:
      template = eu_v2_template_service.resolve_template(db, user_id=user_id, template_id=settings.template_id)
  if settings.template_id == EU_FREEFORM_TEMPLATE_ID and not instructions_text:
      raise EmptyBriefError(
          "A freeform run (no template) requires an instruction profile. "
          "Pick a template or an instruction profile."
      )
  ```
  (Resolve `instructions_text` BEFORE this block — it already happens on the instructions branch.)

In `earnings_update_v2.py`:
- `start_run_async`: wrap `build_run_request` so `EmptyBriefError` → `HTTPException(400, str(exc))`.
- `PUT /settings` handler: before calling `update_settings`, if `payload.template_id == "freeform" and not payload.instructions_id`: raise `HTTPException(400, "Pick a template or an instruction profile — at least one is required.")`.

- [ ] **Step 4: Run to verify pass** — same -k freeform plus the route tests → PASS.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(eu-v2): optional freeform template + not-both-empty guard"
```

---

## Task 2: Frontend — rename Coverage → Watchlist

**Files:**
- Rename: `frontend/src/components/earnings-update/CoverageModal.tsx` → `WatchlistModal.tsx`
- Modify: `frontend/src/pages/departments/EarningsUpdate.tsx`
- Modify: `frontend/src/i18n/locales/en.json`, `zh-TW.json`
- Modify: `frontend/src/pages/departments/EarningsUpdate.test.tsx`

- [ ] **Step 1: Update the failing test first**

In `EarningsUpdate.test.tsx`, change the expectation `await screen.findByRole("button", { name: /coverage/i })` → `/watchlist/i`. Run it → FAIL.

- [ ] **Step 2: Rename component + references**

- `git mv` the file to `WatchlistModal.tsx`; rename the exported `CoverageModal` → `WatchlistModal` and its prop interface.
- In `EarningsUpdate.tsx`: update the import, `coverageOpen`→`watchlistOpen`, `setCoverageOpen`→`setWatchlistOpen`, `onOpenCoverage`→`onOpenWatchlist`, the `<WatchlistModal .../>` usage, and the button label `t("earnings.coverage")` → `t("earnings.watchlist")`.
- Grep for any remaining `Coverage`/`coverage` references in `earnings-update/` + `EarningsUpdate*` and update (e.g. `EuEmptyPage` `onOpenCoverage`).

- [ ] **Step 3: i18n — rename keys + values**

In both `en.json` and `zh-TW.json`: rename `earnings.coverage` → `earnings.watchlist` ("Watchlist" / "觀察清單"), and `earnings.coverage_modal` → `earnings.watchlist_modal` with values updated ("Coverage"→"Watchlist", "No tickers in coverage..." → "No tickers in your watchlist...", etc.). Update all `t("earnings.coverage*")` references to `earnings.watchlist*`.

- [ ] **Step 4: Verify**

`cd frontend && npx tsc --noEmit` clean; the renamed test passes; grep confirms no stray `coverage` keys remain. `npm run build` succeeds.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(eu-v2-fe): rename Coverage to Watchlist"
```

---

## Task 3: Frontend — optional template ("None — free structure") + save guard

**Files:**
- Modify: `frontend/src/components/earnings-update/ReportSettingsModal.tsx`
- Modify: `frontend/src/i18n/locales/en.json`, `zh-TW.json`
- Test: `frontend/src/components/earnings-update/__tests__/ReportSettingsModal.test.tsx`

Context: the modal has a template `<select>` bound to `draft.template_id` over `sortedTemplates`, and (from the instructions branch) an instructions picker exposing the selected `instructionsId` on `draft.instructions_id`.

- [ ] **Step 1: Write failing tests**

- Selecting template "None — free structure" (`value="freeform"`) with no instructions profile → Save button disabled + a visible "at least one is required" message.
- Same with an instructions profile selected → Save enabled.

Run → FAIL.

- [ ] **Step 2: Implement**

- Prepend a `<option value="freeform">{t("earnings.settings_modal.template_freeform")}</option>` to the template select (above `sortedTemplates`).
- When `draft.template_id === "freeform"`: hide the template delete button; show a hint (`template_freeform_hint`).
- Compute `bothEmpty = draft.template_id === "freeform" && !draft.instructions_id`. Disable Save when `bothEmpty`; render `t("earnings.settings_modal.both_empty_error")` inline near the actions when `bothEmpty`.
- `handleSave` already sends the full settings incl. `template_id` + `instructions_id`; no payload change needed beyond the guard.

- [ ] **Step 3: i18n**

Add to both locales under `earnings.settings_modal`: `template_freeform` ("None — free structure" / "無範本 — 自由結構"), `template_freeform_hint`, `both_empty_error` ("Pick a template or an instruction profile — at least one is required." + zh-TW). Verify key parity.

- [ ] **Step 4: Verify** — `npx tsc --noEmit` clean; tests pass; `npm run build` succeeds.

- [ ] **Step 5: Commit**

```bash
git add -A && git commit -m "feat(eu-v2-fe): optional freeform template + not-both-empty save guard"
```

---

## Final verification

- [ ] Backend: `uv run pytest packages/server/tests -k "eu_v2 or earnings_update_v2" -q` green; `ruff check`/`format` clean.
- [ ] Frontend: `cd frontend && npx tsc --noEmit && npm run build` clean; EU FE tests pass.
- [ ] Manual: settings modal — "None — free structure" with no instructions blocks Save; with instructions allows it; topbar reads "Watchlist".

## Non-goals
- Per-connector Data Sources routing (PR 2, separate design).
