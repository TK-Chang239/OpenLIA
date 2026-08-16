# Setup Wizard Spec

## Page Overview

The Setup Wizard is a guided, resumable configuration flow shown on first launch of an OpenLIA instance. It collects everything the server needs to start real department work: deployment mode, user identity (or admin account in company mode), AI model configuration, data providers, optional access control, and an AI review that maps configured providers to the department requirements manifest. On completion it writes a `wizard_completed_at` record to the server config store and routes the user into the app.

The wizard runs in the same frontend that serves the main app; there is no separate installer. Users who want to consume a company-hosted OpenLIA deployment do not run the wizard -- they open the server URL their admin provides and land on `/login`.

> **Cross-reference note (2026-04-15):** This spec has been updated to reflect decisions from `database-design.md`: SQLite-only engine, AES-256-GCM encryption at rest for API keys, invite-only registration as v1 default, deployment recipes (Cloudflare Tunnel / Docker+Caddy / LAN), and new env vars (`OPENLIA_SECRET_KEY`, `OPENLIA_TRUST_PROXY_HEADERS`, `OPENLIA_COOKIE_SECURE`). Tier configuration in Step 3 is gated by the **required-tier set** — the union of `DEFAULT_TIER` across enabled departments — rather than the earlier "zero-or-many models per tier with no blocking requirement" rule.

---

## Entry Conditions

The frontend calls `GET /setup/status` on mount and routes based on the response:

| `mode` | `wizard_completed` | Behavior |
|---|---|---|
| `personal` | false | Render the wizard. |
| `personal` | true | Route to `/` (main app). |
| `company` | false | Render the wizard (company branch). |
| `company` | true | Route to `/login`. |

When the wizard is suppressed, all `/setup/*` endpoints return `410 Gone`.

---

## Deployment Mode

### Mode Detection Order

The server resolves mode from, in precedence order:

1. `OPENLIA_MODE` env var (`personal` or `company`) — wins if set.
2. The wizard's Welcome step selection, persisted to the config store on completion.
3. Default: `personal`.

If `OPENLIA_MODE` is set in env, the Welcome step renders the mode pre-selected and the toggle is disabled with a `from environment` badge.

### Mode-Specific Behavior

**Personal mode** binds the server to `127.0.0.1`, disables auth, and skips the Admin account and Access control steps.

**Company mode** binds the server to `0.0.0.0` (or the admin-specified address), enables auth, and adds Admin account + Access control steps. During the wizard itself the server remains bound to loopback regardless of mode to prevent a networked attacker from racing a local setup; it rebinds on restart after wizard completion.

---

## Flow

Personal path — 5 steps:

1. Welcome / Mode
2. Identity
3. AI Models
4. Data Providers
5. Review

Company path — 6 steps:

1. Welcome / Mode
2. Admin account
3. AI Models
4. Data Providers
5. Access control
6. Review

Navigation is linear with Back/Next. Users cannot jump to later steps.

---

## Resume

Every Save writes to the server. `GET /setup/status` returns the `current_step` and `completed_steps`. If the user closes the tab mid-flow, the next visit opens on the first incomplete step with earlier answers intact and editable.

Only one wizard session is active at a time. A second browser hitting `/setup` sees "Setup is already in progress in another window. Take over?" with a confirm button that invalidates the prior session token.

---

## Configuration Storage and Env Precedence

### Storage Model

The server reads config from three layered sources at startup, in precedence order:

1. Process environment (`OPENLIA_*` vars — set via shell, Docker `-e`, or a user-authored `.env` file loaded by python-dotenv on server boot).
2. DB `config_store` rows (written by the wizard or the Settings page).
3. Hardcoded defaults.

The DB is the canonical store. The wizard never writes to a `.env` file. Env vars are a one-way override lane for ops and Docker deploys.

### Read-Only Fields

Values resolved from the environment render as read-only inputs with a `from environment` badge in the wizard and Settings UI. User Saves submit only editable fields; env-overridden fields are skipped.

### Who Writes the `.env` File

| Who | When | What they do |
|---|---|---|
| Personal user | Never, typically | Runs `openlia serve`, walks through the wizard. Values land in the DB. Zero files touched. |
| Company admin via wizard | First launch on a team server | Runs `openlia serve`, picks Company mode in the wizard. Values land in the DB. Zero files touched. |
| Power user / Docker admin | Ops-driven deploys | Hand-writes `.env` or sets Docker `-e` flags. The repo ships `.env.example` as the canonical template. `.env` is in `.gitignore`. |

No wizard-authored `.env` is generated. `.env.example` in the repo is the only file-based entry point.

### Env Var Surface

The server reads the following, all prefixed `OPENLIA_`:

```
# Deployment
OPENLIA_MODE                     # personal | company (default: personal)
OPENLIA_BIND_HOST                # default: 127.0.0.1 personal / 0.0.0.0 company
OPENLIA_BIND_PORT                # default: 8000
OPENLIA_DB_URL                   # default: sqlite:///~/.openlia/openlia.db
OPENLIA_AUTH_ENABLED             # default: inferred from MODE

# Secrets and security
OPENLIA_SECRET_KEY               # base64-encoded 32-byte AES key for API key encryption at rest
                                 # falls back to auto-generated ~/.openlia/secret.key (0600)
OPENLIA_TRUST_PROXY_HEADERS      # true | false (default: false) — trust X-Forwarded-For/Proto
OPENLIA_COOKIE_SECURE            # true | false (default: true company / false personal)

# LLM provider credentials (env vars reference — admin enters key names during wizard)
# The wizard stores provider configs in the DB (encrypted). These env vars are an override lane
# for ops/Docker deploys. Each provider row can optionally reference an env var by name instead
# of storing the key in the DB.

# Per-department LLM overrides (all optional)
OPENLIA_LLM_DEPARTMENT_<UPPER_ID>_TIER        # "thinking" | "everyday" | "quick"

# Data providers: priority order per category (comma-separated provider IDs)
OPENLIA_PROVIDERS_FINANCIAL      # e.g. fmp,eodhd
OPENLIA_PROVIDERS_NEWS            # e.g. newsapi_ai,mediastack
OPENLIA_PROVIDERS_SOCIAL          # e.g. x,reddit
OPENLIA_PROVIDERS_SEARCH          # optional; e.g. brave,tavily (web-search providers)

# Per-provider credentials (env var name is referenced by the provider row)
OPENLIA_PROVIDER_<ID>_API_KEY

# MCP-mode providers
OPENLIA_PROVIDER_<ID>_MCP_URL
OPENLIA_PROVIDER_<ID>_MCP_AUTH_HEADER

# Access control (company mode)
OPENLIA_SIGNUP_POLICY            # invite_only | closed | open (default: invite_only for company)
OPENLIA_SIGNUP_ALLOWED_DOMAINS   # comma-separated domain allowlist (applied on top of invite)
```

Display name and admin password have no env equivalent — they are wizard-only.

---

## Steps

### Step 1 — Welcome / Mode

A full-screen two-card picker: **Personal** and **Company**. Each card shows a short description and is click-to-select; selection is indicated by an accent-colored border. The footer's Next button advances after a card is selected. The Back button is hidden on Step 1.

Footer hint: *"Trying to use a company deployment someone else set up? Close this and open the URL your admin gave you — no install needed."*

If `OPENLIA_MODE` is set in env, the inherited card is auto-selected, the other is disabled, and a `from environment` badge appears on the active card.

Saves via `POST /setup/mode`.

### Step 2a — Identity (Personal)

Single field: **Display name** (required, 1–60 chars, plain text).

Helper text: *"This is the name LIA departments will use when addressing you."*

Saves via `POST /setup/identity`.

### Step 2b — Admin Account (Company)

Fields:
- **Email** (required, validated format)
- **Password** (required, min 12 chars, strength indicator)
- **Confirm password**
- **Display name**

Section note: *"You are creating the first administrator for this deployment. Additional users sign up on the login page per the policy you'll choose in step 5."*

Saves via `POST /setup/admin`, which creates the first user with `role = admin` and argon2-hashed password. Returns `409` if an admin already exists.

### Step 3 — AI Models

Three grouped tier slots in one step, following `llm-provider-design.md`.

Short explainer at the top: *"OpenLIA uses a top-tier Thinking model for deep analysis, an Everyday model for general chat and standardized tasks, and a Quick model for classification and lightweight jobs. Each department uses a sensible default tier, which you can change later in Settings. You can put any model in any slot — the tier is a routing label, not a restriction."*

**Thinking model** (deep reasoning, long-form report drafting):
- Provider dropdown: OpenAI, Anthropic, Google Gemini, OpenRouter, OpenAI-compatible, Ollama (6 options).
- Model selector:
  - OpenAI / Anthropic / Gemini — dropdown live-populated from each provider's `/models` endpoint once a valid API key is entered; a shipped default is pre-selected (see `llm-provider-design.md` § Shipped tier defaults per provider).
  - OpenRouter — free-text model-name input. Helper text: *"Paste a model ID from [openrouter.ai/models](https://openrouter.ai/models)."*
  - OpenAI-compatible — dropdown probes `{base_url}/models` with a text-input fallback on 404.
  - Ollama — free-text model-name input. Helper text: *"Use the model name shown by `ollama list`."*
- API key input (hidden for Ollama local).
- Base URL input (visible only for OpenAI-compatible and Ollama).
- **Advanced capability flags** (collapsible disclosure):
  - Hidden for named providers (OpenAI / Anthropic / Gemini / OpenRouter) — capability flags come from the shipped map.
  - Shown for OpenAI-compatible and Ollama as checkboxes: streaming, tool_calling, structured_output, vision — pre-filled from the shipped best-guess entry; user can correct.

**Everyday model** (general chat and standardized tasks): same controls as Thinking. Shipped default pre-selects the Everyday variant per provider.

**Quick model** (cheap/fast for classification, micro-tasks, and the Step 6 AI review): same controls as Thinking. Shipped default pre-selects the Quick variant per provider. Capacity note: *"The Quick model runs the AI review at the end of this wizard, as well as runtime structured micro-tasks."*

Users may put the same provider/model/key combination in multiple slots -- e.g. run everything on one top-tier model -- and OpenLIA will faithfully do so. No enforcement of tier quality.

**Required-tier gating.** The wizard reads each enabled department's `DEFAULT_TIER` (declared in `core/openlia/departments/<id>.py`) and computes the **required-tier set** — the union of those defaults across all enabled departments. Every required tier must have at least one green model before Next is enabled. The required-tier set is recomputed live as the user toggles departments on/off in earlier steps; Step 3 displays it inline beneath the tier cards:

> *"Required by your enabled departments: **Thinking** (Equity Research, Macro Research), **Everyday** (Secretary, Earnings Update, Morning Briefing), **Quick** (Retail Sentiment, Macro Research T4/T5, Panic Thermometer). Configure at least one model in each of these tiers to continue."*

A tier *not* in the required set may still be configured (it remains useful for future departments and per-user overrides), but is not gated. If a required tier has no green model, the corresponding tier card displays a blocking error: *"This tier is required by <department list>. Add at least one working model to proceed."*

On Save per slot, the server pings the provider (`list_models` where applicable, plus a 1-token completion) and shows inline green/red status. API keys entered in the wizard are **encrypted at write time** using the AES-256-GCM scheme from `database-design.md` Section 5 -- the UI shows "(stored encrypted)" next to saved keys. Next is enabled when **every required tier** has ≥ 1 green model.

Saves via `POST /setup/models`. Live test via `POST /setup/models/test`. Payload carries provider entries per tier. The admin can add multiple models to a single tier; one can be marked as tier default.

### Step 4 — Data Providers

A sidebar-tabs layout inside the step:

- Left column: four tabs — **Financial** (required), **News** (required), **Social** (optional), **Web Search** (optional). Each tab shows a count badge of configured providers.
- Right column: for the active tab, an ordered list of configured providers with drag handle, name, connection status pill, and per-row actions (edit, remove). Below the list: a single `+ Add <category> provider` button.

Clicking `+ Add` transitions the right panel into the **add-provider form** (content-panel takeover).

#### Add-Provider Form

Segmented control selects one of three modes: **Built-in / MCP URL / OpenAPI**.

**Built-in mode.** Provider dropdown populated from shipped catalog templates (per `data-provider-design.md`), plus an API key input. Helper text: *"Pick from providers OpenLIA ships catalog support for. Your key is stored locally."*

**MCP URL mode.** A single URL input, plus an optional auth header field behind an "Advanced" disclosure. Above the URL input, a prominent info card:

> **Heads up — MCP authentication.** OpenLIA doesn't support OAuth for MCP providers. If your MCP endpoint requires authentication, include your API key directly in the URL as a query parameter. Example:
>
> `https://mcp.example.com/sse?api_key=sk_live_xxxxxxxxxxxxxxxx`
>
> If your provider uses a static header instead (e.g. `Authorization: Bearer …`), use the Advanced field below.

Helper text under the URL input: *"Your URL is saved as-is — including any API key you paste in it."*

**OpenAPI mode.** OpenAPI spec URL or file upload, plus an API key input. The key is injected per the spec's declared auth scheme (API key header, query param, or bearer).

All three modes share a Cancel / Test / Save row. Test runs a minimal connectivity call. Save runs Test first and rejects on failure. Cancel returns to the provider list.

#### List Behavior

- Drag-to-reorder within a category; priority feeds the data-provider spec's user-priority resolution.
- Each row has inline edit (re-opens the add-provider form in edit mode) and remove (confirmation inline).
- Per-row re-test available via `POST /setup/providers/{id}/test`.

#### Web Search Tab

Optional fourth category. Lists configured web-search providers (Brave Search API, Tavily, Serper, You.com) used by departments that benefit from fresh web context when the resolved LLM does not support native web search. Same row layout as other categories; `api_key` mode only (MCP mode not applicable).

Helper text above the list: *"Optional. OpenLIA uses a web-search provider when the active LLM does not natively support web search. If you leave this empty, departments that declare web search as a preferred capability will run without it — you'll see an amber advisory on the Review step but never a block."*

#### Step Gate

Next is enabled only when **≥1 green Financial provider AND ≥1 green News provider** are configured. Social and Web Search are optional.

On leaving the step, the wizard kicks off the AI review in the background so Step 5/6 loads with results ready (or a short wait) rather than starting fresh.

Saves via `POST /setup/providers`, `PATCH /setup/providers/{id}`, `DELETE /setup/providers/{id}`.

### Step 5 -- Access Control (Company only)

Four grouped areas:

- **Signup policy** (segmented control):
  - **Invite-only** (v1 default, recommended). Helper text: *"You'll create invite links in Settings after setup. Share them with your team."*
  - **Closed** -- no public registration; admin creates accounts manually via CLI.
  - **Open signup** (reserved for v2, shown as disabled with "coming soon" badge).
- **Email domain allow-list** (optional, visible for any policy): text input for `@domain.com` entries, comma-separated. Applied on top of invite validation. Helper text: *"Optional. Restrict registrations to specific email domains."*
- **Server bind address** (text input) -- default `0.0.0.0`. Helper text explains network exposure implications.
- **Server port** (number input) -- default `8000`.

**Deployment guidance** (collapsible section below the bind fields):

> **How should users reach this server?**
>
> - **Cloudflare Tunnel (recommended):** Run `cloudflared tunnel` alongside `openlia serve`. Cloudflare handles TLS, DNS, and DDoS protection. No port forwarding needed. Set `OPENLIA_TRUST_PROXY_HEADERS=true` and `OPENLIA_COOKIE_SECURE=true`.
> - **Docker + Caddy:** Run OpenLIA behind a Caddy reverse proxy with auto-provisioned Let's Encrypt TLS. Requires a public domain and port 443.
> - **LAN only:** Users access via `http://<lan-ip>:8000`. No TLS. Suitable for small offices on one network. Set `OPENLIA_COOKIE_SECURE=false`.

Section note: *"Changes to bind address and port take effect after you restart the server."*

Saves via `POST /setup/access_control`.

### Step 6 -- Review

Auto-runs the AI review when the user arrives (or shows cached results from a Step 4 pre-run). The review is executed by the **Quick-tier** LLM configured in Step 3 -- the same model OpenLIA uses at runtime for structured micro-tasks and `find_more_data` expansion. Quick is guaranteed to be configured here whenever any enabled department defaults to Quick (Step 3's required-tier gating ensures it). In the rare case where no enabled department requires Quick *and* the admin chose not to configure it, the review falls back through Everyday → Thinking. If no model is configured at all (only possible when zero departments are enabled), the review is skipped with a warning.

**Unconfigured tier handling:** All required tiers are guaranteed populated by Step 3's gating, so the review only ever encounters empty *non-required* tiers. Those are surfaced as informational notes ("Quick tier is empty -- not currently required by any enabled department; configure later in Settings if you enable departments that use it") and do not block Finish.

**Running state.** Linear progress bar plus "Mapping <provider> endpoints to department requirements…" label with a Cancel button that returns to Data Providers.

**Results state.** Summary line at top (e.g. *"6 of 7 departments ready. Retail Sentiment disabled. 3 advanced capabilities unavailable."*). Below: a 2-column grid of department readiness cards.

Card states:

| State | Styling | Meaning |
|---|---|---|
| Ready | Green left border, green pill | All basic requirements mapped with confidence ≥ 0.7. |
| Ready + advanced gaps | Amber left border, amber pill | All basic mapped; one or more advanced requirements unavailable. Non-blocking. |
| Disabled | Gray left border, gray pill | Department requires optional capability that is not configured (e.g. Retail Sentiment with no sentiment source). Department will be hidden from the main app. |
| Blocked | Red left border, red pill | Basic requirement unmet. Finish is disabled until resolved. |

Each card has a "details" expander listing basic + advanced requirements, the provider chosen for each, and any unmet advanced requirement names.

**Failure state.** If any required department is blocked, Finish is disabled with an inline CTA: *"Go back to Data Providers to add a provider that covers: `<unmet types>`."*

Finish triggers `POST /setup/finish`, which:
1. Validates that no department is Blocked.
2. Writes `wizard_completed_at` and the resolved `mode` to the config store.
3. Clears the in-progress `wizard_state` row.
4. Returns a redirect target: `/` in personal mode, `/login` in company mode.

Company completion also shows a "Setup complete — restart the server to apply company-mode networking" banner on the redirect target, since the wizard-time server is still loopback-bound.

---

## API Surface

All endpoints live under `/setup/*`. None require auth because they only function while `wizard_completed == false`; after completion they return `410 Gone`. In personal mode before completion, non-loopback origins are rejected.

| Method | Path | Purpose |
|---|---|---|
| GET | `/setup/status` | Returns `{mode, wizard_completed, current_step, completed_steps, env_overrides}`. |
| POST | `/setup/mode` | Body: `{mode}`. Rejected if env sets `OPENLIA_MODE`. |
| POST | `/setup/identity` | Personal only. Body: `{display_name}`. |
| POST | `/setup/admin` | Company only. Body: `{email, password, display_name}`. Returns `409` if admin exists. |
| POST | `/setup/models` | Body: `{thinking, everyday, quick}`. Each slot: `{provider, model, api_key?, base_url?, capabilities?}`. |
| POST | `/setup/models/test` | Body: `{provider, model, api_key, base_url?}`. Returns `{ok, latency_ms, error?}`. |
| GET | `/setup/providers` | Returns providers across all categories in priority order. |
| POST | `/setup/providers` | Body: `{category, entry: ProviderEntry}`. Runs validation ping; returns `{ok, entry_id, error?}`. |
| PATCH | `/setup/providers/{id}` | Edit fields or change priority (`{priority: N}`). |
| DELETE | `/setup/providers/{id}` | Remove a provider. |
| POST | `/setup/providers/{id}/test` | Re-ping a stored provider. |
| POST | `/setup/access_control` | Company only. Body: `{signup_policy, allowed_domains?, bind_host, bind_port}`. |
| POST | `/setup/review/run` | Kicks off AI review. Returns `{review_id}`. |
| GET | `/setup/review/{id}` | Poll for review progress and results. |
| POST | `/setup/finish` | Writes completion state and returns `{redirect}`. Rejected if any required department is Blocked. |

---

## Data Model

All tables are defined in `database-design.md`. The wizard writes to:

- **`wizard_state`** -- singleton row tracking wizard progress, current step, and intermediate `step_data` JSON. Cleared on completion.
- **`config_store`** -- KV table for `wizard.completed` flag and miscellaneous settings.
- **`users`** -- inserts the admin user (Step 2b, company mode) or seeds the `local` user (personal mode).
- **`signup_policy`** -- singleton row written on Step 5 (company) or seeded as `closed` (personal).
- **`llm_providers`** -- one row per configured provider credential set (Step 3). Provider/connector secrets are encrypted at rest with **Fernet** (AES-128-CBC + HMAC-SHA256), keyed by `OPENLIA_SECRET_KEY` / `~/.openlia/secret.key`.
- **`llm_models`** -- one row per admin-added model, assigned to a tier with optional `is_tier_default` flag (Step 3).
- **`connectors`** -- one row per configured data source / tool provider (Step 4), replacing the dropped `data_providers` table. Carries the multi-mode `LaunchSpec` JSON; secrets are stored in the encrypted `secrets` column.
- **`runner_callable_specs`** -- the resolved `(department_id, need_id) -> CallableSpec` mapping, replacing the dropped `data_provider_requirement_mapping` table (populated by connector resolve/approve).
- **`web_search_providers`** -- optional web search backends (Step 4 Web Search tab). Secrets encrypted at rest.

> **Note (2026-08-16):** the legacy `data_providers` and `data_provider_requirement_mapping` tables were removed in connector-redesign-v2 (see `projectStructure.md` §Database tables). This section previously still named them; corrected to the `connectors` / `runner_callable_specs` model.

Secrets are **never** stored in `config_store`. Encryption uses Fernet, not AES-256-GCM; see `secrets_crypto.py` and `database-design.md` for the scheme.

---

## Error Handling

| Scenario | Behavior |
|---|---|
| Ping fails on AI model save | Inline red error under the slot; Save is rejected; Back/Next stay enabled. |
| Ping fails on data provider save | Inline red error on the add-provider form; the row is not added. |
| AI review model unreachable during Review step | Error card with Retry and "Back to AI Models" buttons. |
| Basic requirement unmet for a required department | Red card listing unmet requirement types. Finish is disabled. Inline CTA to revisit Data Providers. |
| Network timeout mid-review | Review marked `cancelled`. Wizard polls and shows "Timed out — retry." |
| Server restart mid-wizard | Wizard state is DB-backed; resume works. In-flight review is not auto-resumed; user re-runs it. |
| User edits a provider after completing review | Review is marked stale and re-runs on entering the Review step. |
| Env var changes between sessions | `GET /setup/status` recomputes `env_overrides` on every call. DB values stay intact but shadowed. |
| OpenAPI spec fails to parse | Parse errors shown inline under the spec URL/file field; provider not added. |
| Admin signup called after an admin exists | `409 Conflict`. UI shows "An administrator is already configured — reset the wizard state to re-run" with reference to `openlia wizard reset`. |

---

## User Interface Design

### Overall Chrome

| Element | Spec |
|---|---|
| Container | Full-viewport overlay, `bg-[--color-bg-base]`, no main-app sidebar |
| Wizard card | `max-w-[880px] w-[90%] mx-auto my-10`, `bg-[--color-bg-elevated] rounded-[--radius-lg] shadow-md border border-[--color-border-subtle]` |
| Step header | `h-14 flex items-center justify-between px-6 border-b border-[--color-border-subtle]`; left: step title `text-lg font-semibold`; right: stepper pill `Step N of M` `text-xs text-[--color-text-secondary]` |
| Progress bar | 2px bar below header, `bg-[--color-accent-primary]` scaled to `completed_steps / total_steps`; transition `--duration-base ease-out` |
| Content body | `px-8 py-6`, inner `max-w-[640px]`; overflow scrolls |
| Footer | `h-16 flex items-center justify-between px-6 border-t border-[--color-border-subtle]`; Back (ghost) left; Next/Save (accent filled) right |

### Buttons

Primary (Next / Save / Finish) states mirror the Save button in `SettingsPageSpec.md`:

| State | Spec |
|---|---|
| Disabled | `bg-[--color-surface-active] text-[--color-text-tertiary] cursor-not-allowed h-10 px-5 rounded-[--radius-md] text-sm font-medium` |
| Enabled | `bg-[--color-accent-primary] text-white h-10 px-5 rounded-[--radius-md] text-sm font-medium hover:bg-[--color-accent-hover]` |
| Loading | `opacity-80 cursor-not-allowed`; `Loader2` 14px `animate-spin` + "Saving…" label |
| Success | `bg-[--color-feedback-success] text-white`; `Check` 14px + "Saved"; returns to enabled after 1.5s |

Test buttons use an outline style: `h-9 px-3 rounded-[--radius-md] border border-[--color-border-secondary] text-sm`.

### Mode Cards (Step 1)

| Element | Spec |
|---|---|
| Card | `flex-1 p-6 border border-[--color-border-subtle] rounded-[--radius-lg] bg-[--color-bg-elevated] cursor-pointer hover:border-[--color-border-secondary]`; selected: `border-[--color-accent-primary] ring-2 ring-[--focus-ring-color]` |
| Icon | 32px, top of card |
| Title | `text-lg font-semibold text-[--color-text-primary] mt-3 mb-1` |
| Description | `text-sm text-[--color-text-secondary] leading-relaxed` |
| Selection indicator | Accent-colored border + ring on click; no separate Pick button |
| Inherited card | Adds `from environment` badge top-right; non-inherited card is dimmed and non-interactive |

### Status Pills

Used on provider rows and readiness cards.

| Pill | Spec |
|---|---|
| Connected / Ready | `bg-[--color-feedback-success]/15 text-[--color-feedback-success] text-xs px-2 py-0.5 rounded-full` |
| Advanced gaps | `bg-[--color-feedback-warning]/15 text-[--color-feedback-warning]` |
| Disabled | `bg-[--color-surface-active] text-[--color-text-tertiary]` |
| Error / Blocked | `bg-[--color-feedback-error]/15 text-[--color-feedback-error]` |

### Read-Only Env-Overridden Fields

Input uses the read-only field style from `SettingsPageSpec.md` (`bg-[--color-surface-hover]`) plus a right-aligned badge: `text-[10px] font-medium text-[--color-text-tertiary] px-1.5 py-0.5 bg-[--color-surface-active] rounded-[--radius-sm] uppercase tracking-wide` reading `from environment`.

### Sidebar Tabs (Step 4)

| Element | Spec |
|---|---|
| Container | `flex gap-6`; sidebar `w-44 flex-shrink-0` |
| Tab | `flex items-center justify-between px-3 py-2 rounded-[--radius-md] text-sm cursor-pointer`; inactive: `text-[--color-text-secondary] hover:bg-[--color-surface-hover]`; active: `bg-[--color-surface-active] text-[--color-text-primary] font-medium` |
| Count badge | `text-[10px] px-1.5 py-0.5 bg-[--color-surface-hover] rounded-full text-[--color-text-tertiary]` |

### Provider Row

| Element | Spec |
|---|---|
| Row | `flex items-center justify-between px-3 py-2 border border-[--color-border-subtle] rounded-[--radius-md] bg-[--color-bg-base] mb-2` |
| Drag handle | `GripVertical` 14px, `text-[--color-text-tertiary]`, cursor `grab` |
| Priority index | `text-xs text-[--color-text-tertiary] w-4` |
| Name | `text-sm text-[--color-text-primary] font-medium` |
| Status pill | Right-aligned |
| Action icons | `Edit2`, `Trash2` each 14px, appear on hover, `text-[--color-text-secondary]` |

### Add-Provider Form (Takeover)

| Element | Spec |
|---|---|
| Header | Back chevron + "Add <Category> Provider" `text-lg font-semibold` |
| Segmented control | `flex p-1 bg-[--color-surface-hover] rounded-[--radius-md] w-fit mb-5`; option `px-3 py-1.5 rounded-[--radius-sm] text-sm`; active `bg-[--color-bg-elevated] shadow-sm font-medium` |
| Field wrapper | `flex flex-col gap-1.5 mb-5` |
| Label | `text-sm font-medium text-[--color-text-primary]` |
| Input | Matches `SettingsPageSpec` input spec |
| Advanced disclosure | `button` with chevron, reveals optional fields beneath |
| Action row | `flex justify-end gap-2 mt-6`; Cancel (ghost), Test (outline), Save (accent) |

### MCP Info Card

| Element | Spec |
|---|---|
| Container | `bg-[--color-surface-info]/10 border border-[--color-surface-info]/30 rounded-[--radius-md] p-3 mb-4 flex gap-3` |
| Icon | `Info` 16px, `text-[--color-surface-info]`, aligned top |
| Title | `text-sm font-semibold text-[--color-text-primary] mb-1` — "MCP authentication" |
| Body | `text-sm text-[--color-text-secondary] leading-relaxed` |
| Example code | `text-xs font-mono bg-[--color-surface-active] px-2 py-1 rounded-[--radius-sm] inline-block mt-1 break-all` |

`--color-surface-info` should be added to the token set if missing — a muted blue.

### Readiness Card (Step 6)

| Element | Spec |
|---|---|
| Card | `border border-[--color-border-subtle] rounded-[--radius-md] bg-[--color-bg-elevated] p-4 mb-2 flex justify-between gap-3`; left border 3px colored per state |
| Title | `text-sm font-semibold text-[--color-text-primary]` |
| Note | `text-xs text-[--color-text-secondary] mt-1 leading-relaxed` |
| Pill | Right-aligned |
| Details expander | `text-xs text-[--color-accent-primary] mt-2 cursor-pointer`; expands list of requirements below |

Grid container: `grid grid-cols-2 gap-3`. Disabled-state cards may span both columns via `col-span-2` when the note is long.

### Animations

- Step transition: content `opacity 0→1, translateX 8px→0, 180ms ease-out` on forward nav; mirrored on back.
- Add-provider takeover: list `opacity 1→0, scale 0.98`; form `opacity 0→1, scale 1.02→1`, 150ms.
- Review running: subtle shimmer on the per-provider progress label.
- Progress bar: width transition `--duration-base ease-out`.

---

## Accessibility

- Wizard root is `role="dialog" aria-modal="true" aria-labelledby="wizard-title"`.
- Focus moves to the step's first focusable field on entry.
- All form fields use `<label>`; inline errors link via `aria-describedby`.
- Progress communicated via `role="progressbar" aria-valuenow aria-valuemax`.
- Sidebar tabs in Step 4 use `role="tablist"`; panels `role="tabpanel" aria-labelledby`.
- Readiness pills have `aria-label` with full text ("Equity Research ready, 2 advanced gaps").
- All interactive elements keyboard-reachable in logical tab order.
- Esc does nothing (no dismiss mid-wizard).
- Sufficient color contrast for all text and pills (WCAG AA).

---

## Responsive Behavior

| Breakpoint | Behavior |
|---|---|
| Desktop (≥1024px) | Centered card as specified. Step 4 sidebar tabs on the left. |
| Tablet (768–1024px) | Card full-width with 24px side gutters. Step 4 sidebar collapses into a horizontal tab bar above the content. |
| Mobile (<768px) | Wizard fills viewport, no card margins. Step 4 sidebar becomes a dropdown selector. Password strength meter wraps below its input. |

---

## Configurations

- **Thinking-tier LLM:** Captured in Step 3. Default for departments like Equity Research and Macro Research that perform deep reasoning and long-form report drafting. See `llm-provider-design.md`.
- **Everyday-tier LLM:** Captured in Step 3. Default for Secretary, Earnings Update, and Morning Briefing. Balanced quality/speed.
- **Quick-tier LLM:** Captured in Step 3. Runs the Step 6 AI review, all runtime structured micro-tasks (Retail Sentiment classification, Macro Research T4/T5 assessments, Panic Thermometer scoring), and `find_more_data` catalog search.
- Any tier slot can be overridden per-department, either by selecting a different tier or by pinning a specific model, from Settings → Models after wizard completion.
- The wizard page itself does not invoke any department or produce any report.

---

## Non-Goals (v1)

- Provider discovery from a remote registry (only shipped catalog templates + user-supplied MCP/OpenAPI specs).
- Provider test with sample data preview; the Test button only confirms connectivity.
- OAuth / OIDC authentication for MCP providers. Users with OAuth-protected MCP endpoints must front them with their own proxy that translates to API-key-in-URL.
- Switching modes after completion (requires manual `openlia wizard reset` + env flip, documented in ops docs).
- Password reset / forgot-password inside the wizard (handled by the Login spec post-completion).
- Multi-admin invite flow inside the wizard (Access control step's policy choice is the only surface; invites are issued from Settings post-setup).
- Importing config from a YAML/TOML file (admin-authored `.env` remains the only file-based path).
- Wizard-authored `.env` file generation (duplicates DB state, leaks plaintext keys to disk).
- Localization of the wizard UI (English only for v1).

---

## Open Questions

- ~~**Secrets encryption at rest.**~~ **Resolved (2026-04-15):** API keys are encrypted at rest with AES-256-GCM, keyed by `OPENLIA_SECRET_KEY` env var or `~/.openlia/secret.key`. Secrets are never stored in `config_store`. See `database-design.md` Section 5.
- **Review model cost visibility.** Should Step 3 show an estimated per-run cost for the review model based on average requirement-manifest size and provider pricing? Useful for users on paid APIs; adds complexity to the wizard UI.
- **Review cancel behavior.** If the user clicks "Back to Data Providers" during a running review, should the in-flight LLM call be cancelled server-side (save tokens) or allowed to complete (save latency on return)? Current plan: cancel.
- **Resume across browsers.** Wizard state is DB-backed and unauthenticated in personal mode. Should a second browser on the same machine seamlessly resume, or require take-over confirmation? Current plan: take-over confirmation for both browsers and sessions.
