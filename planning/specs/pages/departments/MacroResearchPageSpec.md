# Macro Research Department Spec

## Page Overview
The Macro Research Department (MR) generates comprehensive research reports on macroeconomic topics. The user prompts MR with a research question or topic — such as monetary policy, inflation trends, GDP forecasts, geopolitical risks, or currency markets — and MR returns a structured analysis report. MR also functions as an LLM chatbot for follow-up questions on any generated report or new macro topic.

## Functions
1. **Macro Research Report**: MR generates a comprehensive macro research report based on the user's prompt. Reports follow the MR report framework.
2. **LLM Chatbot**: MR operates as an LLM chatbot, supporting follow-up questions and clarifications on generated reports or on new macro research questions.
3. **Save Reports**: After a report is generated, the user can save it to the Repository or download it as PDF or DOCX.
4. **Report Preview**: Generated reports appear as a thumbnail card in the chat. Clicking the card opens the report in the FileViewer panel.

---

## User Interface Design

### Layout

MR uses a full-height chat interface. There are two states: **Welcome** (no active conversation) and **Active** (conversation in progress).

**Welcome State:**

```
┌────────────────────────────────────────────────────────────────┐
│  Macro Research                           [⚙ Report Settings]  │
│────────────────────────────────────────────────────────────────│
│                                                                │
│                                                                │
│                     Macro Research                             │
│          Research macroeconomic trends and market forces       │
│                                                                │
│   ┌───────────────────────────────────────────────────────┐   │
│   │ [Fed Policy & Rates] [Inflation Outlook] [Global GDP] │   │
│   │                             [FX & Currency Markets]   │   │
│   └───────────────────────────────────────────────────────┘   │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  Ask a macro question or describe a research topic...    │ │
│  │                                                  [Send]  │ │
│  └──────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────┘
```

**Active State:**

```
┌────────────────────────────────────────────────────────────────┐
│  Macro Research                           [⚙ Report Settings]  │
│────────────────────────────────────────────────────────────────│
│  ┌──────────────────────────────────────────────────────────┐ │
│  │                                                          │ │
│  │        [Scrollable chat: messages + report cards]        │ │
│  │                                                          │ │
│  └──────────────────────────────────────────────────────────┘ │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  Ask a follow-up question...                     [Send]  │ │
│  └──────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────┘
```

---

### Page Header

| Element | Detail |
|---|---|
| Height | 56px (`h-14`), `flex-shrink-0` — does not scroll with chat content |
| Background | `--color-bg-base` |
| Border | 1px bottom, `--color-border-subtle` |
| Page title | "Macro Research" — `text-xl font-semibold text-[--color-text-primary]`, left-aligned, `pl-6` |
| Report Settings button | Right of header, `pr-6`; `Settings` icon (16px) + "Report Settings" label; `text-sm text-[--color-text-secondary]`; border outline style: `border border-[--color-border-secondary] rounded-[--radius-md] px-3 h-8`; hover: `bg-[--color-surface-hover] text-[--color-text-primary]`; transition `--duration-fast`; opens Report Settings modal |

---

### Welcome State

Shown when there is no active conversation. Centered vertically in the content area between the header and input.

| Element | Detail |
|---|---|
| Heading | "Macro Research" — `text-2xl font-semibold text-[--color-text-primary]`, horizontally centered |
| Sub-text | "Research macroeconomic trends and market forces" — `text-md text-[--color-text-secondary]`, centered, `mt-2` |
| Suggestion chips | Horizontal wrapping row of 4 prompt chips: "Fed Policy & Rates", "Inflation Outlook", "Global GDP Trends", "FX & Currency Markets". Clicking a chip populates the input and submits it immediately |
| Chip style | `px-3.5 py-2 rounded-full border border-[--color-border-secondary] text-sm text-[--color-text-secondary]`; hover: `bg-[--color-surface-hover] text-[--color-text-primary] border-[--color-border-subtle]`; transition `--duration-fast` |
| Chips container | `flex flex-wrap gap-2 justify-center mt-8 max-w-[520px] mx-auto` |
| Entry animation | Heading + sub-text: `opacity 0→1, y 12→0, duration 250ms`; chips stagger in `40ms` apart after heading resolves |
| Exit animation | Entire welcome block: `opacity 1→0, y 0→-8, duration 200ms` before chat area enters |

---

### Chat Message Area

Replaces the welcome content once a conversation starts. Scrolls independently within the content area.

| Element | Detail |
|---|---|
| Container | `flex-1 overflow-y-auto px-6 py-6` |
| Content max-width | `max-w-[680px] mx-auto` (matches `--max-width-chat`) |
| User messages | Right-aligned bubble: `rounded-2xl rounded-br-sm px-4 py-2.5 bg-[--color-surface-active] text-[--color-text-primary] text-md`; `max-w-[72%]`; `whitespace-pre-wrap` |
| Assistant messages | Left-aligned, no bubble, no background: `text-md text-[--color-text-primary] leading-relaxed`; full width up to chat max-width; markdown rendered (bold, bullet lists, numbered lists, tables, inline code, code blocks) |
| Timestamps | Hidden by default. On hover of a message group, a timestamp fades in below: `text-xs text-[--color-text-tertiary]`; fade: `opacity 0→1, --duration-fast` |
| Streaming text | Token-by-token reveal; a blinking cursor (`▌`, `--color-text-tertiary`, 800ms blink cycle) follows the last character until streaming completes |
| Loading indicator | While awaiting first token: three animated dots in a row, each `w-1.5 h-1.5 rounded-full bg-[--color-text-tertiary]`; opacity oscillates `0.3→1→0.3` over 1.2s, staggered `200ms` between dots |
| Message entry | Each new message: `opacity 0→1, y 8→0, duration 200ms, ease-out` |
| Between-message gap | `space-y-6` |

---

### Report Thumbnail Card

When MR completes a report, it appears as a structured card inside the assistant's response area in the chat.

```
┌──────────────────────────────────────────────────────────────┐
│ [FileText]  Macro Research Report                            │
│             Fed Policy & Rate Outlook  ·  Apr 9, 2026        │
│──────────────────────────────────────────────────────────────│
│ Global central banks are navigating a complex environment    │
│ as inflation moderates but remains above target in key       │
│ economies. The Federal Reserve held rates steady at...       │
│                                          [read more →]       │
│──────────────────────────────────────────────────────────────│
│ [Open Report]          [Download ▾]    [Save to Repo]        │
└──────────────────────────────────────────────────────────────┘
```

| Element | Detail |
|---|---|
| Card container | `bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[--radius-lg] overflow-hidden shadow-sm`; `max-w-[560px]` |
| Header row | `px-4 py-3 flex items-start gap-3`; `FileText` icon (16px, `--color-text-tertiary`); two-line label — "Macro Research Report" (`text-base font-medium text-[--color-text-primary]`) on line 1, topic + date (`text-sm text-[--color-text-secondary]`) on line 2 |
| Preview text | `px-4 py-3 text-sm text-[--color-text-secondary] leading-relaxed`; clamped to 3 lines (`line-clamp-3`); "read more →" text link fades in at bottom when clamped; clicking expands to full preview |
| Action row | `px-4 py-2.5 flex items-center gap-2 bg-[--color-bg-base] border-t border-[--color-border-subtle]` |
| Open Report button | `px-3 h-7 rounded-[--radius-md] bg-[--color-accent-primary] text-white text-sm font-medium hover:bg-[--color-accent-hover]`; opens FileViewer panel |
| Download button | `px-3 h-7 rounded-[--radius-md] border border-[--color-border-secondary] text-sm text-[--color-text-secondary] hover:bg-[--color-surface-hover]`; opens a small dropdown: "PDF" / "DOCX" |
| Save to Repo button | `flex items-center gap-1.5 text-sm text-[--color-text-secondary] hover:text-[--color-text-primary]`; `Bookmark` icon (14px); on save: icon transitions to filled, color shifts to `--color-accent-primary`, brief scale pulse `1→1.2→1 over 200ms` |
| Card entry animation | `opacity 0→1, y 12→0, duration 250ms, ease-out` |

---

### Message Input

Always visible, fixed to the bottom of the page.

| Element | Detail |
|---|---|
| Container | `flex-shrink-0 px-6 py-4 border-t border-[--color-border-subtle] bg-[--color-bg-base]` |
| Inner wrapper | `max-w-[680px] mx-auto` |
| Input field | Multi-line `<textarea>`, grows from 1 line up to 4 lines (~120px) before scrolling; `bg-[--color-bg-input] rounded-xl border border-[--color-border-subtle] px-4 py-3 text-md text-[--color-text-primary] placeholder:text-[--color-text-tertiary] resize-none outline-none`; on focus: border transitions to `--color-border-secondary`, `--duration-fast` |
| Placeholder — welcome | "Ask a macro question or describe a research topic..." |
| Placeholder — active | "Ask a follow-up question..." |
| Send button | `w-8 h-8 rounded-[--radius-md] bg-[--color-accent-primary] text-white flex items-center justify-center`; `ArrowUp` icon (14px); when input is empty: `opacity-40 cursor-not-allowed`; hover (enabled): `bg-[--color-accent-hover]`; transition `--duration-fast` |
| Stop button | Replaces send while streaming; same dimensions; `bg-[--color-surface-active] text-[--color-text-secondary]`; `Square` icon (14px); click cancels stream |
| Keyboard | Enter = submit; Shift+Enter = newline; empty input cannot be submitted |
| Helper text | `mt-2 text-xs text-[--color-text-tertiary] text-center` — "Press Enter to send · Shift+Enter for new line" |
| Disabled state | While streaming: textarea `opacity-60`, send button replaced with stop button |

---

### Report Settings Modal

Opened via the "Report Settings" button in the page header.

```
┌──────────────────────────────────────────────────────────┐
│  Report Settings                                   [✕]   │
│──────────────────────────────────────────────────────────│
│  Report Length                                           │
│  ┌────────────────────────────────────────────────────┐  │
│  │  Concise   │   Normal ●   │   Elaborative           │  │
│  └────────────────────────────────────────────────────┘  │
│──────────────────────────────────────────────────────────│
│  SECTIONS                                                │
│  ☑  Executive Summary                                    │
│  ☑  Macroeconomic Context                                │
│  ☑  Key Indicators & Data                                │
│  ☑  Policy Analysis                                      │
│  ☑  Market Implications                                  │
│  ☑  Risks & Scenarios                                    │
│  ☑  Outlook                                              │
│──────────────────────────────────────────────────────────│
│  CUSTOM SECTIONS                             [+ Add]     │
│──────────────────────────────────────────────────────────│
│                          [Cancel]  [Save Settings]       │
└──────────────────────────────────────────────────────────┘
```

| Element | Detail |
|---|---|
| Backdrop | `bg-black/40`, covers full viewport, click-to-dismiss |
| Modal container | `bg-[--color-bg-elevated] rounded-[--radius-lg] shadow-lg border border-[--color-border-subtle]`; `w-full max-w-[480px]`; centered `fixed inset-0 m-auto h-fit` |
| Header | `flex justify-between items-center px-6 py-4 border-b border-[--color-border-subtle]`; "Report Settings" `text-lg font-semibold text-[--color-text-primary]`; `✕` close button `text-[--color-text-secondary] hover:text-[--color-text-primary]` |
| Report Length | Segmented 3-button row: Concise / Normal / Elaborative; active: `bg-[--color-surface-active] text-[--color-text-primary] font-medium`; inactive: `text-[--color-text-secondary] hover:bg-[--color-surface-hover]`; `rounded-[--radius-md] px-4 py-2 text-sm`; contained in a `border border-[--color-border-subtle] rounded-[--radius-md] p-1 flex gap-1` pill group |
| Section divider label | `text-xs font-medium text-[--color-text-tertiary] uppercase tracking-[0.04em] px-6 pt-4 pb-2` |
| Section rows | `flex items-center gap-3 px-6 py-2.5 border-b border-[--color-border-subtle] last:border-0`; checkbox on left; section name `text-base text-[--color-text-primary]`; checked: checkbox fills with `--color-accent-primary` |
| Custom sections | Section header row `px-6 py-3 flex justify-between items-center border-t border-[--color-border-subtle]`; `+ Add` button `text-sm text-[--color-accent-primary] hover:text-[--color-accent-hover]`; each custom section row has a section name input + optional description textarea + remove `✕` |
| Footer | `px-6 py-4 border-t border-[--color-border-subtle] flex justify-end gap-2`; Cancel: outline `border border-[--color-border-secondary] text-sm text-[--color-text-secondary] px-4 h-9 rounded-[--radius-md]`; Save: `bg-[--color-accent-primary] text-white text-sm px-4 h-9 rounded-[--radius-md] hover:bg-[--color-accent-hover]` |
| Entry animation | `opacity 0→1, scale 0.97→1, duration 200ms, ease-out`; exit: `opacity 1→0, scale 1→0.97, duration 150ms` |

---

### States

| State | Visual Treatment |
|---|---|
| **Welcome** | Centered heading + chips displayed in the content area; no chat history visible |
| **Generating** | Typing indicator shown where assistant response will appear; send button replaced by stop button; textarea opacity reduced to 60% |
| **Streaming** | Token-by-token text reveal with blinking cursor; stop button visible |
| **Idle** | Chat scrollable; full input enabled; send button active when input has content |
| **Response Stopped** | Partial response shown as-is; muted italicized "Response stopped." label appended below the text |
| **Error** | Inline error row below last message: `text-sm text-[--color-feedback-error]` message + `RotateCcw` icon + "Try again" text link that retries the last user message |

---

### Responsive Behavior

| Breakpoint | Behavior |
|---|---|
| Desktop (>1024px) | Full layout; chat container centered at `max-w-[680px]` |
| Tablet (768–1024px) | Same layout; chat fills available width |
| Mobile (<768px) | Horizontal padding reduced to `px-4`; report card action row allows wrapping; modal is full-width bottom sheet on mobile |

---

## Page Settings
Report section configuration and length preference are accessible via the Report Settings modal in the page header.

## Report Framework
*(To be defined.)*

## Configurations
- LLM Model: `openai/gpt-oss-120b`
- Streaming: enabled
- Max context window: managed by the LLM backend; older messages may be summarized or truncated silently when the conversation grows long

---

## Non-Goals (v1)
- File upload or document analysis
- Embedded charts or live data visualization within the chat
- Export to Excel or CSV formats
- Persistent cross-session memory beyond what Chat History stores

## Open Questions
- Should Macro Research share its report settings configuration with other departments (same section editor UX) or use its own settings panel?
- Should suggestion chips be static or personalized based on current macro news headlines?
