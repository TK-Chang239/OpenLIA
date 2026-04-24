# Phase 10 — Setup Wizard fix plan (→ 100%)


**Current:** ~72% shipped. **Root cause:** IMPLEMENTER (Step 3 backend absent).

**Gap summary:** Wizard frontend and Steps 1/2/4/5/6 shipped, but Step 3 (Models) backend returns 404 — wizard uncompletable. `wizard_gate` session handling and background review task both have correctness bugs. Spec file in `UtilityTools/` may drift from `pages/`.

**Tasks (in execution order):**

1. **P0-03 — Ship `POST /setup/models` + `POST /setup/models/test`.**
   - Files: `packages/server/src/openlia_server/routes/setup.py` (append two handlers); `services/wizard/models.py` (new — `save_models(db, payload) → None`, `test_model(db, payload) → {ok, latency_ms, error}`).
   - Spec ref: SetupWizardSpec §Step 3 "Tier configuration".
   - Acceptance: `test_setup_models_roundtrip` saves a model, then `GET /setup/status` shows `completed_steps` includes `models`; `test_setup_models_test_success` stubs adapter call and asserts `{ok: true}`.

2. **P1-15 — Fix `wizard_gate.py` session injection.**
   - Files: `packages/server/src/openlia_server/middleware/wizard_gate.py:9` — remove `from ...db.session import get_db_session`; accept injected factory via closure.
   - Acceptance: `grep -R "get_db_session" packages/server/src/openlia_server/middleware/` returns empty.

3. **P1-16 — Fix `review/run` session-lifetime race.**
   - Files: `routes/setup.py:250-261` — `_run_review` must open its own session via `session_factory()` context manager rather than capturing request-scoped `db`.
   - Acceptance: regression test spawns `/review/run`, immediately returns, polls `/review/{id}` without `DetachedInstanceError`.

4. **NEW-10-01 — Reconcile `pages/SetupWizardSpec.md` vs `UtilityTools/SetupWizardSpec.md`.** Why new: tracker doesn't call out the two-file split.
   - Files: both spec files.
   - Acceptance: one canonical file; the other redirects with a pointer.

5. **NEW-10-02 — Step 3 frontend `tier_complete` gating.** Why new: spec §Step 3 mandates "required-tier set" gate; verify frontend blocks Next until every tier has ≥1 model.
   - Files: `frontend/src/components/setup/ModelsStep.tsx` (or equivalent).
   - Acceptance: vitest — with one required tier missing, Next button disabled + helper text.

6. **NEW-10-03 — Takeover dialog on concurrent session.** Why new: spec §Resume requires "Setup already in progress in another window. Take over?" prompt.
   - Files: frontend wizard bootstrap, `routes/setup.py` takeover endpoint (line 147 exists — verify frontend uses it).
   - Acceptance: manual two-browser test shows dialog.

**Verification:** `uv run pytest packages/server/tests/test_setup*` green; manual: fresh DB → wizard runs Welcome→Identity→Models→Providers→Review without 404.
