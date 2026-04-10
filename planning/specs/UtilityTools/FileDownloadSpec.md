# File Download Spec

## Overview

The File Download Button allows users to save any file attached to a conversation to their local device. It appears in two surfaces: the **attachment chip** (thumbnail) inline in the chat thread, and the **File Viewer panel** header. Both instances trigger the same underlying download behavior but are styled to fit their respective contexts.

The button is intentionally lightweight — one click, no confirmation dialog, no modal. It should feel like a native browser download.

---

## Surfaces

### 1. Attachment Chip (Thumbnail)

The download button appears as an **icon-only button** on the attachment chip, visible on hover (desktop) or always visible (mobile/touch).

```
┌──────────────────────────────────────────┐
│  📄  quarterly-report.pdf   🔖  ↓       │
└──────────────────────────────────────────┘
                               ↑   ↑
                        SaveToRepo  Download
                        (both appear on hover)
```

- Positioned at the far right of the chip, immediately **right of** the `SaveToRepo` button
- Does not overlap the filename or file type icon
- Clicking it downloads the file without opening the File Viewer
- The chip itself remains clickable (opens viewer) — the download button is a separate hit target

### 2. File Viewer Panel Header

The download button appears as an **icon + label button** in the File Viewer header, always visible regardless of hover state.

```
┌────────────────────────────────────────────────────────────┐
│  quarterly-report.pdf    [🔖 Save to Repo] [↓ Download] [✕] │
│  PDF · 12 pages                                            │
└────────────────────────────────────────────────────────────┘
```

- Positioned in the top-right of the header, immediately **right of** the `SaveToRepo` button and **left of** the close (`✕`) button
- Button order in header (left → right): `Save to Repo` → `Download` → `✕`
- Always visible (not hover-triggered)
- Labeled with text + icon for clarity at this larger surface size

---

## Functionalities

### Core: Trigger Download

- On click, initiates a browser-native file download using the original filename
- File is downloaded as-is — no format conversion, no compression
- Filename used for the download matches the original uploaded filename exactly
- If the browser cannot download the file inline (e.g. certain MIME types), it falls back to opening in a new tab

**Implementation note:** Use an `<a>` tag with `download` attribute and an object URL, or a server-signed download URL depending on whether files are served from blob storage or a CDN.

```html
<!-- Client-side blob approach -->
<a href="{objectUrl}" download="{originalFilename}">Download</a>
 
<!-- Server URL approach -->
<a href="{signedUrl}" download="{originalFilename}" target="_blank">Download</a>
```

### Filename Preservation

- The downloaded file must retain the original filename including extension
- Special characters in filenames (spaces, parentheses, unicode) should be preserved where the OS allows; sanitize only characters that are truly illegal on the target OS (`/`, `\`, `:`, `*`, `?`, `"`, `<`, `>`, `|`)
- Do not append suffixes like `_download` or timestamps unless a filename collision handling strategy is explicitly defined

### Multi-file Behavior

- Each attachment chip has its own independent download button scoped to that file
- In the File Viewer, the download button always refers to the currently displayed file
- There is no "download all" button in v1 (see Non-Goals)

### Download Feedback

- On click: button briefly shows a **checkmark icon** (✓) for ~1.5s to confirm the download was initiated, then reverts to the download icon
- No toast notification, no modal — feedback is contained within the button itself
- If the download fails (e.g. file expired, network error): button briefly shows an **error state** (⚠ icon + red tint) for ~2s, then reverts; a tooltip explains the failure


| Event           | Button Feedback                | Duration         |
| --------------- | ------------------------------ | ---------------- |
| Click (success) | Icon → ✓ checkmark             | 1.5s then revert |
| Click (failure) | Icon → ⚠ warning, red tint     | 2s then revert   |
| Hover           | Tooltip: "Download [filename]" | While hovered    |


### File Expiry Handling

- If a file is no longer available (e.g. server-side expiry), the button should be visually disabled and show a tooltip: "File no longer available"
- Do not silently fail — the user must understand why the download didn't work

---

## Design

### Attachment Chip Button

The attachment chip container visual spec is defined in `FileViewerSpec.md`. The Download button is the rightmost action button on the chip.

| Property | Spec |
|---|---|
| Element | Icon-only `<button>` |
| Icon | `Download` Lucide icon — 14×14px |
| Touch target | `w-7 h-7` (28×28px) — `flex items-center justify-center` |
| Visibility | `opacity-0 pointer-events-none` by default; `opacity-100 pointer-events-auto` on chip hover or keyboard focus; always visible on touch |
| Position | Rightmost action button on the chip, immediately right of `SaveToRepo`; `gap-1` between them |
| Background | `transparent`; hover: `bg-[--color-surface-hover] rounded-[--radius-sm]` |
| Cursor | `pointer` |
| Transition | Opacity: `--duration-fast ease` on chip hover; icon swap: `--duration-fast` |


**States:**

```
Default (chip not hovered): button opacity: 0, pointer-events: none
Chip hovered:               button opacity: 1, pointer-events: auto
Button hovered:             button background: subtle fill
Button active (click):      button background: slightly darker fill
Success (post-click):       icon swaps to ✓ for 1.5s
Error (post-click):         icon swaps to ⚠, tint red for 2s
Disabled (file expired):    opacity: 0.4, cursor: not-allowed
```

### File Viewer Header Button

| Property | Spec |
|---|---|
| Element | Icon + label `<button>` |
| Label | "Download" (default) / "Downloaded" (1.5s post-success) |
| Icon | `Download` Lucide icon, 14×14px, left of label |
| Height | `h-8` (32px) |
| Padding | `px-2.5` horizontal |
| Border | `border border-[--color-border-secondary]` |
| Border radius | `rounded-[--radius-md]` (6px) |
| Font | `text-sm text-[--color-text-secondary]` |
| Background | `transparent`; hover: `bg-[--color-surface-hover]` |
| Position | Immediately right of `SaveToRepo` button, left of `Close` button; `gap-1.5` |
| Always visible | Yes — no hover gate |


**States:**

```
Default:          ghost button, border visible
Hovered:          background fill (surface secondary token)
Active (click):   background slightly darker
Success:          icon → ✓, label → "Downloaded" for 1.5s then revert
Error:            icon → ⚠, label → "Failed", red tint for 2s then revert
Disabled:         opacity: 0.4, cursor: not-allowed, tooltip on hover
```

### Icon Spec

Use a single consistent download icon across both surfaces. Recommended: a downward-pointing arrow with a horizontal baseline (common in system UI iconography). Do not use a cloud icon or floppy disk icon — the arrow-with-baseline reads most universally as "download."

- Stroke-based SVG preferred for sharpness at small sizes
- Icon color inherits from button text color token (adapts to light/dark mode automatically)
- Do not use filled/solid icon variant in the default state — reserve filled for the success ✓ state to signal a state change

### Tooltip

Both button variants show a tooltip on hover:


| Context            | Tooltip text                                                |
| ------------------ | ----------------------------------------------------------- |
| Attachment chip    | `"Download [filename]"`                                     |
| File Viewer header | `"Download [filename]"` (redundant but confirms which file) |
| Disabled (expired) | `"File no longer available"`                                |


- Tooltip appears after 400ms hover delay (avoid flashing on accidental hover)
- Tooltip position: above the button on desktop; below if button is near top of viewport
- Max width: 240px; filename truncates with ellipsis if overflowing tooltip width

### Light / Dark Mode

All colors should reference design tokens, not hardcoded values, so the component adapts automatically:


| Token                       | Usage                              |
| --------------------------- | ---------------------------------- |
| `--color-icon-primary`      | Icon fill/stroke                   |
| `--color-surface-secondary` | Button hover background            |
| `--color-border-secondary`  | Viewer header button border        |
| `--color-text-primary`      | Button label text                  |
| `--color-feedback-success`  | ✓ icon tint on success             |
| `--color-feedback-error`    | ⚠ icon tint + button tint on error |


---

## Accessibility

- Button must have an accessible label at all times
  - Chip button (icon-only): `aria-label="Download [filename]"`
  - Viewer header button (icon + label): visible label is sufficient; `aria-label` not required unless icon and label differ
- Disabled state: use `aria-disabled="true"` rather than the `disabled` attribute so the button remains focusable and its tooltip is reachable via keyboard
- Success/error feedback: announce state change via `aria-live="polite"` region so screen readers confirm the download was initiated or failed
- Keyboard: button is focusable via `Tab`; activated via `Enter` or `Space`
- Do not rely on hover alone to reveal the chip button — ensure it is also reachable via keyboard focus (i.e. show the button when the chip or button itself is focused)

---

## Responsive Behavior


| Breakpoint       | Chip Button                              | Viewer Header Button                                                    |
| ---------------- | ---------------------------------------- | ----------------------------------------------------------------------- |
| Desktop (>768px) | Hidden until chip hover or focus         | Always visible, icon + label                                            |
| Mobile (<768px)  | Always visible (no hover state on touch) | Always visible; label may collapse to icon-only if space is constrained |


On mobile, the chip button should maintain a minimum touch target of **44×44px** even if the visual size is smaller, using padding or a pseudo-element hit area expansion.

---

## Non-Goals (v1)

- **Download all files** — no bulk download button in this release
- **Format conversion** — downloaded file is always the original format; no "Export as PDF" or similar
- **Progress indicator** — for large files, the browser's native download UI handles progress; no custom progress bar in v1
- **Copy to clipboard** — not a download; out of scope
- **Share link generation** — distinct feature, separate spec

---

## Open Questions

- Should the chip download button be permanently visible (not hover-gated) on desktop as well, for discoverability?
- What is the file retention/expiry policy? This determines how aggressively we need to handle the disabled/expired state.
- Should "Download" in the File Viewer header be a ghost button or a filled primary button to draw more attention to it?
- For very large files (>100MB), should we show a size warning before initiating the download?
- Should download events be logged for analytics (file type, size, surface — chip vs. viewer)?

