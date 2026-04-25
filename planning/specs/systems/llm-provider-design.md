# LLM Provider & Configuration System Design

## Purpose

Defines OpenLIA's LLM provider abstraction layer and the end-to-end user flow for configuring it. Backing system for `SetupWizardSpec.md` Step 3 and for a new Settings → Models section. Sibling of `data-provider-design.md`.

> **Cross-reference note (2026-04-15):** This spec has been updated to reflect decisions from `database-design.md`: admin-only API key management (no per-user BYO keys), `llm_providers` and `llm_models` tables replacing `config_store`-based storage, `user_llm_preferences` pointer table, AES-256-GCM encryption at rest for API keys, zero-or-many models per tier with `TierNotConfiguredError`, and revised resolver order.

This is **part 1 of 2** in the LLM system series. Part 2 — the LLM Runtime / Execution spec — will cover prompt assembly, framework/style-guide loading, tool schema construction, and the backend→frontend SSE streaming protocol.

## Scope

In scope:

- Supported providers and the adapter interface (`core/openlia/llm/`).
- Capability matrix and department requirement manifests.
- Three-tier model-role structure (Thinking / Everyday / Quick).
- Configuration storage schema (admin-managed DB tables: `llm_providers`, `llm_models`, `user_llm_preferences`).
- Runtime resolution order (user preference → tier default → any enabled in tier → `TierNotConfiguredError`).
- Wizard Step 3 extension and Settings → Models UI.
- Connection-testing flow shared by wizard and settings.
- Runtime failure behavior (retry policy, error classes, user-facing messaging).

Out of scope (deferred to the Runtime / Execution spec):

- Prompt assembly (system + user + framework injection).
- Framework (`packages/core/src/openlia/reports/frameworks/*.json`) and style-guide loading into LLM calls.
- Tool schema construction from the data-provider surface.
- Backend→frontend SSE streaming protocol (token / tool-call / report-thumbnail events).
- Web search as a department *capability* for chat/report use.

Out of scope entirely:

- Per-user BYO API keys for LLM providers (admin-only in v1; see `database-design.md`).
- Per-user data-provider API key overrides (see `data-provider-design.md`).
- Budget / spend tracking.
- OAuth / SSO for LLM provider authentication.

---

## Provider Surface (v1)

| # | Provider | Kind | Adapter | Credentials | Model listing |
|---|---|---|---|---|---|
| 1 | OpenAI | Native API | `openai` | API key | `GET /v1/models` |
| 2 | Anthropic | Native API | `anthropic` | API key | `GET /v1/models` |
| 3 | Google Gemini | Native API | `gemini` | API key | `GET /v1beta/models` |
| 4 | OpenRouter | OpenAI-compat gateway | `openrouter` | API key | User types model name |
| 5 | OpenAI-compatible | Generic catch-all | `openai_compat` | Base URL + API key | `GET {base_url}/models` (fallback: manual entry) |
| 6 | Ollama | Local | `ollama` | Base URL only (default `http://localhost:11434`) | User types model name |

Providers 1–4 have baked-in HTTPS endpoints; the user only enters a key. Providers 5–6 require a user-supplied Base URL. The catch-all (5) covers DeepSeek, Grok/xAI, Groq, Together, Fireworks, Mistral, Cerebras, Perplexity, Azure OpenAI, self-hosted vLLM, LM Studio, etc. — any provider exposing an OpenAI-compatible endpoint.

The Model dropdown for named providers (1–3) is live-populated from each provider's `/models` endpoint; shipped defaults in `core/llm/model_defaults.py` are only the initial pre-selection. OpenRouter (4) and Ollama (6) use a single text input — users paste model names directly (users look up OpenRouter models on openrouter.ai; Ollama users run `ollama list`). OpenAI-compatible (5) probes `{base_url}/models` with a text-input fallback on 404.

---

## Adapter Interface

All six adapters live under `packages/core/src/openlia/llm/` and implement one base interface (`base.py`):

```python
class LLMProvider(Protocol):
    id: str                          # "openai" | "anthropic" | "gemini" | "openrouter" | "openai_compat" | "ollama"
    capabilities: Capabilities

    def list_models(self) -> list[ModelInfo]:
        """Live list from the provider. Raises LLMProviderError on failure.
        Not invoked by the wizard/Settings UI for OpenRouter and Ollama (those use manual entry)."""

    def test_connection(self, model: str) -> TestResult:
        """1-token completion. Returns {ok, latency_ms, error?}."""

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Non-streaming completion. Raises on non-transient errors."""

    def stream(self, request: LLMRequest) -> Iterator[LLMChunk]:
        """Streaming completion. Raises on non-transient errors."""

    def capabilities_for(self, model: str) -> Capabilities:
        """Resolves the capability set for a specific model on this provider."""
```

`LLMRequest` carries the common call shape: messages, system prompt, tools (optional), response_format (optional `json_schema`), max_tokens, temperature, stop sequences. Adapters translate into each provider's wire format.

---

## Capabilities

```python
@dataclass
class Capabilities:
    streaming: bool
    tool_calling: bool
    structured_output: bool       # JSON schema / response_format
    vision: bool                  # image inputs
    web_search_native: bool       # provider's built-in web-search tool is available
    max_context_tokens: int
    max_output_tokens: int
```

The shipped capability map flags `web_search_native=true` for the model families that support it at time of release:

- Anthropic families supporting `web_search_20250305` (Claude Sonnet / Opus 4.x with the web-search tool enabled).
- OpenAI `gpt-5.4+` with `web_search_preview`.
- Google Gemini models with Google Search grounding available (Gemini 3.x Pro and Flash).
- OpenRouter when routing to any of the above upstream model IDs (the flag is inherited from the upstream family regex).

All other providers (OpenAI-compatible catch-all, Ollama, older-family models) default to `web_search_native=false`. Web search for those providers is served by the `web_search` tool the runtime builds from a configured search provider (see `llm-runtime-design.md` § Web Search).

`web_search` is also exposed as a `Capability` enum value for use in `DepartmentRequirements.preferred` only — never `required`. A department must function without web search; the `Capability.web_search` preference is satisfied if **either** the resolved model has `web_search_native=true` **or** the instance has at least one configured search provider. See the Department Requirements Manifest section below.

### Resolution order for capabilities

- **Named providers (OpenAI, Anthropic, Gemini, OpenRouter):** shipped capability map keyed by `(provider, model-family-regex)`. Lives in `core/llm/capabilities.py`. Maintainer-curated per release. Sane default applied when a model doesn't match any known family (`streaming=true, tool_calling=false, structured_output=false, max_context_tokens=8192`).
- **OpenAI-compatible catch-all:** cannot be probed reliably. On Save, wizard/Settings asks the user to confirm capability flags via checkboxes (pre-filled from a "generic modern OpenAI-compat" default: streaming + tools + JSON mode on, vision off).
- **Ollama:** `GET /api/show {model}` returns metadata including context length. Tool calling is flagged on in the shipped map only for model families known to support it reliably (`llama3.1+`, `qwen2.5+`, `mistral-nemo+`); off for others. Streaming always on. Structured output off by default unless the family is known-good.

### User override

Per `(provider, model)` capability-flags dialog in Settings → Models. Overrides stored as JSON in `config_store` under `llm.capability_override.<provider>.<model>`. Lets power users use brand-new models without waiting for a release.

---

## Department Requirements Manifest

Each department declares its LLM capability requirements:

```python
# packages/core/src/openlia/departments/equity_research.py
REQUIREMENTS = DepartmentRequirements(
    required=[Capability.streaming, Capability.structured_output, Capability.tool_calling],
    preferred=[Capability.max_context_tokens >= 64_000],
    min_output_tokens=4096,
)
```

Input to the Wizard Step 6 Review grid: resolved model capabilities are checked against each department's `required` set. Soft-gate semantics:

- All `required` met → **Ready** (green).
- All `required` met, some `preferred` missing → **Ready + advanced gaps** (amber).
- Any `required` unmet → **Disabled** (gray) for optional departments; **Blocked** (red) for core departments. Blocked state disables the Finish button.

---

## Model Roles: Three Tiers

| Tier | Purpose | Typical picks |
|---|---|---|
| **Thinking** | Deep reasoning, multi-step analysis, long-form report drafting. | Claude Opus, GPT-5.4 Pro, Gemini 3.1 Pro, DeepSeek-R1. |
| **Everyday** | Balanced speed and quality for general chat and standardized analysis. | Claude Sonnet, GPT-5.4, Gemini 3 Flash. |
| **Quick** | Cheap/fast for high-volume classification, structured micro-tasks, and author-time utilities. | Claude Haiku, GPT-5.4 mini, Gemini 3.1 Flash Lite, small Ollama. |

**No enforcement.** The tier is a *routing label*, not a gate. A user can put Claude Opus in the Quick slot if they want — OpenLIA will faithfully use Opus for every quick task. No warning, no rejection. Users who want all workloads on one top-tier model can set all three slots to the same model.

### Shipped tier defaults per provider

| Provider | Thinking | Everyday | Quick |
|---|---|---|---|
| OpenAI | `gpt-5.4-pro` | `gpt-5.4` | `gpt-5.4-mini` |
| Anthropic | `claude-opus-4-6` | `claude-sonnet-4-6` | `claude-haiku-4-5` |
| Gemini | `gemini-3.1-pro` | `gemini-3-flash` | `gemini-3.1-flash-lite` |
| OpenRouter | (user types) | (user types) | (user types) |
| OpenAI-compatible | (user types) | (user types) | (user types) |
| Ollama | (user types) | (user types) | (user types) |

Maintained in `core/llm/model_defaults.py`. This file is used only as a suggestion source for the wizard's first-run model pickers, not as a runtime fallback. Wizard/Settings Model dropdowns for named providers (1–3) live-populate from each provider's `/models` endpoint — the shipped default is only the initial pre-selection. Users are never stuck on a stale default.

### Department default tier mapping

Shipped in `core/openlia/departments/<id>.py` alongside the requirements manifest:

```python
# secretary.py
DEFAULT_TIER = ModelTier.EVERYDAY
DEFAULT_TIER_REASON = "Conversational Q&A needs a balance of speed and reasoning; Thinking is overkill, Quick struggles with nuance."
```

| Department | Default tier | Reason |
|---|---|---|
| Secretary | Everyday | Conversational Q&A needs a balance of speed and reasoning. |
| Equity Research | Thinking | Multi-section report drafting with heavy reasoning over fundamentals. |
| Earnings Update | Everyday | Standardized scorecard analysis; benefits from a solid all-rounder. |
| Morning Briefing | Everyday | News summarization with light reasoning; speed matters. |
| Retail Sentiment | Quick | High-volume classification of social posts; batched micro-tasks. |
| Macro Research | Thinking | Framework-driven analysis with long context and deep reasoning. |
| Panic Thermometer | Quick | Real-time indicator scoring; cheap and fast. |

The Settings UI surfaces `DEFAULT_TIER_REASON` in an info tooltip next to each department row.

---

## Configuration Storage

> **Cross-reference (2026-04-15):** Full table schemas are in `database-design.md` § 4. This section summarizes the storage model; the DB spec is authoritative for column definitions and constraints.

### Provider and model tables (admin-managed)

LLM configuration lives in dedicated relational tables, not `config_store`:

- **`llm_providers`** — one row per configured provider credential set. Admin can have multiple entries for the same provider type (e.g., two OpenAI keys for different budgets). Columns: `id`, `kind`, `label`, `api_key_encrypted`, `env_var_name`, `base_url`, `extra_config`, `is_enabled`.
- **`llm_models`** — admin's roster of available models. Each row is a model the admin has explicitly made available. Columns: `id`, `provider_id` (FK), `tier`, `model_ref`, `display_name`, `is_tier_default`, `is_enabled`, `overrides` (JSON: temperature, max_tokens, reasoning_effort).

**No hard requirement to populate every tier.** Admin configures zero-or-many models per tier. Setup Wizard and Settings show a soft reminder: "We recommend configuring at least one model per tier so every department works." If a department calls into an unconfigured tier, it surfaces a `TierNotConfiguredError` rather than silently downgrading.

### Per-user preferences (pointer table, no credentials)

- **`user_llm_preferences`** — per-user, per-tier model choice. Columns: `user_id`, `tier`, `model_id` (FK to `llm_models`). Users pick from the admin's roster; they do not enter API keys or provider credentials.

### Department tier overrides and capability overrides

- **Department tier overrides**: stored in `config_store` under `llm.department.<id>.tier` (one of `thinking`, `everyday`, `quick`, or null for shipped default). Admin-only.
- **Capability overrides**: stored in `config_store` under `llm.capability_override.<provider>.<model>` as a JSON blob. Admin-only.

### Secrets at rest

API keys in `llm_providers.api_key_encrypted` are encrypted with AES-256-GCM using a server-derived key. See `database-design.md` § 5 for the full encryption scheme (`OPENLIA_SECRET_KEY` env var or auto-generated `~/.openlia/secret.key`).

---

## Runtime Resolution Order

> **Cross-reference (2026-04-15):** The canonical resolver order is defined in `database-design.md` § 4 (`user_llm_preferences` section). This section restates it with the full two-stage flow.

Resolution proceeds in two stages. **Stage 1** determines which tier this call consumes; **Stage 2** resolves a concrete model within that tier.

### Stage 1 — Tier selection

```
1. A caller-supplied tier_override argument to resolve() — used by a heavy department
   that wants Quick for a specific micro-task. Trumps all below.
2. llm.department.<id>.tier in config_store, if non-null (admin override).
3. The department's shipped DEFAULT_TIER (from core/openlia/departments/<id>.py).
```

### Stage 2 — Model resolution within the tier

```
1. user_llm_preferences row for (user_id, tier) — if the pointed-to model is enabled, use it.
2. llm_models row where tier = X AND is_tier_default = true AND is_enabled = true.
3. Any enabled llm_models row in tier X (deterministic tiebreak: oldest created_at).
4. Raise TierNotConfiguredError with a message naming the empty tier.
```

The resolver looks up the model's `provider_id` to get the provider credentials (`llm_providers` row), decrypts `api_key_encrypted`, and returns a ready-to-use adapter.

The resolver is a single function in `core/openlia/llm/resolver.py`:

```python
def resolve(
    department_id: str,
    tier_override: ModelTier | None = None,
    user_id: str | None = None,
) -> LLMProvider:
    """Returns a ready-to-use LLMProvider with credentials + model bound.
    Raises TierNotConfiguredError if the resolved tier has no enabled models.

    Note: TierNotConfiguredError is a defense-in-depth safeguard. The Setup
    Wizard's required-tier gating (see SetupWizardSpec § Step 3) ensures this
    is unreachable for tiers any enabled department defaults to. It can still
    fire if (a) an admin deletes the last model in a required tier post-setup,
    or (b) a caller passes tier_override pointing at an unconfigured tier."""
```

Departments call it like this:

```python
llm = resolve(department_id="equity_research", user_id=user_id)
# llm is a ready provider with model + credentials + capabilities bound

# A heavy-workload department can still reach for Quick for micro-tasks:
llm_quick = resolve(department_id="equity_research", tier_override=ModelTier.QUICK, user_id=user_id)
```

**Scope boundary.** The resolver returns an `LLMProvider`. What the department *does* with it (prompt assembly, tools, streaming back to the frontend) is the Runtime / Execution spec's concern.

---

## Env Var Surface

Provider credentials and model roster are managed entirely in the database (`llm_providers`, `llm_models`). The tier-level `OPENLIA_LLM_{TIER}_*` env vars from earlier drafts are removed — all provider configuration flows through the admin UI (Setup Wizard Step 3 or Settings → Admin → Models).

Remaining LLM-related env vars:

```
# Per-department tier overrides (all optional, admin use)
OPENLIA_LLM_DEPARTMENT_<UPPER_ID>_TIER        # "thinking" | "everyday" | "quick"

# Secrets infrastructure (see database-design.md § 5)
OPENLIA_SECRET_KEY                             # 32-byte base64 encryption key for API keys at rest
```

Env presence for department tier overrides shadows the `config_store` row and renders the corresponding field read-only with a `from environment` badge in Settings.

---

## Wizard Step 3 — Delta from SetupWizardSpec

SetupWizardSpec Step 3 is updated as follows:

- Replace the two-slot structure (Primary + Review) with three tier slots (Thinking, Everyday, Quick), in that visible order.
- Short explainer above the slots: *"OpenLIA uses a top-tier Thinking model for deep analysis, an Everyday model for general chat and standardized tasks, and a Quick model for classification and lightweight jobs. Each department uses a sensible default tier, which you can change later in Settings. You can put any model in any slot — the tier is a routing label, not a restriction."*
- Add Google Gemini to the Provider dropdown (5 → 6 options).
- For OpenRouter and Ollama, replace the populated Model dropdown with a free-text model-name input (helper text points to openrouter.ai/models for OpenRouter, `ollama list` for Ollama).
- Capability flags are captured invisibly for named providers (from shipped map). For Ollama and OpenAI-compatible, checkboxes appear under an "Advanced" disclosure, pre-filled from the shipped map's best-guess entry.
- Test semantics: each configured slot runs `list_models` (skipped for OpenRouter/Ollama) + 1-token completion on the selected model.
- **Required-tier gating:** the wizard computes the union of `DEFAULT_TIER` across enabled departments — the *required-tier set* — and refuses to advance until each required tier has at least one green model. Tiers outside that set are not gated. This guarantees the runtime resolver never raises `TierNotConfiguredError` for a normally-completed installation. See `SetupWizardSpec.md` § Step 3 for the inline UI behavior.

Review-specific copy is retired. The Wizard Step 6 AI Review consumes the Quick tier (guaranteed populated whenever any enabled department defaults to Quick; otherwise the review falls back through Everyday → Thinking).

---

## Settings → Models Section

> **Cross-reference (2026-04-15):** The full UI spec for the Models and Admin sections is in `SettingsPageSpec.md`. This section summarizes the key design points relevant to the provider system.

Settings sidebar entry alongside General, Account, and Admin. Role-gated content.

### User view (non-admin, company mode)

Three tier sections (Thinking, Everyday, Quick), each showing:
- Read-only list of models the admin has configured for this tier (display name, provider, connection status).
- "Not configured yet" state when a tier has zero models.
- Per-tier preference picker dropdown: "Use tier default" or pick from the available models. Writes to `user_llm_preferences`.

No per-user BYO keys. Users pick from the admin's roster only.

### Admin / personal user view

Same as user view, plus a "Manage models in Admin panel" link per tier. Full model roster CRUD (providers and models) lives in Settings → Admin → Models. In personal mode, admin controls are inline since there's no separate Admin section.

### Per-department tier defaults

Read-only reference panel listing each department with its default tier and an info icon showing `DEFAULT_TIER_REASON`. Admin can override per-department tier routing from the Admin panel.

### Edit capability flags dialog

Modal triggered from model edit in the admin panel. Checkboxes: streaming, tool_calling, structured_output, vision. Number inputs: max_context_tokens, max_output_tokens. Save writes to `llm.capability_override.<provider>.<model>` in `config_store`. Clear button removes the override.

### Save semantics

- Each form has its own Save button; saves are scoped.
- Every Save on a provider runs `Test` first; rejects on failure with an inline error.
- Unsaved-changes warning on navigation (pattern from `SettingsPageSpec.md`).

---

## Runtime Failure Handling

The adapter layer implements a uniform retry and error-mapping policy. Departments don't implement retry themselves.

### Transient errors — built-in exponential backoff

| Error class | Triggers | Policy |
|---|---|---|
| `TransportError` | ConnectionReset, read timeout, DNS failure | 3 attempts, backoff 1s / 4s / 10s with jitter |
| `RateLimitError` | HTTP 429 (respects `Retry-After` if present) | 3 attempts, backoff = max(`Retry-After`, exponential) |
| `ProviderOutageError` | HTTP 5xx, upstream gateway errors | 3 attempts, backoff 1s / 4s / 10s |

After the final retry the original exception is re-raised with retry metadata (`attempts=3, total_wait_ms=15012`).

### Non-transient errors — fail loudly, no retry

| Error class | Triggers | Chat-facing message |
|---|---|---|
| `AuthError` | HTTP 401 / 403 | "The API key for `<provider>` isn't valid. Update it in Settings → Models." |
| `ModelNotFoundError` | HTTP 404 on completion, Ollama `model not found` | "Model `<model>` is unavailable on `<provider>`. Pick a different model in Settings → Models." |
| `ContextLengthError` | HTTP 400 with context-length signal | "This request exceeded `<model>`'s context limit (`<limit>` tokens). Split the task or switch to a larger-context model." |
| `CapabilityError` | Provider rejected tools / JSON on an unsupported model | "The current model doesn't support `<capability>`. `<department>` needs this — switch models in Settings → Models." |
| `TierNotConfiguredError` | Resolver found no enabled models in the resolved tier | "The `<tier>` tier has no models configured. Ask your admin to add one in Settings → Admin → Models." |

All five classes derive from `LLMProviderError`. The server layer catches the base class and forwards structured error events to the frontend over the chat SSE stream. The frontend renders the message inline with a **"Open Models settings"** deep-link.

No configurable fallback chains. No silent degradation to a cheaper model.

---

## Connection Testing

Shared code path for Wizard Step 3 (`POST /setup/models/test`) and Settings (`POST /settings/models/test`).

```python
def test_connection(provider, model, api_key, base_url) -> TestResult:
    # 1. Validate required fields for the provider type.
    # 2. Construct an ephemeral adapter.
    # 3. list_models() — skipped for OpenRouter/Ollama.
    # 4. 1-token completion, temperature=0.
    # 5. Return {ok, latency_ms, error_class, error_msg}.
```

Full-test timeout: 10 seconds. Exceeding returns `{ok: false, error_class: "TransportError", error_msg: "Test timed out after 10 seconds."}`.

---

## API Surface

All endpoints require authentication in company mode. Admin-only endpoints return `403` for non-admin users.

### Provider and model CRUD (admin only)

| Method | Path | Purpose |
|---|---|---|
| GET | `/settings/admin/llm/providers` | List all LLM providers with model counts. |
| POST | `/settings/admin/llm/providers` | Create a provider. Tests connection first. |
| PUT | `/settings/admin/llm/providers/{id}` | Update provider. Tests connection first. |
| DELETE | `/settings/admin/llm/providers/{id}` | Delete provider. Blocked if models exist. |
| POST | `/settings/admin/llm/providers/{id}/test` | Test provider connection without persisting. |
| GET | `/settings/admin/llm/providers/{id}/models` | List models for a provider. |
| POST | `/settings/admin/llm/models` | Create a model entry. |
| PUT | `/settings/admin/llm/models/{id}` | Update model (tier, display name, overrides, default, enabled). |
| DELETE | `/settings/admin/llm/models/{id}` | Delete model. Cascades `user_llm_preferences`. |
| GET | `/settings/admin/llm/providers/{id}/remote-models` | Proxy to provider's `/models` endpoint for live model list. Skipped for Ollama/OpenRouter. |

### User-facing (any authenticated user)

| Method | Path | Purpose |
|---|---|---|
| GET | `/settings/models` | Role-shaped payload: tier roster, user preferences, per-department defaults. |
| GET | `/settings/models/preferences` | Current user's per-tier preferences. |
| PUT | `/settings/models/preferences/{tier}` | Set user's preferred model for a tier. Body: `{model_id}`. |
| DELETE | `/settings/models/preferences/{tier}` | Clear preference (fall back to tier default). |

### Department config (admin only)

| Method | Path | Purpose |
|---|---|---|
| POST | `/settings/admin/llm/department/{id}` | Body: `{tier?}`. Null body resets to shipped default. |
| POST | `/settings/admin/llm/capability_override/{provider}/{model}` | Set capability override. Omit body to clear. |

Wizard counterparts (`/setup/models`, `/setup/models/test`) already exist per `SetupWizardSpec.md`. Their payload shape is updated to carry three tier slots and write to `llm_providers` / `llm_models` tables.

---

## Testing Strategy

- **Adapter conformance tests** (one module per adapter under `packages/core/tests/llm/`). Mock provider HTTP responses at the wire level; verify `list_models`, `test_connection`, `generate`, `stream`, and that each error class surfaces its right exception type.
- **Resolver tests** covering each path of the precedence order with both personal and company-mode fixtures.
- **Capability-gate tests** verify Wizard Step 6 Review renders Ready / Amber / Blocked for representative (department, model) pairs.
- **Retry tests** verify transient errors retry 3× with exponential backoff and non-transient errors fail immediately.
- **Server route tests** verify admin-only provider/model CRUD routes return 403 to non-admins, user preference routes respect the logged-in user's scope, and API key encryption round-trips correctly.
- **Integration test** runs the wizard through all three tier slots with a fake Ollama provider (HTTP-level mocked) and asserts `llm_providers` / `llm_models` table contents after Finish.

---

## Non-Goals (v1)

- Fallback model chains. If the configured model is down, OpenLIA fails loudly with a specific error.
- Auto-discovery of new models via web search. Provider `/v1/models` is the authoritative source.
- Per-user BYO API keys. Users pick from the admin's roster; they do not enter their own credentials (v2 consideration).
- Per-user data-provider API key overrides. Data providers stay admin-only (see `data-provider-design.md`).
- Multi-admin LLM config. Only `is_admin = true` users see the admin view; no "model admin" sub-role.
- Budget / spend tracking or cost caps.
- OAuth / SSO for LLM provider authentication. Any OAuth-protected provider must be fronted by a user-run proxy.
- Fine-tuned model management. Users enter a fine-tuned model ID in any slot; OpenLIA doesn't host fine-tuning.
- Capability auto-probing of unfamiliar models.
- Localization of tier / department explanations (English-only per project memory).

---

## Dev Notes

> **Dev note — capability map maintenance.** `core/llm/capabilities.py` requires manual maintainer updates per release. If maintenance burden proves significant, consider migrating to self-declared flags only (wizard / Settings asks the user to tick capabilities when adding Ollama or OpenAI-compatible models; named cloud providers assume-all-on). Named-provider current-gen models almost always support the full capability set, so the map mostly protects Ollama / niche self-hosted users — its value is narrow. Revisit after 2–3 releases of actual maintenance experience.

> **Dev note — model defaults freshness.** `core/llm/model_defaults.py` is maintainer-curated per release, same cadence as `capabilities.py`. Users are never stuck with a stale default because the wizard's Model dropdown is live-populated from each provider's `/v1/models` endpoint; shipped defaults are only pre-selections. Runtime web-search for "newest models" was considered and rejected — the provider's own `/models` endpoint is more authoritative than scraping release notes, and runtime web dependencies would violate the `openlia-core` hermetic-layer rule.

> **Dev note — secrets encryption at rest.** Resolved (2026-04-15). API keys are AES-256-GCM encrypted at rest using `OPENLIA_SECRET_KEY`. See `database-design.md` § 5 for the full scheme.

> **Dev note — test-completion cost during configuration.** Every Save on a tier card runs a 1-token test completion. For users on paid APIs this is ~$0 but non-zero. Consider a debounce on rapid-fire Saves (changing API key then provider within 2 seconds should coalesce into one test). Not urgent for v1.

> **Dev note — shipped model names accuracy.** Tier defaults in this spec (`gpt-5.4-*`, `claude-opus/sonnet/haiku-4-*`, `gemini-3.1-*`) reflect current model generations as of 2026-04-14. Confirm exact variant names against each provider's official docs before shipping; correct if wrong. The Wizard dropdown is live-populated so users can always pick a different model, but shipped defaults should match reality at release time.

---

## Cross-References: Required Edits to Other Specs

This spec introduces changes that require targeted edits to already-written specs. Status tracked in `planning/GAPS.md`.

1. ~~**`SetupWizardSpec.md` § Step 3 — AI Models.** Done (2026-04-15).~~
2. ~~**`SetupWizardSpec.md` § Configuration Storage and Env Precedence.** Done (2026-04-15).~~
3. ~~**`SetupWizardSpec.md` § Step 6 — Review.** Done (2026-04-15).~~
4. ~~**`SettingsPageSpec.md` § Settings Sidebar and Models section.** Done (2026-04-15).~~
5. **`planning/projectStructure.md` § `core/openlia/llm/`.** Pending.
   - Confirm the directory contains: `base.py`, `openai.py`, `anthropic.py`, `gemini.py`, `openrouter.py`, `openai_compat.py`, `ollama.py`, `capabilities.py`, `model_defaults.py`, `resolver.py`, `exceptions.py`.

---

## Next in This Series

The configuration story ends here. The planned follow-up spec — **LLM Runtime / Execution** — will cover:

- How each department assembles prompts (system + user + framework injection).
- How `packages/core/src/openlia/reports/frameworks/*.json` and `*_style_guide.md` are loaded into LLM calls.
- Tool schema construction from the data-provider surface, and how department calls invoke tools.
- The backend→frontend SSE streaming protocol (token events, tool-call events, error events, report-thumbnail events).
- Web search as a *department capability* (distinct from the configuration-time discovery considered and rejected above).

That spec will consume the `LLMProvider` interface defined here. No rework of this spec is anticipated to support it.
