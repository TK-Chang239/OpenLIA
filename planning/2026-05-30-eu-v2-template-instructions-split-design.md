# EU v2 — Watchlist rename + Template/Instructions separation — Design

**Date:** 2026-05-30
**Branch:** `feat/eu-v2-template-split` (stacks on `feat/eu-v2-instructions`, PR #216)
**Status:** Approved design (decomposed from a 3-fix batch; this is "PR 1". "PR 2" = full per-connector routing, separate design.)

## Scope

Two independent changes bundled into one small PR:

1. **Rename "Coverage" → "Watchlist"** (UI label + component).
2. **Draw a clear line between Template and Instructions**, making each independently optional but **never both empty**.

Out of scope (separate effort): per-connector Data Sources routing.

## 1. Coverage → Watchlist

"Coverage" is the ticker-tracking list (topbar button + `CoverageModal` + empty-state CTA). Purely a naming change.

- Frontend: `CoverageModal.tsx` → `WatchlistModal.tsx` (component + props/handlers renamed for clarity: `coverageOpen`→`watchlistOpen`, `onOpenCoverage`→`onOpenWatchlist`, etc.); the topbar button and empty-state wiring in `EarningsUpdate.tsx`.
- i18n: rename the value of `earnings.coverage` → "Watchlist" and the `earnings.coverage_modal.*` strings, in both `en.json` and `zh-TW.json`. Key names may stay `coverage*` (cheap) **or** be renamed to `watchlist*` for clarity — plan renames keys to `watchlist*` and updates references (one source of truth).
- Test: `EarningsUpdate.test.tsx` references `/coverage/i` → update to `/watchlist/i`.

No backend change (the underlying table is already `eu_v2_watchlist`).

## 2. Template ⇄ Instructions

### Contract (the line)

- **Template** = a *forced output schema*: the ordered sections the LLM must produce (one `write_section` per section id). Structure only.
- **Instructions** = the *free-form prompt/methodology* injected into the system prompt as authoritative guidance (already implemented on the instructions branch).
- They **compose**. Valid combinations:
  | Template | Instructions | Result |
  | --- | --- | --- |
  | set | empty | forced schema, default methodology |
  | empty (freeform) | set | model designs its own sections, guided by the instructions |
  | set | set | forced schema + instructions methodology |
  | **empty** | **empty** | **rejected** — nothing to run |

### Making the template optional

Mirror v3's freeform mechanism (`equity_research_v3.py:90` `FREEFORM_TEMPLATE_ID = "freeform"`, `_freeform_template_spec()` builds an empty-`sections` `TemplateSpec` via `model_construct`).

- Add `EU_FREEFORM_TEMPLATE_ID = "freeform"` + an `_eu_freeform_template_spec()` helper (empty sections, `ticker_anchored=True`, a neutral `shape_description`).
- `eu_v2_run_service.build_run_request`: when `settings.template_id == "freeform"`, use the freeform spec instead of `resolve_template(...)`. The engine prompt already renders the freeform structure directive when `sections` is empty (`report_eu/prompts.py:_render_structure_block`), so no engine change is needed.

### The "not both empty" guard

A run is freeform-and-instructionless iff `template_id == "freeform"` **and** `instructions_id is None`. Reject that state at three layers:

1. **Settings save** (`PUT /settings`): 400 with a clear message when `template_id == "freeform"` and `instructions_id` is null. (Validation in the route or settings service.)
2. **Run start** (`build_run_request` / `runs/start`): defensive guard — if a run is assembled with a freeform template and no resolved instructions text, raise a 400-mapped error rather than dispatching an empty-brief run. Covers the case where instructions were deleted after selection.
3. **Frontend** (settings modal): when the template picker is on "None — free structure" and no instructions profile is selected, disable Save and show an inline message ("Pick a template or an instruction profile — at least one is required.").

### Frontend

In `ReportSettingsModal.tsx`:
- Template picker `<select>` gains a first option **"None — free structure"** (value = `"freeform"`) above the built-in/user templates.
- When `draft.template_id === "freeform"`: hide/disable the template delete button (nothing to delete) and surface the freeform meaning ("The model designs its own sections; your instructions drive the report").
- Save-enable rule: block when `template_id === "freeform" && !instructionsId` (ties into the instructions picker already on this modal).
- i18n keys for the new option label + the not-both-empty message (en + zh-TW).

## Testing

**Backend**
- `build_run_request`: `template_id="freeform"` + an instructions profile → `RunRequest.template.sections == []` and `.instructions` set; `template_id="eu_default"` + no instructions → normal template, `.instructions is None`.
- Guard: `template_id="freeform"` + `instructions_id=None` → run-start raises the mapped error; settings-save → 400.
- Existing templated runs unaffected.

**Frontend**
- Template picker shows "None — free structure"; selecting it with no instructions disables Save with the message; selecting it **with** an instructions profile enables Save.
- Watchlist: topbar button reads "Watchlist", modal title "Watchlist", test matches `/watchlist/i`.

## Non-goals

- Per-connector Data Sources routing (PR 2).
- Per-run overrides (settings stay per-user).
- Seeding built-in instruction profiles.
- Changing what a template *is* (still the v2.3 `TemplateSpec`).
