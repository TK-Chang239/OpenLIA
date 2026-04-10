# Secretary Department Spec

## Page Overview
The Secretary is the home page of LIA and serves as the general-purpose LLM chatbot. It handles general inquiries from the user, including questions about how to use the product, real-time market data lookups, and quick topic summaries. When the user makes a request that is better served by another department, the Secretary identifies the appropriate department and redirects the user there. The Secretary prioritizes concise, fast, and accurate responses.

## Functions
1. **General Inquiries**: The Secretary answers open-ended questions from the user, including how-to questions about LIA, quick factual lookups, brief explanations of financial concepts, and general conversation.
2. **Real-Time Market Data**: The Secretary can fetch and display real-time or latest market data for a ticker or asset on request (e.g., current price, daily change, volume). Data is sourced from the same EODHD integration used across the product.
3. **Topic Summaries**: The Secretary generates concise summaries of user-prompted topics, such as a quick overview of a company, a market event, or a financial term.
4. **Department Redirect**: When the user's request maps to a specialized department (e.g., a detailed stock research report, a macro research query, an earnings analysis, or a retail sentiment check), the Secretary recognizes the intent and redirects the user to the appropriate department. The redirect is surfaced as an inline suggestion before navigating, so the user can confirm or continue in the Secretary instead.
5. **Product Guidance**: The Secretary can explain what each department does, how to use features across the product, and what kinds of questions or tasks are best suited to each department.

## User Interface Design

### Layout

The Secretary has no traditional page header — the welcome greeting serves as the heading on first load.

```
┌───────────────────────────────────────────────────────────┐
│                                                           │
│                                                           │
│              Welcome back, [User Name].                   │
│           What can I help you with today?                 │
│                                                           │
│                                                           │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  [Suggestion chip]  [Suggestion chip]  [Suggestion] │  │
│  └─────────────────────────────────────────────────────┘  │
│                                                           │
│  ┌─────────────────────────────────────────────────────┐  │
│  │  Ask me anything...                           [Send] │  │
│  └─────────────────────────────────────────────────────┘  │
└───────────────────────────────────────────────────────────┘
```

- On first load (no conversation history), the welcome message and suggestion chips are shown centered in the content area above the message input.
- Once the conversation starts, the welcome message and chips are replaced by the chat message area, which scrolls independently.
- The message input is pinned to the bottom of the page at all times.

#### Welcome State Layout Details

| Element | Detail |
|---|---|
| Welcome content container | `absolute inset-0 flex flex-col items-center justify-center pb-24` (reserves space for the pinned input) |
| Greeting | `text-2xl font-semibold text-[--color-text-primary] text-center` |
| Sub-text | `text-md text-[--color-text-secondary] text-center mt-2` |
| Chips row | `flex flex-wrap gap-2 justify-center mt-8 max-w-[520px] mx-auto` |
| Entry animation | Greeting + sub-text: `opacity 0→1, y 12→0, duration 250ms`; chips stagger in `40ms` apart after heading; exit: `opacity 1→0, y 0→-8, duration 200ms` |

---

### Welcome State

| Element | Detail |
|---|---|
| Greeting | "Welcome back, [User Name]." in large text, centered |
| Sub-text | "What can I help you with today?" in smaller, muted text below the greeting |
| Suggestion chips | A horizontal row of 3–4 short prompt suggestions (e.g., "What is LIA?", "Get a quick market snapshot", "How do I use Stock Research?", "Summarize [topic]"). Clicking a chip populates the input and submits it. |

---

### Chat Message Area

| Element | Detail |
|---|---|
| Container | `flex-1 overflow-y-auto px-6 py-6` |
| Content max-width | `max-w-[680px] mx-auto` |
| User messages | Right-aligned bubble: `rounded-2xl rounded-br-sm px-4 py-2.5 bg-[--color-surface-active] text-[--color-text-primary] text-md`; `max-w-[72%]`; `whitespace-pre-wrap` |
| Secretary responses | Left-aligned, no bubble: `text-md text-[--color-text-primary] leading-relaxed`; full-width up to chat max-width; markdown rendered (bold, bullets, numbered lists, tables, inline code, code blocks) |
| Timestamps | Hidden by default; fade in `opacity 0→1, --duration-fast` on hover of the message group, displayed below as `text-xs text-[--color-text-tertiary]` |
| Streaming | Token-by-token reveal; blinking cursor `▌` (`--color-text-tertiary`, 800ms blink cycle) at insertion point during generation |
| Loading indicator | Animated three-dot pulse: three `w-1.5 h-1.5 rounded-full bg-[--color-text-tertiary]` dots; opacity cycles `0.3→1→0.3` over 1.2s, staggered `200ms` between dots |
| Message entry | Each new message: `opacity 0→1, y 8→0, duration 200ms, ease-out` |
| Between-message gap | `space-y-6` |

---

### Redirect Suggestion Card

When the Secretary identifies that a request is better handled by another department, it renders a structured card below its brief explanation text.

```
┌──────────────────────────────────────────────────────────┐
│ This looks like a Stock Research request. I can take     │
│ you there for a full in-depth report.                    │
│──────────────────────────────────────────────────────────│
│ [Go to Stock Research →]   Stay here and answer instead  │
└──────────────────────────────────────────────────────────┘
```

| Element | Detail |
|---|---|
| Card container | `mt-3 bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[--radius-lg] p-4 shadow-sm`; `max-w-[480px]` |
| Explanation text | `text-sm text-[--color-text-secondary]`; department name in the sentence styled `font-medium text-[--color-text-primary]` |
| Divider | `border-t border-[--color-border-subtle] mt-3 pt-3` |
| "Go to [Department]" button | `flex items-center gap-1.5 px-3 h-8 rounded-[--radius-md] bg-[--color-accent-primary] text-white text-sm font-medium hover:bg-[--color-accent-hover]`; `ArrowRight` icon (14px) inline |
| "Stay here" link | `text-sm text-[--color-text-secondary] hover:text-[--color-text-primary] ml-3`; clicking closes the card and streams the direct answer |
| Card entry animation | `opacity 0→1, y 6→0, duration 200ms, ease-out` |
| Navigation | Clicking "Go to [Department]" navigates via `router.push(href)`; context from the user's message (e.g., ticker symbol) is passed as a URL search param to pre-fill the target department's input |

---

### Message Input

| Element | Detail |
|---|---|
| Container | `flex-shrink-0 px-6 py-4 bg-[--color-bg-base]`; in active state: `border-t border-[--color-border-subtle]`; in welcome state: `absolute bottom-0 inset-x-0` |
| Inner wrapper | `max-w-[680px] mx-auto` |
| Input field | Multi-line `<textarea>` that expands from 1 to 4 lines (~120px) before scrolling; `bg-[--color-bg-input] rounded-xl border border-[--color-border-subtle] px-4 py-3 text-md text-[--color-text-primary] placeholder:text-[--color-text-tertiary] resize-none outline-none`; on focus: border transitions to `--color-border-secondary`; transition `--duration-fast` |
| Placeholder | "Ask me anything..." |
| Send button | `w-8 h-8 rounded-[--radius-md] bg-[--color-accent-primary] text-white flex items-center justify-center`; `ArrowUp` icon (14px); disabled when input empty: `opacity-40 cursor-not-allowed`; hover (enabled): `bg-[--color-accent-hover]`; transition `--duration-fast` |
| Stop button | Replaces send while response is streaming; same dimensions; `bg-[--color-surface-active] text-[--color-text-secondary]`; `Square` icon (14px); click cancels the stream |
| Input disabled state | While streaming: textarea `opacity-60`, cursor default, send replaced by stop |
| Helper text | `mt-2 text-xs text-[--color-text-tertiary] text-center` — "Press Enter to send · Shift+Enter for new line" |

---

## Redirect Routing Logic

The Secretary uses intent detection to route requests to departments. Routing decisions are based on the nature of the request:

| User Intent | Target Department |
|---|---|
| Detailed company or stock research report | Stock Research |
| Earnings analysis or earnings monitoring | Earnings Reports |
| Retail investor sentiment for a ticker | Retail Sentiment |
| Macro economic research or analysis | Macro Research |
| Morning briefings setup or report review | Morning Briefings |
| Portfolio management | Portfolio |

The Secretary does not redirect for simple factual questions about a company, quick price lookups, or general explanations — those are handled directly. Redirects are only triggered when the user's request would clearly benefit from the full capabilities of a specialized department (e.g., generating a full report, setting up automated monitoring).

---

## Behavior & Interactions

### Conversation Persistence
- Conversation history is saved and restored when the user returns to the Secretary page within the same session.
- On new session start, the page resets to the welcome state with a fresh conversation.
- Chat history across sessions is managed by the Chat History utility tool.

### Input Handling
- Pressing Enter submits the message; Shift+Enter inserts a line break.
- Empty messages cannot be submitted.
- Messages are trimmed of leading and trailing whitespace before submission.

### Response Interruption
- The user can cancel a streaming response by clicking the stop icon that replaces the send button during generation.
- Canceling stops the stream; the partial response is shown as-is with a muted "Response stopped" label.

---

## States

| State | Description |
|---|---|
| **Welcome** | No conversation history for this session; welcome greeting and suggestion chips shown |
| **Conversation Active** | Chat history is visible; message input is at the bottom |
| **Loading** | Secretary is generating a response; typing indicator shown; input is disabled |
| **Redirect Pending** | Secretary has identified a better-suited department and is showing the redirect suggestion card |
| **Error** | LLM call failed; an inline error message is shown with a "Try again" button |

---

## Page Settings
There are no user-configurable settings for the Secretary.

## Report Framework
There are no report frameworks for the Secretary.

## Configurations
- LLM Model: `openai/gpt-oss-120b`
- Streaming: enabled
- Max context window: managed by the LLM backend; older messages may be summarized or truncated silently when the conversation grows long

---

## Non-Goals (v1)
- File uploads or document analysis (not supported in the Secretary; use the File Viewer utility for that)
- Generating full-length department reports — the Secretary redirects instead
- Persistent cross-session memory beyond what Chat History stores
- Voice input or text-to-speech output
- Multi-turn tool use or agent-style task execution

---

## Open Questions
- Should the suggestion chips on the welcome screen be static or personalized based on the user's recent activity across departments?
- Should the Secretary surface a "Did you mean to go to [Department]?" prompt reactively after answering, if it detects the answer would be better as a full report?
