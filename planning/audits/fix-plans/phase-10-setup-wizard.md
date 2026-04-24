# Phase 10 — Setup Wizard fix plan (→ 100%)

**Current:** ~55% shipped. **Root cause:** IMPLEMENTER (two entire route families — `/setup/models*` and `/setup/providers*` — are not wired in `routes/setup.py`, although the Task 9 and Task 10 plan sections spec them explicitly and the frontend already calls them).

**Scope verified against code (all paths absolute):**
- `packages/server/src/openlia_server/routes/setup.py` (291 lines) — only ships `GET /status`, `POST /mode`, `POST /takeover`, `POST /identity`, `POST /admin`, `POST /access_control`, `POST /review/run`, `GET /review/{id}`, `POST /finish`. Confirmed via `grep -n "@router" setup.py`.
- `packages/server/src/openlia_server/services/wizard.py` (195 lines) — status, step machine, session token, user/admin creation, signup policy, finalize. No model-save, no provider-save helpers.
- `packages/server/src/openlia_server/middleware/wizard_gate.py` (43 lines) — imports `get_db_session` at module scope (see line 9).
- `packages/server/src/openlia_server/db/models/infrastructure.py:18-29` — `WizardState` table correct shape.
- `packages/server/src/openlia_server/db/models/config.py` — `llm_providers`, `llm_models`, `data_providers`, `web_search_providers` tables exist with `api_key_encrypted` columns; services (`llm_providers.py`, `data_providers.py`) wrap `encrypt_for_row` correctly.
- `frontend/src/api/setup.ts` (120 lines) — exports `saveModels`, `testModel`, `listProviders`, `addProvider`, `patchProvider`, `deleteProvider`, `retestProvider`, `runReview`, `pollReview`, `finish`, `setAccessControl`, `takeover`. Consumed by `ModelsStep.tsx`, `TierSlotCard.tsx`, `AddProviderForm.tsx`, `ProvidersStep.tsx`.
- `frontend/src/pages/SetupPage.tsx` wires steps based on `status.current_step`. A stale `frontend/src/pages/Setup.tsx` still returns `<PagePlaceholder>` — dead code.
- Tests: `packages/server/tests/test_routes/test_setup_routes.py` covers mode, identity, admin, access_control, review, finish, takeover. **No tests** for models or providers routes — because they do not exist.

---

**Gap summary (by spec area):**
1. **Step 3 (Models) backend absent.** `POST /setup/models` and `POST /setup/models/test` are referenced by the frontend and listed in Task 9 of the plan, but no handlers exist. Wizard is uncompletable on a fresh DB.
2. **Step 4 (Data Providers) backend absent.** `GET /setup/providers`, `POST /setup/providers`, `PATCH /setup/providers/{id}`, `DELETE /setup/providers/{id}`, `POST /setup/providers/{id}/test` referenced by frontend + Task 10 — none shipped in `setup.py`. (The Settings page data-providers router at `routes/settings.py:68` is admin-gated and lives under a different prefix; it is not a substitute.)
3. **`wizard_gate.py` boundary violation.** Line 9 does `from openlia_server.db.session import get_db_session` and lines 22 & 32 use it via `Depends(get_db_session)`. The plan's Task 3 mandates factory injection only (see Design Rules in plan). This bypasses the app's `db_session_factory` in tests and in multi-engine deploys.
4. **Review runner session-lifetime race.** `routes/setup.py:215-263`'s `post_review_run` captures the request-scoped `db: Session` via `Depends(session_dep)` and passes it into `asyncio.create_task(_run_review(... db=db ...))`. The request returns immediately and FastAPI closes that session, leaving the background task with a detached session. Any ORM call on `db` inside `_run_review` risks `DetachedInstanceError` / sqlite-thread errors.
5. **Review runner builds `providers` list from kind only.** Line 236 builds `providers = [{"id": r.id, "category": r.kind, "provider": r.kind}]` — both `category` and `provider` are set to `r.kind` (wrong: `kind` is the provider kind, not a category). This feeds the AI review garbage, so review output cannot distinguish Financial vs News vs Social.
6. **Progress field missing in review poll contract.** Frontend `setup.ts:55` declares `ReviewPoll.progress: number`; backend `GET /review/{id}` returns whatever `ReviewStore.get()` holds. Verify the entry schema includes `progress`; if not, the frontend polling type lies.
7. **ProvidersStep Next skips server save.** `ProvidersStep.tsx:52` invokes `onSaved()` directly without POSTing a `providers` completion marker — wizard's `completed_steps` never gains `providers`, and reloading the wizard mid-Step-4 re-opens Step 4 every time. Needs either a dedicated `POST /setup/providers/confirm` advance endpoint, or auto-advance inside `POST /setup/providers` on each add.
8. **`WizardContext.refresh` as `onSaved` bypasses navigation.** `SetupPage.tsx:37-51` passes `refresh` as both `onBack` and `onSaved`. After a Save, Back behaves identically — no "go to previous step" logic. Spec requires linear Back/Next between steps.
9. **`requiredTiers` hardcoded.** `SetupPage.tsx:45` passes `requiredTiers={["thinking","everyday","quick"]}` — the spec requires computing the union from `DEFAULT_TIER` of enabled departments. No endpoint returns it; `ModelsStep` has no way to honor spec §Step 3.
10. **Company Step 3 gate.** `require_loopback_if_personal` guards `/setup/admin`, `/access_control`, etc., but the wizard is "bound to loopback during setup regardless of mode" (spec §Mode-Specific Behavior). Currently company-mode /setup endpoints are reachable from any origin — violates security contract.
11. **Personal step ordering vs spec.** Plan & code use `[mode, identity, models, providers, review]` (5 steps). Spec §Flow lists the same 5. OK. Company: `[mode, admin, models, providers, access_control, review]` — matches spec. No drift here.
12. **Welcome/mode content not rendered as two-card.** `ModeStep.tsx` exists — needs verification against spec's two-card picker + env-badge. Not re-verified here; call out for UI audit.
13. **Spec-file drift.** `pages/SetupWizardSpec.md` (555 lines, authoritative) disagrees with `UtilityTools/SetupWizardSpec.md` (87 lines): UtilityTools spec describes a 5-step flow with different endpoints (`/config/bootstrap-status`, `/config/llm/test`, `/auth/bootstrap-admin`) that do not exist. One must be retired.
14. **Review depends on departments hardcoded in setup.py.** `_DEPT_REQS` (lines 23-31) duplicates the enabled-department manifest that lives in core. When a new department ships (or `DEFAULT_TIER` changes), this dict silently goes stale. Should read from `openlia.departments.registry` or a shared manifest.
15. **Background task set leaks.** `_background_tasks: set[...]` at module scope (line 21) is fine for a single test run but prevents cleanup in tests that spin the app up multiple times; call out for Task 14 cleanup hook.
16. **No test coverage for Steps 3/4 endpoints.** When added, `test_setup_routes.py` needs ~10 new cases (roundtrip, test endpoint success, test endpoint adapter-failure, idempotency, priority reorder, delete, 410 gate, 409 session gate, personal-loopback gate for models/providers, required-tier gate).
17. **No frontend test for `ProvidersStep` Next gating.** `ProvidersStep.test.tsx` exists but does not assert that Next is disabled until `financial` AND `news` each have ≥1 `status === "ok"` row.
18. **`Setup.tsx` placeholder page.** `frontend/src/pages/Setup.tsx:2` still renders `<PagePlaceholder>` and is a dead file — either delete or ensure router points at `SetupPage.tsx`.
19. **`_run_review` import paths not pinned.** `from openlia.llm.adapters import build_adapter` imports inside the handler — works, but signals this logic should move to a service in `services/wizard/review.py`.

---

**Tasks (in execution order):**

1. **P0-03 — Ship `POST /setup/models` and `POST /setup/models/test`.**
   - Files: `packages/server/src/openlia_server/routes/setup.py` (append two handlers); `packages/server/src/openlia_server/services/wizard_models.py` (new — `save_models(db, payload, *, encrypt_for_row) -> list[str]`, `test_model(provider, model, api_key, base_url) -> TestResult`). `save_models` must:
     - Validate `payload.thinking/everyday/quick` entries.
     - Insert `LLMProvider` rows (one per unique provider+key) via `services.llm_providers.create_provider`, which already AES-encrypts.
     - Insert `LLMModel` rows per tier via `services.llm_providers.create_model`.
     - Enforce at most one `is_tier_default=True` per tier (use existing `uq_llm_models_tier_default` constraint).
     - Be idempotent: a second POST replaces prior wizard-staged models (not settings models) — deletion gated on `wizard.completed == false`.
   - `test_model` calls `openlia.llm.adapters.build_adapter(...)` + a 1-token completion, returns `{ok, latency_ms, error}`.
   - Add `advance_step(db, "models", mode)` at end of handler.
   - Spec ref: pages/SetupWizardSpec.md §Step 3; impl plan Task 9 lines 1338-1571.
   - Acceptance tests in `test_setup_routes.py`: `test_post_models_roundtrip`, `test_post_models_test_success` (stub adapter), `test_post_models_test_failure`, `test_post_models_rejects_unknown_provider`, `test_post_models_requires_loopback_personal`, `test_post_models_410_after_completion`, `test_post_models_409_without_session_token`.

2. **P0-03b — Ship `GET/POST/PATCH/DELETE /setup/providers*`.**
   - Files: `routes/setup.py` (5 new handlers); optional service `services/wizard_providers.py` that delegates to existing `services.data_providers`.
   - Handlers:
     - `GET /setup/providers` → `list_providers(db)` grouped by category with status pill (`ok`|`error`|`pending`).
     - `POST /setup/providers` body `{category, entry: {mode, provider?, api_key?, mcp_url?, mcp_auth_header?, openapi_spec_url?}}` — run test before persist; return `{ok, entry_id, error?}`.
     - `PATCH /setup/providers/{id}` — priority reorder and/or api_key rotation.
     - `DELETE /setup/providers/{id}` — delete + rebalance priority.
     - `POST /setup/providers/{id}/test` — re-ping; update row status.
   - After `POST` of first green `financial` **and** `news`, call `advance_step(db, "providers", mode)`. Alternative: add explicit `POST /setup/providers/confirm` and update `ProvidersStep.tsx` to call it in `onNext`.
   - Must reuse `services.data_providers.create_provider` so AES encryption path is unchanged.
   - Spec ref: pages/SetupWizardSpec.md §Step 4; impl plan Task 10 lines 1572-1807.
   - Acceptance tests: roundtrip add, list, priority patch, delete, re-test, 422 when category invalid, 410 after completion, 409 without session cookie, personal-loopback gate.

3. **NEW-10-01 — Fix `ProvidersStep.onNext` to call backend advance.**
   - Files: `frontend/src/setup/steps/ProvidersStep.tsx:52-59`, `frontend/src/api/setup.ts` (add `confirmProviders()`).
   - Acceptance: after adding one green financial + one green news, Next POSTs to `/setup/providers/confirm`, `completed_steps` includes `providers`, navigation advances.

4. **NEW-10-02 — Hardcoded `requiredTiers` → dynamic.**
   - Files: `frontend/src/pages/SetupPage.tsx:45`, new server endpoint `GET /setup/required_tiers` (or extend `/setup/status` payload) that reads `DEFAULT_TIER` from each enabled department via a shared manifest.
   - Backend source: `packages/core/src/openlia/departments/<id>.py` — each ships a `DEFAULT_TIER` attribute; add a registry helper in `core/openlia/departments/__init__.py` → `get_enabled_default_tiers(enabled: list[str]) -> set[str]`.
   - Acceptance: disabling a department in Step 1 (future) or toggling `departments` config surfaces an updated required-tier set; unit test stubs `openlia.departments.registry` to return `{thinking, quick}` and asserts `ModelsStep` disables Next until both are green.

5. **P1-15 — Fix `wizard_gate.py` session injection.**
   - Files: `packages/server/src/openlia_server/middleware/wizard_gate.py` — remove module-level `from openlia_server.db.session import get_db_session`. Convert to factory-based dependencies built in `build_setup_router`, or accept an injected `session_dep` via `make_session_dependency` (pattern already used in `routes/setup.py:104`).
   - Acceptance: `grep -R "get_db_session" packages/server/src/openlia_server/middleware/` returns empty; `test_wizard_gate.py` updated to build gate via factory.

6. **P1-16 — Fix `review/run` session-lifetime race.**
   - Files: `routes/setup.py:215-263`. `_run_review` task must open its own session via `db_session_factory()` context manager. Pass the factory into `_ReviewLLMWrapper`/runner rather than the live `db`.
   - Tie into Task 4: move review orchestration into `services/wizard_review.py` so the handler only creates a review id and schedules.
   - Acceptance: regression test spawns `/review/run`, immediately polls `/review/{id}` repeatedly through `complete`, asserts no `DetachedInstanceError` in logs (capture with `caplog`).

7. **NEW-10-03 — Fix `_run_review` provider payload.**
   - Files: `routes/setup.py:236`. Build `providers = [{"id": r.id, "category": r.category, "kind": r.kind, "provider": r.kind, "priority": r.priority}]` from the actual `DataProvider` row. Confirm `DataProvider` model exposes `category` (per `db/models/config.py:90-106`); if not, derive from `kind`→`category` mapping.
   - Acceptance: review payload in `ReviewStore` shows correct category routing per department.

8. **NEW-10-04 — Pull review poll contract straight.**
   - Files: `packages/server/src/openlia_server/ai_review/store.py` (verify `progress` field present), `routes/setup.py:266-276` response shape. Align with `frontend/src/api/setup.ts:52-57` `ReviewPoll`.
   - Acceptance: `test_review_poll_shape` asserts keys `{state, progress, result, error}`.

9. **NEW-10-05 — Loopback enforcement during entire wizard (company too).**
   - Files: `routes/setup.py:106-114`. Spec §Mode-Specific Behavior: "During the wizard itself the server remains bound to loopback regardless of mode". Change `require_loopback_if_personal` into `require_loopback_during_wizard` (drop mode check) **and** enforce at the app bind level via `lifespan` so company-mode wizard still binds 127.0.0.1 until `wizard.completed == true`.
   - Acceptance: `test_e2e_smoke_matrix.py` addition — in company mode with `wizard.completed=false`, non-loopback POST returns 403; after finalize + restart, normal bind host is honored.

10. **NEW-10-06 — Dynamic `_DEPT_REQS`.**
    - Files: `routes/setup.py:23-31` → read from `openlia.departments.registry` (new helper) rather than duplicating.
    - Acceptance: `test_review_uses_registry_requirements` patches registry to add a synthetic department and asserts it appears in the review card set.

11. **NEW-10-07 — Reconcile two spec files.**
    - Files: `planning/specs/pages/SetupWizardSpec.md` (authoritative) vs `planning/specs/UtilityTools/SetupWizardSpec.md` (stale 5-step draft referencing `/config/bootstrap-status` endpoints that do not exist).
    - Action: replace UtilityTools file body with a one-line redirect pointer to the pages spec; or delete and update any inbound references.
    - Acceptance: `grep -r "/config/bootstrap-status\|/config/llm/test\|/auth/bootstrap-admin" planning/specs/` returns empty or only the authoritative Login spec.

12. **NEW-10-08 — `Setup.tsx` dead file cleanup.**
    - Files: delete `frontend/src/pages/Setup.tsx` (still a `<PagePlaceholder>`), confirm `SetupPage.tsx` is what the router mounts.
    - Acceptance: `grep -rn "pages/Setup\"" frontend/src` returns only `SetupPage`.

13. **NEW-10-09 — `WizardContext` navigation: Back vs Refresh.**
    - Files: `frontend/src/pages/SetupPage.tsx:35-55`, `WizardContext.tsx`. Separate `onBack` (move to previous `completed_steps` entry, e.g. via `POST /setup/step_back` or purely client-side) from `onSaved` (server-driven refresh after advance).
    - Acceptance: manual — on Step 3, clicking Back returns to Step 2 (Identity/Admin) without losing unsaved input on forward navigation.

14. **NEW-10-10 — Takeover UX on 409.**
    - Files: `frontend/src/api/client.ts` or a new wrapper — on `409 wizard_session_active` from any `/setup/*` route, show modal "Setup already in progress in another window. Take over?" which calls `POST /setup/takeover` and retries the original request.
    - Acceptance: vitest — mock first call to 409, second to 200; assert modal rendered, user click triggers takeover + retry.

15. **NEW-10-11 — Tests for models + providers endpoints.**
    - Files: extend `packages/server/tests/test_routes/test_setup_routes.py` with sections "Task 9: POST /setup/models" and "Task 10: /setup/providers*" mirroring plan's acceptance criteria.
    - Targets: 7 tests for models, 8 for providers, 1 for required-tiers endpoint (if taken), 1 for step advance on final required provider.

16. **NEW-10-12 — Frontend tests for gating logic.**
    - Files: `ModelsStep.test.tsx` — add case "Next disabled when `quick` tier has no green entry". `ProvidersStep.test.tsx` — add case "Next disabled when no green News provider".
    - Acceptance: `npm run test --run` both pass.

17. **NEW-10-13 — E2E smoke for fresh install completion.**
    - Files: `packages/server/tests/test_e2e_smoke_matrix.py` or new file. Script: fresh DB → `GET /setup/status` → `POST /setup/mode personal` → `/identity` → `/models` → `/providers` (one financial + one news) → `/review/run` + poll → `/finish` → assert `wizard_completed == true`, assert 410 on subsequent `/setup/identity`.
    - Acceptance: green in CI.

18. **NEW-10-14 — Background task lifecycle.**
    - Files: `routes/setup.py:21` and app shutdown hook in `app.py`. Register `_background_tasks` cancel on `lifespan` exit; move set into router factory closure instead of module scope.
    - Acceptance: `test_app_lifespan.py` adds a case spawning review-run and verifying clean shutdown.

19. **NEW-10-15 — Persist mode on `WizardState.mode` column.**
    - Files: `services/wizard.py:107-113` — `set_mode` writes to `config_store` key `wizard.mode` but ignores the `WizardState.mode` column (defined `infrastructure.py:27`). Either drop the column via Alembic, or write both (spec's cross-plan contract has `WizardState` as source of truth during setup, `config_store.wizard.mode` after finalize).
    - Acceptance: `test_set_mode_persists_both_columns` or an ADR note justifying one-sided write.

---

**Verification:**
- `uv run pytest packages/server/tests/test_routes/test_setup_routes.py packages/server/tests/test_services/test_wizard.py packages/server/tests/test_middleware/test_wizard_gate.py packages/server/tests/test_db/test_wizard_state_shape.py` green.
- `uv run pytest packages/server/tests/test_e2e_smoke_matrix.py -k setup` green.
- `cd frontend && npm run test -- --run src/setup src/api/setup.test.ts src/pages/SetupPage.test.tsx` green.
- Manual: rm `~/.openlia/openlia.db`, `uv run openlia serve`, open `http://127.0.0.1:8000`, complete Welcome → Identity → Models → Providers → Review → Finish; assert landing on `/` with `wizard_completed == true`.
- Manual (company): same but with `OPENLIA_MODE=company`, verify final redirect to `/login` and 403 on non-loopback during wizard.
- `grep -R "get_db_session" packages/server/src/openlia_server/middleware/` returns empty.
- `grep -R "setup/models\|setup/providers" packages/server/src/openlia_server/routes/setup.py` shows ≥7 route handler lines.
