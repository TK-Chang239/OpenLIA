# Settings Page Spec

## Page Overview
The Settings Page allows the user to manage account preferences and application configuration. Changes take effect immediately on save. The page is organized into two top-level sections: General (display and notification preferences) and Account (identity, security, and language).

## Page Functionalities
1. **Edit Display Name**: Allows the user to set the name that LIA departments use when addressing them in responses.
2. **Notification Preferences**: Allows the user to toggle in-app and email notifications for report completions.
3. **Appearance**: Allows the user to switch between light and dark mode.
4. **Change Account Email**: Allows the user to update the email address associated with their account. Requires password confirmation (not applicable for Google OAuth accounts).
5. **Change Password**: Allows the user to update their password by providing their current password and a new one. Not available for Google OAuth accounts.
6. **Language Settings**: Allows the user to set the display language, the language departments respond in, and the language reports are generated in.
7. **Save Changes**: Changes within each section are saved explicitly via a Save button. Unsaved changes prompt a confirmation dialog if the user attempts to navigate away.
8. **Danger Zone — Delete Account**: Allows the user to permanently delete their account and all associated data. Requires explicit confirmation before proceeding.

---

## Page Design

### Layout

The Settings Page uses a two-panel layout on desktop: a left navigation sidebar listing the settings sections, and a right content panel showing the selected section.

```
┌────────────────────────────────────────────────────────────────┐
│  Settings                                                       │
│────────────────────────────────────────────────────────────────│
│  ┌──────────────────┐  │  ┌─────────────────────────────────┐  │
│  │  General      ●  │  │  │  General                        │  │
│  │  Account         │  │  │  ─────────────────────────────  │  │
│  └──────────────────┘  │  │  Your Name                      │  │
│                        │  │  [ Display name input       ]   │  │
│                        │  │  This is how LIA addresses you  │  │
│                        │  │                                 │  │
│                        │  │  Notifications                  │  │
│                        │  │  ─────────────────────────────  │  │
│                        │  │  Response completions  [toggle] │  │
│                        │  │  Email notifications   [toggle] │  │
│                        │  │                                 │  │
│                        │  │  [ Save Changes ]               │  │
│                        │  └─────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────┘
```

- Active section is highlighted in the sidebar
- Content panel scrolls independently if the section content overflows
- On mobile, the sidebar collapses into a horizontal tab bar above the content panel

---

### Page Header

| Element | Spec |
|---|---|
| Height | 56px (`h-14`), `flex-shrink-0` |
| Background | `--color-bg-base` |
| Border | 1px bottom, `--color-border-subtle` |
| Title | "Settings" — `text-xl font-semibold text-[--color-text-primary]`, `pl-6` |

---

### Settings Sidebar (Desktop)

A secondary navigation panel, distinct from the main app Sidebar. Sits between the app Sidebar and the content panel.

| Element | Spec |
|---|---|
| Width | 200px, `flex-shrink-0` |
| Background | `--color-bg-base` |
| Border | 1px right, `--color-border-subtle` |
| Padding | `px-3 py-4` |
| Section label | `text-xs font-medium text-[--color-text-tertiary] uppercase tracking-[0.04em] px-2 pb-1 mb-1` |
| Nav item | `flex items-center px-2 py-2 rounded-[--radius-md] text-sm cursor-pointer`; inactive: `text-[--color-text-secondary] hover:bg-[--color-surface-hover] hover:text-[--color-text-primary]`; active: `bg-[--color-surface-active] text-[--color-text-primary] font-medium`; transition `--duration-fast` |

Navigation items:
- General
- Account

---

### Content Panel

| Element | Spec |
|---|---|
| Container | `flex-1 overflow-y-auto` |
| Inner max-width | `max-w-[620px] px-8 py-8` |
| Section title | `text-xl font-semibold text-[--color-text-primary] mb-6` |

---

### Setting Group

Groups of related settings within a section are visually separated.

| Element | Spec |
|---|---|
| Group container | `mb-8` |
| Group heading | `text-base font-semibold text-[--color-text-primary] mb-1` |
| Group description | `text-sm text-[--color-text-secondary] mb-4` (optional, below heading) |
| Divider | `border-t border-[--color-border-subtle] mb-6` between groups |

---

### Form Fields

| Element | Spec |
|---|---|
| Field wrapper | `flex flex-col gap-1.5 mb-5` |
| Label | `text-sm font-medium text-[--color-text-primary]` |
| Input | `h-10 rounded-[--radius-md] border border-[--color-border-subtle] bg-[--color-bg-input] px-3 text-sm text-[--color-text-primary]`; focus: `border-[--color-border-secondary] ring-2 ring-[--focus-ring-color]`; transition `--duration-fast` |
| Helper text | `text-xs text-[--color-text-secondary]` below input |
| Read-only value | `text-sm text-[--color-text-primary] px-3 py-2.5 bg-[--color-surface-hover] rounded-[--radius-md] border border-[--color-border-subtle]` |
| Field group width | Full width up to `max-w-[400px]` for single-line fields; full content width for multi-field rows |

---

### Toggle Switch

Used for on/off settings (notifications, etc.).

```
Setting label                                     [○━━━━━━]
Helper text below label                            OFF / ON
```

| Element | Spec |
|---|---|
| Row container | `flex items-center justify-between py-3 border-b border-[--color-border-subtle] last:border-0` |
| Label side | `flex flex-col gap-0.5`; label `text-sm font-medium text-[--color-text-primary]`; sub-label `text-xs text-[--color-text-secondary]` |
| Toggle track | `w-10 h-6 rounded-full relative cursor-pointer`; off: `bg-[--color-border-secondary]`; on: `bg-[--color-accent-primary]`; transition: background `--duration-base` |
| Toggle thumb | `absolute top-1 w-4 h-4 rounded-full bg-white shadow-sm`; off: `left-1`; on: `left-5`; position transition `--duration-base` |

---

### Dropdown (Language Selectors)

| Element | Spec |
|---|---|
| Trigger | `h-10 rounded-[--radius-md] border border-[--color-border-subtle] bg-[--color-bg-input] px-3 text-sm text-[--color-text-primary] flex items-center justify-between`; `ChevronDown` icon (14px, `--color-text-secondary`) right side; focus: border → `--color-border-secondary` |
| Dropdown menu | `bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[--radius-md] shadow-md py-1 min-w-[180px]`; appears below trigger |
| Dropdown option | `px-3 py-2 text-sm text-[--color-text-primary] hover:bg-[--color-surface-hover] cursor-pointer`; active option: `text-[--color-accent-primary]` + `Check` icon (14px) right-aligned |

---

### Appearance Selector

A segmented control with three options: System, Light, Dark.

| Element | Spec |
|---|---|
| Container | `flex gap-1 p-1 bg-[--color-surface-hover] rounded-[--radius-md] w-fit` |
| Option button | `flex items-center gap-1.5 px-3 py-1.5 rounded-[--radius-sm] text-sm cursor-pointer`; inactive: `text-[--color-text-secondary] hover:text-[--color-text-primary]`; active: `bg-[--color-bg-elevated] text-[--color-text-primary] font-medium shadow-sm`; transition `--duration-fast` |
| Icons | `Monitor` (System), `Sun` (Light), `Moon` (Dark) — 14px each |

---

### Change Email Inline Form

Shown when user clicks "Change Email" — expands inline below the current email display.

| Element | Spec |
|---|---|
| Expansion | `max-h-0 overflow-hidden → max-h-[240px]` height transition, `duration 200ms ease-out` |
| New email input | Standard field spec |
| Password confirmation input | Standard field spec; hidden for Google OAuth accounts |
| Save + Cancel buttons | Side by side; Save: accent filled `h-9 px-4 rounded-[--radius-md] text-sm`; Cancel: ghost `h-9 px-4` |

---

### Save Button

| State | Spec |
|---|---|
| Disabled (no changes) | `bg-[--color-surface-active] text-[--color-text-tertiary] cursor-not-allowed h-10 px-5 rounded-[--radius-md] text-sm font-medium` |
| Enabled (dirty) | `bg-[--color-accent-primary] text-white h-10 px-5 rounded-[--radius-md] text-sm font-medium hover:bg-[--color-accent-hover]`; transition `--duration-fast` |
| Saving | `opacity-80 cursor-not-allowed`; `Loader2` icon (14px, `animate-spin`) + "Saving…" label |
| Saved | `bg-[--color-feedback-success] text-white`; `Check` icon (14px) + "Saved" label; holds for `1.5s` then transitions back to disabled |
| Error | Returns to enabled state; inline error appears below the button |

---

### Inline Feedback (below Save button)

| Type | Spec |
|---|---|
| Success | `text-sm text-[--color-feedback-success] flex items-center gap-1 mt-2`; `CheckCircle` icon (14px) |
| Error | `text-sm text-[--color-feedback-error] flex items-center gap-1 mt-2`; `AlertCircle` icon (14px) |

---

### Danger Zone

A visually distinct section at the bottom of the Account panel.

```
┌──────────────────────────────────────────────────────────┐
│  border border-[--color-feedback-error]/30               │
│  rounded-[--radius-lg] p-6                               │
│                                                          │
│  Danger Zone                                             │
│  ─────────────────────────────────────────────────────   │
│  Deleting your account is permanent...                   │
│                                                          │
│  [ Delete Account ]  (outline destructive button)        │
└──────────────────────────────────────────────────────────┘
```

| Element | Spec |
|---|---|
| Container | `border border-[--color-feedback-error]/30 rounded-[--radius-lg] p-6 mt-8` |
| Section label | `text-base font-semibold text-[--color-feedback-error] mb-1` |
| Divider | `border-t border-[--color-feedback-error]/20 mb-4` |
| Warning text | `text-sm text-[--color-text-secondary] mb-4` |
| Delete Account button | `h-9 px-4 rounded-[--radius-md] border border-[--color-feedback-error] text-sm font-medium text-[--color-feedback-error] hover:bg-[--color-feedback-error]/10`; transition `--duration-fast` |

---

### Delete Account Modal

Opened by the "Delete Account" button.

```
┌──────────────────────────────────────────────────────────┐
│  Delete Account                                    [✕]   │
│──────────────────────────────────────────────────────────│
│  This action is permanent and cannot be undone.           │
│  All data including conversation history, portfolio,     │
│  and saved reports will be permanently deleted.          │
│                                                          │
│  Type your email address to confirm:                     │
│  [ your@email.com                                    ]   │
│                                                          │
│  [Cancel]           [Delete My Account]                  │
└──────────────────────────────────────────────────────────┘
```

| Element | Spec |
|---|---|
| Backdrop | `bg-black/40`, full viewport, non-dismissible by click |
| Modal | `bg-[--color-bg-elevated] rounded-[--radius-lg] shadow-lg border border-[--color-border-subtle] max-w-[480px] w-full p-6` |
| Title | `text-lg font-semibold text-[--color-feedback-error] mb-1` |
| Warning text | `text-sm text-[--color-text-secondary] mb-5` |
| Confirmation instruction | `text-sm font-medium text-[--color-text-primary] mb-2` |
| Email input | Standard input field; "Delete My Account" button is disabled until the entered email exactly matches the user's account email |
| "Delete My Account" button | `h-9 px-4 bg-[--color-feedback-error] text-white text-sm font-medium rounded-[--radius-md] hover:opacity-90`; disabled when email doesn't match: `opacity-40 cursor-not-allowed` |
| Cancel button | Outline style `h-9 px-4 border border-[--color-border-secondary] text-sm text-[--color-text-secondary] rounded-[--radius-md] hover:bg-[--color-surface-hover]` |
| Button row | `flex justify-end gap-2 mt-6` |
| Entry animation | `opacity 0→1, scale 0.97→1, duration 200ms, ease-out` |

---

### Unsaved Changes Modal

Triggered when navigating away from a section with unsaved changes.

| Element | Spec |
|---|---|
| Title | "Unsaved changes" |
| Body | "You have unsaved changes. If you leave now, they will be lost." |
| "Leave" button | Outline destructive — `border border-[--color-feedback-error] text-[--color-feedback-error] h-9 px-4 rounded-[--radius-md] text-sm` |
| "Stay" button | Accent filled — `bg-[--color-accent-primary] text-white h-9 px-4 rounded-[--radius-md] text-sm` |
| Modal size | Smaller: `max-w-[400px]` |

---

### General Section

Controls display and notification preferences.

#### Display Name

| Element | Detail |
|---|---|
| Label | "Your Name" |
| Input | Text field, pre-filled with current display name |
| Helper text | "This is the name LIA departments will use when addressing you" |
| Save button | Saves the display name change |

#### Notifications

| Setting | Type | Detail |
|---|---|---|
| Response completions | Toggle | Get an in-app notification when a department finishes a response or report |
| Email notifications | Toggle | Get an email when a report is complete |

#### Appearance

| Setting | Type | Detail |
|---|---|---|
| Theme | Toggle / segmented control | Switch between Light and Dark mode; applies immediately on selection |

---

### Account Section

Controls identity, security, and language settings.

#### Account Email

| Element | Detail |
|---|---|
| Current email | Displayed as read-only text |
| Change Email button | Opens an inline form to enter a new email address |
| Password confirmation | Required to confirm the change (not shown for Google OAuth accounts) |
| Helper text | For Google OAuth accounts: "Email is managed by your Google account" |

#### Change Password

| Element | Detail |
|---|---|
| Current password input | Full-width, labeled "Current Password", with show/hide toggle |
| New password input | Full-width, labeled "New Password", with show/hide toggle and strength indicator |
| Confirm new password input | Full-width, labeled "Confirm New Password" |
| Save button | Saves the password change |
| Availability | Hidden entirely for Google OAuth-only accounts |

#### Language

| Setting | Type | Options |
|---|---|---|
| Display language | Dropdown | English, Traditional Chinese |
| Department response language | Dropdown | English, Traditional Chinese |
| Report output language | Dropdown | English, Traditional Chinese, Both |

---

### Danger Zone

A visually distinct section at the bottom of the Account panel, separated by a red border or warning color treatment.

| Element | Detail |
|---|---|
| Section label | "Danger Zone" |
| Warning text | "Deleting your account is permanent and cannot be undone. All data including conversation history, portfolio, and saved reports will be deleted." |
| Delete Account button | Outlined button in red/destructive styling |

#### Delete Account Flow
- Clicking "Delete Account" opens a confirmation modal
- Modal requires the user to type their email address to confirm intent
- On confirmation, account and all associated data are permanently deleted and the user is redirected to the Login Page

---

### Feedback & Messaging

| Message Type | Placement | Appearance |
|---|---|---|
| Save success | Inline below the Save button | Green confirmation text ("Saved") |
| Save error | Inline below the Save button | Red error text with reason |
| Unsaved changes warning | Modal dialog on navigation away | Standard warning dialog with "Leave" and "Stay" options |
| Account deletion confirmation | Modal dialog | Destructive confirmation modal requiring email re-entry |

---

### Behavior & Interactions

#### Saving
- Each section has its own Save button; settings are not auto-saved
- The Save button is disabled until a change is detected in that section
- After saving, the button briefly shows a success confirmation state before returning to its default state

#### Navigation Guard
- If a section has unsaved changes and the user navigates to a different section or page, a confirmation dialog is shown: "You have unsaved changes. Leave without saving?"

#### Appearance Toggle
- Toggling the appearance theme applies immediately to the entire application without requiring a save

---

## States

| State | Description |
|---|---|
| **Default** | Fields populated with current saved values; Save button disabled |
| **Dirty** | At least one field in the section has been modified; Save button enabled |
| **Saving** | Save button shows loading spinner; inputs are disabled |
| **Saved** | Save button briefly shows "Saved" confirmation; returns to default state |
| **Error** | Save failed; inline error shown; inputs re-enabled for correction |

---

## Accessibility

- Page uses a `<nav>` landmark for the sidebar and `<main>` for the content panel
- Active section in sidebar is indicated with `aria-current="page"`
- All input fields have associated `<label>` elements
- Toggle switches expose state via `aria-checked`
- The Delete Account modal traps focus while open and returns focus to the trigger on close
- All interactive elements are keyboard-navigable in logical tab order
- Sufficient color contrast for all text and UI elements (WCAG AA minimum)

---

## Responsive Behavior

| Breakpoint | Behavior |
|---|---|
| Desktop (>1024px) | Two-panel layout: sidebar on left, content panel on right |
| Tablet (768–1024px) | Sidebar collapses to a horizontal tab bar above the content panel |
| Mobile (<768px) | Sidebar replaced by a dropdown section selector; content fills full width |

---

## Report Framework
There are no report frameworks for this page.

## Configurations
- LLM: None (this page does not interact with any LLM)

---

## Non-Goals (v1)
- Connected accounts management (linking/unlinking OAuth providers)
- Billing and subscription management
- API key management
- Per-department notification settings
- Export of account data

---

## Open Questions
- Should appearance theme changes sync across devices, or be per-device?
- Should email change require re-verification of the new email before it takes effect?
- What happens to saved reports and history when an account is deleted — is there a grace period or is deletion immediate?
- Should the "Both" report language option render English and Traditional Chinese side-by-side, or as separate sections within the same report?
