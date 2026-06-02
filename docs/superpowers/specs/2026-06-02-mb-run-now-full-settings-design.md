# Morning Briefing — Run Now Full Settings + Remembered Choices

Date: 2026-06-02
Status: Approved (pending spec review)

## Problem

The Morning Briefing "Run now" modal only lets the user either run ad-hoc with
hardcoded library defaults, or pick a saved schedule and reuse its bound config.
It exposes none of the per-run settings (model, template, instructions,
connectors, length, language, reasoning). The user wants Run Now to offer the
full settings — the same controls a schedule has — and to remember the choices
from the previous Run Now so each run starts where the last one left off.

## Decisions

1. **Full form only.** Remove the schedule-picker dropdown entirely. Run Now
   becomes a pure ad-hoc config form with all settings controls. (No "use a
   schedule" path inside Run Now; schedules keep their own editor.)
2. **Remember previous choices via `localStorage`.** Prefill the form from the
   user's last Run Now submission. "Previous run" = the last config actually
   submitted via Run Now (per browser). Falls back to library defaults when no
   prior Run Now config exists. This mirrors the existing per-component
   `localStorage` persistence pattern (`MbModelPicker` → `mb.model_id`, etc.)
   and the standing "inherit session defaults from last session" preference.
3. **Approach A — extract a shared `MbConfigFields` component.** The 7 config
   controls already live inside `ScheduleEditorModal`. Lift them into one
   reusable component consumed by both the schedule editor and the new Run Now
   form, rather than duplicating ~400 lines of control markup.

## Scope

Frontend only. No backend route, schema, ORM, or migration change. The
`POST /runs/start` ad-hoc path and `MbRunStartIn` already accept every field
(`template_id`, `instructions_id`, `enabled_connectors`, `provider_kind`,
`model`, `language`, `length`, `reasoning_effort`).

## Components

### New: `frontend/src/components/morning-briefing/MbConfigFields.tsx`

The config portion lifted verbatim from `ScheduleEditorModal`:

- Sections: Model (`MbModelPicker`), Template (select + upload/delete),
  Instructions (select + upload/delete), Connectors (data-source toggles),
  Length, Language, Reasoning (Anthropic-only).
- Owns the hooks `useMbTemplates`, `useMbInstructions`, `useMbDataSources`.
- Owns the handlers `handleModel`, `handleUploadMarkdown`, `handleUploadFile`,
  `handleDeleteTemplate`, `handleUploadInstructions`, `handleDeleteInstructions`,
  `sourceEnabled`, `toggleSource`, `reasonText`, `categoryLabel`, `renderSource`,
  and the `MbTemplateUploadModal` / `MbInstructionsUploadModal` sub-modals.
- Props:
  - `draft: MbConfigDraft` — the config slice (template_id, instructions_id,
    provider_ids, web_search, provider_kind, model, language, length,
    reasoning_effort).
  - `onChange: (patch: Partial<MbConfigDraft>) => void` — patcher the parent
    uses to update its own draft state.
- Passes `draft.{provider_kind, model}` to `MbModelPicker` as `value` so the
  stored model is authoritative.
- Reuses the existing `morning_briefing.schedule_editor.*` i18n keys (shared
  copy across both modals).
- Preserves every existing `data-testid` (`mb-template-select`,
  `mb-instructions-select`, `mb-connector-*`, `mb-language-select`,
  `mb-reasoning-select`, `mb-template-upload-open`, etc.) so schedule-editor
  tests stay green.
- Exports `isBriefEmpty(draft): boolean` — `template_id === "freeform" &&
  !instructions_id`. Both modals use it to gate their submit button.

### Changed: `frontend/src/components/morning-briefing/ScheduleEditorModal.tsx`

- Keeps the Timing section (time, timezone, days_of_week, label, is_enabled),
  the `noDays` validation, and the Save/Cancel footer.
- Replaces its inline Model/Template/Instructions/Connectors/Length/Language/
  Reasoning markup with `<MbConfigFields draft={configSlice} onChange={...} />`.
- `bothEmpty` now derived via the exported `isBriefEmpty(...)`.
- Behavior unchanged; the schedule create/edit payload is identical.

### Rewritten: `frontend/src/components/morning-briefing/MbRunNowModal.tsx`

- Adopts the schedule-editor chrome: 560px Radix dialog, header / scrollable
  body (`max-h-85vh`) / footer.
- Drops the `schedules` prop and the schedule dropdown.
- Props: `{ open, onClose, onStarted(reportId) }`.
- Draft state initialized by `loadRunNowDraft()`:
  - Read `localStorage["mb.run_now.last_config"]`, JSON-parse inside try/catch.
  - If present and parseable, use it.
  - Else library defaults: `template_id="mb_default"`, `instructions_id=null`,
    `provider_ids=[]`, `web_search=false`, `provider_kind=null`, `model=null`,
    `language="en"`, `length="normal"`, `reasoning_effort=null`.
  - The library default (`mb_default`, a builtin template) is a valid runnable
    state, so Generate is enabled immediately on first use.
- Body = `<MbConfigFields draft={draft} onChange={patch}/>`.
- Footer: Cancel + Generate. Generate disabled when `isBriefEmpty(draft)` or
  while submitting.
- On Generate:
  1. Build `MbRunStartIn` (no `schedule_id`): `{ template_id, instructions_id,
     enabled_connectors: { provider_ids, web_search }, provider_kind ?? undefined,
     model ?? undefined, language, length, reasoning_effort }`.
  2. `await startMbRun(payload)`.
  3. On success, `saveRunNowDraft(draft)` → write the submitted config to
     `localStorage["mb.run_now.last_config"]`, then `onStarted(report_id)` and
     `onClose()`.
  4. On error, surface the message in the modal (existing `err` state).

### Changed: `frontend/src/pages/departments/MorningBriefing.tsx`

- Drop the `schedules={...}` prop on `<MbRunNowModal/>`. No other change; the
  page still owns `liveReportId` via `onStarted`.

## Data Flow

```
Run Now click → modal opens
  → loadRunNowDraft(): localStorage["mb.run_now.last_config"] OR library defaults
  → MbConfigFields renders controls bound to draft
  → user tweaks (onChange patches draft)
  → Generate:
       startMbRun({ ...config, no schedule_id })   [POST /runs/start ad-hoc path]
       → saveRunNowDraft(draft)                     [persist for next time]
       → onStarted(report_id)                        [page streams live card]
```

The backend ad-hoc branch (`schedule_id is None`) consumes the payload exactly
as today and calls `build_run_request(trigger_kind="on_demand", ...)`.

## i18n

- `MbConfigFields` reuses existing `morning_briefing.schedule_editor.*` keys.
- Remove now-dead `morning_briefing.run_now_modal.schedule_label` and
  `morning_briefing.run_now_modal.schedule_adhoc`.
- Update `morning_briefing.run_now_modal.title` / `.description` to
  configure-and-run wording. Keep `.cancel`, `.generate`, `.starting`,
  `.failed`. Update both `en` and `zh-Hant`.

## Testing

- Rewrite the Run Now modal test:
  - Renders the full config controls (model/template/instructions/connectors/
    length/language/reasoning); no schedule dropdown.
  - Default (first-use) state is runnable → Generate enabled.
  - Selecting freeform + no instructions disables Generate (`isBriefEmpty`).
  - Generate posts an ad-hoc payload (no `schedule_id`) and calls `onStarted`.
  - After a successful Generate, `localStorage["mb.run_now.last_config"]` holds
    the submitted config; reopening prefills from it.
- Schedule-editor tests unchanged (testids preserved).
- `cd frontend && npm run build` for TypeScript typecheck.
- `uv run pytest` as a sanity pass (backend untouched).

## Non-Goals / Out of Scope

- No server-side / cross-device persistence of the last Run Now config.
- No inheritance from scheduled runs or from runs started on another browser.
- No new persistence of `enabled_connectors` on the `report_mb` run row.
- No change to schedule create/edit behavior or payload.

## Risks

- The `MbConfigFields` extraction touches a working 862-line component. Mitigate
  by lifting markup verbatim and preserving all `data-testid`s; schedule-editor
  tests are the regression guard.
- `MbModelPicker` self-persists `mb.model_id` on change. Passing the stored
  `value` makes the Run Now draft authoritative; the picker's own key is
  harmless redundancy.
