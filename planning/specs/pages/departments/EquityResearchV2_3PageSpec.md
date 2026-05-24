# Equity Research Department Spec — v2.3

This spec defines the **v2.3** user interface for the Equity Research Department. v2.3 is built around the subagent-pipeline engine (`packages/core/src/openlia/llm/runtime/report_v2_3/`) merged via PR #156 and is the production surface going forward. The v1 spec at `EquityResearchPageSpec.md` is retained for historical reference only.

## What Changed From v1

| Dimension | v1 | v2.3 |
|---|---|---|
| Engine | Single-prompt LLM with framework templates | 9-stage subagent pipeline: CLARIFY → PLAN → RESEARCH → COMPUTE → SYNTHESIZE → WRITE → VISUALIZE → VERIFY → ASSEMBLE |
| Output | Markdown report rendered by `ReportFrameworks` | Structured `RunPayload` rendered by `<V23ReportView>` (React) and `v2_3_docx.py` (Word) from the same payload |
| Disambiguation | None (single prompt → report) | CLARIFY stage that may suspend the run for user answers |
| Citations | Inline links / none | Deterministic `[^N]` footnotes deduped across sections, resolved from `Provenance` |
| Charts | None / static images | `ChartSpec`s rendered as `<V23ChartSVG>` from real `BundleFact` numbers; figures auto-numbered |
| Valuation | LLM-written paragraphs | DCF / Comps / Sensitivity computed by `compute/valuation/` and surfaced as facts the WRITE stage cites |
| Models | Department-level model | Per-stage model assignments (`er_v2_3_model_assignments`); per-user overrides |
| Status | Polling, no per-stage progress | SSE stream (`POST /runs/stream`) yielding `stage_started` / `stage_completed` / `suspended` / `failed` / `completed` |
| Run shape | Anonymous chat session | First-class `Run` with `run_id`, persisted state, resumable via `?run_id=…`, listable via `GET /runs` |
| Export | PDF/DOCX from rendered markdown | `.docx` from `/runs/{id}/docx`; PDF via browser print on the React renderer (shared CSS, PR22) |

## Pipeline Stages — UI Surfaces

The user sees the pipeline as a single linear progress strip. Each stage maps to a label and an optional inline UX surface:

| Slot | Label | Inline UI when active | Terminal effect |
|---|---|---|---|
| `clarify` | Clarifying | Pending — may suspend to `WAITING_ON_USER` | If `needs_input`, opens Clarify modal |
| `plan` | Planning | Pending | Outline + valuation_plan persisted |
| `research` | Researching | Pending (shows ticker scope) | Bundle facts accumulate |
| `compute` | Computing valuation | Pending | DCF/Comps/Sensitivity facts added to bundle |
| `synthesize` | Synthesizing thesis | Pending | `Thesis` + `ChartSpec`s persisted |
| `write` | Writing sections | Pending | Section bodies with `[^N]` and `{{FIG:id}}` markers persisted |
| `visualize` | Validating charts | Pending | ChartSpecs validated against bundle facts |
| `verify` | Verifying | Pending — may retry `write` once on hard issues | `retry_count` increments visible |
| (assemble — deterministic) | Assembling | Implicit; no separate stage event | `ResolvedReport` ready; UI flips to `complete` |

The progress strip renders all stages in order with the active one highlighted and prior ones marked complete; failed runs show the failing stage in danger color.

## Run Lifecycle States

`RunStatus` from `report_v2_3/schemas.py` drives the entire surface:

| Status | Page behavior |
|---|---|
| `running` | Progress strip animates; input disabled; send → stop |
| `waiting_on_user` | Clarify modal mounted with `pending_questions` |
| `failed` | Error banner with `last_error`; "Restart" button |
| `complete` | Report card appears in chat; full report opens in viewer; `.docx` + Save buttons enabled |

## Page Layout

Two top-level states, identical to v1 in shape but adapted for v2.3 affordances.

### Welcome State

```
┌────────────────────────────────────────────────────────────────────┐
│  Equity Research                      [⚙ Engine] [⚙ Report Settings]│
│────────────────────────────────────────────────────────────────────│
│                                                                    │
│                      Equity Research                               │
│       Research companies, sectors, and market trends               │
│                                                                    │
│   ┌──────────────────────────────────────────────────────────┐    │
│   │  [AAPL]  [TSLA]  [NVDA]  [MSFT]  [From Portfolio ↗]      │    │
│   └──────────────────────────────────────────────────────────┘    │
│                                                                    │
│  ┌──────────────────────────────────────────────────────────┐     │
│  │  Tickers · Report type ▾ · Length ▾                      │     │
│  │ ────────────────────────────────────────────────────────  │     │
│  │  What should this report cover?                          │     │
│  │                                                  [Send]  │     │
│  └──────────────────────────────────────────────────────────┘     │
└────────────────────────────────────────────────────────────────────┘
```

### Active State

```
┌────────────────────────────────────────────────────────────────────┐
│  Equity Research                      [⚙ Engine] [⚙ Report Settings]│
│────────────────────────────────────────────────────────────────────│
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  [Scrollable chat: prompts + stage strip + report cards]   │   │
│  │                                                            │   │
│  │  ◯─◯─◉ Clarifying · Planning · Researching · …             │   │
│  │                                                            │   │
│  └────────────────────────────────────────────────────────────┘   │
│  ┌────────────────────────────────────────────────────────────┐   │
│  │  Ask a follow-up about the report…                  [Send] │   │
│  └────────────────────────────────────────────────────────────┘   │
└────────────────────────────────────────────────────────────────────┘
```

A collapsible **Run History** drawer on the left lists past runs from `GET /runs`, ordered newest first, with status badge + tickers + raw_prompt preview. Clicking a run re-attaches via `?run_id=<id>` and replays the conversation thread from persisted state.

## Page Header

| Element | Detail |
|---|---|
| Height / chrome | Same as v1: 56px, `flex-shrink-0`, bottom border |
| Title | "Equity Research" |
| **Engine** button | Opens **Engine Models** modal (`V23EngineModelsPicker`) for per-stage model assignment; warning dot when `clarify` slot is unset |
| **Report Settings** button | Opens **Report Settings** modal (mode, length, sections, custom sections) — same role as v1 |

## Composer (Input)

Pinned to bottom, replaces v1's plain textarea with a structured composer:

| Field | Detail |
|---|---|
| Tickers | Free text, parsed on `[,\s]+`, uppercased; min 1 (matches `StartPayload.tickers`) |
| Report type | Select: Initiation / Update / Morning Brief / Earnings Review (`ReportType` enum) |
| Length | Concise / Normal / Elaborative (passed via Report Settings, persisted per user) |
| Language | EN / ZH-TW (from user prefs, no field unless overridden) |
| Prompt | Multi-line textarea, 4 → 8 rows, Enter to send, Shift+Enter newline |
| Send | Disabled when `clarify` model not assigned; tooltip directs user to Engine modal |
| Stop | Replaces Send while `busy`; aborts the SSE stream and leaves the run in its current persisted state |

The composer is exactly one piece — no separate "ticker chips" row in the active state; chips are welcome-only.

## Stage Progress Strip

Rendered as an in-chat block beneath the latest user prompt while a run is `running` or `waiting_on_user`.

```
  Clarifying ─ Planning ─ Researching ─ Computing ─ Synthesizing ─ Writing ─ Visualizing ─ Verifying
     ●            ◯           ◯            ◯            ◯            ◯           ◯            ◯
```

| Element | Detail |
|---|---|
| Container | `bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-md px-4 py-3`; `max-w-[680px]` |
| Per-stage chip | Dot + label; states: `pending` (outline dot, muted), `active` (filled dot + pulse, primary), `complete` (check, success), `failed` (x, danger) |
| Retry indicator | When `retry_count > 0`, the WRITE/VERIFY stage shows "· retry 1" suffix |
| Source of truth | SSE events from `POST /runs/stream`; on reconnect or page reload, polls `GET /runs/{id}` once and reconstructs strip from `current_stage` |
| Fallback | If SSE fails or env-driven factory yields no observer, falls back to 1.5s polling until `complete` / `failed` |

## Clarify Modal

Triggered when SSE emits `event: suspended` for slot `clarify` or `GET /runs/{id}` returns `status: waiting_on_user`.

```
┌──────────────────────────────────────────────────────────┐
│  Quick check before I start                       [✕]   │
│──────────────────────────────────────────────────────────│
│  I need to confirm a couple of things for this report.   │
│                                                          │
│  1. Which fiscal year for the comp set?                  │
│     Why blocking: drives the Comps table baseline.       │
│     [ FY2025 (default)                              ]    │
│                                                          │
│  2. Should I include the recent SEC filing?              │
│     Why blocking: changes the risk section weighting.    │
│     [ Yes — include                                 ]    │
│                                                          │
│──────────────────────────────────────────────────────────│
│  [Use defaults]                       [Continue → ]      │
└──────────────────────────────────────────────────────────┘
```

| Element | Detail |
|---|---|
| Top-level | Mounted at page level, not inside the composer — blocks the chat |
| Question row | Question, `why_blocking` subtext, input prefilled with `default` |
| Submit | Calls `POST /runs/{id}/answer/stream` with `{ answers: { id: value } }`; empty values fall back to the question's `default` server-side |
| Use defaults | Sends an empty `answers` object — server fills with defaults |
| Cancel (`✕`) | Closes modal but **does not** cancel the run; user can reopen via the "Continue clarifying" pill on the stage strip |
| Persistence | Modal state is keyed by `run_id`; if user reloads, the modal reopens from persisted `pending_questions` |

## Report Card (in Chat)

Appears in the chat once `RunStatus.complete` is reached. Drawn from `RunPayloadOut`.

```
┌──────────────────────────────────────────────────────────────┐
│ [FileText]  Stock Initiation Report  · EN                    │
│             NVDA  ·  Apr 9, 2026                             │
│──────────────────────────────────────────────────────────────│
│ Central argument: Memory pricing is the dominant constraint  │
│ on AI infra margins through 2026; NVDA's HBM supply hedge…   │
│                                                              │
│ • DCF base $1,420 (12% upside)                               │
│ • 7 charts · 38 footnotes                                    │
│                                          [read more →]       │
│──────────────────────────────────────────────────────────────│
│ [Open Report]   [Download ▾]   [Save to Repo]                │
└──────────────────────────────────────────────────────────────┘
```

| Element | Detail |
|---|---|
| Title | Report type formatted: "Stock Initiation Report" / "Update" / "Morning Brief" / "Earnings Review"; language tag (EN / ZH-TW) |
| Subtitle | Tickers joined by `,`; created_at formatted `MMM D, YYYY` |
| Preview | First sentence of `payload.thesis.central_argument`; then up to 2 lines of bullet summary: top valuation figure + counts (charts, footnotes) |
| Open Report | Opens the report viewer (modal or route — see below) |
| Download dropdown | "Download as DOCX" → `GET /runs/{id}/docx` ; "Save as PDF" → opens report in viewer with print dialog pre-triggered |
| Save to Repo | Toggles bookmark via existing Repo APIs (`saveV23Run` / `unsaveV23Run` to be added; mirrors v2.2 pattern) |
| Source | `getV23RunPayload(run_id)` issued once and cached in chat context |

Failed runs render a **Failed Report Card** with `last_error`, the failing stage, and a "Restart from beginning" button (no resume-from-stage in v2.3 — the engine doesn't support mid-stage resume yet).

## Report Viewer

Opens full-screen when "Open Report" is clicked. The viewer wraps `<V23ReportView>` with chrome.

```
┌──────────────────────────────────────────────────────────────────────┐
│  ← Back            NVDA · Initiation · Apr 9, 2026     [Print] [.docx]│
│──────────────────────────────────────────────────────────────────────│
│  ┌───────────┐ ┌───────────────────────────────────────────────────┐ │
│  │ Outline   │ │  [Report cover: thesis · key takeaways · figures] │ │
│  │           │ │                                                   │ │
│  │ ○ Company │ │  ## Company Overview                              │ │
│  │ ○ Industry│ │  Lorem ipsum [^1]… {{FIG:fig_revenue_5y}}         │ │
│  │ ● Products│ │  ┌───────────────────┐                            │ │
│  │ ○ Business│ │  │ Figure 1: Revenue │                            │ │
│  │ …         │ │  └───────────────────┘                            │ │
│  │           │ │                                                   │ │
│  │           │ │  ## Valuation                                     │ │
│  │           │ │  ┌───────────────────────────────────────────┐    │ │
│  │           │ │  │ Method  │ Bear  │ Base   │ Bull   │ PT   │    │ │
│  │           │ │  │ DCF     │ $1,180│ $1,420 │ $1,650 │ +12% │    │ │
│  │           │ │  └───────────────────────────────────────────┘    │ │
│  │           │ │                                                   │ │
│  │           │ │  Footnotes                                        │ │
│  │           │ │  1. EODHD income statement, FY2025 10-K … [^1]    │ │
│  │           │ │  2. …                                             │ │
│  └───────────┘ └───────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────────┘
```

### Cover Page

Renders `payload.thesis`:

- `central_argument` — large heading
- `key_takeaways` — bulleted list
- `valuation_stance` — labelled paragraph
- `canonical_figures` — pill row, each pill is `<fact_id>: <display>`; clicking a pill jumps to the first section that cites the fact

### Sections

For each `payload.sections[i]`:

- `<h3>` with section title; anchor `#section-<id>`
- Body rendered from `payload.section_bodies[id]`:
  - Paragraphs split on blank lines
  - `[^N]` markers → `<sup><a href="#fn-N">[N]</a></sup>` (and reverse `↩` arrow in the footnote list)
  - `{{FIG:id}}` lone paragraph → `<V23ChartSVG>` with caption "Figure N: <title>" using `payload.figure_labels[id]`
  - `{{FIG:id}}` inline → small inline chart slot

### Valuation Breakout

When the run included `compute` and produced DCF/Comps/Sensitivity facts, render a dedicated **Valuation & Price Target** card above the relevant section:

| Method | Bear | Base | Bull | Implied PT | vs. Spot |
|---|---|---|---|---|---|
| DCF (2-stage) | … | … | … | … | … |
| Comps (median) | — | … | — | … | … |
| Sensitivity grid | (collapsible 2D table) |

Facts are pulled from `payload.bundle_facts` by id convention emitted by `compute/valuation/` (e.g. `dcf_base`, `comps_median_pt`, `sens_grid_<row>_<col>`).

### Footnotes

`payload.footnotes` rendered as a numbered list at the bottom with backlinks (`fn-N` anchor).

### Outline / TOC

Left rail shows section titles from `payload.sections`; active section highlighted via scroll-spy; clicking jumps to anchor.

### Print / PDF

The viewer's CSS includes the v2.3 print stylesheet (PR22). The **Print** button calls `window.print()`; `data-print-hide` chrome elements collapse and the report renders in print-safe styles. **Save as PDF** = the same flow; users use the OS print-to-PDF dialog. There is no separate server-side PDF rendering — the docx covers the editable export, the browser handles the read-only PDF.

### Open as Route vs Modal

The viewer mounts at `/equity-research?run_id=<id>&view=report`. Closing returns to the chat with the `run_id` still attached so the report card stays visible.

## Engine Models Modal

Opened via the **Engine** button. Wraps `<V23EngineModelsPicker>`. Lists the 7 LLM-driven slots (`clarify`, `plan`, `research`, `synthesize`, `write`, `verify`, plus any future LLM slot) — COMPUTE and VISUALIZE are deterministic and not listed. For each slot:

- Current assignment (provider + model_ref) or "Unassigned"
- Dropdown of available models from `SQLModelRegistry` (filtered to those with `structured_output` capability)
- Save persists via `POST /api/v2-3/models/assignments`

Warning banner if `clarify` is unassigned (engine cannot run at all). Side-banner explains: "Unassigned LLM slots fall back to a NoOp stub — the pipeline still produces a report, but those stages won't add real content."

## Report Settings Modal

Same shape as v1's Report Settings modal (mode + length + sections + custom sections), with two changes:

1. **Mode** options: Initiation / Update / Morning Brief / Earnings Review / Sector Research. The mode determines the default outline the PLAN stage proposes — PLAN may still adjust based on the prompt.
2. **Sections list** is informational only in v2.3: the PLAN stage owns the outline and may add or drop sections per the prompt. The settings list expresses user preferences; the engine treats them as defaults, not hard constraints. A subtitle reads: "Defaults — the planner may adjust based on your prompt."

## Run History Drawer

| Element | Detail |
|---|---|
| Trigger | Sidebar icon in main app sidebar; also accessible via "History" link in Welcome state |
| Source | `GET /api/departments/equity-research/v2.3/runs?limit=50` |
| Row | Status dot + tickers (joined) + 1-line raw_prompt preview + `created_at` (relative time) |
| Actions | Click → load run into chat; right-click / overflow → Delete (`DELETE /runs/{id}`) |
| Filters | Status pill row: All / Running / Waiting / Failed / Complete |
| Empty state | "No runs yet. Start one from the composer." |

## SSE vs Polling

| Path | When |
|---|---|
| `streamV23Run` (POST `/runs/stream`) | Initial start; primary path |
| `streamV23Answer` (POST `/runs/{id}/answer/stream`) | After clarify modal submit |
| Polling `GET /runs/{id}` every 1.5s | Fallback when SSE errors, or on page reload of a `running` run (no live SSE stream to re-attach) |
| `GET /runs/{id}/payload` | Once on `complete` to hydrate report card and viewer |
| `GET /runs/{id}/docx` | On download click |

Aborting an in-flight SSE on send / page navigation is required (`streamRef.abort()` in `V23Composer.tsx:67-72`).

## States

| State | Visual |
|---|---|
| Welcome | Centered heading + chips; composer prefilled empty |
| Running | Progress strip in chat; composer disabled; Stop button visible |
| WaitingOnUser | Progress strip with `clarify` pulsing in warning color; Clarify modal mounted |
| Complete | Stage strip collapses to "Done · 8 stages · 4.2s" summary pill; report card appears; composer becomes follow-up mode |
| Failed | Stage strip shows failing stage in danger color; error banner with `last_error`; Restart button |
| Reattached | URL has `?run_id=<id>`; chat restored from persisted state; if status is `running`, polling kicks in |

## Responsive

| Breakpoint | Behavior |
|---|---|
| Desktop (>1024px) | Chat `max-w-[760px]`; Run History drawer pinned left; Report Viewer at full width with TOC rail |
| Tablet (768–1024px) | Drawer collapses to overlay; Report Viewer TOC collapses to a top dropdown |
| Mobile (<768px) | Stage strip compresses to "Stage 4 of 8 · Researching"; viewer is single-column; Engine/Report Settings open as bottom sheets |

## Endpoints Consumed

| UI surface | Method · Path |
|---|---|
| Send | `POST /api/departments/equity-research/v2.3/runs/stream` |
| Clarify submit | `POST /api/departments/equity-research/v2.3/runs/{id}/answer/stream` |
| Reattach run | `GET /api/departments/equity-research/v2.3/runs/{id}` |
| Run history | `GET /api/departments/equity-research/v2.3/runs?limit=50` |
| Delete run | `DELETE /api/departments/equity-research/v2.3/runs/{id}` |
| Report viewer hydrate | `GET /api/departments/equity-research/v2.3/runs/{id}/payload` |
| DOCX download | `GET /api/departments/equity-research/v2.3/runs/{id}/docx` |
| Engine models read | `GET /api/v2-3/models/assignments` |
| Engine models write | `POST /api/v2-3/models/assignments` |

## Out of Scope for v2.3 UI

- Mid-stage resume (engine doesn't expose it)
- Per-stage retry from a specific failure point
- Live token-stream of WRITE prose (the engine produces sections atomically per `WriteResult`)
- Side-by-side comparative multi-ticker layout (multi-ticker reports render as a single composed report; comparative view is a future PR)
- Server-side PDF rendering (browser print handles it)

## Implementation PR Sequence

Each PR is a single vertical slice; the gap audit (chat 2026-05-23) is the source. Sequence on `feat/equity-research-v2.3-ui`:

1. **PR1 (this doc)** — v2.3 UI spec
2. **PR2** — Page wiring: replace hidden preview toggle with v2.3 as the default surface; session/`?run_id=` reattach; history persistence
3. **PR3** — SSE consumer + Stage Progress Strip; polling fallback
4. **PR4** — Report card in chat + Report Viewer (full-screen route) with cover page, sections, footnotes, charts
5. **PR5** — Valuation breakout card + Outline rail + print stylesheet integration
6. **PR6** — Clarify modal at page level (lift out of composer) + run history drawer
7. **PR7** — Engine Models modal + Report Settings modal refresh for v2.3 semantics
8. **PR8** — Save/unsave to Repo + Failed report card + Restart from beginning
