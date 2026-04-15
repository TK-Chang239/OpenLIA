# LLM Provider & Configuration System Design

## Purpose

Defines OpenLIA's LLM provider abstraction layer and the end-to-end user flow for configuring it. Backing system for `SetupWizardSpec.md` Step 3 and for a new Settings → Models section. Sibling of `data-provider-design.md`.

This is **part 1 of 2** in the LLM system series. Part 2 — the LLM Runtime / Execution spec — will cover prompt assembly, framework/style-guide loading, tool schema construction, and the backend→frontend SSE streaming protocol.

## Scope

In scope:

- Supported providers and the adapter interface (`core/openlia/llm/`).
- Capability matrix and department requirement manifests.
- Three-tier model-role structure (Thinking / Everyday / Quick).
- Configuration storage schema (instance-level and per-user).
- Runtime resolution order (env > user BYO > department pin > department tier > shipped default > tier slot).
- Wizard Step 3 extension and Settings → Models UI.
- Connection-testing flow shared by wizard and settings.
- Runtime failure behavior (retry policy, error classes, user-facing messaging).

Out of scope (deferred to the Runtime / Execution spec):

- Prompt assembly (system + user + framework injection).
- Framework (`planning/frameworks/*.json`) and style-guide loading into LLM calls.
- Tool schema construction from the data-provider surface.
- Backend→frontend SSE streaming protocol (token / tool-call / report-thumbnail events).
- Web search as a department *capability* for chat/report use.

Out of scope entirely:

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
    max_context_tokens: int
    max_output_tokens: int
```

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

Maintained in `core/llm/model_defaults.py`. Wizard/Settings Model dropdowns for named providers (1–3) live-populate from each provider's `/models` endpoint — the shipped default is only the initial pre-selection. Users are never stuck on a stale default.

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

### Instance-level config keys (in `config_store`)

```
llm.thinking.provider / model / api_key / base_url
llm.everyday.provider / model / api_key / base_url
llm.quick.provider    / model / api_key / base_url

llm.department.<id>.tier           # "thinking" | "everyday" | "quick" | null (null = use shipped default)
llm.department.<id>.provider       # optional; overrides tier entirely for a specific model pin
llm.department.<id>.model
llm.department.<id>.api_key
llm.department.<id>.base_url

llm.capability_override.<provider>.<model>   # JSON blob: Capabilities struct
```

`<id>` values: `secretary`, `equity_research`, `earnings_update`, `morning_briefing`, `retail_sentiment`, `macro_research`, `panic_thermometer`.

`api_key` is null for Ollama. `base_url` is null for named cloud providers (1–4), required for `openai_compat` and `ollama`.

### Per-user BYO override (company mode only)

New table:

```
user_llm_overrides
  user_id              fk -> users.id
  tier                 text  ("thinking" | "everyday" | "quick")
  enabled              bool
  provider             text nullable
  model                text nullable
  api_key              text nullable
  base_url             text nullable
  updated_at           timestamp
  primary key (user_id, tier)
```

Users can opt in to BYO on any subset of tiers independently — e.g. BYO Thinking with their personal Anthropic key, fall through to instance default for Everyday and Quick.

Per-department overrides and capability overrides are **admin-only** — not available at the per-user level.

### Secrets at rest

V1 plaintext in SQLite, inherited from `SetupWizardSpec.md`. See Dev Notes.

---

## Runtime Resolution Order

Resolution proceeds in two stages. **Stage 1** decides whether this call uses a pinned model or a tier; **Stage 2** fills in the tier credentials from the highest-precedence source available.

### Stage 1 — Model source

```
1. If the department has a model pin set (llm.department.<id>.provider/model non-null, or the
   matching OPENLIA_LLM_DEPARTMENT_<ID>_PROVIDER/MODEL env vars are set), use those creds directly.
   Skip Stage 2.

2. Otherwise, determine which tier this call consumes:
   a. OPENLIA_LLM_DEPARTMENT_<ID>_TIER env var, if set.
   b. llm.department.<id>.tier DB row, if non-null.
   c. The department's shipped DEFAULT_TIER (from core/openlia/departments/<id>.py).
   d. A caller-supplied tier_override argument to resolve() trumps all of the above — used by
      a heavy department that wants Quick for a specific micro-task.
```

### Stage 2 — Tier credentials

```
1. OPENLIA_LLM_{TIER}_PROVIDER/MODEL/API_KEY/BASE_URL env vars (instance-wide).
2. user_llm_overrides row for this (user_id, tier) with enabled=true (company mode only).
3. llm.{tier}.provider/model/api_key/base_url in config_store.
```

If none of Stage 2's sources produces a complete credential set, `resolve()` raises `LLMConfigError` with a message naming the missing tier.

The resolver is a single function in `core/openlia/llm/resolver.py`:

```python
def resolve(
    department_id: str,
    tier_override: ModelTier | None = None,
    user_id: str | None = None,
) -> LLMProvider:
    """Returns a ready-to-use LLMProvider with credentials + model bound.
    Raises LLMConfigError if resolution fails (e.g. dept pinned to a model whose credentials are missing)."""
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

```
# Three tier models
OPENLIA_LLM_THINKING_PROVIDER / MODEL / API_KEY / BASE_URL
OPENLIA_LLM_EVERYDAY_PROVIDER / MODEL / API_KEY / BASE_URL
OPENLIA_LLM_QUICK_PROVIDER    / MODEL / API_KEY / BASE_URL

# Per-department overrides (all optional)
OPENLIA_LLM_DEPARTMENT_<UPPER_ID>_TIER        # "thinking" | "everyday" | "quick"
OPENLIA_LLM_DEPARTMENT_<UPPER_ID>_PROVIDER    # pin a specific provider
OPENLIA_LLM_DEPARTMENT_<UPPER_ID>_MODEL
OPENLIA_LLM_DEPARTMENT_<UPPER_ID>_API_KEY
OPENLIA_LLM_DEPARTMENT_<UPPER_ID>_BASE_URL
```

Env presence shadows the DB row and renders the corresponding field read-only with a `from environment` badge in both Wizard Step 3 and Settings → Models.

---

## Wizard Step 3 — Delta from SetupWizardSpec

SetupWizardSpec Step 3 is updated as follows:

- Replace the two-slot structure (Primary + Review) with three tier slots (Thinking, Everyday, Quick), in that visible order.
- Short explainer above the slots: *"OpenLIA uses a top-tier Thinking model for deep analysis, an Everyday model for general chat and standardized tasks, and a Quick model for classification and lightweight jobs. Each department uses a sensible default tier, which you can change later in Settings. You can put any model in any slot — the tier is a routing label, not a restriction."*
- Add Google Gemini to the Provider dropdown (5 → 6 options).
- For OpenRouter and Ollama, replace the populated Model dropdown with a free-text model-name input (helper text points to openrouter.ai/models for OpenRouter, `ollama list` for Ollama).
- Capability flags are captured invisibly for named providers (from shipped map). For Ollama and OpenAI-compatible, checkboxes appear under an "Advanced" disclosure, pre-filled from the shipped map's best-guess entry.
- Test semantics: each slot runs `list_models` (skipped for OpenRouter/Ollama) + 1-token completion on the selected model. All three slots must return green for Next.

Review-specific copy is retired. The Wizard Step 6 AI Review consumes the Quick tier.

---

## Settings → Models Section

New sidebar entry in `SettingsPageSpec.md` alongside General and Account. Role-gated content.

### Admin / personal user view

```
Models
  Three tiers — Thinking, Everyday, Quick. Assign any model to any slot.

  ┌─ Thinking model ───────────────────────────────────────────┐
  │ Provider [Anthropic ▾]   Model [claude-opus-4-6 ▾]          │
  │ API key  [••••••••••]       [Edit capabilities]             │
  │ ● Connected (62ms)                   [Test]  [Save changes] │
  └─────────────────────────────────────────────────────────────┘
  ┌─ Everyday model ───────────────────────────────────────────┐
  │ ... same controls ...                                       │
  └─────────────────────────────────────────────────────────────┘
  ┌─ Quick model ──────────────────────────────────────────────┐
  │ ... same controls ...                                       │
  └─────────────────────────────────────────────────────────────┘

  ┌─ Per-department defaults ──────────────────────────────────┐
  │ Each department uses a recommended tier by default. Click   │
  │ the info icon for the reason, or override individually.     │
  │                                                             │
  │  Secretary          [Default: Everyday ⓘ ▾]                 │
  │  Equity Research    [Default: Thinking ⓘ ▾]                 │
  │  Earnings Update    [Default: Everyday ⓘ ▾]                 │
  │  Morning Briefing   [Default: Everyday ⓘ ▾]                 │
  │  Retail Sentiment   [Default: Quick ⓘ ▾]                    │
  │  Macro Research     [Default: Thinking ⓘ ▾]                 │
  │  Panic Thermometer  [Default: Quick ⓘ ▾]                    │
  │                                                             │
  │  Dropdown options per row:                                  │
  │    - Use default (<tier>)                                   │
  │    - Use Thinking tier                                      │
  │    - Use Everyday tier                                      │
  │    - Use Quick tier                                         │
  │    - Pin to a specific model...  (opens model-picker form)  │
  └─────────────────────────────────────────────────────────────┘
```

Hovering the ⓘ icon shows `DEFAULT_TIER_REASON` for the department.

### Company non-admin user view

```
Models
  Currently using: instance defaults configured by your administrator
     Thinking:  Anthropic / claude-opus-4-6
     Everyday:  Anthropic / claude-sonnet-4-6
     Quick:     Anthropic / claude-haiku-4-5

  ┌─ My own models (optional, per tier) ──────────────────────┐
  │ [ ] Override Thinking tier with my own model                │
  │ [ ] Override Everyday tier with my own model                │
  │ [ ] Override Quick tier with my own model                   │
  │                                                             │
  │ (each unfolds a provider/model/key/base-URL form with       │
  │  Test + Save when checked)                                  │
  └─────────────────────────────────────────────────────────────┘
```

### Edit capability flags dialog

Modal triggered from the `[Edit capabilities]` link on any configured model. Checkboxes: streaming, tool_calling, structured_output, vision. Number inputs: max_context_tokens, max_output_tokens. Save writes to `llm.capability_override.<provider>.<model>`. Clear button removes the override.

### Save semantics

- Each card has its own `[Save changes]` button; saves are scoped.
- Every Save runs `Test` first; rejects on failure with an inline error.
- Unsaved-changes warning on navigation (pattern from `SettingsPageSpec.md`).
- Env-shadowed fields render read-only with the `from environment` badge.

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
| `LLMConfigError` | Resolver couldn't produce a provider (missing key, unreachable instance default) | "LLM isn't configured. Open Settings → Models to set up your `<tier>` model." |

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

All endpoints under `/settings/models/*` require authentication in company mode. Admin-only endpoints return `403` for non-admin users.

| Method | Path | Purpose | Auth |
|---|---|---|---|
| GET | `/settings/models` | Full config view. Role-shaped payload. | any user |
| POST | `/settings/models/tier/{thinking\|everyday\|quick}` | Set tier slot. Tests first. | admin / personal |
| POST | `/settings/models/tier/{tier}/test` | Test a tier config without persisting. | admin / personal |
| POST | `/settings/models/department/{id}` | Body: `{tier?, pin?}`. One or the other. Null body resets to shipped default. | admin / personal |
| POST | `/settings/models/department/{id}/test` | Test the department's currently resolved model. | admin / personal |
| POST | `/settings/models/capability_override/{provider}/{model}` | Set capability override. Omit body to clear. | admin / personal |
| GET | `/settings/models/user_override` | Current user's BYO overrides across tiers. | any authenticated user |
| POST | `/settings/models/user_override/tier/{tier}` | Per-tier user BYO. | any authenticated user |
| POST | `/settings/models/user_override/tier/{tier}/test` | Test user BYO without persisting. | any authenticated user |
| GET | `/settings/models/providers/{provider}/models` | Proxy to provider's `/models` endpoint. Skipped for Ollama/OpenRouter. | any authenticated user |

Wizard counterparts (`/setup/models`, `/setup/models/test`) already exist per `SetupWizardSpec.md`. Their payload shape is updated to carry three tier slots instead of Primary + Review.

---

## Testing Strategy

- **Adapter conformance tests** (one module per adapter under `packages/core/tests/llm/`). Mock provider HTTP responses at the wire level; verify `list_models`, `test_connection`, `generate`, `stream`, and that each error class surfaces its right exception type.
- **Resolver tests** covering each path of the precedence order with both personal and company-mode fixtures.
- **Capability-gate tests** verify Wizard Step 6 Review renders Ready / Amber / Blocked for representative (department, model) pairs.
- **Retry tests** verify transient errors retry 3× with exponential backoff and non-transient errors fail immediately.
- **Server route tests** verify admin-only routes return 403 to non-admins, user BYO routes respect the logged-in user's scope, and env-shadowed keys render read-only.
- **Integration test** runs the wizard through all three tier slots with a fake Ollama provider (HTTP-level mocked) and asserts `config_store` contents after Finish.

---

## Non-Goals (v1)

- Fallback model chains. If the configured model is down, OpenLIA fails loudly with a specific error.
- Auto-discovery of new models via web search. Provider `/v1/models` is the authoritative source.
- Per-user data-provider API key overrides. Data providers stay admin-only (see `data-provider-design.md`).
- Multi-admin LLM config. Only `role=admin` users see the admin view; no "model admin" sub-role.
- Budget / spend tracking or cost caps.
- OAuth / SSO for LLM provider authentication. Any OAuth-protected provider must be fronted by a user-run proxy.
- Fine-tuned model management. Users enter a fine-tuned model ID in any slot; OpenLIA doesn't host fine-tuning.
- Capability auto-probing of unfamiliar models.
- Promotion of a user BYO override to instance default.
- Localization of tier / department explanations (English-only per project memory).

---

## Dev Notes

> **Dev note — capability map maintenance.** `core/llm/capabilities.py` requires manual maintainer updates per release. If maintenance burden proves significant, consider migrating to self-declared flags only (wizard / Settings asks the user to tick capabilities when adding Ollama or OpenAI-compatible models; named cloud providers assume-all-on). Named-provider current-gen models almost always support the full capability set, so the map mostly protects Ollama / niche self-hosted users — its value is narrow. Revisit after 2–3 releases of actual maintenance experience.

> **Dev note — model defaults freshness.** `core/llm/model_defaults.py` is maintainer-curated per release, same cadence as `capabilities.py`. Users are never stuck with a stale default because the wizard's Model dropdown is live-populated from each provider's `/v1/models` endpoint; shipped defaults are only pre-selections. Runtime web-search for "newest models" was considered and rejected — the provider's own `/models` endpoint is more authoritative than scraping release notes, and runtime web dependencies would violate the `openlia-core` hermetic-layer rule.

> **Dev note — secrets encryption at rest.** Inherited from `SetupWizardSpec.md`. V1 stores API keys as plaintext in SQLite with a schema comment noting the intended upgrade to a server-derived encryption key. Revisit once the user base includes company deployments that materially raise the stakes of a stolen DB file.

> **Dev note — test-completion cost during configuration.** Every Save on a tier card runs a 1-token test completion. For users on paid APIs this is ~$0 but non-zero. Consider a debounce on rapid-fire Saves (changing API key then provider within 2 seconds should coalesce into one test). Not urgent for v1.

> **Dev note — shipped model names accuracy.** Tier defaults in this spec (`gpt-5.4-*`, `claude-opus/sonnet/haiku-4-*`, `gemini-3.1-*`) reflect current model generations as of 2026-04-14. Confirm exact variant names against each provider's official docs before shipping; correct if wrong. The Wizard dropdown is live-populated so users can always pick a different model, but shipped defaults should match reality at release time.

---

## Cross-References: Required Edits to Other Specs

This spec introduces changes that require targeted edits to already-written specs.

1. **`SetupWizardSpec.md` § Step 3 — AI Models.**
   - Replace the two-slot structure (Primary + Review) with the three-tier structure (Thinking + Everyday + Quick). Review-specific copy is retired; the Quick tier serves the AI Review and any runtime structured micro-tasks.
   - Add Google Gemini to the provider dropdown (5 → 6 options).
   - Replace "model dropdown populated via `list_models`" for OpenRouter and Ollama with a free-text model-name input.

2. **`SetupWizardSpec.md` § Configuration Storage and Env Precedence.**
   - Replace `OPENLIA_LLM_PRIMARY_*` / `OPENLIA_LLM_REVIEW_*` with the three-tier triplet (`OPENLIA_LLM_THINKING_*`, `OPENLIA_LLM_EVERYDAY_*`, `OPENLIA_LLM_QUICK_*`) plus the per-department override env surface.

3. **`SetupWizardSpec.md` § Step 6 — Review.**
   - Clarify that the AI Review LLM is the Quick tier (formerly "Review model").

4. **`SettingsPageSpec.md` § Settings Sidebar (Desktop).**
   - Add `Models` to the navigation list alongside General and Account.
   - Add the Models-section design (role-gated: admin/personal view and company-user view) per this spec.

5. **`planning/projectStructure.md` § `core/openlia/llm/`.**
   - Confirm the directory contains: `base.py`, `openai.py`, `anthropic.py`, `gemini.py`, `openrouter.py`, `openai_compat.py`, `ollama.py`, `capabilities.py`, `model_defaults.py`, `resolver.py`, `exceptions.py`.

---

## Next in This Series

The configuration story ends here. The planned follow-up spec — **LLM Runtime / Execution** — will cover:

- How each department assembles prompts (system + user + framework injection).
- How `planning/frameworks/*.json` and `planning/frameworks/*_style_guide.md` are loaded into LLM calls.
- Tool schema construction from the data-provider surface, and how department calls invoke tools.
- The backend→frontend SSE streaming protocol (token events, tool-call events, error events, report-thumbnail events).
- Web search as a *department capability* (distinct from the configuration-time discovery considered and rejected above).

That spec will consume the `LLMProvider` interface defined here. No rework of this spec is anticipated to support it.
