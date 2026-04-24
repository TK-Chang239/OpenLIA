# Phase 11 — Settings Page fix plan (→ 100%)


**Current:** ~72% shipped. **Root cause:** IMPLEMENTER (auth gate omitted + missing migration + test debt).

**Gap summary:** Settings UI and routes shipped, but three new route modules bypass `must_change_password` gate (direct REM-P1-001 violation); `user_prefs` Alembic migration never generated; admin service + admin route + frontend tests largely absent.

**Tasks (in execution order):**

1. **P0-06 (prerequisite) — Fix `build_require_auth` return shape** (see Phase 2 entry).

2. **P0-07 — Apply `build_require_active_user` to settings routes.**
   - Files: `settings_general.py:49`, `settings_email.py:22`, `settings_models.py:24` — replace `Depends(build_require_auth(...))` with `Depends(build_require_active_user(...))`.
   - Spec ref: SettingsPageSpec §Must-change-password gate.
   - Acceptance: `test_settings_blocked_when_must_change_password` — authenticate user with `must_change_password=true`, call `GET /settings/prefs` → 403 with `code: "must_change_password"`; repeat for `/settings/email` and `/settings/admin/llm/*`.

3. **P0-09 (user_prefs slice) — Generate `user_prefs` Alembic migration.**
   - Files: `packages/server/src/openlia_server/db/alembic/versions/2026-04-XX_user_prefs.py` (new).
   - Spec ref: SettingsPageSpec §General tab.
   - Acceptance: `uv run alembic upgrade head` on fresh Postgres creates `user_prefs`; `test_migrations.py` EXPECTED_TABLES contains `user_prefs`.

4. **P1-11 — `update_model` route accepts-but-drops `model_ref` + `tier`** (see Phase 4 entry).

5. **P2-14 — Ratify `MustChangePasswordGate` router-level implementation.**
   - Files: amend Phase 11 plan §"Must-change-password gate".
   - Acceptance: plan text matches shipped architecture.

6. **P2-TESTS (slice) — Fill Phase 11 test gaps.**
   - Files: `test_settings_general.py`, `test_settings_email.py`, `test_settings_models.py`, `test_user_prefs.py`, `test_settings_email_service.py`, `test_settings_models_service.py`; frontend `SettingsPage.test.tsx` + section vitests.
   - Acceptance: coverage for new modules ≥80%.

7. **NEW-11-01 — SettingsPageSpec per-tab parity audit.** Why new: tracker focused on auth gate + migration; spec has per-tab requirements.
   - Files: per-section tsx + matching service routes.
   - Acceptance: spec walk-through lists each tab as shipped or gap.

**Verification:** `uv run pytest packages/server/tests/test_routes/test_settings* packages/server/tests/test_migrations.py` green.
