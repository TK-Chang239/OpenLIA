# Phase 11 — Settings Page fix plan (→ 100%)

**Status at audit (2026-04-24):** ~68% shipped (down from tracker's 72% once
frontend completeness is tallied honestly).

**Root cause:** IMPLEMENTER — three new route modules forgot the
`must_change_password` gate, admin-side frontend panels (Models, Data
Providers) were stubbed, and the Unsaved-Changes navigation guard / admin
one-shot reset flow were either unwired or replaced with a `window.prompt`.
Backend `user_prefs` migration **did land** (file
`db/migrations/versions/2026-04-22-2100_add_user_prefs.py`) contrary to the
earlier audit note; close that portion of P0-09.

**Gap summary:** Server routes largely complete but three leak past the
must-change-password gate (P0-07). Admin CRUD frontend is a stub
(`ModelsAdminPanel` 15 lines; `DataProvidersAdminPanel` read-only,
hard-coded wrong URL). Users panel violates spec (prompts admin for
temp password instead of server-generating + one-time display). No
navigation guard. Service-level admin tests missing. Per-department
tier defaults reference panel (spec §Models → Per-department tier
defaults) not built. `settings_email.py` is account-email change only —
spec/plan contain no SMTP admin; the user-prompt mention of "SMTP test
endpoint" is non-existent scope and is therefore not tracked here.
"Schedules" / "Departments" tabs also not part of the Phase 11 spec.

---

## P0 — Auth / data-integrity blockers

### P0-07 — Settings routes bypass `build_require_active_user`

- **Severity:** P0 (direct REM-P1-001 violation; users flagged
  `must_change_password=true` can edit prefs, email, and LLM
  preferences before setting a new password).
- **Bug:** Three factories call `build_require_auth(...)` instead of the
  `build_require_active_user` wrapper that rejects flagged users with
  `{"code":"must_change_password"}`.
- **Files (verified):**
  - `packages/server/src/openlia_server/routes/settings_general.py:49`
    (`require_auth = build_require_auth(...)`); used at `:55` and `:64`.
  - `packages/server/src/openlia_server/routes/settings_email.py:22`;
    used at `:29`.
  - `packages/server/src/openlia_server/routes/settings_models.py:26`;
    used at `:32`, `:41`, `:71`.
  - Import site: `middleware/auth.py:78` defines
    `build_require_active_user`; `:104` defines
    `build_require_active_admin` (the admin routes already use it —
    `routes/admin.py:34`, `routes/settings.py:79/406`).
- **Plan ref:** 2026-04-17-phase-11 §Design Rules #4; Task 23
  "Must-change-password enforcement at the shell".
- **Spec ref:** `SettingsPageSpec.md` §Change Password — "must-change
  banner … other navigation is blocked until the password is changed".
- **Acceptance:**
  - Replace `build_require_auth` with `build_require_active_user` in
    the three factories. Keep the admin LLM factory on
    `build_require_active_admin` (already correct in `settings.py`).
  - Extend `tests/test_routes/test_must_change_password_gate.py` (or
    per-route test files) with parametrised coverage for:
    `GET /settings/prefs`, `PATCH /settings/prefs`,
    `PATCH /settings/email`,
    `GET /settings/admin/llm/preferences`,
    `PUT /settings/admin/llm/preferences`,
    `DELETE /settings/admin/llm/preferences/{tier}` →
    403 with body `{"detail":{"code":"must_change_password"}}`.
- **Verification:** `uv run pytest
  packages/server/tests/test_routes/test_must_change_password_gate.py
  packages/server/tests/test_routes/test_settings_*`.

### P0-09 (user_prefs slice) — CLOSE

- **Severity:** P0 was tracked; on reinspection the migration exists.
- **Evidence:**
  - `packages/server/src/openlia_server/db/migrations/versions/2026-04-22-2100_add_user_prefs.py`
    creates `user_prefs` with FK to `users.id`, the theme check
    constraint (`ck_user_prefs_theme`), and the language check
    constraint (`ck_user_prefs_language`).
  - `db/models/config.py:126` declares `UserPrefs` with matching
    `__tablename__ = "user_prefs"` (line 127).
- **Action:** Update master tracker §2 P0-09 to remove the `user_prefs`
  bullet; confirm
  `packages/server/tests/test_migrations.py::EXPECTED_TABLES` contains
  `user_prefs` before closing. No code change required here.

---

## P1 — Feature/contract gaps

### NEW-11-02 — `UsersPanel` admin reset flow diverges from spec

- **Severity:** P1.
- **Bug:** The admin "Reset Password" action in the frontend uses
  `window.prompt('Enter a temporary replacement password')` and POSTs
  the admin-typed password to
  `/api/admin/users/{id}/direct-reset` with
  `{ new_password }` (see `UsersPanel.tsx:38–41`). Spec requires the
  **server** to generate a random temp password, sets
  `must_change_password=true`, revokes sessions, and returns it to the
  admin exactly once in a copy-ready modal with
  "This value will not be shown again".
- **Files:**
  - `frontend/src/components/settings/admin/UsersPanel.tsx:38–41`.
  - `frontend/src/api/admin.ts:72` (`adminResetPassword(id, new_password)`).
  - `packages/server/src/openlia_server/routes/admin.py:136` handler
    `direct_reset` + `DirectResetIn(new_password: str)` at `:28`.
  - `packages/server/src/openlia_server/services/auth/password_reset.py`
    (`admin_direct_reset`).
- **Plan ref:** Plan 11 Task 19 (UsersPanel).
- **Spec ref:** `SettingsPageSpec.md` §Users → Reset Password (direct).
- **Acceptance:**
  - Server side: change `DirectResetIn` to optional-or-none; have the
    handler call a helper that generates a secure random password
    (e.g. `secrets.token_urlsafe(18)`), hashes/stores it, sets
    `must_change_password=true`, revokes sessions, and returns
    `{ "temporary_password": "<plain>" }`.
  - Frontend: replace `window.prompt` with an inline confirm + call
    `adminResetPassword(id)` (no password arg); display the returned
    `temporary_password` in `OneTimeSecretModal` with the standard
    "won't be shown again" copy.
  - Tests: unit test on `services/auth/password_reset.py::admin_direct_reset`
    verifying randomness, hash, `must_change_password=true`, session
    revoke, `password_reset_by_admin` audit row. Route-level test
    verifies the temp password appears in the 200 body once and that
    `GET` never leaks it.
- **Verification:** `uv run pytest
  packages/server/tests/test_services/test_admin_password_reset.py
  packages/server/tests/test_routes/test_admin_routes.py`; frontend
  `UsersPanel.test.tsx` covers modal render + copy button.

### NEW-11-03 — `DataProvidersAdminPanel` calls the wrong endpoint and is read-only

- **Severity:** P1.
- **Bug:**
  - Calls `/api/data-providers` (no such route). The shipped router is
    `/settings/data-providers` — see `routes/settings.py:82`
    (`prefix="/settings/data-providers"`).
  - Panel is read-only; spec requires add/edit/delete, connection test,
    and a requirement-mapping table below the provider list.
  - Types hardcoded (`kind: 'builtin' | 'mcp' | 'openapi'`) do not
    match the shipped server model
    (`Literal["financial","news","social_media"]` for category; `kind`
    is an open string).
- **Files:**
  - `frontend/src/components/settings/admin/DataProvidersAdminPanel.tsx:19, 3–10, 44–67`.
  - `frontend/src/api/` (new file `data_providers.ts` needed; none
    exists today).
  - Server surface already shipped:
    `routes/settings.py:68–266` (CRUD + `/auto-map`, `/mappings`,
    `/test-connection`).
- **Plan ref:** Plan 11 Task 21 "reuse Plan 10 components".
- **Spec ref:** `SettingsPageSpec.md` §Data Providers (admin CRUD).
- **Acceptance:**
  - New typed API client at `frontend/src/api/data_providers.ts`
    wrapping the `/settings/data-providers*` routes.
  - Rewrite the panel with Create/Edit form (kind, label, category,
    mode, api_key password input, env_var_name alt, base_url,
    extra_config), connection-test button calling
    `POST /settings/data-providers/{id}/test-connection`, and a
    requirement-mapping table using `GET /mappings` +
    `PUT /mappings/{requirement_type}`.
  - Delete is blocked when assigned to a mapping (surface 409 error).
  - Frontend tests in `admin/__tests__/DataProvidersAdminPanel.test.tsx`
    covering create / delete-while-mapped / test-connection success.
- **Verification:** `npm run test` + manual smoke via admin role.

### NEW-11-04 — `ModelsAdminPanel` is a 15-line placeholder

- **Severity:** P1.
- **Bug:** Panel shows "Server-wide model CRUD is not yet wired up in
  this panel. Use the setup wizard to edit the roster." Plan 11
  Task 21 required reusing Plan 10 model CRUD (providers + models
  tables, inline forms, tier-default constraint UI, connection test).
  All eight endpoints under `/settings/admin/llm/*` (listed in
  `routes/settings.py:400–673`) are already server-side shipped and
  unused by this panel.
- **Files:**
  - `frontend/src/components/settings/admin/ModelsAdminPanel.tsx:1–15`.
  - Existing test `admin/__tests__/ModelsAdminPanel.test.tsx` asserts
    only the placeholder copy — rewrite when the real UI lands.
  - Server surface (reuse):
    - `GET/POST /providers`, `POST /providers/test`,
      `PUT/DELETE /providers/{id}`, `GET /providers/{id}/models`,
      `GET /providers/{id}/remote-models`,
      `POST /models`, `PUT /models/{id}`,
      `DELETE /models/{id}`,
      `POST /department/{department_id}`,
      `POST /capability_override/{kind}/{model}`.
- **Plan ref:** Plan 11 Task 21; Plan 10 setup-wizard model components.
- **Spec ref:** `SettingsPageSpec.md` §Models (admin CRUD) + soft-
  reminder banner for tiers with zero enabled models.
- **Acceptance:**
  - Real admin CRUD: provider cards, per-provider model table, inline
    create/edit forms, connection test, tier-default enforcement,
    delete-with-fallback semantics.
  - New typed API client at `frontend/src/api/llm_admin.ts`.
  - Banner "The {tier} tier has no models configured …" when any tier
    has zero `is_enabled` rows across the roster.
  - Rewrite `ModelsAdminPanel.test.tsx`.
- **Verification:** `npm run test`.

### NEW-11-05 — `ModelsSection` missing per-department tier defaults panel

- **Severity:** P1.
- **Bug:** `ModelsSection.tsx` renders the three tier pickers but
  never renders the read-only "Per-department tier defaults" table
  required by spec, nor the info icon surfacing
  `DEFAULT_TIER_REASON`.
- **Files:** `frontend/src/components/settings/sections/ModelsSection.tsx`
  (127 lines — only tier loop + Save).
- **Plan ref:** Plan 11 Task 15.
- **Spec ref:** `SettingsPageSpec.md` §Models → Per-department tier
  defaults table.
- **Acceptance:** Add a read-only panel below the three tier cards
  listing the seven departments with their default tier and hover
  tooltip showing `DEFAULT_TIER_REASON`. Source data via a new
  `GET /settings/admin/llm/department-defaults` endpoint or, if
  already derivable, via the existing
  `openlia.llm.config.DEPARTMENT_TIER_DEFAULTS` constant re-exposed to
  the frontend.
- **Verification:** vitest `ModelsSection.test.tsx` covers render.

### P1-11 — `update_model` accepts-but-drops `model_ref` + `tier`

- **Severity:** P1 (data-integrity; silent field loss).
- **Bug:** `_ModelIn` in `routes/settings.py:311–319` declares
  `model_ref` and `tier` required, but the `PUT /models/{model_id}`
  handler (`:604–637`) only forwards `display_name`,
  `is_tier_default`, `is_enabled`, `overrides` to
  `llm_svc.update_model`. Callers who change `model_ref`/`tier`
  succeed but nothing persists.
- **Files:**
  - `packages/server/src/openlia_server/routes/settings.py:604–637`.
  - `packages/server/src/openlia_server/services/llm_providers.py`
    `update_model` signature.
- **Plan ref:** Plan 4 §Admin routes; Plan 11 Task 21 inherits.
- **Spec ref:** `SettingsPageSpec.md` §Models (admin CRUD) — Model Ref
  and Tier are editable fields in the Create/Edit form.
- **Acceptance:**
  - Either **(a)** extend `llm_svc.update_model` and the route to
    accept and persist `model_ref` + `tier`, enforcing the
    "at most one default per tier" constraint on a tier change; or
    **(b)** split the PUT into a separate
    `_ModelUpdate` pydantic with an explicit field set and 422 on
    attempted `model_ref`/`tier` edit with a helpful message.
  - Option (a) preferred; add route test asserting the updated
    `model_ref`/`tier` round-trip, and a test exercising the
    default-clear-on-tier-change branch.
- **Verification:** `uv run pytest
  packages/server/tests/test_routes/test_llm_admin_routes.py`.

### NEW-11-06 — Unsaved-changes navigation guard never wired

- **Severity:** P1 (spec-mandated UX; active data-loss risk).
- **Bug:** `UnsavedChangesModal` exists at
  `frontend/src/components/settings/UnsavedChangesModal.tsx` but is
  never imported or rendered anywhere outside its own file. Grep:
  only self-reference. `SettingsShell` has no `useBlocker` /
  `unstable_usePrompt` hook; clicking a sidebar item with dirty form
  state destroys the unsaved edits silently.
- **Files:**
  - `frontend/src/components/settings/SettingsShell.tsx`.
  - `frontend/src/components/settings/UnsavedChangesModal.tsx`.
  - `frontend/src/components/settings/useDirtyForm.ts:21`
    (hook exposes `isDirty` but no shell-level collector).
- **Plan ref:** Plan 11 Task 11 "Dirty-form hook + unsaved-changes
  modal"; Design Rule #3.
- **Spec ref:** `SettingsPageSpec.md` §Unsaved Changes Modal and
  §Navigation Guard.
- **Acceptance:**
  - Introduce `SettingsDirtyContext` (new file
    `frontend/src/components/settings/dirty-context.tsx`) with
    `register(sectionId)`/`unregister(sectionId)` and
    `isAnyDirty()`. Each section's `useDirtyForm` reports in.
  - `SettingsShell` wraps `<Outlet />` in a
    `unstable_usePrompt`/`useBlocker` bridge; on block, opens
    `UnsavedChangesModal`. Confirm discard → proceed; cancel → stay.
  - Also register a `beforeunload` handler for hard nav.
  - Tests in `SettingsShell.test.tsx` cover: dirty + click sibling
    nav → modal opens; Stay keeps URL; Leave navigates.
- **Verification:** `npm run test`.

### NEW-11-07 — `GeneralSection` patch drops language fields

- **Severity:** P1.
- **Bug:** `GeneralSection.save` (`sections/GeneralSection.tsx:57–62`)
  builds the patch with only `display_name`, `theme`, `notify_inapp`,
  `notify_email`. Languages live in `AccountSection`. If the user
  edits language *then* General in the same session without
  persisting languages first, nothing breaks — but the shell never
  propagates the latest full `Prefs` back to other sections because
  each section re-fetches independently. That's acceptable; however
  the plan's Task 14 explicitly listed display name + notifications +
  appearance only. Call this out as a **spec mismatch**: the spec's
  General section also covers Appearance (already shipped) but the
  Language dropdowns live under Account per spec — confirm this
  matches and leave as-is.
- **Resolution:** No code change. Update the Phase 11 plan Task 14
  header comment to explicitly note "language fields ship under
  Account per spec" to prevent future confusion.
- **Verification:** Diff check only.

### NEW-11-08 — `/settings/admin/llm/preferences` prefix collision with admin LLM router

- **Severity:** P1 (route mapping).
- **Bug:** `settings_models.py:25` declares
  `prefix="/settings/admin/llm"`, same as the admin LLM provider
  router at `settings.py:405`. Both factories are registered by
  `app.py`; the per-user `preferences` endpoints happen not to collide
  with the admin `/providers`, `/models`, etc. — but any future route
  added under `/settings/admin/llm/<static>` risks silent shadowing.
  The prefix also misleadingly places a **user-level** resource under
  `/admin/`.
- **Files:**
  - `packages/server/src/openlia_server/routes/settings_models.py:25`.
  - `packages/server/src/openlia_server/routes/settings.py:405`.
  - `frontend/src/api/settings.ts:71, 74, 80` (uses the `/admin/llm`
    prefix for user preferences).
- **Plan ref:** Plan 4/11 cross-plan contract; master tracker P2-11.
- **Spec ref:** `SettingsPageSpec.md` §Models — "preferences" is a
  user-level resource; no `/admin` in its path.
- **Acceptance:**
  - Move user preferences to `/settings/models/preferences` (or
    `/settings/llm/preferences`). Update
    `frontend/src/api/settings.ts` and the three tests accordingly.
  - Keep admin provider/model CRUD at `/settings/admin/llm/*`.
  - Add a contract row to `planning/docs/endpoint-contract-matrix.md`.
- **Verification:** `uv run pytest
  packages/server/tests/test_routes/test_settings_models_routes.py`
  + `npm run test -- settings`.

---

## P2 — Test coverage, documentation, polish

### P2-14 — Ratify `MustChangePasswordGate` router-level implementation

- **Severity:** P2.
- **Bug:** Plan 11 §Design Rules #4 describes `MustChangePasswordGate`
  wrapping `SettingsPage`; shipped implementation puts the gate at
  the router layer (`frontend/src/router/MustChangePasswordGate.tsx`)
  instead. Equivalent behaviour, but the plan text is wrong.
- **Files:**
  - `planning/implementation-plans/2026-04-17-phase-11-settings-page.md`
    §Design Rules #4 and §Task 23.
  - `frontend/src/router/MustChangePasswordGate.tsx`.
- **Acceptance:** Amend the plan and Task 23 to record "gate at
  router level (forces users into `/settings/account` via the
  router wrapper) rather than wrapping `<SettingsPage>` directly".
- **Verification:** Diff check.

### NEW-11-09 — Missing server tests (Phase 11 plan coverage)

- **Severity:** P2.
- **Bug:** Plan 11 §New backend tests lists six admin test files that
  were never created: `test_admin_invites.py`, `test_admin_users.py`,
  `test_admin_password_reset.py` (services) and
  `test_admin_invites_routes.py`, `test_admin_users_routes.py`,
  `test_admin_password_reset_routes.py` (routes). Shipped files:
  `tests/test_routes/test_admin_routes.py` (119 lines, combined) and
  no service-level tests.
- **Files:**
  - Create `packages/server/tests/test_services/test_admin_invites.py`,
    `test_admin_users.py`, `test_admin_password_reset.py`.
  - Split `tests/test_routes/test_admin_routes.py` into the three
    per-surface files (or at least add the missing coverage inside
    the existing file).
- **Plan ref:** Plan 11 §File Structure → New backend tests.
- **Acceptance:**
  - `uv run pytest packages/server/tests/test_services/test_admin_*`
    green with ≥80% coverage of the three admin service modules.
  - Route tests cover: admin-gate 403 for non-admin, 403 with
    `must_change_password` admin, invite token-hash round-trip,
    reset-request approval one-shot, disable-revokes-sessions, and
    the new direct-reset flow from NEW-11-02.
- **Verification:** `uv run pytest packages/server/tests`.

### NEW-11-10 — Missing frontend tests (Phase 11 plan coverage)

- **Severity:** P2.
- **Bug:** Plan 11 §New frontend tests listed nine files; shipped
  eleven, but three are thin placeholders
  (`ModelsAdminPanel.test.tsx` 28 lines asserts only placeholder,
  `AdminSection.test.tsx` 30 lines smoke, `DataProvidersAdminPanel`
  has **no** test file at all). No integration-level test of the
  full `SettingsPage` route tree.
- **Files:**
  - Add `frontend/src/components/settings/admin/__tests__/DataProvidersAdminPanel.test.tsx`.
  - Rewrite `ModelsAdminPanel.test.tsx` once NEW-11-04 lands.
  - Add `frontend/src/pages/__tests__/SettingsPage.test.tsx`
    covering: admin sees Admin tab; non-admin does not; must-change
    redirect; 404 → general redirect.
- **Plan ref:** Plan 11 §New frontend tests.
- **Acceptance:** `npm run test` shows ≥80% coverage on Settings
  components.
- **Verification:** `npm run test -- settings`.

### NEW-11-11 — `admin.ts` has no typed error envelope parity

- **Severity:** P3 (DX).
- **Bug:** `api/admin.ts:38` re-implements `request<T>` with a
  slightly different error shape than `api/settings.ts:45`. Two
  ad-hoc `ApiError` constructors cause slight drift in code/
  message fallbacks.
- **Files:** `frontend/src/api/admin.ts`, `frontend/src/api/settings.ts`.
- **Acceptance:** Extract a single `request` helper
  (`frontend/src/api/_request.ts`) both import.
- **Verification:** `npm run lint && npm run test`.

### NEW-11-12 — Plan 11 §Modified files lists `db/models/user.py` but model lives in `db/models/config.py`

- **Severity:** P3 (doc-only).
- **Bug:** Plan 11 §Modified files (line 143) says
  "modify `db/models/user.py` — add user_prefs model" but
  `UserPrefs` was added to `db/models/config.py:126` alongside the
  existing LLM/provider config tables.
- **Acceptance:** Update the plan's file list to reference the real
  path.
- **Verification:** Diff check.

---

## Execution order

1. **P0-07** — three-line diff + tests (unblocks shipping).
2. **NEW-11-08** — move user `/admin/llm/preferences` out of the
   `/admin/` prefix (small, client + test churn).
3. **NEW-11-02** — server random-temp-password + frontend modal.
4. **P1-11** — `update_model` persists `model_ref` + `tier`.
5. **NEW-11-06** — dirty-form shell-level guard + `UnsavedChangesModal`.
6. **NEW-11-03 / NEW-11-04** — real admin CRUD panels (Data
   Providers, Models).
7. **NEW-11-05** — per-department tier reference panel.
8. **NEW-11-09 / NEW-11-10 / NEW-11-11** — test + DX cleanup.
9. **P2-14 / NEW-11-07 / NEW-11-12** — plan text corrections.
10. Close **P0-09 (user_prefs slice)** once
    `test_migrations.py::EXPECTED_TABLES` is verified.

## Master verification

```
uv run ruff check packages/server/src/openlia_server/routes packages/server/src/openlia_server/services
uv run pytest \
  packages/server/tests/test_routes/test_settings_general_routes.py \
  packages/server/tests/test_routes/test_settings_email_routes.py \
  packages/server/tests/test_routes/test_settings_models_routes.py \
  packages/server/tests/test_routes/test_must_change_password_gate.py \
  packages/server/tests/test_routes/test_admin_routes.py \
  packages/server/tests/test_routes/test_llm_admin_routes.py \
  packages/server/tests/test_services/test_user_prefs.py \
  packages/server/tests/test_services/test_admin_invites.py \
  packages/server/tests/test_services/test_admin_users.py \
  packages/server/tests/test_services/test_admin_password_reset.py \
  packages/server/tests/test_migrations.py
cd frontend && npm run lint && npm run test
```
