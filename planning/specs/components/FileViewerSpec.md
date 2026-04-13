# FileViewer Spec

## Tool Overview
Each time a report is generated, a file thumbnail, a small preview element, will appear inline in the chat, showing the file name and type icon before you click into it.

Clicking on the thumbnail opens up a preview window on the right hand side of the screen and splits the chat window to the left hand side. The preview window allows the user to scroll and read through the report as is.

## Tool Functionalities
The `File Viewer` is a side panel that opens when a user clicks on a file attachment chip in the chat interface. It renders file contents in a readable, structured format without leaving the conversation context. The viewer sits alongside the chat, not on top of it, preserving conversational flow.

## Tool Design

### Entry Point: Attachment Chip

Before the viewer opens, the file is represented as an **attachment chip** — a structured inline card in the message thread.

```
┌──────────────────────────────────────────────────────┐
│ [FileText]  quarterly-report.pdf       [🔖]  [↓]    │
│              PDF · 248 KB                             │
└──────────────────────────────────────────────────────┘
```

| Property | Spec |
|---|---|
| Container | `inline-flex items-center gap-3 bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[--radius-lg] px-3 py-2.5 cursor-pointer`; max-width `320px` |
| Hover state | `border-[--color-border-secondary] shadow-sm`; transition `--duration-fast` |
| Active (clicked) | `bg-[--color-surface-active]` briefly, `100ms` |
| File icon | Lucide icon sized 20×20px, `--color-text-secondary`; mapped by file extension: PDF → `FileText`, CSV → `Sheet`, image → `Image`, code → `FileCode`, DOCX → `FileText` (default) |
| Filename | `text-base font-medium text-[--color-text-primary]`; `truncate max-w-[160px]` |
| Metadata line | `text-xs text-[--color-text-secondary]`; format: "PDF · 248 KB" or "CSV · 12 rows · 4 columns" |
| Action buttons | `SaveToRepo` + `Download` icon buttons on the right; hidden by default; revealed on chip hover or keyboard focus; always visible on touch |
| Action button spacing | `gap-1` between buttons; `ml-2` gap from the filename/meta column |
| Interaction | Click anywhere on chip except action buttons → opens FileViewer |

---

### Layout

```
┌─────────────────────────────────────────────────────────────────┐
│  Chat Thread (compresses)        │  FileViewer Panel            │
│                                  │ ┌────────────────────────┐   │
│  [msg]                           │ │  Header                │   │
│  [msg]                           │ │────────────────────────│   │
│  [attachment chip] ────────────► │ │                        │   │
│                                  │ │  Content Area          │   │
│                                  │ │  (scrollable)          │   │
│                                  │ │                        │   │
│                                  │ │────────────────────────│   │
│                                  │ │  Footer (optional)     │   │
│                                  │ └────────────────────────┘   │
│                              ◄── resize handle ──►              │
└─────────────────────────────────────────────────────────────────┘
```

- Panel slides in from the right edge: `x 100%→0, duration 200ms, ease-out`
- Chat thread width shrinks simultaneously using `framer-motion layout` animation, `duration 200ms`
- Panel is persistent — stays open while the user continues chatting; the chat thread compresses to its left
- Panel closes with: `x 0→100%, duration 150ms, ease-in`; chat thread expands back simultaneously

---

### Panel Dimensions

| Property | Spec |
|---|---|
| Default width | 40% of the main content area width |
| Min width | 360px |
| Max width | 70% of the main content area width |
| Height | Full height of the main content area (`h-full`) |
| Background | `--color-bg-elevated` |
| Left border | `border-l border-[--color-border-subtle]` |
| Shadow | `shadow-lg` on the left side of the panel (`box-shadow: -4px 0 24px rgba(0,0,0,0.08)`) |

---

### Resize Handle

| Property | Spec |
|---|---|
| Position | `absolute left-0 inset-y-0 w-1 cursor-col-resize z-10` |
| Default visual | Transparent; no visible indicator until hover |
| Hover visual | `bg-[--color-border-secondary]` — a 1px subtle line appears |
| Active (dragging) | `bg-[--color-accent-primary]` — color shifts to accent |
| Drag behavior | Clamps panel width between `min 360px` and `max 70% of viewport` |

---

### Panel Header

```
┌────────────────────────────────────────────────────────────────┐
│  quarterly-report.pdf                 [🔖 Save] [↓] [✕]       │
│  PDF · 12 pages · Equity Research · Generated Apr 3, 2026      │
└────────────────────────────────────────────────────────────────┘
```

| Element | Detail |
|---|---|
| Container | `flex-shrink-0 h-auto min-h-[56px] px-4 py-3 border-b border-[--color-border-subtle] flex items-start justify-between gap-3` |
| Background | `--color-bg-elevated` |
| Filename | `text-base font-medium text-[--color-text-primary]`; single line, `truncate` |
| Metadata line | `text-xs text-[--color-text-secondary] mt-0.5`; format: "PDF · 12 pages · [Department] · Generated [date]" (or "12 pages · [filesize]" for non-report files) |
| Left column | `flex flex-col min-w-0 flex-1` — filename + metadata stacked |
| Right column | `flex items-center gap-1.5 flex-shrink-0 ml-2` — action buttons |
| Save to Repo button | `flex items-center gap-1.5 px-2.5 h-8 rounded-[--radius-md] border border-[--color-border-secondary] text-sm text-[--color-text-secondary] hover:bg-[--color-surface-hover]`; `Bookmark` icon (14px) + "Save" label; transitions to saved state per `SaveToRepoSpec` |
| Download button | Same style: `Download` icon (14px) + "Download" label |
| Close button | `w-8 h-8 rounded-[--radius-md] text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]`; `X` icon (14px); closes panel |
| Button order | Save to Repo → Download → Close (left to right) |

---

### Content Area

| Property | Spec |
|---|---|
| Container | `flex-1 overflow-y-auto` |
| Background | `--color-bg-elevated` |
| Padding | Varies by file type (see per-type specs below) |

---

### File Type Rendering

#### PDF

| Element | Detail |
|---|---|
| Rendering | Embedded PDF canvas (`<canvas>` via pdf.js or similar); text is selectable |
| Page container | `px-6 py-4`; each page rendered as a canvas element with `shadow-sm rounded-[--radius-md]` and `mb-4` gap between pages |
| Background | Page canvas has white background even in dark mode (documents preserve their own colors) |
| Footer | Fixed `border-t border-[--color-border-subtle] px-4 py-2 flex items-center justify-between` — page indicator "Page 3 of 12" (`text-sm text-[--color-text-secondary]`) + `ChevronLeft` / `ChevronRight` nav buttons (`w-7 h-7 rounded-[--radius-md] hover:bg-[--color-surface-hover]`) |

#### Plain Text / Markdown (`.txt`, `.md`, `.log`)

| Element | Detail |
|---|---|
| For `.md` | Rendered markdown (same markdown component as chat messages); `px-6 py-5 text-md text-[--color-text-primary] leading-relaxed` |
| For `.txt`, `.log` | Monospace (`--font-mono`), `text-sm`; `px-0 py-4`; line numbers shown in left gutter (see Code below) |
| Line length cap | `max-w-[680px]` for rendered markdown; no cap for raw text (horizontal scroll instead) |

#### Code Files (`.py`, `.js`, `.ts`, `.json`, `.yaml`, etc.)

| Element | Detail |
|---|---|
| Container | `flex text-sm` |
| Line number gutter | `flex-shrink-0 pr-4 pl-4 py-4 text-right select-none text-[--color-text-tertiary] bg-[--color-bg-base] border-r border-[--color-border-subtle] font-mono` |
| Code body | `flex-1 overflow-x-auto px-4 py-4 font-mono text-[--color-text-code] bg-[--color-bg-code]` |
| No word wrap | `whitespace-pre` |
| Syntax highlighting | Language-appropriate token colors; use a minimal theme that respects the light/dark mode tokens |

#### CSV / TSV

| Element | Detail |
|---|---|
| Container | `overflow-auto` (both axes) |
| Table | `w-full border-collapse text-sm` |
| Header row | `bg-[--color-bg-base] sticky top-0 z-10`; cells: `px-3 py-2 font-medium text-[--color-text-primary] border-b border-[--color-border-subtle] whitespace-nowrap` |
| Data rows | `border-b border-[--color-border-subtle] last:border-0`; cells: `px-3 py-2 text-[--color-text-secondary] whitespace-nowrap` |
| Alternating row shading | Even rows: `bg-[--color-surface-hover]/40` |
| Header metadata | Column count + row count shown in the panel header metadata line: "CSV · 1,240 rows · 8 columns · 48 KB" |

#### Images (`.png`, `.jpg`, `.gif`, `.svg`, `.webp`)

| Element | Detail |
|---|---|
| Default | Image centered, `object-contain`, scaled to fit panel width while preserving aspect ratio; `p-6` padding |
| Click to zoom | Click opens a lightbox overlay: image at natural size (capped at `90vw × 90vh`); backdrop `bg-black/80`; `Escape` or click backdrop to close |
| Dimensions | Shown in panel header metadata: "PNG · 1920 × 1080 px · 2.4 MB" |

#### Documents (`.docx`, `.pptx`)

| Element | Detail |
|---|---|
| Rendering | Best-effort HTML conversion; displayed in content area with `px-6 py-5 prose text-md` |
| Fallback | If conversion fails: extracted plain text in `font-mono text-sm px-4 py-4`; muted notice at top: "Full formatting unavailable — showing plain text" |

#### Unsupported Types

| Element | Detail |
|---|---|
| Layout | Centered in content area: `flex flex-col items-center justify-center h-full gap-3` |
| Icon | `FileX` Lucide icon, 40px, `--color-text-tertiary` |
| Message | `text-base text-[--color-text-secondary]` — "Preview not available for this file type" |
| Download prompt | Accent text link below: "Download the file to view it" |

---

### Behavior & Interactions

#### Opening
- Triggered by clicking the attachment chip
- Panel animates in from right: `x 100%→0, duration 200ms, ease-out`
- Chat thread compresses simultaneously via layout animation

#### Closing
- Click `✕` in header
- Press `Escape` key while focus is within the panel
- Panel animates out: `x 0→100%, duration 150ms, ease-in`; chat thread expands

#### Scroll
- Content area scrolls independently from the chat thread
- Scroll position is preserved within the session if the user clicks away and returns to the same file

#### Multi-file
- Clicking a different chip while the viewer is open swaps content in place (no second panel)
- Content area fades out then fades in with new content: `opacity 1→0, duration 100ms` then `0→1, duration 150ms`
- Header filename and metadata update simultaneously with the content swap

#### Resize
- Panel width is draggable via the resize handle on the left edge
- Width is clamped between min `360px` and max `70% of main content area`
- Width preference is saved to `localStorage` key `fileviewer_width`

---

### Loading State

While the file is being fetched or parsed:

| Element | Detail |
|---|---|
| Header | Filename and metadata areas replaced with skeleton rectangles: `bg-[--color-surface-hover] rounded-[--radius-md] animate-pulse`; filename width ~60%, metadata width ~40% |
| Content area | 6–8 skeleton rows of varying widths (simulate text lines): `h-4 rounded bg-[--color-surface-hover] animate-pulse mx-6 my-2` |

---

### States

| State | Visual Treatment |
|---|---|
| **Loading** | Skeleton header and content placeholders; `animate-pulse` |
| **Rendered** | Full content displayed; scrollable; action buttons active |
| **Error** | Content area: centered `AlertCircle` icon (40px, `--color-feedback-error`) + "Failed to load file." message + "Try again" accent text link |
| **Unsupported** | Content area: centered `FileX` icon + "Preview not available" message + download link |
| **Empty** | Content area: centered `FileText` icon + "This file is empty." in `text-[--color-text-tertiary]` |
 
---
 
### Accessibility
 
- Panel should be a `<aside>` or `role="complementary"` landmark
- Focus should move into the panel when it opens (`focus` on close button or first interactive element)
- `Escape` key closes and returns focus to the triggering chip
- All interactive elements keyboard-navigable
- Screen reader announces panel open/close state
- Sufficient color contrast for text and UI chrome (WCAG AA minimum)
 
---

## Responsive Behavior
 
| Breakpoint | Behavior |
|---|---|
| Desktop (>1024px) | Side panel, chat compresses |
| Tablet (768–1024px) | Side panel, chat may fully hide or show at reduced width |
| Mobile (<768px) | Full-screen overlay; back button or swipe-down to dismiss |
 
---
 
## Non-Goals (v1)
 
- In-viewer editing or annotation
- Commenting or highlighting within the viewer
- Version history
- Collaborative viewing
- AI-powered summarization panel within the viewer (future consideration)
 
---
 
## Open Questions
 
- Should scroll position persist across sessions (not just within-session)?
- Should the viewer support printing directly?
- For CSV, should we support basic column sorting in the table?
- Should there be a "Copy all text" button in the header for plain text files?