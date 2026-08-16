# Equity Research (v3) Page Spec

> **Status:** SHIPPED. v3 is the **sole** equity-research engine (per CLAUDE.md § *Equity Research Engine*). This spec documents the shipped v3 page as built; it supersedes `EquityResearchPageSpec.md` and `EquityResearchV2_3PageSpec.md`, which describe the removed v1/v2.x surfaces.
>
> **Grounded in shipped code:** `frontend/src/pages/departments/EquityResearchV3.tsx`, `frontend/src/components/equity-research-v3/*`, `frontend/src/components/equity-research/{WelcomeStage,ErComposer}.tsx`, `frontend/src/router/routes.tsx` (route `/equity-research` → `EquityResearchV3`), and the design spec `planning/2026-05-27-equity-research-v3-single-model-spec.md`.

## Page Overview

The Equity Research page runs the v3 **single-model tool-use engine**: one LLM session, one tool loop, one final structured emit (see the design spec § *Architecture*). The page deliberately reuses the v1/v2 equity-research chrome — a centered `WelcomeStage` greeting on first load and a bottom-pinned free-form `ErComposer` — so it looks and feels like the earlier surfaces while dispatching to the v3 SSE run API.

The page is mounted at `/equity-research`. It has **no chat-session model**: each submission produces one report ("run"); runs are the unit of history. A completed run can be **revised** in place through follow-up prompts.

Key differences from the legacy surface:
- **Free-form composer, no ticker form.** The composer is a single textarea. The v3 `subject` is "either a ticker (RKLB.US) or a free-form topic" — whatever the user types is passed straight through as the subject. There is no separate ticker field and no clarify stage.
- **Template + instruction profile drive the report shape**, chosen in a Report Settings modal, not a config form.
- **Model is chosen inline** via a single-slot model-picker pill in the composer toolbar.

## Page Functionalities

1. **Free-form prompt composer** — a single-textarea `ErComposer` pinned to the bottom. Enter submits; Shift+Enter inserts a newline. Supports file attachments (drag/click paperclip; client-validated against the same MIME allowlist and 25 MB / 10-file caps as the server). Attachments are allowed on an original run but **not** on a revision.
2. **Model-picker pill** — `V3ModelPicker` in the composer toolbar. Lists enabled models from `getEnabledModels()`, grouped by provider kind (Radix dropdown, `Cpu` icon). The chosen model is persisted in `localStorage["er.v3.model_id"]`; it is passed as `provider_kind` + `model` on the run payload (v3 does not write `user_prefs`). When no model is enabled it renders a warning pill linking to `/settings/models`.
3. **Report Settings modal** — `V3ReportSettingsModal`, opened from the `WelcomeStage` mode-row pill or the composer mode pill. Controls: **Length** (Concise / Normal / Elaborative), **Language** (English / 繁體中文), **Reasoning effort** (Off / Medium / High — Off keeps the run lean; Medium/High enable extended thinking on supported models), **Template** picker, **Instructions** picker. Settings are staged locally and applied only on Save; they persist in `localStorage["er.v3.settings"]`.
4. **Template picker + upload** — inside the settings modal. Lists built-in templates (`is_builtin`, e.g. "Stock Initiation" / `initiation_default`) and user-uploaded templates, plus a **"No template"** option (the `FREEFORM_TEMPLATE_ID` sentinel — instructions-only, the analyst designs the structure). Uploaded templates can be deleted. "Upload" opens `V3TemplateUploadModal`; a successful upload auto-selects the new template and reopens settings.
5. **Instruction-profile picker + upload** — standing free-form methodology guidance for the analyst. Lists saved profiles plus **None**. Optional in general, but **required** when "No template" is selected (a freeform run has no shape without a profile; Save is blocked and an inline error is shown). "Upload" opens `V3InstructionsUploadModal`; a successful upload auto-selects the new profile.
6. **Run dispatch (SSE)** — Submit calls `POST /v3/runs/start` (`startV3RunAsync`) with `{subject, language, length, template_id, instructions_id, provider_kind, model, reasoning_effort}` and returns a `report_id`. `useV3RunStream` opens an `EventSource` on `/v3/runs/{id}/events`.
7. **Live generation view** — while streaming, the `V3ReportCard` shows a `V3GeneratingCockpit` (phase line + spinner + **indeterminate** progress sweep — v3 is adaptive and does not pre-declare a section count) above a `V3ActivityFeed` of events. A live meta row counts sections / charts / sources / elapsed seconds. A Stop button cancels the run (`cancelV3Run`).
8. **Runs history popover** — `V3RunsPopover` is plugged into the global TopBar chat-header via `useChatHeaderRegistry`'s `renderPopover` slot (department id `equity_research_v3`). It lists prior runs (`listV3Runs`) with search; each row maps to a `report_id` and shows subject + status + created date. Capabilities are select + delete only (no pin/archive/rename). Deleting the active run clears the page.
9. **Revisions** — once a run is completed, the composer switches to "Ask a follow-up or describe a revision…". Submitting calls `startV3Revision(reportId, {request})`. `V3ChatThread` polls `listV3Revisions` and calls `refreshDetail` when the latest revision lands terminal. Only one revision may be in flight (a 409 surfaces "Another revision is already in flight"). The report card pill flips to "Revising…" while a revision runs.
10. **Report card + export + save-to-repo** — on completion, `V3ReportCard` (ready phase) shows the report subject, a template + date meta line, a "Ready" pill, a 3-line preview with **Read more** (opens the report in the `FileViewer`), and an action row:
    - **Open report** — opens the rendered report in the `FileViewer` panel (source `{kind: "v3_report", reportId}`), or a new tab if no FileViewer is mounted.
    - **Download** — `ReportDownloadButton` (`engine="v3"`) downloads the report; format menu offers **PDF** and **DOCX** (DOCX gated by `docxEnabled()`).
    - **Save to Repo** — `SaveToRepoButton` (`engine="v3"`) toggles the report into the Repository.
    - **Standalone** — an `ExternalLink` to the printable HTML (`v3HtmlUrl`) in a new tab; tooltip notes the browser's "Save As" grabs a Word or PDF copy.
11. **Deep-linking** — the active run id is mirrored to the URL as `?id=<report_id>` (replace). Loading the page with `?id=` reconnects to that run (late-connect uses a `run.snapshot` event); the runs popover highlights the matching row.

## Page Design

### Shell

- Full-height flex column on `--color-bg-base`. A scrollable content region fills the middle; the `ErComposer` is pinned at the bottom (`flex-shrink-0`, top border).
- **Welcome state** (`activeReportId === null && detail === null && !streaming`): renders `WelcomeStage` — an accent `TrendingUp` glyph, a time-of-day greeting with the user's first name, a rotating headline, a subtitle, and a mode-row pill (`Template · Length`) that opens the Report Settings modal. In v3 the pill's left half shows the active **template name** (or the instruction-profile name for a no-template run) via the `templateLabel` override.
- **Run state**: renders `V3ChatThread` — the initial prompt as a chat message with setting chips (template, length, language, reasoning effort, model), followed by the `V3ReportCard` (generating → ready) and the revision thread.

### Composer (`ErComposer`, single-textarea mode)

| Element | Detail |
|---|---|
| Textarea | One auto-growing textarea (max 120px). Placeholder is context-aware: welcome → "What should this report cover? (e.g., …)"; revisable → "Ask a follow-up or describe a revision…"; streaming → "Run in progress…"; revision in flight → "Revision in flight…". |
| Attach | Paperclip button; client-side MIME/size validation; pending files render as removable chips. |
| Mode pill | Shows `Template · Length` (template label overrides the report-type label); pulses and reads "Generating" while streaming; opens the settings modal. |
| Model pill | `V3ModelPicker` (see functionalities). |
| Send / Stop | Send (`ArrowUp`) dispatches; while streaming a Stop (`Square`) button cancels. |
| Disabled | Locked when no model is selected on a fresh run, while a revision is in flight, or while the initial run streams (and no revision is possible). |

### Report Settings modal (`V3ReportSettingsModal`)

Radix dialog, `max-w-[520px]`, titled "Report settings" with a "v3 engine" tag. Sections in order: Length (segmented), Language (segmented), Reasoning effort (segmented + explainer), Template (No-template option + list, per-row built-in/uploaded tag, delete for uploads, Upload button), Instructions (None option + list, delete, Upload button, freeform-needs-instructions inline error). Footer: Cancel / Save. Save is disabled when "No template" is selected without a profile.

### Generating card (`V3ReportCard` generating phase + `V3GeneratingCockpit`)

Scan-line animation across the card top while streaming; header with a `FileText` glyph, subject, template + date, and a status pill (Generating / Finalizing / Failed / Cancelled). Cockpit phase line derives from the most recent meaningful event (Researching / Analyzing results / Drafting section / Building chart / Initializing). Indeterminate sweep progress bar. Below: the activity feed of streamed events.

## States

| State | Description |
|---|---|
| **Welcome** | No active run; `WelcomeStage` centered; composer awaiting a prompt. |
| **Streaming** | `V3ReportCard` generating; cockpit + activity feed live; Stop available; composer locked. |
| **Ready** | Persisted `detail` rendered; report card with preview + actions; composer switches to revision mode. |
| **Revising** | Revision in flight; card pill shows "Revising…"; composer shows "Revision in flight…". |
| **Failed / Cancelled** | Terminal pill + message; the run stays in history. |
| **No model** | Model pill shows a warning linking to `/settings/models`; submit blocked with an inline error. |
| **Engine disabled (503)** | Start / template-list calls return 503; error banner: "v3 engine disabled on the server." (Note: per CLAUDE.md the engine is now always on; this is a defensive path.) |

## Error / Feedback Messages

- Empty prompt → "Tell the engine what to research."
- No model on a fresh run → "No model selected. Configure one in Settings → Models."
- No-template run without a profile → "No template selected. Pick an instruction profile in Settings, or choose a template."
- Attachments on a revision → "Source files aren't supported on revisions yet — start a new report to attach documents."
- Concurrent revision (409) → "Another revision is already in flight."
- Stream drop → "Event stream dropped — refresh to reload the run state."

## Persistence

| Key | Contents |
|---|---|
| `localStorage["er.v3.settings"]` | Length, language, reasoning effort, template id/name, instructions id/name. |
| `localStorage["er.v3.model_id"]` | Selected roster entry id (resolved to `provider_kind` + `model` at dispatch). |
| URL `?id=<report_id>` | The active run, for deep-linking and reconnect. |

## Report Framework

v3 produces one HTML/PDF/DOCX report per run. Report content is emitted only through the engine's output tools (`add_section`, `emit_chart`); citations resolve against a server-side tool-call ledger. Templates supply the section skeleton; instruction profiles supply free-form methodology. See `planning/2026-05-27-equity-research-v3-single-model-spec.md` for the tool catalog, citation mechanism, and chart rendering.

## Configurations

- **LLM:** chosen inline via the model-picker pill (any enabled roster model with the required native-web-search capability). Reasoning effort per the settings modal.
- **Data/tools:** server-executed function tools (EODHD fundamentals, DCF/Comps/sensitivity) plus provider-native web search; see the design spec.
