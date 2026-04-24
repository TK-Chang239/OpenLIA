# Phase 4 — LLM Provider System fix plan (→ 100%)

**Current shipped:** ~72%
**Plan:** [planning/implementation-plans/2026-04-16-phase-4-llm-provider-system.md](../../implementation-plans/2026-04-16-phase-4-llm-provider-system.md)
**Spec:** [planning/specs/systems/llm-provider-design.md](../../specs/systems/llm-provider-design.md)

**Dominant root cause(s):** IMPLEMENTER (Task 18 user-preference router mis-implemented and mis-mounted; retry wrapper unused; PUT body drops fields). SPEC_DRIFT (spec uses `/admin/llm/*`; shipped uses `/settings/admin/llm/*`; cross-plan contracts locked the shipped prefix). PLAN↔IMPL drift on `_ModelIn`/`_ModelUpdateIn` split. DEFERRED (per-adapter retry wiring, `list_models` for `openai_compat`/`openrouter`/`ollama` fallbacks, LLM user-pref routes at the spec's `/settings/models*` paths, user-pref frontend wiring).

**Gap summary:** Adapters, registry, factory, SQL resolver, admin-provider CRUD, admin-model CRUD, `test-provider`, `remote-models`, and encryption-at-rest are all shipped and tested. What broke the implementation's 100%: (a) the Task 18 user-preference router is mis-pathed (it sits under `/settings/admin/llm/preferences*` instead of the spec's `/settings/models*` surface and returns pointer-only ids with no resolved payload or `effective/{department_id}` endpoint); (b) `PUT /settings/admin/llm/models/{id}` re-uses `_ModelIn` which accepts `provider_id`, `tier`, `model_ref` but the service only persists `display_name`, `is_tier_default`, `is_enabled`, `overrides` — silent data loss; (c) the `with_retries` helper in `core/llm/retry.py` is exported but no adapter wraps its calls in it, so the spec's 3× exponential-backoff policy on `TransportError`/`RateLimitError`/`ProviderOutageError` is dead code; (d) `openai.llm.__init__` is empty, so the plan-promised public API (`build_adapter`, `resolve`, `ModelRegistry`, `ProviderCredentials`, capability types, `with_retries`) isn't re-exported; (e) frontend `ModelsSection.tsx` exists but is a placeholder — no admin model-roster CRUD UI and no Step-3 tier slots for Gemini/compat/Ollama advanced capability capture.

---

## P0 — Live failures

### NEW-4-10 — `PUT /settings/admin/llm/models/{id}` silently drops `model_ref` + `tier` + `provider_id`
- **Severity:** P0
- **Bug:** The route uses `_ModelIn` (same class as POST) which advertises `provider_id`, `tier`, `model_ref`, `display_name`, `is_tier_default`, `is_enabled`, `overrides`, but `update_model(...)` in `services/llm_providers.py:213-237` only accepts `display_name`, `is_tier_default`, `is_enabled`, `overrides`. A caller that changes `model_ref` (fix a typo, bump to `gpt-5.4-pro` from `gpt-5.4`) or changes `tier` (promote Quick→Everyday) receives `200` + an `_ModelOut` that reflects the *old* values — UI thinks the change stuck. Because resolver is keyed on `model_ref`, this is user-visible: the wrong model runs.
- **Files:** `packages/server/src/openlia_server/routes/settings.py:311-319` (`_ModelIn`), `:604-637` (`update_model` route), `packages/server/src/openlia_server/services/llm_providers.py:213-237` (`update_model` service).
- **Plan ref:** Task 17 "Admin routes — provider/model CRUD + test + remote-models + overrides" (plan §17, line 4878).
- **Spec ref:** `llm-provider-design.md` §API Surface — `PUT /admin/llm/models/{id}` — "Update model (tier, display name, overrides, default, enabled)".
- **Acceptance:** Either (a) extend `update_model` service to accept `tier`, `model_ref`, and to keep the partial-unique-index invariant on tier flips, and keep one Pydantic body; or (b) introduce `_ModelUpdateIn` with exactly the mutable subset (`display_name`, `is_tier_default`, `is_enabled`, `overrides`) and reject unknown fields via `model_config = {"extra": "forbid"}`. Choose (a) because the spec says "tier" is mutable.
- **Verification:** Add `packages/server/tests/test_routes/test_llm_admin_routes.py::test_update_model_persists_tier_and_model_ref` — PUT changes both fields, GET confirms, resolver returns the new `model_ref`.

### NEW-4-11 — User-preference router paths violate spec and cross-plan contract
- **Severity:** P0
- **Bug:** `packages/server/src/openlia_server/routes/settings_models.py` mounts at `/settings/admin/llm` with `GET /preferences`, `PUT /preferences` (body-based), `DELETE /preferences/{tier}`. The spec's user-facing surface is `GET /settings/models`, `GET /settings/models/preferences`, `PUT /settings/models/preferences/{tier}`, `DELETE /settings/models/preferences/{tier}`, plus the frontend/setup wizard expects `GET /settings/models/effective/{department_id}` for department-resolution preview. Two independent consequences: (1) non-admin users in company mode can't reach preferences because frontend expects `/settings/models/*` and `/settings/admin/*` may be guarded differently over time; (2) the roster payload (`GET /settings/models`) returning `{thinking: [...], everyday: [...], quick: [...]}` with per-model provider kind/display is absent, so the Settings → Models user view cannot render per the spec §Settings → Models Section.
- **Files:** `packages/server/src/openlia_server/routes/settings_models.py` (rename + refactor), `packages/server/src/openlia_server/app.py:478-480` (mount).
- **Plan ref:** Task 18 "User preference routes + wire routers into `create_app` + README update" (plan §18, line 5524).
- **Spec ref:** `llm-provider-design.md` §API Surface — "User-facing (any authenticated user)".
- **Acceptance:** Rename file to `routes/settings_llm_user.py`; expose `build_llm_user_router()` returning prefix `/settings/models`; four endpoints (`GET /`, `GET /preferences`, `PUT /preferences/{tier}`, `DELETE /preferences/{tier}`) plus `GET /effective/{department_id}` returning the resolver output for the logged-in user; `PUT` validates `model.is_enabled` AND tier match; 404 if model_id not in roster; 403 for unauthenticated; 200 for regular users (no admin gate).
- **Verification:** `packages/server/tests/test_routes/test_llm_user_routes.py` (new) covers: roster payload shape, non-admin happy path, 404 disabled model, tier mismatch 422, effective/{department} returns `{model_ref, provider_kind, tier}`.

---

## P1 — Silent correctness gaps

### NEW-4-20 — `with_retries` exported but no adapter uses it
- **Severity:** P1
- **Bug:** Spec §Runtime Failure Handling requires the adapter layer to retry `TransportError`, `RateLimitError`, `ProviderOutageError` 3× with 1s/4s/10s backoff + jitter (and honor `Retry-After`). `core/llm/retry.py` ships `with_retries(...)` but `grep -n "with_retries" packages/core/src/openlia/llm/adapters/*.py` returns zero hits. Every adapter call (`generate`, `list_models`, `test_connection`) fails on first transient error. Department chat sessions will show `TransportError` on any flaky network blip the spec promised to hide.
- **Files:** `packages/core/src/openlia/llm/adapters/openai.py:55-75, 77-136`; `anthropic.py` (list_models+generate); `gemini.py`; `openrouter.py`; `openai_compat.py`; `ollama.py`.
- **Plan ref:** Task 5 "Retry wrapper" (line 1154) + Tasks 7-12 (each adapter should wire calls through it).
- **Spec ref:** `llm-provider-design.md` §Runtime Failure Handling — "Transient errors — built-in exponential backoff".
- **Acceptance:** Each adapter's `generate` / `list_models` wraps its httpx round-trip in `await with_retries(lambda: ...)`. `test_connection` intentionally does NOT retry (failure returns `TestResult(ok=False)` immediately per spec §Connection Testing).
- **Verification:** Add `packages/core/tests/test_llm/test_adapter_retry.py` asserting 3 retries on `ProviderOutageError` across at least OpenAI+Anthropic with respx.

### NEW-4-21 — `openlia.llm.__init__` is empty; promised public API lives in submodules only
- **Severity:** P1
- **Bug:** `packages/core/src/openlia/llm/__init__.py` is a 0-byte file. Plan Task 1 "Scaffold `openlia/llm/`" and spec §Adapter Interface imply a stable import surface, and the existing fix-plan's NEW-4-02 codified it: `from openlia.llm import build_adapter, resolve, ProviderCredentials, Capabilities, Capability, ModelTier, LLMProviderError, with_retries`. Today every call site must reach into `openlia.llm.adapters`, `openlia.llm.types`, `openlia.llm.resolver`, `openlia.llm.exceptions` — brittle and violates the layering contract documented in `CLAUDE.md` ("`from openlia import ...` must work with only `openlia-core` installed").
- **Files:** `packages/core/src/openlia/llm/__init__.py` (currently empty).
- **Plan ref:** Task 1 (line 144).
- **Spec ref:** `llm-provider-design.md` §Adapter Interface.
- **Acceptance:** Re-export `build_adapter`, `ADAPTERS`, `LLMProvider`, `resolve`, `resolve_tier`, `ModelRegistry`, `ResolvedModel`, `ResolvedModelRow`, `ModelTier`, `Capability`, `Capabilities`, `LLMRequest`/`LLMResponse`/`LLMChunk`/`Message`/`ToolSchema`/`ToolCall`/`ResponseFormat`, `ModelInfo`, `ProviderCredentials`, `TestResult`, `DepartmentRequirements`, all `LLMProviderError` subclasses, `with_retries`, `is_transient`, `SHIPPED_TIER_DEFAULTS`, `DEPARTMENT_DEFAULT_TIERS`, `DEPARTMENT_TIER_REASONS`, `capabilities_for`.
- **Verification:** `packages/core/tests/test_llm/test_public_api.py` (new): imports every symbol above from `openlia.llm`.

### NEW-4-22 — Setup Wizard Step 3 backend handlers still missing (`POST /setup/models`, `/setup/models/test`)
- **Severity:** P1 (tracker logs as P0-03 — flagged here for Phase 4 scope so fix-plan is complete)
- **Bug:** Spec §Wizard Step 3 requires the wizard to write through to `llm_providers` / `llm_models` via `POST /setup/models`; the frontend `api/setup.ts::saveModels` calls this path; server has no handler in `routes/setup.py`. Wizard Finish can't persist model selections. Tracker covers this as P0-03; cross-referenced here to keep Phase 4 fix-plan complete.
- **Files:** `packages/server/src/openlia_server/routes/setup.py` (add handlers), `packages/server/src/openlia_server/services/llm_providers.py` (reuse).
- **Plan ref:** Task 17 (admin CRUD is reused) + cross-ref to Phase 10 Task 9 Step 3 (already rewritten, per memory timeline `Apr 22 10:13a`).
- **Spec ref:** `llm-provider-design.md` §Wizard Step 3.
- **Acceptance:** `POST /setup/models` accepts three tier blocks and upserts matching `llm_providers`+`llm_models`; `POST /setup/models/test` proxies to `_run_connection_test`.
- **Verification:** `test_setup_routes.py::test_post_setup_models_persists_three_tiers`.

### NEW-4-23 — Resolver/registry never filters on capability; capability-gate tests absent
- **Severity:** P1
- **Bug:** Spec §Department Requirements Manifest requires Wizard Step 6 Review to render Ready/Amber/Blocked by checking each department's `DepartmentRequirements.required` against the resolved model's capabilities. The `Capability`, `Capabilities`, and `DepartmentRequirements` types exist; `capabilities_for()` is wired into `ResolvedModel.capabilities` in `resolver.py::_to_resolved`. But no server-side helper `check_department_capabilities(resolved, requirements) -> CapabilityReport` exists, and department modules don't declare a `REQUIREMENTS = ...` constant yet (plan Task 4 hints at the shape but core department files lack it). Wizard Review, Settings → Models per-department row, and the runtime CapabilityError path all break silently.
- **Files:** `packages/core/src/openlia/llm/capabilities.py` (add `evaluate_requirements`), `packages/core/src/openlia/departments/<dept>.py` × 7 (add `REQUIREMENTS`).
- **Plan ref:** Task 3 "Capability map" (line 641), Task 4 "Model defaults + department default tiers" (line 967).
- **Spec ref:** `llm-provider-design.md` §Department Requirements Manifest.
- **Acceptance:** `evaluate_requirements(caps, requirements) -> {status: "ready"|"amber"|"blocked", missing_required, missing_preferred}` returns Ready for all shipped (dept, tier-default-model) pairs; blocked for `ollama:codellama` + `equity_research`.
- **Verification:** `packages/core/tests/test_llm/test_capabilities_gate.py` with representative pairs per spec.

### NEW-4-24 — `remote-models` route returns 500 for OpenRouter/Ollama instead of spec-mandated skip
- **Severity:** P1
- **Bug:** Spec §Provider Surface v1 and §API Surface say `GET /admin/llm/providers/{id}/remote-models` is "skipped for Ollama/OpenRouter" (users paste model names). Shipped code in `routes/settings.py:537-565` calls `adapter.list_models()` unconditionally; for `openrouter`, OpenAI's `/v1/models` scheme returns a different payload shape, and for `ollama` the base URL may be `http://localhost:11434` with no `/v1/models` endpoint. First call crashes with `KeyError` or `ModelNotFoundError`.
- **Files:** `packages/server/src/openlia_server/routes/settings.py:537-565`; adapters `ollama.py`, `openrouter.py` `list_models`.
- **Plan ref:** Tasks 10 + 12 (OpenRouter + Ollama adapters, lines 2611 + 3253).
- **Spec ref:** `llm-provider-design.md` §Provider Surface v1 row 4,6 + §API Surface note.
- **Acceptance:** Route returns `{"skipped": true, "reason": "manual entry"}` with HTTP 200 for kinds `openrouter` + `ollama`. Adapter methods stay available for future use but are not invoked from this route.
- **Verification:** `test_llm_admin_routes.py::test_remote_models_skipped_for_openrouter_and_ollama`.

### NEW-4-25 — `openai_compat` provider cannot save without Advanced capability checkboxes
- **Severity:** P1
- **Bug:** Spec §Capabilities — Resolution order — "OpenAI-compatible catch-all": "cannot be probed reliably. On Save, wizard/Settings asks the user to confirm capability flags via checkboxes". No server endpoint or body surface for capability-flag capture on provider creation exists; `_ProviderIn` has no `advertised_capabilities` field. A power user adding a Grok/DeepSeek/Together endpoint cannot tell OpenLIA "this model supports tools" — resolver always uses `_OPENAI_COMPAT_DEFAULT` or the `(openai_compat, model)` override under `llm.capability_override`.
- **Files:** `packages/server/src/openlia_server/routes/settings.py` (extend `_ProviderIn` + `_ModelIn`), `services/llm_providers.py::create_model` (accept `advertised_capabilities`), `set_capability_override`.
- **Plan ref:** Task 17 + Task 11 (openai-compat adapter, line 2897).
- **Spec ref:** `llm-provider-design.md` §Capabilities.
- **Acceptance:** `_ModelIn` accepts `advertised_capabilities: Capabilities | None = None`; on create, if `kind == "openai_compat"` and non-null, the service persists an `llm.capability_override.openai_compat.<model_ref>` row automatically.
- **Verification:** `test_llm_admin_routes.py::test_create_openai_compat_model_persists_capability_override`.

### NEW-4-26 — `get_provider_api_key` doesn't surface missing-key after decrypt failure
- **Severity:** P1
- **Bug:** `services/llm_providers.py:143-157` returns `None` whenever `decrypt_for_row` raises (caller sees "no key configured" from downstream), but `decrypt_for_row` currently raises `DecryptError` on authenticity failure which bubbles up and triggers a 500 at `remote-models` / resolver. Inconsistent behavior: env-var miss vs encrypted-column tamper collapse to different observed errors. Spec §Secrets at rest promises decryption-on-use; it doesn't promise 500.
- **Files:** `packages/server/src/openlia_server/services/llm_providers.py:143-157`; `packages/server/src/openlia_server/db/crypto.py`.
- **Plan ref:** Task 15 "Server service layer — `llm_providers.py` (CRUD + crypto)" (line 3985).
- **Spec ref:** `llm-provider-design.md` §Secrets at rest + §Runtime Failure Handling (`AuthError` row).
- **Acceptance:** Wrap `decrypt_for_row` in try/except — on `DecryptError` raise `AuthError("API key unreadable; ask admin to re-save")` so the chat SSE surfaces the spec's `AuthError` message.
- **Verification:** `test_llm_providers_service.py::test_decrypt_failure_raises_auth_error`.

### NEW-4-27 — `create_provider` doesn't enforce `run_test` ok before persisting when kind requires it
- **Severity:** P1
- **Bug:** Spec §Settings → Models — Save semantics: "Every Save on a provider runs `Test` first; rejects on failure with an inline error." Shipped route (`routes/settings.py:431-469`) honors `run_test=True` but makes `run_test` optional, default `False`. Frontend may skip it; a bad key persists and surfaces only at first department call. Spec is stricter than shipped.
- **Files:** `packages/server/src/openlia_server/routes/settings.py:277-288, 431-469` (`_ProviderIn` + `create_provider`).
- **Plan ref:** Task 17.
- **Spec ref:** `llm-provider-design.md` §Settings → Models — Save semantics.
- **Acceptance:** `run_test` defaults to `True`; explicit opt-out requires `run_test=False` + `skip_reason` in body. Document in spec.
- **Verification:** `test_llm_admin_routes.py::test_create_provider_runs_test_by_default`.

---

## P2 — Drift / hygiene

### P2-11 — Spec path prefix `/admin/llm/*` vs shipped `/settings/admin/llm/*`
- **Severity:** P2
- **Bug:** Spec §API Surface (lines 399-433) lists admin endpoints under `/admin/llm/*`; shipped code uses `/settings/admin/llm/*` (locked by cross-plan contracts 2026-04-20 per project memory). Spec is out of date.
- **Files:** `planning/specs/systems/llm-provider-design.md:399-433`.
- **Plan ref:** Task 17.
- **Spec ref:** Self.
- **Acceptance:** Rewrite all `/admin/llm/*` entries to `/settings/admin/llm/*`.
- **Verification:** `grep -n "/admin/llm" planning/specs/systems/llm-provider-design.md` returns zero hits.

### P2-12 — User-preference router's missing `GET /settings/models` and `effective/{department_id}`
- **Severity:** P2 (supersedes original P2-12 — the router exists but is wrong shape; see NEW-4-11 for P0 portion)
- **Bug:** The two non-preferences endpoints the spec lists (`GET /settings/models` roster, `GET /settings/models/effective/{department_id}`) are missing entirely.
- **Files:** Same as NEW-4-11.
- **Plan ref:** Task 18.
- **Spec ref:** `llm-provider-design.md` §API Surface §User-facing.
- **Acceptance:** Included in NEW-4-11 acceptance.
- **Verification:** Same test file as NEW-4-11.

### NEW-4-30 — `openai.llm` doesn't expose `SHIPPED_TIER_DEFAULTS` for setup wizard pre-selection
- **Severity:** P2
- **Bug:** Wizard Step 3 should pre-select tier defaults per provider kind (spec §Shipped tier defaults per provider). The constant lives in `core/llm/model_defaults.py` but the server-side setup handler can't import it without reaching into the submodule because of NEW-4-21.
- **Files:** Same as NEW-4-21.
- **Plan ref:** Task 4.
- **Spec ref:** `llm-provider-design.md` §Shipped tier defaults per provider.

### NEW-4-31 — Partial unique index on `llm_models(tier) WHERE is_tier_default` is SQLite-only
- **Severity:** P2
- **Bug:** `db/models/config.py:62-67` uses `sqlite_where=text("is_tier_default = 1")` but no `postgresql_where=` clause; baseline migration `2026-04-18-1609_baseline.py:517, 684` mirrors. In a Postgres deploy the partial index isn't created, and the `create_model` service's "clear existing tier default before setting new one" (`services/llm_providers.py:176-180`) is the only guard. A concurrent PUT on two models at the same tier could produce two `is_tier_default=True` rows and silently violate the spec's invariant "one default per tier".
- **Files:** `packages/server/src/openlia_server/db/models/config.py:62-67`; `.../db/migrations/versions/2026-04-18-1609_baseline.py:517, 684`.
- **Plan ref:** Task 15 + Phase 1a DB baseline.
- **Spec ref:** `database-design.md` §4 (authoritative per spec note).
- **Acceptance:** Add `postgresql_where=text("is_tier_default")` alongside sqlite variant; migration op.create_index mirrors.
- **Verification:** `test_llm_models_partial_index_postgres` (skip under sqlite).

### NEW-4-32 — Frontend `ModelsSection.tsx` + `ModelsAdminPanel` are placeholders
- **Severity:** P2
- **Bug:** `frontend/src/components/settings/sections/ModelsSection.tsx` exists and is routed from `SettingsPage.tsx:23,39`, but does not render the three-tier roster or per-tier preference picker per spec §Settings → Models Section. `ModelsAdminPanel` path is declared in the router but the component file isn't in the admin folder (`components/settings/admin/`).
- **Files:** `frontend/src/components/settings/sections/ModelsSection.tsx`, `frontend/src/components/settings/admin/ModelsAdminPanel.tsx` (create), `frontend/src/api/settings.ts:68-81` (extend).
- **Plan ref:** plan does not include frontend; spec does.
- **Spec ref:** `llm-provider-design.md` §Settings → Models Section (plus `SettingsPageSpec.md`).
- **Acceptance:** User view renders three tier cards with roster + per-tier preference dropdown writing through `PUT /settings/models/preferences/{tier}`; admin view renders provider+model CRUD table with `Test`, `Edit capabilities`, `Set as default` actions.
- **Verification:** `frontend/src/components/settings/__tests__/ModelsSection.test.tsx`.

### NEW-4-33 — `ModelInfo.context_window` never populated from provider for OpenAI (no field in `/v1/models`)
- **Severity:** P2
- **Bug:** `adapters/openai.py:72` pulls `item.get("context_length")` — OpenAI's public `/v1/models` doesn't return `context_length`; value is always `None`. Spec §Capabilities — Resolution order — leaves `context_window` as "best-effort from the shipped map" for OpenAI, so falling back is fine, but silently returning `None` without falling through to `capabilities_for(...).max_context_tokens` leaves the admin UI missing a column.
- **Files:** `packages/core/src/openlia/llm/adapters/openai.py:67-75`.
- **Plan ref:** Task 7.
- **Acceptance:** Fall back to `capabilities_for(provider_kind="openai", model=item["id"]).max_context_tokens` when `/v1/models` omits the field.

### NEW-4-34 — `services/llm_providers.py::update_provider` doesn't allow clearing `env_var_name` or `api_key`
- **Severity:** P2
- **Bug:** Guard clauses use `is not None`, so the only way to "unset the env var" or "remove the encrypted key" is to PUT `null` — but the service ignores null by design. Admin who misconfigures `OPENLIA_OPENAI_KEY` env lookup must delete + recreate the provider row.
- **Files:** `packages/server/src/openlia_server/services/llm_providers.py:105-129`.
- **Plan ref:** Task 15.
- **Acceptance:** Distinguish sentinel `UNCHANGED` vs explicit `None` (use a module-level sentinel) in the service signature, and expose via route body via `{"field": {"clear": true}}` or a dedicated `DELETE /providers/{id}/api-key` / `DELETE /providers/{id}/env-var`.

### NEW-4-35 — Dead/duplicate `_TRANSIENT` tuple + `is_transient` mismatch with plan docstring
- **Severity:** P2 (hygiene)
- **Bug:** `exceptions.py:55-64` defines `_TRANSIENT` + `is_transient`; this is used by `retry.py` but not re-exported. Once NEW-4-21 lands, `is_transient` should be exported too.
- **Files:** `packages/core/src/openlia/llm/exceptions.py`, `__init__.py`.
- **Acceptance:** `is_transient` + `_TRANSIENT` tuple listed in `__all__` of `exceptions` and re-exported from `openlia.llm`.

### NEW-4-36 — `_http.py` file present but empty on inspection
- **Severity:** P2 (potentially P1 if truly empty)
- **Bug:** `packages/core/src/openlia/llm/adapters/_http.py` read returned only `from __future__ import annotations` — but adapters import `make_client`, `status_to_exception`, `wrap_httpx_error` from it. Either the file is actually longer (1,996 bytes per `ls`) and the hook returned an observation-only stub, or it is genuinely empty and adapters fail at import time. Verify at audit execution.
- **Files:** `packages/core/src/openlia/llm/adapters/_http.py`.
- **Acceptance:** Confirm `make_client`, `status_to_exception`, `wrap_httpx_error` implementations exist; add module docstring + `__all__` if missing.
- **Verification:** `python -c "from openlia.llm.adapters._http import make_client, status_to_exception, wrap_httpx_error"` succeeds.

### NEW-4-37 — No test file for `llm_registry.SQLModelRegistry` ↔ `resolve()` integration
- **Severity:** P2
- **Bug:** `services/llm_registry.py` implements the `ModelRegistry` Protocol with real SQL queries. `resolver.py` has unit tests (`test_resolver.py`) against a fake registry, but no test exercises `SQLModelRegistry` end-to-end (user-pref → tier-default → any-in-tier → `TierNotConfiguredError`). First Postgres deploy may surface joinedload / lazy-load bugs.
- **Files:** `packages/server/tests/test_routes/test_llm_registry.py` (new).
- **Plan ref:** Task 16 "Server service layer — `llm_registry.py` (SQLModelRegistry)" (line 4576).
- **Acceptance:** Round-trip test covers all four resolver stages via real SQLite session.

### NEW-4-38 — No integration test walking wizard Step 3 → DB → resolver.resolve() for three tiers
- **Severity:** P2
- **Bug:** Spec §Testing Strategy — "Integration test runs the wizard through all three tier slots with a fake Ollama provider (HTTP-level mocked) and asserts `llm_providers` / `llm_models` table contents after Finish." Not present.
- **Files:** `packages/server/tests/test_e2e_wizard_models.py` (new).
- **Plan ref:** Task 19 "End-to-end integration test" (line 5816).
- **Acceptance:** Wizard POSTs three tier slots against respx-mocked Ollama; DB contains one provider + three models; `resolve(department_id="equity_research", registry=SQLModelRegistry(db), user_id=uid)` returns thinking tier model.

### NEW-4-39 — `OPENLIA_LLM_DEPARTMENT_<UPPER_ID>_TIER` env surface unimplemented
- **Severity:** P2
- **Bug:** Spec §Env Var Surface enumerates `OPENLIA_LLM_DEPARTMENT_<UPPER_ID>_TIER` env overrides that should shadow `llm.department.<id>.tier` ConfigStore rows and render fields read-only in Settings. No code path reads these env vars. `SQLModelRegistry.get_department_tier_override` only reads ConfigStore.
- **Files:** `packages/server/src/openlia_server/services/llm_registry.py:16-23`.
- **Plan ref:** Task 16 + spec.
- **Spec ref:** `llm-provider-design.md` §Env Var Surface.
- **Acceptance:** Registry consults env first, then ConfigStore, then null; Settings route returns `from_env: bool` flag per tier.

### NEW-4-40 — `department_defaults.DEPARTMENT_DEFAULT_TIERS` missing `NEWS`/`web_search` departments defined in spec
- **Severity:** P2 (scope: confirm no mismatch)
- **Bug:** Spec §Department default tier mapping lists seven departments; `department_defaults.py` also lists seven. Acceptable as of today; note this in the fix-plan so future department additions remember to add a tier row.

---

## Missing tests

- `packages/core/tests/test_llm/test_public_api.py` — NEW-4-21.
- `packages/core/tests/test_llm/test_adapter_retry.py` — NEW-4-20 (3× retry on transient, no retry on `AuthError`).
- `packages/core/tests/test_llm/test_capabilities_gate.py` — NEW-4-23.
- `packages/server/tests/test_routes/test_llm_user_routes.py` — NEW-4-11, P2-12 (roster, preferences CRUD, effective/{dept}).
- `packages/server/tests/test_routes/test_llm_admin_routes.py` — extend with `test_update_model_persists_tier_and_model_ref` (NEW-4-10), `test_remote_models_skipped_for_openrouter_and_ollama` (NEW-4-24), `test_create_openai_compat_model_persists_capability_override` (NEW-4-25), `test_create_provider_runs_test_by_default` (NEW-4-27).
- `packages/server/tests/test_routes/test_llm_registry.py` — NEW-4-37 (resolver+SQL integration).
- `packages/server/tests/test_e2e_wizard_models.py` — NEW-4-38.
- `packages/server/tests/test_services/test_llm_providers_service.py` — NEW-4-26 (DecryptError → AuthError), NEW-4-34 (explicit clear of env/api_key).
- `frontend/src/components/settings/__tests__/ModelsSection.test.tsx` — NEW-4-32.

## Verification checklist

- [ ] `uv run pytest packages/core/tests/test_llm/ -q` — all pass, including new `test_public_api`, `test_adapter_retry`, `test_capabilities_gate`.
- [ ] `uv run pytest packages/server/tests/test_routes/test_llm_admin_routes.py packages/server/tests/test_routes/test_llm_user_routes.py packages/server/tests/test_routes/test_llm_registry.py -q`.
- [ ] `grep -n "with_retries" packages/core/src/openlia/llm/adapters/*.py` — ≥6 hits (one per adapter).
- [ ] `grep -n "/admin/llm" planning/specs/systems/llm-provider-design.md` — 0 hits.
- [ ] `python -c "from openlia.llm import build_adapter, resolve, with_retries, ProviderCredentials, Capabilities, ModelTier, LLMProviderError, SHIPPED_TIER_DEFAULTS"` — exits 0.
- [ ] `grep -n "build_llm_user_router\|settings_llm_user" packages/server/src/openlia_server/app.py` — one mount line at `/settings/models`.
- [ ] Admin PUT `/settings/admin/llm/models/{id}` with changed `tier` + `model_ref` round-trips correctly in `test_update_model_persists_tier_and_model_ref`.
- [ ] Wizard e2e test (`test_e2e_wizard_models.py`) asserts three `llm_models` rows after Finish.
- [ ] `frontend/src/components/settings/sections/ModelsSection.tsx` renders three tier cards; admin panel renders provider + model CRUD.
- [ ] Spec path change to `/settings/admin/llm/*` committed alongside the cross-plan contract entry reference.
