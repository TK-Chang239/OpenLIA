# Settings Page Spec

## Page Overview
The Settings Page allows the user to manage account preferences and application configuration. Changes take effect immediately on save. The page is organized into four top-level sections: General (display and notification preferences), Models (LLM tier preferences for users; full model roster CRUD for admins), Account (identity, security, and language), and Admin (visible to admins only: invite management, user management, password reset requests, model roster CRUD, data provider CRUD).

> **Cross-reference note (2026-04-15):** This spec has been updated to reflect decisions from `database-design.md`: admin-only API key management, user-facing model picker (per-tier preference from admin roster), admin-approved password reset review panel, invite management, no per-user BYO keys, and `must_change_password` change-password flow.

## Page Functionalities
1. **Edit Display Name**: Allows the user to set the name that LIA departments use when addressing them in responses.
2. **Notification Preferences**: Allows the user to toggle in-app and email notifications for report completions.
3. **Appearance**: Allows the user to switch between light and dark mode.
4. **Change Account Email**: Allows the user to update the email address associated with their account. Requires password confirmation.
5. **Change Password**: Allows the user to update their password by providing their current password and a new one. Also handles the `must_change_password` flow (set by admin password reset).
6. **Language Settings**: Allows the user to set the display language, the language departments respond in, and the language reports are generated in.
7. **Save Changes**: Changes within each section are saved explicitly via a Save button. Unsaved changes prompt a confirmation dialog if the user attempts to navigate away.
8. **Admin Panel** (admin only): Manage invites, users, pending password reset requests, LLM model roster, and data providers.

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
- Models
- Account
- Admin (visible only when `current_user.is_admin = true`)

The Models item is visible to all authenticated users. In company mode, non-admin users see a read-only roster of available models per tier plus a per-tier preference picker. Admins see the full model roster CRUD surface. The Admin section is hidden entirely for non-admin users.

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
| Password confirmation input | Standard field spec |
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

### Models Section

Displays the three LLM tiers (Thinking, Everyday, Quick) and lets users pick their preferred model per tier from the admin's configured roster. Content is role-gated. Full model roster CRUD lives in the Admin section (see below).

#### User view (non-admin, company mode)

Three tier sections -- Thinking, Everyday, Quick -- each showing:

| Element | Detail |
|---|---|
| Tier label | "Thinking", "Everyday", or "Quick" with a short description of what the tier is used for |
| Available models list | Read-only list of models the admin has configured for this tier. Each row shows: display name, provider name, connection status pill. |
| "Not configured yet" state | When a tier has zero models, show: "Your admin hasn't set up a *thinking*-tier model yet." with muted styling. |
| My preference picker | Dropdown: "Use tier default" (which model is the default is shown), or pick from the available models. Selecting a model writes to `user_llm_preferences (user_id, tier, model_id)`. |
| Save button | Saves the preference for this tier. |

No per-user BYO keys. Users pick from what the admin has made available; they do not enter API keys or provider credentials.

#### Admin / personal user view

Same as the user view above, plus a link per tier: "Manage models in Admin panel" that navigates to Admin -> Models. In personal mode, the admin view is the only view and the full model CRUD is inline (since there's no separate Admin section -- personal mode users see the admin controls directly within each tier card).

#### Per-department tier defaults

Below the three tier sections (visible to all users): a read-only reference panel listing each department with its default tier and an info icon showing `DEFAULT_TIER_REASON`.

| Department | Default tier |
|---|---|
| Secretary | Everyday |
| Equity Research | Thinking |
| Earnings Update | Everyday |
| Morning Briefing | Everyday |
| Retail Sentiment | Quick |
| Macro Research | Thinking |
| Panic Thermometer | Quick |

Admin can override per-department tier routing from Admin -> Models.

---

### Account Section

Controls identity, security, and language settings.

#### Account Email

| Element | Detail |
|---|---|
| Current email | Displayed as read-only text |
| Change Email button | Opens an inline form to enter a new email address |
| Password confirmation | Required to confirm the change |

#### Change Password

| Element | Detail |
|---|---|
| Current password input | Full-width, labeled "Current Password", with show/hide toggle |
| New password input | Full-width, labeled "New Password", with show/hide toggle and strength indicator |
| Confirm new password input | Full-width, labeled "Confirm New Password" |
| Save button | Saves the password change |
| Must-change-password banner | When `must_change_password = true`, an amber banner is shown above the form: "Your administrator has reset your password. Please set a new one to continue." The Settings page opens directly to this section and other navigation is blocked until the password is changed. After successful change, the flag is cleared and normal navigation resumes. |

#### Language

| Setting | Type | Options |
|---|---|---|
| Display language | Dropdown | English, Traditional Chinese |
| Department response language | Dropdown | English, Traditional Chinese |
| Report output language | Dropdown | English, Traditional Chinese, Both |

---

### Admin Section (admin only)

Visible only when `current_user.is_admin = true`. In personal mode the synthetic `local` user is always admin, so this section is always visible. The Admin section contains five subsections: Invites, Users, Password Reset Requests, Models, and Data Providers. Each subsection is separated by a group divider (same spec as Setting Group above).

#### Admin sidebar

Within the Admin content panel, a horizontal tab bar selects the active subsection:

| Element | Spec |
|---|---|
| Tab bar | `flex gap-1 border-b border-[--color-border-subtle] mb-6` |
| Tab item | `px-3 py-2 text-sm cursor-pointer`; inactive: `text-[--color-text-secondary] hover:text-[--color-text-primary]`; active: `text-[--color-text-primary] font-medium border-b-2 border-[--color-accent-primary]`; transition `--duration-fast` |

Tabs: Invites, Users, Reset Requests, Models, Data Providers.

---

#### Invites

Manage `signup_invites`. Create, list, and revoke invite tokens.

| Element | Detail |
|---|---|
| Create Invite button | Accent primary button at top-right. Opens an inline form. |
| Inline create form | Fields: Label (optional, `String(128)`), Max uses (optional, integer input, NULL = unlimited), Expires (optional, date picker, NULL = never). Submit: "Create". |
| Invite list | Table with columns: Label, Token (truncated, click to copy full), Uses (use_count / max_uses or "unlimited"), Created, Expires, Status, Actions. |
| Status pill | `Active` (green), `Expired` (muted), `Revoked` (red), `At capacity` (amber). |
| Actions | "Copy link" icon button (copies full registration URL with token), "Revoke" text button (destructive, inline confirm). |
| Empty state | "No invites created yet. Create one to let users register." |

Revoking sets `revoked_at = now()`. Revoked invites stay in the list with status "Revoked" (no un-revoke in v1).

---

#### Users

Manage user accounts. List all users, disable/enable accounts, perform direct admin password reset.

| Element | Detail |
|---|---|
| User list | Table with columns: Display Name, Email, Role (Admin / User), Status (Active / Disabled), Joined (created_at), Actions. |
| Actions per user | "Disable" / "Enable" toggle button, "Reset Password" button. Admins cannot disable themselves. |
| Disable/Enable | Toggles `users.is_disabled` and emits a `user_disabled` / `user_enabled` `auth_events` row (the audit log is the source of truth for *when* the change happened). Disabled users cannot log in; their active sessions are revoked. Inline confirmation: "Disable [name]? They will be logged out immediately." |
| Reset Password (direct) | Inline confirm: "Set a temporary password for [name]?" On confirm: server generates random temporary password, sets `users.password_hash` and `users.must_change_password = true`, revokes all sessions. The temporary password is shown to the admin exactly once in a copy-ready block. Admin delivers it out-of-band. |
| Empty state | "No users registered yet." (Only the admin exists.) |
| Personal mode | User list is hidden (only the `local` user exists). |

---

#### Password Reset Requests

Review pending admin-approved password reset requests from the login page's "Forgot password?" flow.

| Element | Detail |
|---|---|
| Request list | Table with columns: User (email), Requested At, IP Address, Status, Actions. Sorted by requested_at descending. |
| Status pill | `Pending` (amber), `Approved` (green), `Rejected` (muted), `Consumed` (muted), `Expired` (muted). |
| Actions (pending only) | "Approve" button (accent), "Reject" button (destructive outline). |
| Approve flow | On click: server generates one-time token, sets status to `approved`, `expires_at = now + 24h`. The one-time reset link is displayed to the admin exactly once in a modal with a "Copy link" button. Admin copies and delivers out-of-band. The modal warns: "This link will not be shown again." |
| Reject flow | Inline confirmation. Sets status to `rejected`. |
| Non-pending rows | Read-only status display. No actions. Kept for audit visibility. |
| Filter | Dropdown filter by status (All, Pending, Approved, Rejected). Default: Pending. |
| Empty state (filtered to Pending) | "No pending password reset requests." |
| Personal mode | This subsection is hidden (no login page, no password reset flow). |

---

#### Models (admin CRUD)

Full model roster management. Create, edit, remove LLM provider credentials and model entries.

**Provider management:**

| Element | Detail |
|---|---|
| Provider list | Card per provider. Shows: label, kind pill (e.g., "openai", "anthropic"), enabled/disabled toggle, model count badge, "Edit" and "Delete" actions. |
| Add Provider button | Accent primary button. Opens a create form. |
| Create/Edit form | Fields: Kind (dropdown of supported providers), Label (text), API Key (password input, "(stored encrypted)" helper text), Env Var Name (alternative to API key, text input), Base URL (text, shown for openai_compat/ollama/self-hosted), Extra Config (JSON editor, optional). |
| Connection test | "Test Connection" button in create/edit form. Runs a 1-token completion against the provider. Shows green checkmark or red error inline. |
| Delete provider | Blocked if provider has models. Error: "Remove all models from this provider first." |
| Empty state | "No LLM providers configured. Add one to get started." |

**Model management (within each provider card, or as a separate tab):**

| Element | Detail |
|---|---|
| Model list per provider | Table: Display Name, Model Ref, Tier, Default (star icon if `is_tier_default`), Enabled, Actions. |
| Add Model button | Per provider. Opens an inline form. |
| Create/Edit form | Fields: Model Ref (text, provider's model identifier), Display Name (text, defaults to model ref), Tier (dropdown: Thinking/Everyday/Quick), Set as tier default (checkbox), Enabled (toggle). Overrides (expandable): temperature, max_tokens, reasoning_effort. |
| Tier default constraint | At most one default per tier. Setting a new default automatically clears the previous one (with confirmation). |
| Delete model | Inline confirm: "Remove [name]? Users who selected this model will fall back to the tier default." On delete, `user_llm_preferences` rows cascade-delete. |
| Soft reminder | Banner at the top of the Models tab if any tier has zero enabled models: "The [tier] tier has no models configured. Departments using this tier will show an error." Amber warning style. |

---

#### Data Providers (admin CRUD)

Manage data source credentials and requirement mappings.

| Element | Detail |
|---|---|
| Provider list | Card per provider. Shows: label, kind pill, enabled/disabled toggle, "Edit" and "Delete" actions. |
| Add Provider button | Accent primary button. Opens a create form. |
| Create/Edit form | Fields: Kind (dropdown of supported data source types), Label (text), API Key (password input, "(stored encrypted)"), Env Var Name (alternative to API key), Base URL (optional), Extra Config (JSON, optional). |
| Connection test | "Test Connection" button. Runs a lightweight API call (e.g., quote lookup for AAPL). Shows success/error inline. |
| Requirement mapping | Below the provider list: a table showing each requirement type (stock_quote, company_news, etc.) and which provider is assigned to it, with priority ordering. Admin can reassign via dropdown per requirement row. |
| Delete provider | Blocked if provider is assigned to any requirement mapping. Error: "Reassign or remove all requirement mappings for this provider first." |
| Empty state | "No data providers configured. Add one to enable market data." |

---

### Feedback & Messaging

| Message Type | Placement | Appearance |
|---|---|---|
| Save success | Inline below the Save button | Green confirmation text ("Saved") |
| Save error | Inline below the Save button | Red error text with reason |
| Unsaved changes warning | Modal dialog on navigation away | Standard warning dialog with "Leave" and "Stay" options |
| One-time secret display (invite link, reset link, temp password) | Modal dialog | Copy-ready block with "Copy" button, warning that value won't be shown again |

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
- LLM: The page itself does not invoke any LLM. The Models section configures which LLMs other pages use — see `llm-provider-design.md` for the full provider, tier, and resolution model. Connection Test runs a 1-token completion against the selected model; this is the only LLM traffic originating from this page.

---

## Non-Goals (v1)
- OAuth provider integration (Google, GitHub, etc.)
- Billing and subscription management
- Per-user API key management (admin-only in v1)
- Per-department notification settings
- Export of account data
- Self-service account deletion (admin can hard-delete via DB if needed; see `AccountManagementSpec.md` § 16 Non-Goals)

---

## Open Questions
- Should appearance theme changes sync across devices, or be per-device?
- Should email change require re-verification of the new email before it takes effect?
- Should the "Both" report language option render English and Traditional Chinese side-by-side, or as separate sections within the same report?
