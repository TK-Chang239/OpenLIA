# Login Page Spec

## Page Overview
The Login Page is the entry point for all users. It handles authentication so users can access their accounts and retrieve saved data such as conversation history, portfolio, and repository reports. Unauthenticated users are redirected here before accessing any other page.

## Page Functionalities
1. **Google OAuth Login**: Allows the user to sign in with their Google account via OAuth 2.0. This is the primary and recommended sign-in method. On success, the user is redirected to the Secretary (home page). If the Google account email has no existing LIA account, one is created automatically.
2. **Email and Password Login**: Allows the user to log in with their registered email address and password. On successful login, the user is redirected to the Secretary (home page).
3. **Account Registration**: Allows new users to create an account by providing an email address and setting a password. After registration, the user is logged in automatically and redirected to the Secretary. Users who signed up via Google OAuth do not need a separate password.
4. **Forgot Password**: Displays an inline form where the user enters their email address. A password reset link is sent to that email. A confirmation message is shown after submission regardless of whether the email exists (to prevent email enumeration). Not applicable for Google OAuth accounts.
5. **Keep Me Logged In**: A checkbox that, when selected, persists the user session on the device so the user is not required to log in again on subsequent visits. When unchecked, the session expires when the browser is closed.
6. **Input Validation**: Email format and password requirements are validated on the client side before submission. Server-side validation is also enforced. Clear inline error messages are shown below the relevant field.
7. **Rate Limiting**: Failed login attempts are rate-limited server-side. After 5 consecutive failed attempts, the account is temporarily locked for 15 minutes and the user is notified on screen.

## Page Design

### Layout

All three views (Login, Register, Forgot Password) share the same centered single-column layout. Only the form content changes — no full page navigation occurs between views.

```
┌──────────────────────────────────────────────┐
│                                              │
│            [Logo + Product Name]             │
│                                              │
│   ┌──────────────────────────────────────┐   │
│   │                                      │   │
│   │       [Continue with Google]         │   │
│   │                                      │   │
│   │     ─────────── or ───────────       │   │
│   │                                      │   │
│   │          [Form Content]              │   │
│   │                                      │   │
│   │          [Primary Button]            │   │
│   │                                      │   │
│   │          [Secondary Links]           │   │
│   │                                      │   │
│   └──────────────────────────────────────┘   │
│                                              │
└──────────────────────────────────────────────┘
```

- Form card is centered horizontally and vertically on the page
- Page background is minimal — no decorative imagery
- The page respects the light/dark appearance setting from Settings, defaulting to light for unauthenticated users

---

### Visual Design

#### Page & Card

| Element | Spec |
|---|---|
| Page container | `min-h-screen bg-[--color-bg-base] flex flex-col items-center justify-center p-4` |
| Wordmark block | Above the card, centered: "LIA" `text-2xl font-semibold text-[--color-text-primary]` + "Your financial assistant" `text-sm text-[--color-text-secondary] mt-1`; `mb-6` gap below before card |
| Card | `bg-[--color-bg-elevated] border border-[--color-border-subtle] rounded-[--radius-xl] shadow-lg w-full max-w-[420px] px-8 py-10` |
| Card — mobile | `border-none shadow-none rounded-none px-6 py-8` (full-width, no card treatment) |

#### Google OAuth Button

| Element | Spec |
|---|---|
| Container | `w-full h-10 flex items-center justify-center gap-2.5 rounded-[--radius-md] border border-[--color-border-secondary] bg-[--color-bg-elevated] text-sm font-medium text-[--color-text-primary]` |
| Hover | `bg-[--color-surface-hover]`; transition `--duration-fast` |
| Icon | Google "G" SVG logo, 18px, rendered at natural colors (not tinted) |
| Label | "Continue with Google" |
| Loading | Button disabled, spinner replaces icon, `opacity-70` |

#### OR Divider

| Element | Spec |
|---|---|
| Container | `flex items-center gap-3 my-5` |
| Lines | `flex-1 h-px bg-[--color-border-subtle]` on each side |
| Text | "or" — `text-xs text-[--color-text-tertiary]` |

#### Form Fields

Applies to all text inputs across Login, Registration, and Forgot Password views.

| Element | Spec |
|---|---|
| Field wrapper | `flex flex-col gap-1.5 mb-4` |
| Label | `text-sm font-medium text-[--color-text-primary]` |
| Input | `w-full h-10 rounded-[--radius-md] border border-[--color-border-subtle] bg-[--color-bg-input] px-3 text-sm text-[--color-text-primary] placeholder:text-[--color-text-tertiary] outline-none` |
| Focus | `border-[--color-border-secondary] ring-2 ring-[--focus-ring-color]`; transition `--duration-fast` |
| Error state | `border-[--color-feedback-error] ring-2 ring-[--color-feedback-error]/20` |
| Helper text | `text-xs text-[--color-text-secondary] -mt-1` shown below label when present |
| Inline error | `text-xs text-[--color-feedback-error] flex items-center gap-1`; `AlertCircle` icon (12px) prepended; fades in `opacity 0→1, duration 150ms` |

#### Password Show/Hide Toggle

| Element | Spec |
|---|---|
| Position | Absolute right side of input, `right-3 top-1/2 -translate-y-1/2` |
| Button | `w-7 h-7 flex items-center justify-center rounded-[--radius-sm] text-[--color-text-secondary] hover:text-[--color-text-primary]`; `Eye` icon (16px) when hidden, `EyeOff` when visible |
| Input padding | `pr-10` when toggle is present |

#### Password Strength Indicator

Shown only on the Registration view's password field, below the input and above the helper text.

| Element | Spec |
|---|---|
| Bar row | `flex gap-1 mt-1.5` — 4 bars of equal width |
| Individual bar | `h-1 flex-1 rounded-full bg-[--color-border-subtle]` default (empty); filled: color varies by strength level |
| Strength 1 — Weak | 1 bar filled `bg-[--color-feedback-error]`; label "Weak" `text-xs text-[--color-feedback-error]` |
| Strength 2 — Fair | 2 bars filled `bg-[--color-feedback-warning]`; label "Fair" `text-xs text-[--color-feedback-warning]` |
| Strength 3 — Good | 3 bars filled `bg-[--color-feedback-warning]`; label "Good" `text-xs text-[--color-feedback-warning]` |
| Strength 4 — Strong | 4 bars filled `bg-[--color-feedback-success]`; label "Strong" `text-xs text-[--color-feedback-success]` |
| Label position | `flex justify-between items-center` — bars on left, label text right-aligned |

#### Keep Me Logged In Checkbox

| Element | Spec |
|---|---|
| Container | `flex items-center gap-2 mb-5` |
| Checkbox | Native `<input type="checkbox">` styled with accent color: `accent-[--color-accent-primary] w-4 h-4 rounded-[--radius-sm] cursor-pointer` |
| Label | `text-sm text-[--color-text-secondary] cursor-pointer` |

#### Primary Button

| Element | Spec |
|---|---|
| Default | `w-full h-10 rounded-[--radius-md] bg-[--color-accent-primary] text-white text-sm font-medium flex items-center justify-center` |
| Hover | `bg-[--color-accent-hover]`; transition `--duration-fast` |
| Loading | `opacity-80 cursor-not-allowed`; spinner (`Loader2` icon, 16px, `animate-spin`) replaces button label; inputs disabled |
| Disabled | `opacity-40 cursor-not-allowed` (e.g., empty required fields) |

#### Secondary Links Row

| Element | Spec |
|---|---|
| Container | `flex items-center justify-between mt-4` |
| Text links | `text-sm text-[--color-accent-primary] hover:text-[--color-accent-hover]`; transition `--duration-fast` |
| Sign up / Log in link | `mt-6 text-sm text-[--color-text-secondary] text-center`; the action text portion: `text-[--color-accent-primary] hover:text-[--color-accent-hover]` |

#### Banners (Form-Level Messages)

| Type | Spec |
|---|---|
| Container | `rounded-[--radius-md] px-4 py-3 text-sm mb-5 flex items-start gap-2`; appears above the form fields; fade-in `opacity 0→1, y -4→0, duration 150ms` |
| Error | `bg-[--color-feedback-error]/10 text-[--color-feedback-error] border border-[--color-feedback-error]/20`; `AlertCircle` icon (14px) |
| Success | `bg-[--color-feedback-success]/10 text-[--color-feedback-success] border border-[--color-feedback-success]/20`; `CheckCircle` icon (14px) |
| Warning | `bg-[--color-feedback-warning]/10 text-[--color-feedback-warning] border border-[--color-feedback-warning]/20`; `AlertTriangle` icon (14px) |

#### View Transitions

Switching between Login, Register, and Forgot Password views:
- Outgoing content: `opacity 1→0, y 0→-8, duration 100ms`
- Incoming content: `opacity 0→1, y 8→0, duration 150ms` after outgoing completes
- Focus moves to the first input of the new view on entry

---

### Login View (Default)

Entry point for returning users.

| Element | Detail |
|---|---|
| Logo + product name | Displayed above the form card |
| Continue with Google button | Full-width button with Google logo; initiates OAuth 2.0 flow |
| Divider | "or" divider separating OAuth from email/password form |
| Email input | Full-width text field, labeled "Email" |
| Password input | Full-width, labeled "Password", with show/hide toggle |
| Keep me logged in | Checkbox with label, positioned below the password field |
| Log In button | Full-width primary action button |
| Forgot password? | Text link below the button |
| Sign up link | "Don't have an account? Sign up" at the bottom of the card |

---

### Registration View

Accessed by clicking "Sign up" from the Login View.

| Element | Detail |
|---|---|
| Logo + product name | Displayed above the form card |
| Continue with Google button | Full-width button with Google logo; creates account and signs in via OAuth 2.0 |
| Divider | "or" divider separating OAuth from email/password form |
| Email input | Full-width text field, labeled "Email" |
| Password input | Full-width, with show/hide toggle and password strength indicator |
| Confirm password input | Full-width, labeled "Confirm Password" |
| Create Account button | Full-width primary action button |
| Log in link | "Already have an account? Log in" at the bottom of the card |

---

### Forgot Password View

Accessed by clicking "Forgot password?" from the Login View.

| Element | Detail |
|---|---|
| Logo + product name | Displayed above the form card |
| Instruction text | "Enter your email to receive a password reset link" |
| Email input | Full-width text field, labeled "Email" |
| Send Reset Link button | Full-width primary action button |
| Back to Log In link | Text link at the bottom of the card |

---

### Feedback & Messaging

| Message Type | Placement | Appearance |
|---|---|---|
| Inline field error | Below the relevant input field | Red text, small font |
| Form-level error | Banner above the form fields | Red background banner |
| Success message (e.g., reset link sent) | Banner above the form fields | Green background banner |
| Rate limit / account locked notice | Banner above the form fields | Yellow/warning background banner |

---

### Behavior & Interactions

#### View Transitions
- Switching between Login, Registration, and Forgot Password views swaps form content in place
- Transition animates with a short fade (~150ms)
- The URL may update to reflect the current view (e.g. `/login`, `/register`, `/forgot-password`) to support direct linking and browser back navigation

#### Google OAuth Flow
- Clicking "Continue with Google" opens the Google account selector in a popup or redirect (redirect preferred for mobile)
- On Google authorization, the backend exchanges the auth code for tokens, creates or retrieves the LIA account, and issues a session
- If the Google account is already linked to an existing email/password LIA account, the accounts are treated as the same account
- On failure (user cancels, Google error), the user is returned to the Login View with an appropriate error message

#### Form Submission
- Client-side validation runs on submit before any network request
- Fields with errors are highlighted and focused automatically
- The primary button enters a loading state (spinner) while the request is in flight
- On success, redirect occurs automatically with no additional user action required

#### Closing / Leaving
- Unauthenticated users cannot navigate away from this page to protected routes
- Navigating to any protected route while unauthenticated redirects back to Login View

---

## States

| State | Description |
|---|---|
| **Default** | Empty form, no errors, ready for input |
| **Submitting** | Primary button shows loading spinner; inputs are disabled |
| **Error** | Inline or banner error message displayed; form re-enabled for correction |
| **Success** | Redirect occurs (login/register) or success banner shown (forgot password) |
| **Rate Limited** | Form disabled with a locked notice showing remaining lockout time |

---

## Accessibility

- Form landmark uses `<main>` with a descriptive `aria-label`
- All input fields have associated `<label>` elements
- Error messages are linked to their input via `aria-describedby`
- Password show/hide toggle is keyboard accessible and announces state change to screen readers
- Primary button communicates loading state via `aria-busy="true"` during submission
- Focus is managed on view transition — moves to the first input of the new view
- All interactive elements are keyboard-navigable in logical tab order
- Sufficient color contrast for all text and UI elements (WCAG AA minimum)

---

## Responsive Behavior

| Breakpoint | Behavior |
|---|---|
| Desktop (>1024px) | Centered card with fixed max-width (~420px), ample surrounding whitespace |
| Tablet (768–1024px) | Centered card, slightly narrower margins |
| Mobile (<768px) | Full-width card with horizontal padding; no card border/shadow |

---

## Page Settings
There are no user-configurable settings for this page.

## Report Framework
There are no report frameworks for this page.

## Configurations
- LLM: None (this page does not interact with any LLM)

---

## Non-Goals (v1)
- Additional OAuth providers beyond Google (e.g. GitHub, Apple)
- Two-factor authentication (2FA)
- Magic link (passwordless) login
- Account deletion from this page
- CAPTCHA or bot detection challenges

---

## Open Questions
- Should the reset password link expire after a set time (e.g. 1 hour)? If so, what happens when an expired link is clicked?
- Should failed login attempts be per-IP, per-account, or both for rate limiting?
- Should the Registration view require email verification before first login, or allow immediate access?
- What are the minimum password requirements (length, character types)?
