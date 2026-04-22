# Setup Wizard Spec

## Purpose
The Setup Wizard is a guided first-launch flow that lets a fresh OpenLIA install be brought online without editing `.env` files by hand. It collects the minimum configuration needed to reach a working state — LLM provider + key, EODHD key, and (in company mode) initial admin credentials — and writes them to the server's config store. After the wizard finishes, the user lands on the normal product home page.

Per PLAN.md §Configuration, the wizard and `.env` / environment variables are two paths into the **same** server-side config store. If both provide a value, the environment variable wins. This lets advanced users skip the wizard entirely by pre-populating `.env` before starting the server; the wizard detects already-configured values and prefills or skips those steps.

## When the Wizard Runs

The server exposes `GET /config/bootstrap-status`, which returns one of:

| Status | Meaning |
|---|---|
| `needs_setup` | Required keys missing; the frontend routes the user to the wizard regardless of the URL they requested |
| `ready` | Core config is complete; wizard is never shown |

The frontend calls this endpoint on app startup before any route is rendered. If the response is `needs_setup`, the router forces the user into `/setup` and will not release them until the wizard completes.

In **personal mode**, the setup wizard is reachable at any time from the main Settings page for users who want to update their keys through the UI rather than editing `.env`. In **company mode**, only users with `is_admin=true` can open it from Settings; non-admins see a placeholder.

## Mode Differences

- **Personal mode**: one-step flow — enter LLM provider + key, EODHD key, optional NewsAPI key. No user account created (there is no user system in personal mode).
- **Company mode**: the above **plus** a final step that creates the initial administrator account (username + password). This is the bootstrap route for the very first admin — after that, further users are created via the `openlia user create` CLI.

## Steps

### Step 1 — Welcome
- Product wordmark, one-sentence description, a "Get started" button.
- Shown once to set expectations; small, not obstructive.

### Step 2 — LLM Provider
- Radio / card selector: OpenAI, Anthropic, OpenRouter, Ollama, "Custom OpenAI-compatible endpoint".
- Dynamic fields based on the selection:
  - OpenAI / Anthropic / OpenRouter: API key input (password-masked with show/hide toggle); model dropdown populated from a static allowlist per provider.
  - Ollama: base URL input (defaults to `http://localhost:11434`); model dropdown populated by calling `GET {base_url}/api/tags` at validation time.
  - Custom: base URL + API key + model name (free text).
- A "Test connection" button fires a one-shot probe request to the server (`POST /config/llm/test`) which calls the core LLM adapter with the entered values and returns success or the underlying error string. The user cannot advance to the next step until the test passes, unless they explicitly check "Skip verification" with an inline warning.

### Step 3 — Data Sources
- **EODHD API key** — required; same password-masked input + "Test connection" pattern calling `POST /config/eodhd/test`.
- **NewsAPI.ai key** — optional in v1; skipping it disables news-driven indicators in the Panic Thermometer but does not block setup.
- **X / Twitter API credentials** — optional; required only if Retail Sentiment should run. Skipping it disables Retail Sentiment.

### Step 4 — Admin Account (company mode only)
- Username (required)
- Password (required, with show/hide toggle and strength hint)
- Confirm password
- "Create admin" button submits to `POST /auth/bootstrap-admin`, which:
  - Verifies no user exists yet (the endpoint 409s otherwise — protects against replay)
  - Creates the user with `is_admin=true` via the same hashing module used by `AccountManagementSpec.md`
  - Immediately logs the new admin in by calling the same session-issuing path as `/auth/login`, so they're authenticated when they land on Home

### Step 5 — Finish
- Summary card: mode, LLM provider + model, data sources enabled, admin username (company mode)
- "Go to OpenLIA" button: writes all collected values to the config store in a single transaction, marks bootstrap complete, and redirects to `/`.

## Persistence

All config values collected by the wizard are stored server-side — either in the database (for values that should live through redeploys) or written to a managed `.env.local` file that the server loads on startup. The storage location is an implementation detail of the server package; the frontend never sees raw key material after the wizard submits them.

Values already set via environment variable at startup are **read-only** in the wizard: the corresponding fields are displayed as "Managed by environment — change in `.env` to update" and their inputs are disabled.

## Security

- The wizard is only usable while `bootstrap-status == needs_setup` for unauthenticated access. After that, accessing `/setup` requires admin auth (company mode) or is simply a shortcut to the Settings equivalent (personal mode).
- `POST /config/llm/test` and `POST /config/eodhd/test` never log the submitted credentials. The server caches the value in memory for the duration of the bootstrap session only.
- `POST /auth/bootstrap-admin` is a one-shot endpoint; it refuses further calls once any user exists.
- All wizard traffic should go over the same TLS as the rest of the app. Nothing special is logged on failed probes beyond a generic error.

## UI Notes

The wizard reuses the standard form field, toggle, and button components from `SettingsPageSpec.md`. Its visual shell is a centered card (`max-w-[560px]`) on a neutral background, much like `LoginPageSpec.md`, with a slim step indicator (`1 ── 2 ── 3 ── 4 ── 5`) at the top and prev/next buttons at the bottom of each step.

## Non-Goals (v1)

- Importing config from a file drop
- Re-running the wizard to rotate individual keys (the Settings page owns key rotation in a future iteration; for now, `.env` is the rotation path)
- Multi-admin bootstrap (only one admin is created here; any others come from the CLI)
- Interactive Ollama model pull / download
- Network diagnostics beyond the per-provider "Test connection" button

## Open Questions

- Should the wizard collect the deployment mode (personal vs company), or should it be forced by the starting environment variable? Default assumption: mode is set externally via `OPENLIA_MODE` and the wizard only reads it.
- Should we offer preset "profile" presets (e.g. "OpenAI + EODHD only")? Default assumption: no — keep the wizard literal in v1.
