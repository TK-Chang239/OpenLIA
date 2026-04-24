# Phase 7 — CLI Surface fix plan (→ 100%)

**Current:** ~97% shipped. **Root cause:** IMPLEMENTER (residual banner + stdin fallback) + SPEC_DRIFT (`list-invites` header, `create-invite` output shape) + TEST_GAP (banner assertion missing, version-flag coverage thin).

**Scope reality check.** Spec (`planning/specs/systems/cli-surface-design.md`) enumerates exactly these top-level commands: `serve`, `admin *`, `wizard reset`, `secrets rotate-key`, `maintenance`. Every one is implemented in `packages/server/src/openlia_server/cli.py` (811 lines) with Typer sub-apps for `admin`, `admin lockout`, `wizard`, `secrets`. `init`, `migrate`, `user-management`, `secret-set`, `healthcheck` — named in the audit request — are explicit non-goals (spec §"Non-Goals v1" + migrations are auto-run inside `serve` per startup sequence step 4). Do not invent them.

**Verified shipped (do not re-open):**
- Global flags `--no-color`, `--db-url`, `--version` wired through `_root` callback (cli.py:51-71) with eager version callback.
- Entry point `openlia = "openlia_server.cli:main"` registered (packages/server/pyproject.toml:63).
- `serve --host --port --reload --no-scheduler` flags all land; `--no-scheduler` sets `OPENLIA_SCHEDULER_ENABLED=false` before uvicorn (cli.py:103-112); asserted by `test_cli_serve.py::TestServeFlags`.
- `admin` sub-app gated on company mode via `_admin_callback` → `require_company()` (cli.py:126-129, _cli_support.py:66-71).
- Every admin command: `list-users`, `unlock`, `reset-password` (with interactive `hide_input=True, confirmation_prompt=True`), `disable-user`, `enable-user`, `revoke-sessions`, `create-invite`, `list-invites`, `revoke-invite`, `lockout enable|disable|status` — all present, all call `log_cli_event()` which enforces `metadata.source = "cli"` and `actor_user_id = NULL` (_cli_support.py:84-100).
- `wizard reset` writes the named-step shape (status/current_step/completed_steps) per REM-P1-005 and syncs `wizard.completed` config row (cli.py:582-633).
- `secrets rotate-key` takes `BEGIN EXCLUSIVE`, translates "database is locked" → `"Error: stop the server before rotating keys."` exit 1 (cli.py:710-716), re-encrypts LLMProvider/DataProvider/WebSearchProvider rows atomically, writes new key file with `KEY_FILE_MODE` or prints env-var instruction.
- `maintenance --dry-run` rolls back instead of commits; output prefix `[dry-run]`.
- Exit codes: 0 success, 1 general/mode guard (`require_company`, rotate-key failures, wizard reset decline), 2 entity-not-found (`exit_not_found`).
- Test files exist and pass (per 2026-04-21 review: "CLI tests passed, 70 passed"): `test_cli_serve.py`, `test_cli_admin_users.py`, `test_cli_admin_invites.py`, `test_cli_admin_lockout.py`, `test_cli_wizard.py`, `test_cli_secrets.py`, `test_cli_crypto_rotation.py`, `test_cli_maintenance.py`, `test_cli_support.py`.

---

## Tasks (in execution order)

### NEW-7-01 — Emit `serve` startup banner before uvicorn takes over
**Type:** IMPLEMENTER (missing P2 functional).
**Root cause:** Plan Task 2 deferred the banner; spec §"Startup output" mandates the four-line block.
**Files:**
- `packages/server/src/openlia_server/_cli_support.py` — add `render_startup_banner(*, version: str, mode: str, db_url: str, host: str, port: int, scheduler_enabled: bool, wizard_pending: bool) -> str`. Shorten `sqlite:///` paths to `~`-relative form. Omit query params. Four lines: `OpenLIA v<version>`, `Mode:      <mode>`, `Database:  <shortened>`, `Listening: http://<host>:<port>`, `Scheduler: enabled|disabled`. Append the wizard-pending line only if `wizard_pending` true (spec lines 106-110).
- `packages/server/src/openlia_server/cli.py:101-112` — call the helper after `bootstrap()` and before `uvicorn.run(...)`; resolve mode from `OPENLIA_MODE`, db_url from `bootstrap.resolve_db_url()`, scheduler flag from the post-mutation `OPENLIA_SCHEDULER_ENABLED` env, wizard_pending from a quick `ConfigStore.key == "wizard.completed"` synchronous read (open/close its own session; do not reuse the uvicorn-owned one).
**Acceptance:**
- `render_startup_banner` is pure (no DB, no env reads) and unit-testable in `test_cli_support.py::TestRenderStartupBanner` covering sqlite-path shortening, `0.0.0.0` display, wizard-pending toggle.
- `test_cli_serve.py::test_serve_prints_banner` captures stdout via `CliRunner` + monkeypatched `uvicorn.run`/`bootstrap`, asserts the four canonical lines appear in order and before `uvicorn.run` is called.
- `test_serve_prints_wizard_pending_line` covers the conditional extra line by seeding `wizard.completed=false`.

### NEW-7-02 — Reconcile `list-invites` header with shipped output
**Type:** SPEC_DRIFT.
**Root cause:** Spec §list-invites (line 291) says "Token (first 12 chars)" but REM-P1-003 switched to invite UUIDs; shipped emits `ID` with 8-char prefix (cli.py:420). Raw tokens are hashed-only at rest — printing them is impossible.
**Files:**
- `planning/specs/systems/cli-surface-design.md:291-298` — replace header `Token` → `ID`, prefix length `12` → `8`, update the sample table accordingly, add one sentence: "Raw invite tokens are never stored (only `token_hash`), so `list-invites` shows the invite UUID instead. Use the 8-char prefix with `revoke-invite`."
- `planning/specs/systems/cli-surface-design.md:302-308` — `revoke-invite <token>` → `revoke-invite <invite-id>`; argument accepts full UUID or 8-char prefix; multi-match guard already implemented (cli.py:446-451) — spec should note it.
**Acceptance:** Spec diff compiled; no code change.

### NEW-7-03 — Spec `create-invite` output: add shipped `ID:` line
**Type:** SPEC_DRIFT.
**Root cause:** Shipped output includes `ID: <uuid>` (cli.py:369); spec §create-invite (lines 277-283) omits it. Shipped version is the correct one because the admin needs the invite ID to later run `revoke-invite`.
**Files:** `planning/specs/systems/cli-surface-design.md:277-283` — insert `ID:       <uuid>` between `URL:` and `Label:` rows in the sample output.
**Acceptance:** Spec sample matches shipped output byte-for-byte (modulo real UUID).

### NEW-7-04 — Decide and land `secrets rotate-key` stdin fallback
**Type:** IMPLEMENTER (P2 functional) + PLAN_GAP (Task 13 silent on stdin).
**Root cause:** Spec §`secrets rotate-key` (line 340) says "If omitted, reads from stdin. If neither provided, generates a random key." Shipped code treats omitted `--new-key` as "generate random" with no stdin path (cli.py:695-699), so admins who want to pass a key in CI without exposing it in shell history or `ps aux` have no safe route.
**Decision (land it):** add an explicit `--from-stdin` flag rather than sniff `sys.stdin.isatty()` (avoids surprising behavior in tests/CI where stdin is always a pipe).
**Files:**
- `packages/server/src/openlia_server/cli.py:678-706` — add `from_stdin: bool = typer.Option(False, "--from-stdin", help="Read base64 key from stdin (one line, trailing newline stripped).")`. Mutually exclusive with `--new-key`; if both supplied → `echo_error("use either --new-key or --from-stdin, not both")` exit 1. If `--from-stdin`: `raw = sys.stdin.readline().strip()`; if empty → `echo_error("no key read from stdin")` exit 1; then reuse `_decode_new_key(raw)`.
- `planning/specs/systems/cli-surface-design.md:338-341` — replace the ambiguous "reads from stdin" sentence with the explicit `--from-stdin` flag description.
**Acceptance:**
- `test_cli_secrets.py::test_rotate_key_from_stdin` pipes a valid base64 key and asserts rotation succeeds (reuse fake providers from `test_cli_crypto_rotation.py`).
- `test_rotate_key_from_stdin_empty` asserts empty stdin → exit 1 with clear message.
- `test_rotate_key_rejects_both_flags` asserts `--new-key X --from-stdin` → exit 1.

### NEW-7-05 — Align shipped version with banner example (cosmetic)
**Type:** SPEC_DRIFT (example only, not a contract).
**Root cause:** Spec example banner (line 99) shows `OpenLIA v1.0.0`; shipped `OPENLIA_VERSION = "0.1.0"` (pre-1.0). Either amend the spec example to `v0.1.0` or treat `v1.0.0` as a placeholder. Not a bug, but the audit flagged version-in-banner as a spec match point.
**Files:** `planning/specs/systems/cli-surface-design.md:98-103` — replace the literal `v1.0.0` in the sample banner with `vX.Y.Z` and add "(actual version read from `openlia_server._cli_support.OPENLIA_VERSION`)" below the block.
**Acceptance:** No shipped-version lock-in in the spec.

### NEW-7-06 — Tighten `--version` coverage to assert behavior across sub-apps
**Type:** TEST_GAP (small).
**Root cause:** `test_version_prints_and_exits_zero` only covers root `--version` (test_cli_serve.py:10-13). Eager callback is declared on the root; if anyone later moves flags onto sub-apps the regression would slip through.
**Files:** `packages/server/tests/test_cli/test_cli_serve.py` — add `test_version_flag_runs_before_subcommand` asserting `cli_runner.invoke(app, ["admin", "--version"])` exits 0 with the version string (should because of Typer eager callback) AND does not hit `require_company()`.
**Acceptance:** Test green; one new assertion.

### NEW-7-07 — Assert `--no-color` round-trips into context
**Type:** TEST_GAP.
**Root cause:** `_root` stashes `no_color` into `ctx.obj` (cli.py:71) but nothing consumes it today — every command uses plain `typer.echo`. Risk: Rich integration lands later and forgets the flag. Add a behavioral test now that fails if the flag is dropped.
**Files:** `packages/server/tests/test_cli/test_cli_serve.py` — invoke a no-op subcommand with `--no-color`, capture `ctx.obj["no_color"]` via a test-only spy command OR, preferably, just assert `cli_runner.invoke(app, ["--no-color", "--help"]).exit_code == 0` plus grep that no ANSI escape sequences appear in stdout.
**Acceptance:** Regression guard in place.

### NEW-7-08 — `admin unlock` audit emission (spec decision)
**Type:** SPEC_DRIFT (v1 decision already made — recodify).
**Root cause:** Spec §admin (line 142) says "Default v1 behavior: omit." Shipped code also omits (cli.py:173-189, no `log_cli_event`). Fine, but the decision is buried; surface it.
**Files:** `planning/specs/systems/cli-surface-design.md:142` — keep "Default v1 behavior: omit," add a one-line note "Current implementation (cli.py `admin_unlock`) matches this — no `auth_events` row emitted."
**Acceptance:** Spec and shipped reconciled in writing.

### NEW-7-09 — Cover `admin unlock` with a test
**Type:** TEST_GAP.
**Root cause:** `test_cli_admin_users.py` covers disable/enable/reset-password/revoke-sessions but `unlock` is not exercised (grep-confirmed absent; not listed in 2026-04-21 audit summary of 70 passing tests as a named case).
**Files:** `packages/server/tests/test_cli/test_cli_admin_users.py` — add `test_unlock_clears_locked_until_and_attempts` (seed user with `locked_until` + `failed_login_attempts=5`, invoke, assert both cleared, stdout `"Unlocked: <email>"`, no `auth_events` row created) and `test_unlock_user_not_found_exits_2`.
**Acceptance:** Two new green tests.

---

## Verification

- `uv run pytest packages/server/tests/test_cli/` green with ≥73 tests (70 baseline + banner + stdin + version cross-command + no-color + two unlock tests).
- `uv run openlia serve --no-scheduler --port 9999` (stub uvicorn locally) prints the banner on stdout before uvicorn boots.
- `echo $NEW_KEY_B64 | uv run openlia secrets rotate-key --from-stdin` rotates silently in a scripted env.
- Spec diff review: §list-invites header, §create-invite output, §rotate-key stdin, §unlock audit note, §banner version placeholder all aligned with shipped code.

## Out of scope (spec-declared non-goals, reaffirm here)

`openlia init`, `openlia migrate`, `openlia healthcheck`, `openlia user-management`, `openlia secret-set`, interactive shell, tab completion, `--json` output, remote CLI, `openlia backup|restore|upgrade`. Do not add. Migrations run inside `serve` startup sequence step 4 (spec line 118) per the "auto-upgrade" open-question resolution.
