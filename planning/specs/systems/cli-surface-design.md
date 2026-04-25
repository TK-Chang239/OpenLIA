# CLI Surface Design

Unified reference for all `openlia` CLI commands. The CLI is the primary interface for starting the server, performing admin operations, and running maintenance tasks.

## Scope

### In scope

- Complete command tree with all flags and arguments
- Output format conventions
- Error handling and exit codes
- Mode guards (which commands require company mode)
- DB access patterns for non-server commands
- Audit trail for CLI-driven changes

### Out of scope

- Server internals started by `serve` (owned by `app.py`, scheduler, etc.)
- Business logic behind admin commands (owned by `AccountManagementSpec.md`)
- Encryption scheme details (owned by `database-design.md`)
- Background task scheduling internals (owned by `background-task-scheduling-design.md`)

---

## Stack

| Concern | Choice |
|---|---|
| CLI framework | Typer (built on Click, type-hint-driven, auto-generated help) |
| Entry point | `openlia = "openlia_server.cli:main"` in server `pyproject.toml` `[project.scripts]` |
| File location | `packages/server/src/openlia_server/cli.py` |

### Why Typer

- Type-hint-driven: matches the project's "modern Python, strict type hints" philosophy.
- Auto-generated help text and argument validation.
- Built on Click (mature, widely used).
- Rich integration for table output and colored terminal output.
- Subcommand groups map naturally to the `admin` and `wizard` command groups.

---

## Command Tree

```
openlia                            # shows help with available subcommands
openlia serve                      # start the FastAPI server
openlia admin list-users           # list all user accounts
openlia admin unlock               # unlock a locked account
openlia admin lockout enable       # enable the account-lockout feature
openlia admin lockout disable      # disable the account-lockout feature
openlia admin lockout status       # show whether lockout is enabled
openlia admin reset-password       # reset a user's password
openlia admin disable-user         # disable a user account
openlia admin enable-user          # re-enable a user account
openlia admin revoke-sessions      # revoke all sessions for a user
openlia admin create-invite        # create a signup invite
openlia admin list-invites         # list all invites
openlia admin revoke-invite        # revoke an invite
openlia wizard reset               # reset wizard to re-run setup
openlia secrets rotate-key         # re-encrypt all API keys with a new key
openlia maintenance                # run the pruning sweep manually
```

`admin` and `wizard` are Typer sub-apps (command groups). `serve`, `secrets`, and `maintenance` are top-level commands. Running `openlia` with no subcommand displays help text listing all available commands.

---

## Global Flags

Available on all commands:

| Flag | Type | Default | Notes |
|---|---|---|---|
| `--no-color` | flag | off | Disable colored output (for piping/scripting) |
| `--db-url` | string | from `OPENLIA_DB_URL` | Override the database URL (useful for pointing at a different DB file) |
| `--version` | flag | -- | Print version and exit |

---

## Commands

### `openlia serve`

Starts the FastAPI server with the background task scheduler, Alembic migration check, and secret key bootstrap.

**When to use:** Every time you want to run OpenLIA. Personal users run this on their machine, company admins run this on a team server. This is the main command.

| Flag | Type | Default | Notes |
|---|---|---|---|
| `--host` | string | Auto (`127.0.0.1` personal, `0.0.0.0` company) | Overrides `OPENLIA_BIND_HOST` env var |
| `--port` | integer | `8000` | Overrides `OPENLIA_BIND_PORT` env var |
| `--reload` | flag | off | Enable auto-reload on code changes (development only) |
| `--no-scheduler` | flag | off | Start the server without the background task scheduler. Equivalent to `OPENLIA_SCHEDULER_ENABLED=false`. Useful for development and debugging. |

**Startup output:**

```
OpenLIA vX.Y.Z
Mode:      personal
Database:  ~/.openlia/openlia.db
Listening: http://127.0.0.1:8000
Scheduler: enabled (12 active jobs)
```

(actual version read from `openlia_server._cli_support.OPENLIA_VERSION`)

If the wizard has not been completed, the startup message includes:

```
Setup wizard: pending -- open the URL above to configure.
```

**Startup sequence:**

1. Load `.env` file (if present) via python-dotenv.
2. Resolve config from env vars, DB config_store, and hardcoded defaults (in precedence order).
3. Bootstrap the secret key (see `database-design.md` Section 5).
4. Run Alembic migration check (auto-upgrade to head if behind).
5. Initialize the FastAPI app, mount routes, middleware.
6. Initialize the scheduler (if enabled): rebuild jobs from DB, catch up missed jobs, start.
7. Start uvicorn on the configured host and port.

**Exit codes:** `0` clean shutdown, `1` startup failure (missing dependencies, DB locked, bad secret key permissions, migration failure).

**Mode:** Both personal and company.

---

### `openlia admin` (command group)

Admin operations for managing users, invites, and sessions in company-mode deployments. Faster and more scriptable than the web UI admin panel for common tasks.

**When to use:** When the admin needs to manage users without logging into the web UI -- during initial setup (creating invites before the UI is accessible), when a user is locked out, or for scripted user management.

**Mode guard:** Company mode only. All commands in this group reject with `"Error: admin commands require company mode."` and exit `1` if the current mode is personal.

**DB access:** All admin commands connect directly to the database via a synchronous SQLAlchemy session. They do not require the server to be running. This means an admin can manage users even if the server is down.

**Audit trail:** All admin commands emit an `auth_events` row using the *same* `event_type` value as the equivalent web-admin action (`unlock` -> none today, `reset-password` -> `password_reset_by_admin`, `disable-user` -> `user_disabled`, `enable-user` -> `user_enabled`, `revoke-sessions` -> `session_revoked`, `create-invite` -> `invite_created`, `revoke-invite` -> `invite_revoked`). CLI invocations are distinguished from UI invocations by two columns: `actor_user_id = NULL` (CLI has no logged-in user) and `metadata.source = "cli"`. This means audit queries like "who disabled this account?" use a single `WHERE event_type = 'user_disabled'` filter regardless of the interface that triggered it.

The `lockout` subcommand follows the same convention -- it emits `auth.lockout_setting_changed` (the canonical action name), not a `cli.*` variant.

`unlock` does not have a dedicated event type in the v1 enum; emit it as `session_revoked` with `metadata = {"action": "unlock", "source": "cli"}` if any audit row is desired, or omit (since unlocking is not a security-relevant state change in the way disabling is). Default v1 behavior: omit. Current implementation (cli.py `admin_unlock`) matches this -- no `auth_events` row emitted.

---

#### `openlia admin list-users`

Lists all user accounts in a table.

| Flag | Type | Default | Notes |
|---|---|---|---|
| `--disabled` | flag | off | Only show disabled accounts |

**Output:** Table with columns: `ID`, `Email`, `Display Name`, `Admin`, `Disabled`, `Last Login`.

```
ID         Email                Display Name   Admin   Disabled   Last Login
a1b2c3...  alice@company.com    Alice Chen     yes     no         2026-04-15 09:30
d4e5f6...  bob@company.com      Bob Kim        no      no         2026-04-14 14:22
g7h8i9...  carol@company.com    Carol Wu       no      yes        2026-03-01 08:00
```

---

#### `openlia admin unlock <email>`

Clears `locked_until` and resets `failed_login_attempts` for the given user.

**When to use:** When a user is locked out after 5 failed login attempts and the admin wants to unlock them immediately rather than waiting 15 minutes.

**Output:** `"Unlocked: alice@company.com"`

**Exit code:** `2` if user not found.

---

#### `openlia admin lockout` (subcommand group)

Toggles the account-lockout feature on or off, or prints its current state. The feature is stored in `config_store` under the key `auth.lockout.enabled` (boolean, default `true`). When disabled, the login flow stops both incrementing `users.failed_login_attempts` and consulting `users.locked_until`. The columns remain on the row, so re-enabling later resumes counting from zero with no data loss.

**When to use:** When the admin needs to silence the lockout temporarily (e.g., during a load test that hammers the login endpoint, or after a malformed SSO proxy starts producing spurious password failures), or to re-enable it once the underlying issue is fixed. Not a routine operation -- the default is on for a reason.

**Subcommands:**

| Subcommand | Effect |
|---|---|
| `enable` | Sets `auth.lockout.enabled = true`. No-op if already enabled. |
| `disable` | Sets `auth.lockout.enabled = false`. No-op if already disabled. Does **not** clear existing `locked_until` values; use `openlia admin unlock <email>` per-user if the admin wants to release currently-locked accounts immediately. |
| `status` | Prints current value, the timestamp it was last changed, and the actor (always `cli` in v1; reserved for future UI toggle). |

**Output:**

```
$ openlia admin lockout disable
Lockout disabled. Currently-locked accounts remain locked until you run `openlia admin unlock <email>`.

$ openlia admin lockout enable
Lockout enabled.

$ openlia admin lockout status
Lockout: enabled
Last changed: 2026-04-16 14:32 (actor: cli)
```

**Audit:** `enable` and `disable` each emit one `auth_events` row with `event_type = "auth.lockout_setting_changed"` and `metadata = {"old": <bool>, "new": <bool>, "source": "cli"}`. `status` emits no event.

**Exit code:** `1` if the config_store write fails (e.g., DB locked).

---

#### `openlia admin reset-password <email>`

Prompts for a new password (hidden input with confirmation), hashes with Argon2id, updates the user, sets `must_change_password=true`, revokes all active sessions.

**When to use:** When a user has forgotten their password and the admin wants to set a temporary one directly, or during onboarding to create initial credentials for a new user.

| Flag | Type | Notes |
|---|---|---|
| `--password` | string | Skip interactive prompt (for scripting). Discouraged -- visible in shell history. |

**Output:** `"Password reset for alice@company.com. User will be required to change it on next login."`

**Exit code:** `2` if user not found.

---

#### `openlia admin disable-user <email>`

Sets `is_disabled=true` and revokes all active sessions. The user can no longer log in. Their scheduled background jobs will not fire (the scheduler skips disabled users).

**When to use:** When an employee leaves the company or when an account needs to be suspended.

**Output:** `"Disabled: alice@company.com (3 sessions revoked)"`

**Exit code:** `2` if user not found.

---

#### `openlia admin enable-user <email>`

Sets `is_disabled=false`. The user can log in again. Their scheduled background jobs resume on the next scheduler sync.

**When to use:** When a previously disabled account needs to be reactivated.

**Output:** `"Enabled: alice@company.com"`

**Exit code:** `2` if user not found.

---

#### `openlia admin revoke-sessions <email>`

Revokes all active sessions for the user, forcing them to log in again on all devices.

**When to use:** When the admin suspects a session has been compromised, or as a precautionary measure after a security incident.

**Output:** `"Revoked 4 sessions for alice@company.com."`

**Exit code:** `2` if user not found.

---

#### `openlia admin create-invite`

Creates a signup invite token and prints the full invite URL. The admin delivers this URL to the intended user out-of-band (Slack, email, in person).

**When to use:** When the admin wants to invite new users to register. This is the only way to register new accounts in v1 (invite-only policy).

| Flag | Type | Default | Notes |
|---|---|---|---|
| `--label` | string | none | Human-readable label (e.g. "Engineering team") |
| `--max-uses` | integer | unlimited | Maximum number of registrations with this invite |
| `--expires` | string | none | Expiry duration (e.g. `7d`, `24h`, `30d`). No expiry if omitted. |

**Output:**

```
Invite created.
URL:      http://localhost:8000/register?invite=abc123...
ID:       7c91e2b4-3fae-4c1d-9b6a-9d7e0f2b1a55
Label:    Engineering team
Max uses: 10
Expires:  2026-04-23
```

---

#### `openlia admin list-invites`

Lists all invites with usage stats.

**Output:** Table with columns: `ID` (first 8 chars of the invite UUID), `Label`, `Uses` (count/max or count/unlimited), `Created`, `Expires`, `Status` (active/expired/revoked/exhausted).

```
ID         Label              Uses          Created      Expires      Status
7c91e2b4   Engineering team   3/10          2026-04-15   2026-04-23   active
a3f80d12   Summer interns     5/unlimited   2026-04-10   --           active
b6219ce7   --                 1/1           2026-04-08   2026-04-09   exhausted
```

Raw invite tokens are never stored (only `token_hash`), so `list-invites` shows the invite UUID instead. Use the 8-char prefix with `revoke-invite`.

---

#### `openlia admin revoke-invite <invite-id>`

Revokes an invite so it can no longer be used for registration. Takes the full invite UUID or the 8-character prefix shown in `list-invites`. If the prefix matches more than one invite, the command fails with an error and lists the matches.

**When to use:** When an invite link was shared with the wrong person, or when the admin wants to close registration after enough users have signed up.

**Output:** `"Invite revoked: abc123def456..."`

---

### `openlia wizard reset`

Resets the setup wizard state to `not_started` in the `wizard_state` DB table. On next server start (or next browser visit if the server is running), the wizard re-runs from Step 1.

**When to use:** When the admin wants to re-run the setup wizard -- typically to switch from personal to company mode (or vice versa), or to reconfigure the initial setup from scratch. Existing configuration (API keys, providers, user accounts) is preserved; only the wizard completion flag is cleared.

**Confirmation prompt:** `"This will reset the setup wizard. Existing configuration (API keys, providers, user accounts) is preserved -- only the wizard completion flag is cleared. Continue? [y/N]"`

| Flag | Type | Notes |
|---|---|---|
| `--yes` | flag | Skip confirmation prompt |

**Output:** `"Wizard state reset. The setup wizard will run on next visit."`

**DB access:** Direct synchronous connection. Does not require the server to be running.

**Mode:** Both personal and company.

---

### `openlia secrets rotate-key`

Re-encrypts all API keys in the database with a new AES-256-GCM key. Walks `llm_providers.api_key_encrypted`, `data_providers.api_key_encrypted`, and `web_search_providers.api_key_encrypted`, decrypts with the old key, re-encrypts with the new key in a single all-or-nothing transaction.

**When to use:** When the admin suspects the encryption key (`~/.openlia/secret.key` or `OPENLIA_SECRET_KEY`) has been compromised. No routine rotation requirement.

| Flag | Type | Notes |
|---|---|---|
| `--new-key` | string | Base64-encoded 32-byte key. If omitted (and `--from-stdin` not set), generates a random key. Mutually exclusive with `--from-stdin`. |
| `--from-stdin` | flag | Read the base64 key from stdin (one line, trailing newline stripped). Use in scripted/CI contexts where the key must not appear in argv or shell history. Mutually exclusive with `--new-key`. |

**Output:**

```
Rotated encryption key. 8 values re-encrypted.
New key written to ~/.openlia/secret.key
```

Or, if using `OPENLIA_SECRET_KEY`:

```
Rotated encryption key. 8 values re-encrypted.
Update your OPENLIA_SECRET_KEY env var to: <base64-encoded-key>
```

**Safety:** Must not be run while the server is running. Checks for an advisory lock on the DB file. Exits `1` with `"Error: stop the server before rotating keys."` if detected.

**DB access:** Direct synchronous connection. Does not require the server to be running.

**Mode:** Both personal and company.

---

### `openlia maintenance`

Runs the nightly pruning sweep manually. Same logic as the `system_maintenance` background job defined in `background-task-scheduling-design.md`.

**When to use:** When the admin wants to run cleanup on demand rather than waiting for the automatic daily run, or for debugging (checking what would be pruned with `--dry-run`). Also useful for cron-based scheduling as an alternative to the in-process scheduler.

| Flag | Type | Notes |
|---|---|---|
| `--dry-run` | flag | Print what would be pruned without deleting |

**Output:**

```
sessions:                 deleted 14 expired rows
password_reset_requests:  expired 2 rows, deleted 0 old rows
mr_assessment_cache:      deleted 3 stale rows
rs_snapshots:             deleted 847 old snapshots
user_notifications:       deleted 31 old notifications
job_runs:                 deleted 8 old completed runs
```

Dry run prefixes each line with `[dry-run]`.

**DB access:** Direct synchronous connection. Does not require the server to be running.

**Mode:** Both personal and company.

---

## Output Conventions

- **Tables** use simple column-aligned plain text. Typer's Rich integration handles formatting and alignment.
- **Success messages** go to stdout. **Error messages** go to stderr.
- **No color by default detection:** Rich auto-detects terminal capability. `--no-color` forces plain output for piping and scripting.
- **Confirmations** use `[y/N]` format (default no). `--yes` flag skips confirmation on destructive commands.
- **Sensitive values** (passwords, tokens) are never echoed to the terminal during interactive input. Invite tokens and reset URLs are printed exactly once.

---

## Exit Codes

| Code | Meaning |
|---|---|
| `0` | Success |
| `1` | General error (invalid arguments, DB connection failure, mode guard violation, server already running) |
| `2` | Entity not found (user not found for admin commands, invite not found) |

---

## Mode Guards

| Command | Personal | Company |
|---|---|---|
| `serve` | Yes | Yes |
| `admin *` | No (exits 1) | Yes |
| `wizard reset` | Yes | Yes |
| `secrets rotate-key` | Yes | Yes |
| `maintenance` | Yes | Yes |

---

## DB Access Patterns

| Command | Access method | Server required? |
|---|---|---|
| `serve` | Full async SQLAlchemy + Alembic migrations | N/A (it is the server) |
| `admin *` | Direct sync SQLAlchemy session | No |
| `wizard reset` | Direct sync SQLAlchemy session | No |
| `secrets rotate-key` | Direct sync SQLAlchemy session | No (must not be running) |
| `maintenance` | Direct sync SQLAlchemy session | No |

All non-serve commands open a synchronous connection to the SQLite DB file, perform their operation, and exit. They do not start the server, scheduler, or any background tasks. This means admin operations work even when the server is down -- useful for emergency recovery.

---

## File Layout

The CLI is a single file with Typer sub-apps for command groups:

```
packages/server/src/openlia_server/
├── cli.py                   # Typer app: main, serve, secrets, maintenance
│                            # Sub-apps: admin (group), wizard (group)
```

The entry point is registered in `pyproject.toml`:

```toml
[project.scripts]
openlia = "openlia_server.cli:main"
```

Business logic for admin commands calls into service functions that are shared with the web API routes (e.g. the same `disable_user()` function handles both `POST /admin/users/{id}/disable` and `openlia admin disable-user`). The CLI is a thin wrapper that parses arguments, calls the service, and formats output.

---

## Cross-Reference Edits

This spec consolidates commands already defined in other specs. Minimal edits needed:

| Spec | Edit |
|---|---|
| `planning/GAPS.md` | Add CLI Surface section. Remove the `openlia wizard reset` gap from Setup Wizard section (now specced). |
| `planning/projectStructure.md` | Update `cli.py` comment to reference this spec. |
| `planning/specs/components/AccountManagementSpec.md` | Add the `lockout enable\|disable\|status` row to the Admin CLI Tooling table; gate § 6.2 lockout steps on `auth.lockout.enabled`. (Done) |
| `planning/specs/systems/database-design.md` | Add `auth.lockout.enabled` to `config_store` expected keys; add `account_locked` and `auth.lockout_setting_changed` to the `auth_events.event_type` enum. (Done) |

For all other admin commands (`unlock`, `reset-password`, `disable-user`, etc.), this spec references `AccountManagementSpec.md` as the source of truth -- no edits to that spec are needed for those commands.

---

## Testing Strategy

### Unit

- Mode guard enforcement: admin commands reject in personal mode.
- Argument parsing: flag combinations, missing required args, invalid types.
- Exit code mapping: user not found -> 2, general error -> 1.

### Integration

- `serve` startup and shutdown with `--no-scheduler`.
- `admin create-invite` -> `admin list-invites` -> `admin revoke-invite` lifecycle.
- `admin reset-password` -> verify `must_change_password` flag set and sessions revoked.
- `wizard reset` -> verify `wizard_state.status` flipped to `not_started`.
- `maintenance --dry-run` vs actual run: verify dry run doesn't delete.
- `secrets rotate-key` -> verify all encrypted values are re-encrypted and readable with new key.

### Edge cases

- `admin` commands on an empty database (no users).
- `secrets rotate-key` while server is running (should refuse).
- `maintenance` on a fresh database (nothing to prune).
- `--db-url` pointing to a non-existent file (should error clearly).

---

## Non-Goals (v1)

- Interactive shell / REPL mode.
- Tab completion (Typer supports it but not a priority for v1).
- JSON output mode (`--json` flag for machine-readable output) -- plain text is sufficient for v1.
- Remote CLI (commands always run locally against the DB file).
- `openlia backup` / `openlia restore` commands (backup is `cp openlia.db openlia.db.bak` per database-design.md).
- `openlia upgrade` or self-update command.

---

## Open Questions

1. **Should `serve` auto-run Alembic migrations on startup, or require an explicit `openlia db upgrade` command?** Current plan: auto-upgrade. This is simpler for self-hosted users who just want to update and restart. A separate `openlia db upgrade` could be added later if users want more control.
2. **Should `admin` commands work while the server is running?** Current plan: yes, they connect directly to SQLite. With WAL mode enabled, concurrent reads and writes from the CLI and server are safe. The exception is `secrets rotate-key`, which requires exclusive access.
