# Auth And Authorization Audit

Date: 2026-04-21

Scope: route access control, deployment modes, session cookies, user scoping,
admin scoping, and must-change-password handling.

Validation commands run: none. Static audit only.

## Executive Summary

The current auth foundation is usable for existing backend routes, but the
frontend integration is broken and future plans still import old auth helpers.
Personal/company mode semantics are partly implemented, but setup wizard,
must-change-password gating, and future department routes need a route-by-route
authorization matrix before implementation continues.

## Current Access Model

Personal mode:

- Auth routes are not mounted.
- `build_require_auth(..., mode="personal")` resolves synthetic local user.
- Admin dependencies allow local user because seeded local user is admin.

Company mode:

- `/auth/*` and `/admin/*` are mounted.
- `openlia_session` cookie is required for authenticated routes.
- Admin routes require `is_admin`.

## Findings

### 1. High - Frontend Auth State Cannot Be Trusted Yet

Backend auth routes return flat DTOs. Frontend auth client expects nested
`{user}`. This can produce `status="authenticated"` with missing user fields.

Impact: every frontend auth gate, admin gate, and settings/account feature is
unsafe until the DTO boundary is fixed.

Required fix: patch `frontend/src/api/auth.ts`, `AuthContext`, and tests before
building Plan 9+ UI.

### 2. High - Must-Change-Password Is Not Enforced Globally

Backend login reports `must_change_password`, and password reset sets it.
There is no middleware/dependency that blocks non-password routes for users
with `must_change_password=True`.

Impact: Plan 11 expects this gate, but it does not yet exist. Users with forced
password reset can still access existing authenticated backend routes if they
have a valid session.

Required fix:

- Define exact routes exempt from the gate:
  - `/auth/change-password`
  - `/auth/logout`
  - `/auth/logout-all`
  - `/setup/*` if setup remains pre-auth
- Add dependency or middleware for company-mode authenticated routes.
- Add tests for allowed and blocked routes.

### 3. High - Future Plan Auth Imports Are Wrong

Plans 10-15 still import `current_user`, `require_user`, `get_db_session`, or
`get_db` in executable snippets. These helpers do not ship.

Impact: future department routes will either fail to import or drift from the
existing factory pattern.

Required fix: rewrite future routes as factory functions accepting
`db_session_factory` and `mode`, then bind `build_require_auth`.

### 4. Medium - Setup Wizard Auth Boundary Is Not Implemented

Plan 10 says `/setup/*` is pre-auth with wizard-session cookie gating. No
backend setup routes or wizard gate exist yet.

Risk: if implemented after AuthProvider remains broken, setup may be blocked by
auth bootstrap or expose setup write routes after completion.

Required fix:

- Implement `/setup/status` first.
- Render setup outside `AuthProvider`.
- Add `410 Gone` for completed wizard except status.
- Reject non-loopback personal-mode setup writes as planned.

### 5. Medium - Cookie Security Default Does Not Match Spec

Spec says `OPENLIA_COOKIE_SECURE` defaults true in company mode and false in
personal mode. Current code defaults false unconditionally unless env var is
set.

Impact: company deployments can set insecure cookies unless operators know to
set `OPENLIA_COOKIE_SECURE=true`.

Required fix:

- Default secure cookie to true when `OPENLIA_MODE=company`.
- Keep override env var.
- Update tests for both modes.

### 6. Medium - `.env.example` Uses Old Mode Variable

`.env.example` documents `OPENLIA_DEPLOYMENT_MODE=personal`, but source reads
`OPENLIA_MODE`.

Impact: operators following `.env.example` will not enable company mode.

Required fix: replace with `OPENLIA_MODE=personal`.

## Route Authorization Matrix Needed

Create a table for every route:

- public
- setup-session only
- authenticated user
- admin
- personal-mode behavior
- company-mode behavior
- owner scoping rule
- must-change-password behavior

This should be a merge gate for Plans 10-15.
