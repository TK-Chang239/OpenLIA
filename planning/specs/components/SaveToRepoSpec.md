# SaveToRepo Spec

## Tool Overview
 
The `SaveToRepo` button allows users to persist generated reports into the `Repository` — the centralized store of saved outputs accessible across the product. When a user is satisfied with a generated report, they can click `SaveToRepo` to archive it with metadata for future reference.
 
The button appears on all report thumbnails (attachment chips) and inside the `FileViewer` panel. It is scoped exclusively to **generated reports** — not to arbitrary uploaded files — and is available to all departments across all pages of the product.
 
Saving is a deliberate, one-click action with no form or confirmation dialog. Once saved, the button transitions to a persistent saved state to prevent duplicate saves and provide clear confirmation.
 
---
 
## Tool Functionalities
 
### Core: Save Report to Repository
 
On click, the button writes the report to the `Repo` along with the following metadata:
 
| Metadata Field | Description | Source |
|---|---|---|
| `report_id` | Unique identifier for the saved report | System-generated (UUID) |
| `filename` | Original report filename including extension | Derived from the report file |
| `generated_at` | Timestamp when the report was originally generated | Set at generation time; read at save time |
| `saved_at` | Timestamp when the user explicitly saved the report | Set at save time (UTC) |
| `department` | The department that generated the report | Derived from session/user context |
| `saved_by` | User ID or name of the user who clicked `SaveToRepo` | Derived from auth context |
 
**Implementation note:** The `generated_at` and `department` values should be attached to the report object at generation time, not inferred at save time. `SaveToRepo` only reads these values — it does not compute them.
 
### Toggle: Save and Unsave
 
- The button toggles the report's presence in the `Repo`
- Once saved, the button transitions to a **saved state** (checkmark icon); clicking it again removes the report from the `Repo` and reverts the button to its default state
- Unsave is a deliberate one-click action with no confirmation dialog, mirroring the save interaction
- If the report is removed from the `Repo`, it can be saved again — the button returns to its default (unsaved) state and is fully clickable
 
### Save Feedback
 
| Event | Button Feedback | Duration |
|---|---|---|
| Save click (in progress) | Brief loading spinner inside button | Until API responds |
| Save success | Icon → ✓ checkmark; button enters saved state | Until user unsaves |
| Unsave click (in progress) | Brief loading spinner inside button | Until API responds |
| Unsave success | Icon reverts to default bookmark; button enters unsaved state | Until user saves again |
| Save failure | Icon → ⚠ warning, red tint; tooltip shows reason | 2s then reverts to default |
| Unsave failure | Icon → ⚠ warning, red tint; tooltip shows reason | 2s then reverts to saved state |
| Already saved (page load) | Button renders directly in saved/checkmark state | Persistent |
 
- On save success, transition to saved state; on unsave success, revert to default state
- If the operation fails, the button reverts to its pre-click state so the user can retry
 
### Conflict Handling
 
- If a save request is made for a report already in the `Repo` (e.g. a race condition or duplicate request), the API should return a success response — do not surface an error to the user
- If an unsave request is made for a report not in the `Repo` (e.g. already removed by another session), the API should return a success response — do not surface an error
- The button should reflect the actual state of the report in the `Repo` after each operation
 
### Error Handling
 
| Error Scenario | User-facing Behavior |
|---|---|
| Network failure (save) | Button shows ⚠ state, tooltip: "Save failed — please try again" |
| Network failure (unsave) | Button shows ⚠ state, tooltip: "Remove failed — please try again" |
| Auth error | Button shows ⚠ state, tooltip: "You don't have permission to perform this action" |
| Repo storage full (save) | Button shows ⚠ state, tooltip: "Repository is full — contact your admin" |
| Unknown error | Button shows ⚠ state, tooltip: "Something went wrong — please try again" |
 
---
 
## Tool Design
 
### Surfaces
 
The `SaveToRepo` button appears in two surfaces, mirroring the placement of the `FileDownloadButton`:
 
#### 1. Attachment Chip (Thumbnail)
 
```
┌──────────────────────────────────────────┐
│  📄  q1-macro-briefing.pdf   🔖  ↓      │
└──────────────────────────────────────────┘
                               ↑   ↑
                        SaveToRepo  Download
                        (left of Download)
```
 
- Icon-only button
- Positioned immediately **left of** the `FileDownloadButton` on the right side of the chip
- Follows the same hover-visibility rule as `FileDownloadButton`: hidden by default on desktop, revealed on chip hover or keyboard focus; always visible on touch
- Does not interfere with the chip's primary click action (opening `FileViewer`)
 
#### 2. File Viewer Panel Header
 
```
┌────────────────────────────────────────────────────────────┐
│  q1-macro-briefing.pdf       [🔖 Save to Repo] [↓ Download] [✕] │
│  PDF · 8 pages · Macro Research                            │
└────────────────────────────────────────────────────────────┘
```
 
- Icon + label button, always visible (not hover-gated)
- Positioned **left of** the `FileDownloadButton`, which is left of the close (`✕`) button
- Button order in header (left → right): `Save to Repo` → `Download` → `✕`
 
---

### Attachment Chip Button Design

The attachment chip container visual spec is defined in `FileViewerSpec.md`. The `SaveToRepo` button is one of the action buttons on the right side of that chip.

| Property | Spec |
|---|---|
| Element | Icon-only `<button>` |
| Icon | `Bookmark` (Lucide) — 14×14px; stroke in default state, filled in saved state |
| Touch target | `w-7 h-7` (28×28px) — `flex items-center justify-center` |
| Visibility | `opacity-0 pointer-events-none` by default; `opacity-100 pointer-events-auto` on chip hover or keyboard focus; always visible on touch |
| Position | Right side of chip, immediately left of `FileDownloadButton`; `gap-1` between them |
| Background | `transparent`; hover: `bg-[--color-surface-hover] rounded-[--radius-sm]` |
| Cursor | `pointer` |
| Transition | Opacity: `--duration-fast ease` on chip hover; icon state: `--duration-fast` |
 
**States:**
 
```
Default (chip not hovered):   opacity: 0, pointer-events: none
Chip hovered:                 opacity: 1, pointer-events: auto
Button hovered:               background: subtle fill
Button active (click):        background: slightly darker fill
Save loading:                 spinner icon, pointer-events: none
Saved:                        icon → ✓ filled checkmark, opacity: 1 always (not hover-gated),
                              cursor: pointer — clickable to unsave
Saved + button hovered:       background: subtle error tint, icon → stroke bookmark (unsave hint)
Unsave loading:               spinner icon, pointer-events: none
Unsave success:               reverts to Default state (opacity: 0 unless chip is hovered)
Save error:                   icon → ⚠, tint red for 2s then revert to Default
Unsave error:                 icon → ⚠, tint red for 2s then revert to Saved
```
 
Note: once in **saved state**, the button remains visible at full opacity on the chip at all times (not hidden behind hover), so users can see at a glance that a report has been saved and can click to unsave without hovering first.
 
---
 
### File Viewer Header Button Design
 
| Property | Spec |
|---|---|
| Element | Icon + label `<button>` |
| Label | "Save" (default) / "Saved" (saved state) / "Remove" (saved + hovered) |
| Icon | `Bookmark` Lucide icon, 14×14px, left of label; stroke default, filled saved |
| Height | `h-8` (32px) |
| Padding | `px-2.5` horizontal |
| Border | `border border-[--color-border-secondary]` |
| Border radius | `rounded-[--radius-md]` (6px) |
| Font | `text-sm text-[--color-text-secondary]` |
| Background | `transparent`; hover: `bg-[--color-surface-hover]` |
| Position | Top-right of header, immediately left of Download button; `gap-1.5` between buttons |
| Always visible | Yes — no hover gate |
 
**States:**
 
```
Default:            ghost button, border visible, label: "Save to Repo"
Hovered:            background fill (surface secondary token)
Active (click):     background slightly darker
Save loading:       spinner replaces icon, label: "Saving…", pointer-events: none
Saved:              icon → ✓ filled, label: "Saved", border color → success token, cursor: pointer
Saved + hovered:    background: subtle error tint, border color → error token,
                    icon → stroke bookmark, label: "Remove from Repo"
Unsave loading:     spinner replaces icon, label: "Removing…", pointer-events: none
Unsave success:     reverts to Default state
Save error:         icon → ⚠, label: "Failed", red tint for 2s then revert to Default
Unsave error:       icon → ⚠, label: "Failed", red tint for 2s then revert to Saved
```
 
---
 
### Icon Spec
 
Use a consistent icon across both surfaces that clearly communicates "save" or "archive" — distinct from the download arrow used by `FileDownloadButton`.
 
**Recommended icon:** A bookmark (🔖) or inbox-tray symbol. Do not reuse the download arrow — the two actions must be visually distinguishable at a glance.
 
- Stroke-based SVG in default state; switch to filled variant in saved state to reinforce permanence
- Icon color inherits from button text color token in default state
- In saved state, icon color shifts to `--color-feedback-success` token
 
---
 
### Tooltip
 
| Context | Tooltip text |
|---|---|
| Chip (default) | `"Save to Repo"` |
| Chip (saved, not hovered) | `"Saved to Repo"` |
| Chip (saved, hovered) | `"Remove from Repo"` |
| Viewer header (default) | `"Save to Repo"` |
| Viewer header (saved, not hovered) | `"Saved to Repo"` |
| Viewer header (saved, hovered) | `"Remove from Repo"` |
| Error state | Varies by error (see Error Handling table above) |
 
- 400ms hover delay before tooltip appears
- Tooltip position: above button on desktop; below if near top of viewport
- Max width: 240px
 
---
 
### Light / Dark Mode
 
All colors use design tokens:
 
| Token | Usage |
|---|---|
| `--color-icon-primary` | Default icon stroke/fill |
| `--color-surface-secondary` | Button hover background |
| `--color-border-secondary` | Viewer header button border (default state) |
| `--color-border-success` | Viewer header button border (saved state) |
| `--color-text-primary` | Button label text |
| `--color-feedback-success` | ✓ icon color and border in saved state |
| `--color-feedback-error` | ⚠ icon tint + button tint in error state |
 
---
 
## Access
 
The `SaveToRepo` button is available:
 
- On **all report thumbnails** across the product, regardless of department or page
- Inside **all `FileViewer` windows** opened from a report thumbnail
- For **all departments**: stock research, earnings, morning briefing, retail sentiment, macro research, and any future departments
- For **all authenticated users** — no role-gating in v1
 
The button is **not** shown on non-report file attachments (e.g. raw data uploads, user-uploaded reference documents). It is exclusively a report output action.
 
---
 
## Accessibility
 
- Chip button (icon-only): `aria-label="Save to Repo"` in default state; `aria-label="Remove from Repo"` in saved state (reflects the action that will be taken on click)
- Viewer header button: visible label is primary; `aria-label` updates to `"Remove from Repo"` in saved state
- Do **not** use `aria-disabled` or `disabled` on the button in saved state — the button is fully interactive and triggers unsave on click
- Loading state: `aria-busy="true"` while a save or unsave request is in flight; `aria-label` updates to `"Saving…"` or `"Removing…"` accordingly
- State change announcements via `aria-live="polite"` region: announce "Report saved to Repository" on save success, "Report removed from Repository" on unsave success, "Save failed — please try again" or "Remove failed — please try again" on error
- Keyboard: focusable via `Tab`; activated via `Enter` or `Space` in both default and saved states
- Saved state chip button: remains visible at full opacity and focusable even when chip is not hovered, so keyboard users can discover the saved status and unsave without hovering
 
---
 
## Responsive Behavior
 
| Breakpoint | Chip Button | Viewer Header Button |
|---|---|---|
| Desktop (>768px) | Hidden until chip hover or focus (except in saved state, always visible) | Always visible, icon + label |
| Mobile (<768px) | Always visible | Always visible; label may collapse to icon-only if space is constrained alongside `FileDownloadButton` and `✕` |
 
On mobile, maintain a minimum **44×44px** touch target using padding or a pseudo-element hit area, consistent with `FileDownloadButton`.
 
---
 
## Non-Goals (v1)
 
- **Save with custom label or notes** — no tagging or annotation at save time
- **Bulk save** — no "save all" action; each report is saved individually
- **Repo browsing UI** — the `SaveToRepo` button is the write-side only; the `Repo` view is a separate spec
- **Duplicate detection across departments** — reports from different departments with the same filename are treated as distinct entries
- **Save conflict resolution** — if two users save the same report simultaneously, both saves succeed; no merge or conflict UI
 
---
 
## Open Questions
 
- Should `saved_by` capture user ID, display name, or both? What is the display format inside the `Repo`?
- What is the storage limit per department in the `Repo`, if any? Does hitting the limit block saves or trigger a warning?
- Should there be a visual indicator on the `Repo` nav item (e.g. a badge) when new reports are saved, to drive users to the `Repo`?
- If a report is regenerated (new version), should saving the new version create a new `Repo` entry or overwrite the previous one?
- Should the `SaveToRepo` button appear on reports in a "preview" or "draft" state, or only on finalized reports?
- Who has permission to view saved reports in the `Repo` — only the saving user, the whole department, or the whole organization?