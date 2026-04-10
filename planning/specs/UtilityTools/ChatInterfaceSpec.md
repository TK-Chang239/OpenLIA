# Chat Interface Spec

## Overview

This spec defines the shared chat interface design used across all LIA department pages (Secretary, Stock Research, Macro Research). All department chat pages conform to this layout, message treatment, animation system, and state patterns. Department-specific elements (welcome content, input placeholder, report thumbnails) are defined in each department's page spec.

---

## Core Layout

### Chat Column Centering

The chat column is always **centered within the available content area**. When the FileViewer panel is open, the content area compresses via Framer Motion `layout` and the chat column re-centers within the narrowed space.

```
┌────────────────────────────────────────────────────────────────────┐
│ Sidebar   │              Content Area               │  FileViewer  │
│  240px    │         max-w-[720px] mx-auto           │  (if open)   │
│           │                                         │              │
│           │   ╔═══════════════════════════════╗     │              │
│           │   ║  [User bubble]                ║     │              │
│           │   ║                               ║     │              │
│           │   ║  [L] Assistant response       ║     │              │
│           │   ║  [L] Thinking ● ● ●           ║     │              │
│           │   ╚═══════════════════════════════╝     │              │
│           │   ┌───────────── input ──────────┐      │              │
└────────────────────────────────────────────────────────────────────┘
```

| Element | Spec |
|---|---|
| Scrollable container | `absolute inset-0 overflow-y-auto` |
| Message column | `max-w-[720px] mx-auto px-6 py-8` |
| Message spacing | `space-y-2` between same-role consecutive messages; `mt-6` between role changes (creates natural conversation beat) |
| Bottom padding | `pb-6` inside message column to prevent content hiding behind input |

---

## Message Components

### 1. User Message

Right-aligned bubble. The blue tint connects the user message visually to the accent color, reinforcing ownership without being loud.

```
                          ┌───────────────────────────┐
                          │  What moved the market    │
                          │  today?                   │
                          └───────────────────────────┘
```

| Element | Spec |
|---|---|
| Wrapper | `flex justify-end` |
| Bubble | `max-w-[72%] px-4 py-3 rounded-2xl rounded-br-sm bg-[--color-accent-primary]/8 border border-[--color-border-secondary] text-md text-[--color-text-primary] leading-relaxed whitespace-pre-wrap` |
| Entry animation | `x: 12→0, opacity: 0→1, duration: 200ms, ease: easeOut` via Framer Motion |

---

### 2. Assistant Message

Left-aligned. Each assistant response group begins with the LIA badge — a 28×28px rounded square — anchoring the message and signaling "this is from the AI." Only one badge per response group, not one per streamed chunk.

```
  ┌───┐
  │ L │  Top movers this session:
  └───┘
       NVDA +3.2% — strong data center demand...
       META +1.8% — Threads engagement...
```

| Element | Spec |
|---|---|
| Wrapper | `flex items-start gap-3` |
| LIA badge | `w-7 h-7 rounded-md bg-[--color-accent-primary] text-white text-xs font-semibold flex items-center justify-center flex-shrink-0 mt-0.5 shadow-sm` — shows letter "L" |
| Content area | `flex-1 min-w-0` |
| Text | `text-md text-[--color-text-primary] leading-[1.75] whitespace-pre-wrap` |
| Entry animation | `y: 8→0, opacity: 0→1, duration: 200ms, ease: easeOut` |
| Streaming cursor | `▌` inline after last token — `cursor-blink` CSS animation (800ms), color `text-[--color-accent-primary]/50` |

---

### 3. Thinking / Loading State

Shown while the LLM is generating. Uses the same avatar layout as the assistant message to maintain spatial consistency. The dots float in a pill container — not raw dots on the background.

```
  ┌───┐  ┌───────────┐
  │ L │  │  ●  ●  ●  │
  └───┘  └───────────┘
```

| Element | Spec |
|---|---|
| Wrapper | `flex items-center gap-3` |
| LIA badge | Same spec as assistant message badge |
| Dot pill | `flex items-center gap-1.5 px-3.5 py-2.5 bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-full shadow-sm` |
| Dots | Three `w-1.5 h-1.5 rounded-full bg-[--color-accent-primary]/50` |
| Dot animation | `scaleY: [0.5, 1.0, 0.5], opacity: [0.4, 1, 0.4]` — wave formation, `duration: 0.9s, repeat: Infinity`, stagger `150ms` between dots via `delay`; use Framer Motion |
| Entry | Same as assistant message entry |

---

### 4. Streaming State

While tokens are being revealed, the assistant message is shown with a trailing cursor. The badge is visible from the start of streaming (not after completion).

| Element | Spec |
|---|---|
| Badge | Visible immediately at stream start |
| Content | Text grows character by character |
| Cursor | `▌` appended inline — `cursor-blink` CSS keyframe, `text-[--color-accent-primary]/50` |
| Transition to complete | Cursor disappears immediately when stream ends; no fade |

---

### 5. Timestamps

| Element | Spec |
|---|---|
| Trigger | Mouse hover over the message group wrapper |
| Position | Below the message content, aligned to the message side (right for user, left for assistant) |
| Style | `text-xs text-[--color-text-tertiary]` |
| Format | `h:mm AM/PM` |
| Animation | `opacity: 0→1, duration: 120ms` via Framer Motion `AnimatePresence` |

---

### 6. Response Stopped Label

When the user stops a streaming response mid-generation:

| Element | Spec |
|---|---|
| Label | `text-xs text-[--color-text-tertiary] italic mt-1.5 block` — "Response stopped." |
| Position | Below the partial response content, inside the content area |

---

### 7. Inline Error State

When the LLM call fails:

| Element | Spec |
|---|---|
| Wrapper | Same `flex items-start gap-3` layout as assistant message |
| Badge | Same LIA badge |
| Content | `flex items-center gap-2 text-sm text-[--color-feedback-error]`; `AlertCircle` icon (14px); error text; "Try again" button `text-[--color-accent-primary] hover:underline ml-1` |

---

## Welcome State

The welcome state covers the message area until the first message is sent, then exits to reveal the conversation.

### Background Treatment

| Element | Spec |
|---|---|
| Dot grid | CSS `background-image: radial-gradient(circle, var(--color-border-subtle) 1px, transparent 1px)` at `size: 28px 28px`; `opacity: 0.5`; covers the full content area behind the welcome overlay |
| Accent glow | `radial-gradient(ellipse 65% 45% at 50% 65%, var(--color-accent-subtle) 0%, transparent 70%)`; overlaid above dot grid; `opacity: 0.6` |

### Content

| Element | Spec |
|---|---|
| Greeting | `DM Serif Display`, 30px, `text-[--color-text-primary]`, centered |
| Sub-text | `text-md text-[--color-text-secondary] mt-2 text-center` |
| Chips row | `flex flex-wrap gap-2 justify-center mt-8 max-w-[540px]` |
| Chip style | `bg-[--color-bg-elevated]/80 backdrop-blur-sm border border-[--color-border-secondary]/60 text-sm text-[--color-text-secondary] px-3.5 py-2 rounded-full hover:border-[--color-accent-primary]/40 hover:text-[--color-accent-primary] hover:bg-[--color-accent-subtle]/50` |
| Chip entry | Staggered: `opacity 0→1, y 8→0`, each chip 50ms after previous; first chip starts at 200ms delay |
| Overlay exit | `opacity 1→0, y 0→-12, duration: 200ms, ease: easeIn`; triggered on first message submit |

---

## Message Input

### Layout

| Element | Spec |
|---|---|
| Outer container | `flex-shrink-0 px-6 py-4 bg-[--color-bg-base]` |
| Border | `border-t border-[--color-border-subtle]` (always visible; not just in active state) |
| Inner wrapper | `max-w-[720px] mx-auto` |

### Input Field

| Element | Spec |
|---|---|
| Container | `flex items-end gap-2 rounded-xl border border-[--color-border-subtle] bg-[--color-bg-input] px-4 py-3 transition-all duration-fast` |
| Focus-within | `border-[--color-accent-primary]/40 shadow-[0_0_0_1px_rgba(59,130,246,0.12),_0_4px_20px_rgba(59,130,246,0.06)]` |
| Textarea | `flex-1 bg-transparent resize-none outline-none text-md text-[--color-text-primary] placeholder:text-[--color-text-tertiary] leading-relaxed`; expands from 1 to max 4 lines (~120px) |
| Placeholder | Department-specific (e.g., "Ask me anything...") |

### Buttons

| Element | Spec |
|---|---|
| Send button (enabled) | `w-8 h-8 rounded-lg bg-[--color-accent-primary] text-white flex items-center justify-center hover:bg-[--color-accent-hover] hover:scale-105 transition-all duration-fast`; `ArrowUp` icon (14px) |
| Send button (disabled) | `opacity-40 cursor-not-allowed hover:scale-100` |
| Stop button | `w-8 h-8 rounded-lg bg-[--color-surface-active] text-[--color-text-secondary] flex items-center justify-center hover:bg-[--color-surface-hover] transition-colors duration-fast`; `Square` icon (14px) |

### Helper Text

| Element | Spec |
|---|---|
| Text | `mt-2 text-xs text-[--color-text-tertiary] text-center select-none` |
| Content | "Enter to send · Shift+Enter for new line" |

---

## Animation Summary

| Interaction | Tool | Spec |
|---|---|---|
| Message enter (user) | Framer Motion | `x: 12→0, opacity: 0→1, 200ms easeOut` |
| Message enter (assistant) | Framer Motion | `y: 8→0, opacity: 0→1, 200ms easeOut` |
| Thinking dots | Framer Motion | `scaleY [0.5→1→0.5] + opacity [0.4→1→0.4], 0.9s, stagger 150ms` |
| Streaming cursor | CSS `cursor-blink` | `opacity 1↔0, 800ms ease-in-out, infinite` |
| Welcome overlay exit | Framer Motion | `opacity 1→0, y 0→-12, 200ms easeIn` |
| Timestamp appear | Framer Motion | `opacity 0→1, 120ms` |
| Chip enter | Framer Motion | `y 8→0, opacity 0→1, 220ms easeOut, stagger 50ms` |
| Chip hover | Framer Motion | `scale 1→1.02, spring stiffness: 400, damping: 20` |
| Input focus glow | CSS transition | `box-shadow, border-color, 150ms` |
| Send button hover | CSS + Framer | `bg-color (CSS) + scale 1→1.05 (Framer)` |

---

## Accessibility

- Each message group is a `role="article"` or semantic `<div>` with appropriate aria labeling
- LIA badge has `aria-hidden="true"` — it is decorative
- Thinking indicator has `aria-live="polite"` region announcing "LIA is thinking..."
- Streaming content is appended to an `aria-live="polite"` region
- Input textarea has `aria-label` describing its purpose
- Stop button has `aria-label="Stop generating"`

---

## Non-Goals (v1)

- Message reactions or editing
- Copy-to-clipboard button on individual messages
- Search within conversation history
- Message threading or branching
- File upload within the chat input
