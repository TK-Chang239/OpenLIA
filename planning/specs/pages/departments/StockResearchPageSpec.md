# Stock Research Deparment Spec

## Page Overview
The Stock Research Department (SR) is used by the user to research into specific companies or stocks by generating a stock research report. The user will prompt the SR with a company that he is interested in, and any specific topics that he would like the report to focus or elaborate on. The SR will then return the generated report using the SR report framework.

## Functions
1. **Stock Research Report**: SR manages generating the stock research report. The report will be written according to the SR report framework.
2. **LLM Chatbot**: SR will operate as a LLM chatbot, meaning that SR will also be able to handle follow-up questions from the user regarding the company or the report.
3. **Save Reports**: After the reports are generated, there will be options to save the report to the Repository or to download it as pdf or word files.
4. **Report Preview** When reports are generated, it will be shown as a thumbnail in the chat. Opening the thumbnail will then open up report preview to allow the user to read it in greater detail and in a more visually-friendly format.

## Page Settings
In the settings page for SR, changeable settings are avaliable as below:
1. Report Sections: Allows the user to select what sections the user wants to be included in the report. Default sections are included for the user to check or uncheck.
2. Custom Sections: There is also a custom button that allows users to add custom sections. The custom button opens up another pop-up that allows user to input a name for their custom section as well as a description box for what the section should be about.
3. Length Adjuster: Allows user to choose the length of reports, such as concise, normal, or ellaborative.

## User Interface Design

### Layout

SR uses a full-height chat interface. There are two states: **Welcome** (no active conversation) and **Active** (conversation in progress).

**Welcome State:**

```
┌────────────────────────────────────────────────────────────────┐
│  Stock Research                           [⚙ Report Settings]  │
│────────────────────────────────────────────────────────────────│
│                                                                │
│                                                                │
│                      Stock Research                            │
│           Generate deep-dive reports on any company            │
│                                                                │
│   ┌───────────────────────────────────────────────────────┐   │
│   │  [AAPL]  [TSLA]  [NVDA]  [MSFT]  [From Portfolio ↗]  │   │
│   └───────────────────────────────────────────────────────┘   │
│                                                                │
│  ┌──────────────────────────────────────────────────────────┐ │
│  │  Enter a ticker or company name (e.g., AAPL, NVIDIA)...  │ │
│  │                                                  [Send]  │ │
│  └──────────────────────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────┘
```

**Active State:**

```
┌────────────────────────────────────────────────────────────────┐
│  Stock Research                           [⚙ Report Settings]  │
│────────────────────────────────────────────────────────────────│
│  ┌──────────────────────────────────────────────────────────┐ │
│  │                                                          │ │
│  │       [Scrollable chat: messages + report cards]         │ │
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
| Height | 56px (`h-14`), `flex-shrink-0` — does not scroll |
| Background | `--color-bg-base` |
| Border | 1px bottom, `--color-border-subtle` |
| Page title | "Stock Research" — `text-xl font-semibold text-[--color-text-primary]`, left-aligned, `pl-6` |
| Report Settings button | Right of header, `pr-6`; `Settings` icon (16px) + "Report Settings" label; `text-sm text-[--color-text-secondary]`; outline style: `border border-[--color-border-secondary] rounded-[--radius-md] px-3 h-8`; hover: `bg-[--color-surface-hover] text-[--color-text-primary]`; opens Report Settings modal |

---

### Welcome State

Shown when there is no active conversation. Centered vertically in the content area between the header and input.

| Element | Detail |
|---|---|
| Heading | "Stock Research" — `text-2xl font-semibold text-[--color-text-primary]`, horizontally centered |
| Sub-text | "Generate deep-dive reports on any company" — `text-md text-[--color-text-secondary]`, centered, `mt-2` |
| Suggestion chips | 5 chips: "AAPL", "TSLA", "NVDA", "MSFT", and "From Portfolio ↗". The first four immediately populate the input and submit. "From Portfolio" opens a compact picker showing the user's tracked tickers |
| Chip style | `px-3.5 py-2 rounded-full border border-[--color-border-secondary] text-sm text-[--color-text-secondary]`; hover: `bg-[--color-surface-hover] text-[--color-text-primary]`; transition `--duration-fast` |
| "From Portfolio" chip | Same style, with `ArrowUpRight` icon (12px) inline; opens a popover listing Portfolio tickers in a scrollable list, each row clickable to populate the input |
| Entry animation | Heading + sub-text: `opacity 0→1, y 12→0, duration 250ms`; chips stagger in `40ms` apart |

---

### Chat Message Area

Replaces the welcome content once a conversation starts. Scrolls independently.

| Element | Detail |
|---|---|
| Container | `flex-1 overflow-y-auto px-6 py-6` |
| Content max-width | `max-w-[680px] mx-auto` |
| User messages | Right-aligned bubble: `rounded-2xl rounded-br-sm px-4 py-2.5 bg-[--color-surface-active] text-[--color-text-primary] text-md`; `max-w-[72%]` |
| Assistant messages | Left-aligned, no bubble: `text-md text-[--color-text-primary] leading-relaxed`; full-width up to chat max-width; markdown rendered (bold, bullets, tables, inline code, code blocks) |
| Timestamps | Hidden by default; fade in on hover: `text-xs text-[--color-text-tertiary]`, `--duration-fast` |
| Streaming | Token-by-token reveal with blinking cursor `▌` at the insertion point |
| Loading indicator | Animated three-dot pulse while awaiting first token: three `w-1.5 h-1.5 rounded-full bg-[--color-text-tertiary]` dots, opacity cycling `0.3→1→0.3` over 1.2s, staggered `200ms` apart |
| Message entry | `opacity 0→1, y 8→0, duration 200ms, ease-out` |

---

### Report Thumbnail Card

When SR completes a report, a structured card appears within the assistant's response area.

```
┌──────────────────────────────────────────────────────────────┐
│ [FileText]  Stock Research Report                            │
│             AAPL  ·  Apple Inc.  ·  Apr 9, 2026              │
│──────────────────────────────────────────────────────────────│
│ Apple Inc. reported a strong Q1 2026, with revenue of        │
│ $124.3B exceeding consensus estimates by 3.2%. iPhone        │
│ sales drove outperformance, particularly in emerging...      │
│                                          [read more →]       │
│──────────────────────────────────────────────────────────────│
│ [Open Report]          [Download ▾]    [Save to Repo]        │
└──────────────────────────────────────────────────────────────┘
```

| Element | Detail |
|---|---|
| Card container | `bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[--radius-lg] overflow-hidden shadow-sm`; `max-w-[560px]` |
| Header row | `px-4 py-3 flex items-start gap-3`; `FileText` icon (16px, `--color-text-tertiary`); two-line label — "Stock Research Report" (`text-base font-medium text-[--color-text-primary]`); ticker + company name + date (`text-sm text-[--color-text-secondary]`) |
| Preview text | `px-4 py-3 text-sm text-[--color-text-secondary] leading-relaxed`; `line-clamp-3`; "read more →" text link at end; clicking expands to full preview inline |
| Action row | `px-4 py-2.5 flex items-center gap-2 bg-[--color-bg-base] border-t border-[--color-border-subtle]` |
| Open Report | `px-3 h-7 rounded-[--radius-md] bg-[--color-accent-primary] text-white text-sm hover:bg-[--color-accent-hover]`; opens FileViewer |
| Download | Outline button with `▾` chevron; dropdown: "Download as PDF" / "Download as DOCX" |
| Save to Repo | Text-icon button; `Bookmark` icon toggles filled/outline; on save: brief scale pulse on icon |
| Card entry animation | `opacity 0→1, y 12→0, duration 250ms, ease-out` |

---

### Message Input

Always visible, pinned to the bottom of the page.

| Element | Detail |
|---|---|
| Container | `flex-shrink-0 px-6 py-4 border-t border-[--color-border-subtle] bg-[--color-bg-base]` |
| Inner wrapper | `max-w-[680px] mx-auto` |
| Input field | Multi-line `<textarea>`; grows from 1 to 4 lines (~120px max) before scrolling; `bg-[--color-bg-input] rounded-xl border border-[--color-border-subtle] px-4 py-3`; on focus: border → `--color-border-secondary`; transition `--duration-fast` |
| Placeholder — welcome | "Enter a ticker or company name (e.g., AAPL, NVIDIA)..." |
| Placeholder — active | "Ask a follow-up question about the company or report..." |
| Send button | `w-8 h-8 rounded-[--radius-md] bg-[--color-accent-primary] text-white`; `ArrowUp` icon (14px); disabled when empty: `opacity-40 cursor-not-allowed` |
| Stop button | Replaces send while streaming; `bg-[--color-surface-active] text-[--color-text-secondary]`; `Square` icon (14px) |
| Keyboard | Enter = submit; Shift+Enter = newline |
| Helper text | `mt-2 text-xs text-[--color-text-tertiary] text-center` — "Press Enter to send · Shift+Enter for new line" |

---

### Report Settings Modal

Opened via the "Report Settings" button in the page header.

```
┌──────────────────────────────────────────────────────────┐
│  Report Settings                                   [✕]   │
│──────────────────────────────────────────────────────────│
│  Report Length                                           │
│  ┌─────────────────────────────────────────────────────┐ │
│  │   Concise   │   Normal ●   │   Elaborative          │ │
│  └─────────────────────────────────────────────────────┘ │
│──────────────────────────────────────────────────────────│
│  SECTIONS                                                │
│  ☑  Executive Summary                                    │
│  ☑  Financial Overview                                   │
│  ☑  Revenue & Earnings                                   │
│  ☑  Business Segments                                    │
│  ☑  Competitive Landscape                                │
│  ☑  Recent News & Developments                           │
│  ☑  Analyst Ratings & Price Targets                      │
│  ☑  Risk Factors                                         │
│──────────────────────────────────────────────────────────│
│  CUSTOM SECTIONS                             [+ Add]     │
│──────────────────────────────────────────────────────────│
│                          [Cancel]  [Save Settings]       │
└──────────────────────────────────────────────────────────┘
```

| Element | Detail |
|---|---|
| Backdrop | `bg-black/40`, full-viewport, click-to-dismiss |
| Modal container | `bg-[--color-bg-elevated] rounded-[--radius-lg] shadow-lg border border-[--color-border-subtle] w-full max-w-[480px]`; fixed centered |
| Report Length | 3-option segmented control: Concise / Normal / Elaborative; active: `bg-[--color-surface-active] font-medium`; contained in a bordered pill group |
| Section rows | Checkbox left + section name `text-base text-[--color-text-primary]`; `py-2.5 px-6 border-b border-[--color-border-subtle]`; checked checkbox fills `--color-accent-primary` |
| Custom sections | "+ Add" opens a new row with name input (required) + description textarea (optional) + `✕` remove; existing custom sections are editable inline |
| Footer buttons | Cancel (outline) + Save Settings (accent filled); `h-9 px-4 rounded-[--radius-md]` |
| Entry animation | `opacity 0→1, scale 0.97→1, duration 200ms, ease-out` |

---

### States

| State | Visual Treatment |
|---|---|
| **Welcome** | Centered heading + chips; no chat history |
| **Generating** | Typing indicator; send → stop; textarea dimmed |
| **Streaming** | Token-by-token reveal; blinking cursor; stop button active |
| **Idle** | Input fully enabled; chat scrollable |
| **Response Stopped** | Partial response retained; italicized muted "Response stopped." appended |
| **Error** | Inline error below last message with "Try again" `RotateCcw` button |

---

### Responsive Behavior

| Breakpoint | Behavior |
|---|---|
| Desktop (>1024px) | Centered chat at `max-w-[680px]`; full layout |
| Tablet (768–1024px) | Chat fills available width; same component structure |
| Mobile (<768px) | Reduced horizontal padding `px-4`; modal becomes full-width bottom sheet |

## Report Framework

## Configuartions
- LLM Model: