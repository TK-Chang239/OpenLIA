# Phase 7 — CLI Surface fix plan (→ 100%)


**Current:** ~97% shipped. **Root cause:** IMPLEMENTER (residual) + SPEC_DRIFT (spec needs to catch up).

**Gap summary:** Every admin/wizard/secrets/maintenance command shipped and is tested; the only functional gap is the missing `serve` startup banner. Remaining items are spec/plan reconciliation (`list-invites` header wording, `rotate-key` stdin decision).

**Tasks (in execution order):**

1. **P2-07 — Emit `serve` startup banner before uvicorn takes over.**
   - Files: `packages/server/src/openlia_server/cli.py:90-112`; `_cli_support.py` (add `render_startup_banner(version, mode, db_url, host, port)` helper with SQLite-path shortening and credential redaction).
   - Plan ref: Task 2 (Global flags + `serve --no-scheduler`).
   - Spec ref: `cli-surface-design.md` §`openlia serve` — mandates the four-line banner.
   - Acceptance: running `serve` prints the banner exactly; `test_cli_serve.py::test_serve_prints_banner` asserts banner contents via `typer.testing.CliRunner` + monkeypatched `uvicorn.run`.

2. **P2-08 — Reconcile `list-invites` column header (`ID` vs `Token`) in spec.**
   - Files: `planning/specs/systems/cli-surface-design.md:243-260` (amend — spec must read `ID` with 8-char prefix; note raw tokens are hashed-only per REM-P1-003).
   - Acceptance: spec wording matches shipped output; no code change.

3. **P2-09 — Decide and land `secrets rotate-key` stdin fallback.**
   - Files: `packages/server/src/openlia_server/cli.py:678-753` — add `--from-stdin` flag that reads a new key from STDIN when piped.
   - Plan ref: Task 13.
   - Spec ref: `cli-surface-design.md` §`openlia secrets rotate-key`.
   - Acceptance: `echo "$NEW_KEY_BASE64" | openlia secrets rotate-key --from-stdin` rotates without prompting; `test_rotate_key_from_stdin` passes.

4. **NEW-7-01 — Add banner assertion to `test_cli_serve.py`.** Why new: kept separate so test PR can land atomically with code.
   - Files: `packages/server/tests/test_cli/test_cli_serve.py` (modify).
   - Acceptance: `uv run pytest -k test_serve_prints_banner` green.

**Verification:** `uv run pytest packages/server/tests/test_cli/` green; `uv run openlia serve` emits the banner before uvicorn's own logs; spec diff on `list-invites` committed.
