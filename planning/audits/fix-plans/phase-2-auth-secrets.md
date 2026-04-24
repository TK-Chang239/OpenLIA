# Phase 2 — Auth & Secrets fix plan (→ 100%)


**Current:** ~92% shipped. **Root cause:** IMPLEMENTER.

**Gap summary:** All 18 tasks landed, but the dependency factory shape is incorrect (`build_require_auth` returns a `Depends(...)` sentinel that FastAPI treats as a default value and cannot re-enter — causing nested `require_admin`/`require_active_user` to silently resolve to a `Depends` object, not a `User`). Also: empty `services/auth/__init__.py` and a `route-authorization-matrix.md` path mismatch.

**Tasks (in execution order):**

1. **P0-06 — Fix `build_require_auth` return shape so nested `Depends` resolve correctly.**
   - Files: `packages/server/src/openlia_server/middleware/auth.py:22-57, 61-75, 78-100, 103-127` (modify all four factories).
   - Plan ref: Task 13 "`require_auth` dependency".
   - Spec ref: `route-authorization-matrix.md` "Auth gate primitives".
   - Acceptance: return the bare callable (not `Depends(...)`) and switch callers to `Depends(require_auth_callable)`; `uv run pytest packages/server/tests/test_middleware/ packages/server/tests/test_routes/ -v` green; a regression test asserts nested `require_admin` resolves a concrete `User`, not `Depends`.

2. **P0-07 — Apply `build_require_active_user` in `settings_general.py`, `settings_email.py`, `settings_models.py`.**
   - Files: `packages/server/src/openlia_server/routes/settings_general.py:11,49`, `routes/settings_email.py:11,22`, `routes/settings_models.py:12,26` (replace `build_require_auth` with `build_require_active_user`).
   - Plan ref: Task 13 notes on `require_active_user`.
   - Spec ref: `route-authorization-matrix.md` must-change-password gate row.
   - Acceptance: test that a user with `must_change_password=true` receives 403 with `{"code":"must_change_password"}` on all three routers.

3. **P2-02 — Normalize `route-authorization-matrix.md` path.**
   - Files: move `planning/implementation-plans/route-authorization-matrix.md` → `planning/route-authorization-matrix.md`, OR update REM-P0-006 cross-references.
   - Acceptance: every reference resolves.

4. **P2-03 — Populate `services/auth/__init__.py` with the plan's re-exports.**
   - Files: `packages/server/src/openlia_server/services/auth/__init__.py` (currently empty).
   - Plan ref: Task 4–11 expect `from openlia_server.services.auth import <name>`.
   - Acceptance: `from openlia_server.services.auth import authenticate, register_invited, request_password_reset` succeeds.

5. **NEW-2-01 — Verify per-IP + per-account lockout thresholds match spec table.** Why new: plan Tasks 10 + 12 implement lockout/rate-limit, but `database-design.md` §3 "Rate limiting" fixes concrete numbers (5/min per IP on `/auth/login`, 10/hr per account on `/auth/forgot`) that aren't asserted anywhere.
   - Files: `packages/server/src/openlia_server/middleware/rate_limit.py` (audit), `services/auth/login.py` (audit).
   - Spec ref: `database-design.md` §3.
   - Acceptance: new `test_auth_rate_limits.py` asserts exact thresholds.

**Verification:** `uv run pytest packages/server/tests/services/ packages/server/tests/test_middleware/ packages/server/tests/test_routes/test_auth*.py -v` green.
