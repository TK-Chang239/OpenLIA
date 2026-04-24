# Phase 4 — LLM Provider System fix plan (→ 100%)


**Current:** ~72% shipped. **Root cause:** mixed (IMPLEMENTER for missing user-pref router; SPEC_DRIFT on `/admin/llm/*` prefix; plan-impl drift on `update_model` body).

**Gap summary:** Admin CRUD, registry, adapters, and wizard Step-3 wiring all shipped, but the Plan Task 18 user-preference router was never built, `PUT /models/{id}` accepts fields it silently drops, and the shipped `/settings/admin/llm/*` prefix disagrees with the spec's `/admin/llm/*`.

**Tasks (in execution order):**

1. **P1-11 — Tighten `update_model` request body or wire the dropped fields.**
   - Files: `packages/server/src/openlia_server/routes/settings.py:311-318, 604-637`; `services/llm_providers.py` (modify if broadening service sig is preferred).
   - Plan ref: Task 17 (Admin routes — provider/model CRUD).
   - Spec ref: `llm-provider-design.md` §API Surface "Provider and model CRUD" (PUT `/models/{id}`).
   - Acceptance: either split `_ModelUpdateIn` off `_ModelIn` with only the mutable subset, or honor `model_ref` + `tier` changes. New unit test asserts PUT payload round-trips every advertised field.

2. **P2-12 / NEW-4-01 — Ship `build_llm_user_router`.**
   - Files: `packages/server/src/openlia_server/routes/settings.py` (or new file `routes/settings_llm_user.py`); `app.py:74-77, 343` (register).
   - Plan ref: Task 18 "User preference routes + wire routers into `create_app`".
   - Spec ref: `llm-provider-design.md` §API Surface "User-facing" — `GET /settings/models`, `PUT /settings/models/preference`, `GET /settings/models/effective/{department_id}`.
   - Acceptance: non-admin auth'd user can call the three routes; returns pointer-only payload (no credentials); `PUT` validates model is enabled; integration test in `test_llm_user_routes.py` covers happy path + 403 on non-existent model.

3. **P2-11 — Reconcile `/settings/admin/llm/*` prefix in spec.**
   - Files: `planning/specs/systems/llm-provider-design.md:399-433` (amend).
   - Acceptance: spec language reads `/settings/admin/llm/*`; no code change needed.

4. **NEW-4-02 — Align `openlia.llm` + `services.auth` public exports.**
   - Files: `packages/server/src/openlia_server/services/auth/__init__.py` (populate); `packages/core/src/openlia/llm/__init__.py` (verify `build_adapter`, `ModelRegistry`, `resolve_model`, capability types re-exported).
   - Plan ref: Task 1 "Scaffold `openlia/llm/`".
   - Acceptance: `from openlia.llm import build_adapter, resolve_model, ProviderCredentials, LlmProviderError` works without reaching into submodules.

5. **NEW-4-03 — Connection-test wiring via real adapter registry.**
   - Files: `packages/core/src/openlia/llm/adapters/__init__.py`; `routes/settings.py:364-399` (`_run_connection_test`).
   - Plan ref: Tasks 7–13 (adapter registry + factory).
   - Spec ref: `llm-provider-design.md` §Connection Testing.
   - Acceptance: `pytest packages/server/tests/test_routes/test_settings_connection_test.py` covers each of the six adapter kinds with `respx` mocks.

**Verification:** `uv run pytest packages/server/tests/test_routes/test_llm_user_routes.py packages/server/tests/test_routes/test_settings_llm.py packages/server/tests/test_routes/test_settings_connection_test.py packages/core/tests/test_llm/test_public_api.py` all pass; `grep -R "build_llm_user_router" packages/server/src/openlia_server/app.py` returns one mount line.
