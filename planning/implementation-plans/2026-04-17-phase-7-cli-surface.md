# Phase 7 — CLI Surface Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expand the Typer CLI shipped in Phase 0 into the full operator surface defined in `cli-surface-design.md`: admin user management (9 subcommands), the lockout toggle, invite lifecycle, `wizard reset`, `secrets rotate-key`, and `maintenance`. Every non-`serve` command opens a synchronous SQLAlchemy session directly against the SQLite DB and does its work without the server running. Admin commands are gated to company mode and write `auth_events` rows with `actor_user_id=NULL`, `metadata.source="cli"` so audit queries group CLI- and UI-driven actions under the same `event_type`.

**Architecture:** A single `cli.py` holds the root Typer app plus four sub-apps (`admin`, `admin lockout`, `wizard`, `secrets`) and two top-level commands (`maintenance`, `serve`). A small `_cli_support.py` sibling module owns the cross-command plumbing: `build_session()` (resolves the DB URL, configures the engine lazily, returns a fresh sync `Session`), `require_company()` (reads `OPENLIA_MODE`, exits 1 in personal mode), `log_cli_event()` (wraps Plan 2's `log_auth_event` with `actor_user_id=None` and `metadata.source="cli"`), `format_table()` (plain column-aligned ASCII table — no Rich dependency yet), and `parse_duration()` (7d/24h/30m → `timedelta`). Admin subcommands call directly into Plan 2's `services/auth/*` modules (`sessions.revoke_all_sessions`, `passwords.hash_password`, `tokens.generate_opaque_token`). Key rotation piggy-backs on Plan 2's `db/crypto.py` — this plan adds two new *keyed* helpers (`encrypt_with_key`, `decrypt_with_key`) that bypass the module-level cache so the old and new keys can coexist inside one transaction. `maintenance` re-exports Plan 6's `run_maintenance_once()` inside a session that either commits (real run) or rolls back (dry run).

**Tech Stack:** Typer ≥0.12 (already pinned in Phase 0), Click context objects for global-flag propagation, `cryptography.hazmat.primitives.ciphers.aead.AESGCM` (already a Plan 2 dep), `typer.testing.CliRunner` for integration tests, pytest + SQLite temp files.

**Source spec:** `planning/specs/systems/cli-surface-design.md`

**Depends on:**
- Plan 1A — `db/session.py` (`configure_engine`, `SessionLocal`, `dispose_engine`), `db/bootstrap.py` (`resolve_db_url`, `openlia_home`, `bootstrap`), all auth + provider models (`User`, `Session`, `SignupInvite`, `PasswordResetRequest`, `AuthEvent`, `ConfigStore`, `WizardState`, `LlmProvider`, `DataProvider`, `WebSearchProvider`).
- Plan 1B — `JobRun` / `UserNotification` / `MrAssessmentCache` / `RsSnapshot` models (consumed indirectly via Plan 6).
- Plan 2 — `db/crypto.py` (`load_secret_key`, `encrypt_for_row`, `decrypt_for_row`, `SecretKeyError`, `KEY_FILE_NAME`, `KEY_LENGTH_BYTES`, `KEY_FILE_MODE`, `_reset_cached_key`), `services/auth/passwords.py` (`hash_password`, `validate_password_policy`), `services/auth/tokens.py` (`generate_opaque_token`), `services/auth/sessions.py` (`revoke_all_sessions`), `services/auth/password_reset.py` (`admin_direct_reset`), `services/auth/events.py` (`log_auth_event`), `services/auth/errors.py` (`AuthError`, `TokenInvalidError`), `LOCKOUT_CONFIG_KEY = "auth.lockout.enabled"` constant.
- Plan 6 — `scheduler/executors/maintenance.py` (`run_maintenance_once`), `scheduler/settings.py` (`OPENLIA_SCHEDULER_ENABLED` env name).

**Unblocks:**
- Company-mode deployments — an admin can create the first invite from the CLI before the web UI is reachable.
- Plan 8 (frontend shell) — the CLI is an alternative seeding path so frontend smoke tests don't need a running admin UI.
- Emergency recovery — all non-`serve` commands work with the server down.

**Out of scope (handled elsewhere):**
- Interactive shell / REPL mode, `--json` output, tab completion, `openlia upgrade`, `openlia backup` — Non-Goals per spec.
- The scheduler/notification polling routes themselves (Plan 6).
- Department-specific scheduling commands (owned by Plans 15/16/19 if any ever land).
- Typer's Rich integration (deferred — plain text is sufficient for v1 and removes a transitive dep).

---

## File Structure

```
packages/server/src/openlia_server/
├── cli.py                              # MODIFIED — root app + sub-apps + every command
└── _cli_support.py                     # NEW — build_session, require_company, log_cli_event,
                                       #        format_table, parse_duration, echo_error, OPENLIA_VERSION
├── db/
│   └── crypto.py                       # MODIFIED — add encrypt_with_key, decrypt_with_key

packages/server/tests/test_cli/
├── conftest.py                          # cli_db / cli_runner / cli_secret_key fixtures,
│                                       # sys.path helper for `_fakes`-style sibling imports
├── test_cli_support.py                  # build_session, require_company, parse_duration,
│                                       # format_table, log_cli_event
├── test_cli_serve.py                    # --no-scheduler sets env, banner shape
├── test_cli_admin_users.py              # list-users, unlock, reset-password, disable-user,
│                                       # enable-user, revoke-sessions
├── test_cli_admin_lockout.py            # enable / disable / status + audit rows
├── test_cli_admin_invites.py            # create-invite, list-invites, revoke-invite
├── test_cli_wizard.py                   # wizard reset + --yes + confirmation
├── test_cli_secrets.py                  # rotate-key success, exclusive-lock refusal
├── test_cli_maintenance.py              # real sweep vs --dry-run
├── test_cli_crypto_rotation.py          # encrypt_with_key/decrypt_with_key AAD binding

planning/
├── projectStructure.md                  # MODIFIED — cli.py comment + services/auth/ package note
└── implementation-plans/README.md       # MODIFIED — Plan 7 row flipped to Draft
```

### Design rules

1. **One file for commands, one file for plumbing.** All Typer objects (root app + sub-apps + command functions) live in `cli.py` per the spec. Shared plumbing lives in `_cli_support.py` so the command file stays scannable.
2. **`--db-url` propagates via Click context.** The root `@app.callback()` parses the global flags and stashes them in `ctx.obj`. Every subcommand that needs DB access takes `ctx: typer.Context` and calls `build_session(ctx.obj["db_url"])`.
3. **Exit codes are explicit.** `typer.Exit(code=1)` for general errors and mode-guard violations, `typer.Exit(code=2)` for "entity not found" (user not found, invite not found). `typer.Exit()` with no code defaults to 0.
4. **Stdout vs stderr.** Success messages → stdout via `typer.echo(...)`. Error messages → stderr via `typer.echo(..., err=True)`. `echo_error(msg)` wraps the stderr pattern and prefixes `Error: `.
5. **Audit rows from the CLI.** Every state-changing admin command calls `log_cli_event(db, event_type=..., user_id=..., metadata={...})`. The wrapper sets `actor_user_id=None` and merges `{"source": "cli"}` into metadata so UI and CLI rows collapse under one `event_type`.
6. **Mode guard runs *inside* the admin sub-app callback, not every subcommand.** Typer supports `@admin_app.callback()` — we invoke `require_company()` there once.
7. **`rotate-key` takes an exclusive DB lock.** The command issues `BEGIN EXCLUSIVE` on the SQLite connection before any re-encryption SQL. If the server is running its WAL-mode writer will block it → the exclusive begin raises `OperationalError("database is locked")`. We catch that, print the spec's exact "stop the server before rotating keys." message, and exit 1. No polling, no retry.
8. **Tests hit a real SQLite file.** CLI tests use a file-backed `sqlite:///{tmp_path}/t.db` — `:memory:` doesn't round-trip through `configure_engine` cleanly because each new `SessionLocal()` would open its own in-memory DB. The `conftest.py` fixture seeds via `Base.metadata.create_all` (faster than running Alembic) and wires `OPENLIA_SECRET_KEY` / `OPENLIA_HOME` / `OPENLIA_DB_URL` / `OPENLIA_MODE` through `monkeypatch`.
9. **No `tests/__init__.py`.** Match the repo-wide `--import-mode=importlib` pattern set in Phase 0 — `conftest.py` does `sys.path.insert(0, str(Path(__file__).parent))` when sibling-file imports are needed.
10. **Reuse existing services, don't duplicate logic.** `admin reset-password` calls `password_reset.admin_direct_reset`. `admin revoke-sessions` calls `sessions.revoke_all_sessions`. The CLI is a *thin* formatting layer; business rules stay in Plan 2.

### Notes for the executor

- If `services/auth/password_reset.admin_direct_reset`'s signature requires `admin_user_id`, the CLI passes `None` (the column is nullable). Plan 2 Task 11 wrote the function with `admin_user_id: str` (required). If the type is strict, either (a) relax to `str | None` in a one-line patch noted in Task 6 below, or (b) pass the sentinel string `"cli"` — **the plan assumes option (a)** and includes the patch. Keep that change in the same commit as Task 6.
- Typer's `CliRunner` doesn't preserve `sys.exit` codes automatically — read `result.exit_code` from the `Result` object.
- `SignupInvite.token` is the full token value; the spec's `list-invites` displays a 12-char prefix. Follow the spec — print `token[:12]` only.
- `--expires 7d` yields an `expires_at = datetime.now(UTC) + timedelta(days=7)`. `parse_duration` accepts `(\d+)([hdwm])` where `m` = minutes, `h` = hours, `d` = days, `w` = weeks. No months/years (ambiguous).
- When `secret.key` doesn't exist (i.e., the install is using `OPENLIA_SECRET_KEY` env var), `rotate-key` prints the second output form ("Update your OPENLIA_SECRET_KEY env var to: …") and does **not** write any file. Detect this by checking whether `openlia_home()/KEY_FILE_NAME` exists at the start of the command.
- The `lockout status` command prints "actor: cli" always. The spec reserves the "actor" field for a future UI toggle — today we read it from the latest `auth.lockout_setting_changed` event's `metadata.source`, defaulting to `cli` if no rows exist (fresh install case).

---

## Task 1: `_cli_support.py` — shared plumbing

**Files:**
- Create: `packages/server/src/openlia_server/_cli_support.py`
- Create: `packages/server/tests/test_cli/conftest.py`
- Create: `packages/server/tests/test_cli/test_cli_support.py`

- [ ] **Step 1: Sys-path helper + shared fixtures**

Create `packages/server/tests/test_cli/conftest.py`:

```python
"""CLI test fixtures + sys.path helper so sibling test modules can share
local imports under --import-mode=importlib (no tests.* package)."""
from __future__ import annotations

import base64
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent))


@pytest.fixture
def cli_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point OPENLIA_HOME at a fresh tmp dir so secret.key auto-creation
    and DB resolution don't touch the real ~/.openlia."""
    home = tmp_path / "openlia_home"
    home.mkdir()
    monkeypatch.setenv("OPENLIA_HOME", str(home))
    return home


@pytest.fixture
def cli_secret_key(monkeypatch: pytest.MonkeyPatch) -> bytes:
    raw = b"\x11" * 32
    monkeypatch.setenv("OPENLIA_SECRET_KEY", base64.b64encode(raw).decode())
    from openlia_server.db import crypto

    crypto._reset_cached_key()
    yield raw
    crypto._reset_cached_key()


@pytest.fixture
def cli_db_url(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> str:
    url = f"sqlite:///{tmp_path}/cli.db"
    monkeypatch.setenv("OPENLIA_DB_URL", url)
    return url


@pytest.fixture
def cli_engine(cli_db_url: str):
    """Configure the engine once per test + create every table. Yields the
    engine and disposes at teardown so state doesn't leak across tests."""
    from openlia_server.db import session as session_mod
    from openlia_server.db.models import Base

    session_mod.dispose_engine()
    engine = session_mod.configure_engine(cli_db_url)
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        session_mod.dispose_engine()


@pytest.fixture
def cli_session(cli_engine):
    from openlia_server.db.session import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def cli_runner():
    from typer.testing import CliRunner

    return CliRunner(mix_stderr=False)


@pytest.fixture
def company_mode(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENLIA_MODE", "company")


@pytest.fixture
def personal_mode(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setenv("OPENLIA_MODE", "personal")
```

- [ ] **Step 2: Write the failing test**

Create `packages/server/tests/test_cli/test_cli_support.py`:

```python
from __future__ import annotations

from datetime import timedelta

import pytest
import typer

from openlia_server import _cli_support as support


class TestParseDuration:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("30m", timedelta(minutes=30)),
            ("24h", timedelta(hours=24)),
            ("7d", timedelta(days=7)),
            ("2w", timedelta(weeks=2)),
        ],
    )
    def test_happy_paths(self, raw: str, expected: timedelta) -> None:
        assert support.parse_duration(raw) == expected

    @pytest.mark.parametrize("raw", ["", "7", "7x", "d7", "-3d", "abc", "7dd"])
    def test_invalid_raises(self, raw: str) -> None:
        with pytest.raises(ValueError):
            support.parse_duration(raw)


class TestFormatTable:
    def test_pads_each_column_to_widest_value(self) -> None:
        out = support.format_table(
            headers=["A", "Long"],
            rows=[["x", "yy"], ["zzz", "q"]],
        )
        lines = out.splitlines()
        assert len(lines) == 3
        # Column widths: A=3 (zzz), Long=4 (header)
        assert lines[0] == "A    Long"
        assert lines[1] == "x    yy  "
        assert lines[2] == "zzz  q   "

    def test_empty_rows_returns_header_only(self) -> None:
        out = support.format_table(headers=["H"], rows=[])
        assert out == "H"


class TestEchoError:
    def test_prefixes_error_and_writes_to_stderr(self, capsys: pytest.CaptureFixture[str]) -> None:
        support.echo_error("nope")
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == "Error: nope\n"


class TestRequireCompany:
    def test_personal_mode_exits_1(self, personal_mode) -> None:
        with pytest.raises(typer.Exit) as exc:
            support.require_company()
        assert exc.value.exit_code == 1

    def test_company_mode_returns(self, company_mode) -> None:
        support.require_company()  # no raise


class TestBuildSession:
    def test_uses_explicit_db_url(self, tmp_path, monkeypatch) -> None:
        from openlia_server.db import session as session_mod
        from openlia_server.db.models import Base

        monkeypatch.delenv("OPENLIA_DB_URL", raising=False)
        session_mod.dispose_engine()
        url = f"sqlite:///{tmp_path}/explicit.db"
        # No fixture-driven bootstrap — build_session configures the engine,
        # then we create tables and round-trip a row to prove it works.
        session = support.build_session(url)
        Base.metadata.create_all(session.get_bind())
        session.close()
        session_mod.dispose_engine()

    def test_falls_back_to_resolve_db_url(
        self, tmp_path, monkeypatch
    ) -> None:
        from openlia_server.db import session as session_mod

        session_mod.dispose_engine()
        monkeypatch.setenv("OPENLIA_DB_URL", f"sqlite:///{tmp_path}/env.db")
        session = support.build_session(None)
        assert str(session.get_bind().url).endswith("env.db")
        session.close()
        session_mod.dispose_engine()


class TestLogCliEvent:
    def test_emits_with_source_cli_and_null_actor(self, cli_session) -> None:
        from openlia_server.db.models.auth import AuthEvent, User
        from datetime import datetime, timezone

        user = User(
            id="u_1",
            email="u@e.com",
            display_name="u",
            password_hash="h",
            is_admin=False,
            is_disabled=False,
        )
        cli_session.add(user)
        cli_session.commit()

        support.log_cli_event(
            cli_session,
            event_type="user_disabled",
            user_id=user.id,
            metadata={"note": "ran from terminal"},
        )
        rows = cli_session.query(AuthEvent).all()
        assert len(rows) == 1
        row = rows[0]
        assert row.event_type == "user_disabled"
        assert row.user_id == user.id
        assert row.actor_user_id is None
        assert row.event_metadata == {"note": "ran from terminal", "source": "cli"}

    def test_metadata_source_preserved_when_already_set(self, cli_session) -> None:
        support.log_cli_event(
            cli_session, event_type="user_disabled", metadata={"source": "script"}
        )
        from openlia_server.db.models.auth import AuthEvent

        row = cli_session.query(AuthEvent).one()
        assert row.event_metadata["source"] == "script"
```

- [ ] **Step 3: Run the test to verify it fails**

Run: `uv run pytest packages/server/tests/test_cli/test_cli_support.py -v`
Expected: `ModuleNotFoundError: No module named 'openlia_server._cli_support'`.

- [ ] **Step 4: Implement `_cli_support.py`**

Create `packages/server/src/openlia_server/_cli_support.py`:

```python
"""Shared plumbing for the Typer CLI.

Kept in a sibling module to keep cli.py scannable. Every helper is usable
without a running FastAPI server — the CLI connects directly to the SQLite
DB via Plan 1A's session factory."""
from __future__ import annotations

import os
import re
import sys
from datetime import timedelta
from typing import Any

import typer
from sqlalchemy.orm import Session as DBSession

from openlia_server.db import bootstrap, session as session_mod
from openlia_server.services.auth import events as events_service

OPENLIA_VERSION = "0.1.0"

_DURATION_PATTERN = re.compile(r"^(\d+)([mhdw])$")
_DURATION_UNITS = {
    "m": "minutes",
    "h": "hours",
    "d": "days",
    "w": "weeks",
}


def parse_duration(raw: str) -> timedelta:
    """Convert '7d', '24h', '30m', '2w' into a timedelta. Raises ValueError
    on malformed input. No months/years — ambiguous."""
    match = _DURATION_PATTERN.fullmatch(raw or "")
    if match is None:
        raise ValueError(
            f"Invalid duration {raw!r}. Expected <int><unit> where unit is one "
            "of m (minutes), h (hours), d (days), w (weeks)."
        )
    amount = int(match.group(1))
    unit = _DURATION_UNITS[match.group(2)]
    if amount <= 0:
        raise ValueError(f"Duration must be positive, got {raw!r}.")
    return timedelta(**{unit: amount})


def format_table(*, headers: list[str], rows: list[list[str]]) -> str:
    """Plain column-aligned text table. Double-space gutter between columns.
    Pads rows to column max widths. No borders, no Rich dependency."""
    if not rows:
        return "  ".join(headers).rstrip()
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(cell))
    lines = []
    header_line = "  ".join(h.ljust(widths[i]) for i, h in enumerate(headers))
    lines.append(header_line.rstrip())
    for row in rows:
        line = "  ".join(cell.ljust(widths[i]) for i, cell in enumerate(row))
        lines.append(line)
    return "\n".join(lines)


def echo_error(message: str) -> None:
    """Write `Error: <message>` to stderr. Does not exit."""
    typer.echo(f"Error: {message}", err=True)


def require_company() -> None:
    """Exit 1 unless OPENLIA_MODE is 'company'. Used by the admin sub-app
    callback so every admin subcommand is gated in one place."""
    mode = os.environ.get("OPENLIA_MODE", "personal").lower()
    if mode != "company":
        echo_error("admin commands require company mode.")
        raise typer.Exit(code=1)


def build_session(db_url: str | None) -> DBSession:
    """Open a synchronous SQLAlchemy session for a CLI command.

    If the engine has not been configured in this process yet, configure it
    against the provided URL (explicit `--db-url` wins over env). Otherwise
    reuse the existing engine — Typer's callback chain can invoke this more
    than once in a single command invocation when sub-apps nest."""
    url = db_url or bootstrap.resolve_db_url()
    try:
        session_mod.get_engine()
    except RuntimeError:
        session_mod.configure_engine(url)
    return session_mod.SessionLocal()


def log_cli_event(
    db: DBSession,
    *,
    event_type: str,
    user_id: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    """Audit wrapper. Guarantees actor_user_id=None (CLI has no logged-in
    user) and that metadata carries source=cli (existing keys preserved)."""
    merged: dict[str, Any] = {"source": "cli"}
    if metadata:
        merged = {**merged, **metadata}  # caller's keys win — e.g., source=script
    events_service.log_auth_event(
        db,
        event_type=event_type,
        user_id=user_id,
        actor_user_id=None,
        metadata=merged,
    )


def exit_not_found(entity: str, identifier: str) -> None:
    """Print a standard 'not found' error and exit 2."""
    echo_error(f"{entity} not found: {identifier}")
    raise typer.Exit(code=2)


def print_version_and_exit() -> None:
    """`--version` handler. Eager callback prints and exits before argument parsing."""
    typer.echo(OPENLIA_VERSION)
    raise typer.Exit()
```

- [ ] **Step 5: Run the test to confirm it passes**

Run: `uv run pytest packages/server/tests/test_cli/test_cli_support.py -v`
Expected: all pass.

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/_cli_support.py \
        packages/server/tests/test_cli/conftest.py \
        packages/server/tests/test_cli/test_cli_support.py
git commit -m "phase-7(cli): shared CLI plumbing — session builder, mode guard, audit wrapper"
```

---

## Task 2: Global flags + `serve --no-scheduler`

**Files:**
- Modify: `packages/server/src/openlia_server/cli.py`
- Create: `packages/server/tests/test_cli/test_cli_serve.py`

Extend the Phase-0 CLI skeleton with the three global flags (`--no-color`, `--db-url`, `--version`) and widen `serve` with the `--no-scheduler` flag. No admin/wizard/secrets sub-apps yet — those land in the next tasks. Preserves the existing `bootstrap()` → `uvicorn.run(..., factory=True)` ordering.

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_cli/test_cli_serve.py`:

```python
from __future__ import annotations

import os

import pytest

from openlia_server.cli import app


class TestGlobalFlags:
    def test_version_prints_and_exits_zero(self, cli_runner) -> None:
        result = cli_runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert result.stdout.strip() == "0.1.0"

    def test_help_lists_every_subcommand(self, cli_runner) -> None:
        result = cli_runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        for cmd in ("serve", "admin", "wizard", "secrets", "maintenance"):
            assert cmd in result.stdout


class TestServeFlags:
    def test_no_scheduler_sets_env_before_uvicorn(
        self, cli_runner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        called: dict[str, object] = {}

        def fake_uvicorn(target: str, **kwargs: object) -> None:
            called["target"] = target
            called["kwargs"] = kwargs
            called["scheduler_env"] = os.environ.get("OPENLIA_SCHEDULER_ENABLED")

        def fake_bootstrap() -> None:
            called["bootstrap"] = True

        monkeypatch.setattr("openlia_server.cli.uvicorn.run", fake_uvicorn)
        monkeypatch.setattr("openlia_server.cli.bootstrap", fake_bootstrap)
        monkeypatch.delenv("OPENLIA_SCHEDULER_ENABLED", raising=False)

        result = cli_runner.invoke(app, ["serve", "--no-scheduler", "--port", "1234"])
        assert result.exit_code == 0, result.output
        assert called["bootstrap"] is True
        assert called["target"] == "openlia_server.app:create_app"
        assert called["kwargs"]["factory"] is True
        assert called["kwargs"]["port"] == 1234
        assert called["scheduler_env"] == "false"

    def test_serve_without_no_scheduler_does_not_override_env(
        self, cli_runner, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        captured: dict[str, object] = {}

        def fake_uvicorn(target: str, **kwargs: object) -> None:
            captured["scheduler_env"] = os.environ.get("OPENLIA_SCHEDULER_ENABLED")

        monkeypatch.setattr("openlia_server.cli.uvicorn.run", fake_uvicorn)
        monkeypatch.setattr("openlia_server.cli.bootstrap", lambda: None)
        monkeypatch.setenv("OPENLIA_SCHEDULER_ENABLED", "true")

        result = cli_runner.invoke(app, ["serve"])
        assert result.exit_code == 0
        assert captured["scheduler_env"] == "true"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest packages/server/tests/test_cli/test_cli_serve.py -v`
Expected: `--version` / `--no-scheduler` flags don't exist yet → test errors.

- [ ] **Step 3: Update `cli.py`**

Replace `packages/server/src/openlia_server/cli.py` with:

```python
"""Typer CLI entry point. Registered as the `openlia` console script.

The CLI is the primary operator surface: `serve` runs the HTTP server,
everything else (admin, wizard, secrets, maintenance) opens a synchronous
SQLAlchemy session directly against the DB file.
"""
from __future__ import annotations

import os

import typer
import uvicorn

from openlia_server._cli_support import OPENLIA_VERSION, print_version_and_exit
from openlia_server.db.bootstrap import bootstrap

app = typer.Typer(
    name="openlia",
    help="OpenLIA — open-source self-hosted AI investor assistant.",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        print_version_and_exit()


@app.callback()
def _root(
    ctx: typer.Context,
    no_color: bool = typer.Option(
        False, "--no-color", help="Disable colored output (for piping/scripting)."
    ),
    db_url: str | None = typer.Option(
        None, "--db-url", help="Override the database URL (defaults to OPENLIA_DB_URL).",
    ),
    version: bool = typer.Option(
        False,
        "--version",
        help="Print version and exit.",
        is_eager=True,
        callback=_version_callback,
    ),
) -> None:
    """Force Typer into multi-command mode and stash the global flags so
    subcommands can read them via `ctx.obj`."""
    ctx.obj = {"no_color": no_color, "db_url": db_url, "version": version}


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Bind address."),
    port: int = typer.Option(8000, help="Bind port."),
    reload: bool = typer.Option(
        False, "--reload", help="Auto-reload on code changes (development only)."
    ),
    no_scheduler: bool = typer.Option(
        False,
        "--no-scheduler",
        help="Start the server without the background task scheduler.",
    ),
) -> None:
    """Start the OpenLIA HTTP server."""
    if no_scheduler:
        # Must be set before app factory runs — the scheduler reads it from env.
        os.environ["OPENLIA_SCHEDULER_ENABLED"] = "false"
    bootstrap()
    uvicorn.run(
        "openlia_server.app:create_app",
        host=host,
        port=port,
        reload=reload,
        factory=True,
    )


def main() -> None:
    """Console-script entry point."""
    app()


__all__ = ["app", "main", "OPENLIA_VERSION"]
```

- [ ] **Step 4: Run the test to confirm it passes**

Run: `uv run pytest packages/server/tests/test_cli/test_cli_serve.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/cli.py \
        packages/server/tests/test_cli/test_cli_serve.py
git commit -m "phase-7(cli): add --version/--no-color/--db-url + serve --no-scheduler"
```

---

## Task 3: `admin` sub-app + `admin list-users`

**Files:**
- Modify: `packages/server/src/openlia_server/cli.py`
- Create: `packages/server/tests/test_cli/test_cli_admin_users.py`

Stand up the `admin` sub-app with its mode-guard callback, then ship the first subcommand (`list-users`). The sub-app pattern established here is reused for every subsequent admin command.

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_cli/test_cli_admin_users.py`:

```python
from __future__ import annotations

from datetime import datetime, timezone

import pytest

from openlia_server.cli import app
from openlia_server.db.models.auth import User


@pytest.fixture
def seed_users(cli_session):
    alice = User(
        id="u_alice",
        email="alice@company.com",
        display_name="Alice Chen",
        password_hash="hash",
        is_admin=True,
        is_disabled=False,
        last_login_at=datetime(2026, 4, 15, 9, 30, tzinfo=timezone.utc),
    )
    bob = User(
        id="u_bob",
        email="bob@company.com",
        display_name="Bob Kim",
        password_hash="hash",
        is_admin=False,
        is_disabled=False,
    )
    carol = User(
        id="u_carol",
        email="carol@company.com",
        display_name="Carol Wu",
        password_hash="hash",
        is_admin=False,
        is_disabled=True,
    )
    cli_session.add_all([alice, bob, carol])
    cli_session.commit()
    return {"alice": alice, "bob": bob, "carol": carol}


class TestAdminGuard:
    def test_personal_mode_rejects(self, cli_runner, personal_mode, cli_engine):
        result = cli_runner.invoke(app, ["admin", "list-users"])
        assert result.exit_code == 1
        assert "admin commands require company mode" in result.stderr


class TestListUsers:
    def test_lists_all_users_with_columns(
        self, cli_runner, company_mode, cli_engine, seed_users
    ):
        result = cli_runner.invoke(app, ["admin", "list-users"])
        assert result.exit_code == 0, result.output
        out = result.stdout
        assert "Email" in out and "Display Name" in out
        assert "alice@company.com" in out
        assert "bob@company.com" in out
        assert "carol@company.com" in out
        # Admin column: alice=yes, others=no
        alice_row = next(line for line in out.splitlines() if "alice@" in line)
        assert "yes" in alice_row.split("alice@company.com")[1][:20]

    def test_disabled_filter(
        self, cli_runner, company_mode, cli_engine, seed_users
    ):
        result = cli_runner.invoke(app, ["admin", "list-users", "--disabled"])
        assert result.exit_code == 0
        out = result.stdout
        assert "carol@company.com" in out
        assert "alice@company.com" not in out
        assert "bob@company.com" not in out

    def test_last_login_blank_when_null(
        self, cli_runner, company_mode, cli_engine, seed_users
    ):
        result = cli_runner.invoke(app, ["admin", "list-users"])
        bob_line = next(line for line in result.stdout.splitlines() if "bob@" in line)
        # Bob has no last_login_at — the trailing column should render empty
        assert bob_line.rstrip().endswith("no")
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest packages/server/tests/test_cli/test_cli_admin_users.py -v`
Expected: `No such command 'admin'`.

- [ ] **Step 3: Add the admin sub-app + list-users to `cli.py`**

Append to `packages/server/src/openlia_server/cli.py` (below `serve`, above `main`):

```python
# ---------------------------------------------------------------------------
# admin sub-app
# ---------------------------------------------------------------------------

from sqlalchemy import select  # noqa: E402 — kept near admin code

from openlia_server._cli_support import (  # noqa: E402
    build_session,
    format_table,
    require_company,
)
from openlia_server.db.models.auth import User  # noqa: E402

admin_app = typer.Typer(
    name="admin",
    help="Admin operations: manage users, invites, and sessions (company mode only).",
    no_args_is_help=True,
)


@admin_app.callback()
def _admin_callback() -> None:
    """Gate every admin subcommand on company mode."""
    require_company()


@admin_app.command("list-users")
def admin_list_users(
    ctx: typer.Context,
    disabled: bool = typer.Option(False, "--disabled", help="Only show disabled accounts."),
) -> None:
    """List all user accounts."""
    db = build_session(ctx.obj["db_url"])
    try:
        stmt = select(User).order_by(User.email)
        if disabled:
            stmt = stmt.where(User.is_disabled.is_(True))
        users = list(db.execute(stmt).scalars())
        rows = []
        for u in users:
            last_login = (
                u.last_login_at.strftime("%Y-%m-%d %H:%M") if u.last_login_at else ""
            )
            rows.append(
                [
                    u.id[:8],
                    u.email,
                    u.display_name,
                    "yes" if u.is_admin else "no",
                    "yes" if u.is_disabled else "no",
                    last_login,
                ]
            )
        typer.echo(
            format_table(
                headers=["ID", "Email", "Display Name", "Admin", "Disabled", "Last Login"],
                rows=rows,
            )
        )
    finally:
        db.close()


app.add_typer(admin_app, name="admin")
```

- [ ] **Step 4: Run the tests to confirm they pass**

Run: `uv run pytest packages/server/tests/test_cli/test_cli_admin_users.py::TestAdminGuard packages/server/tests/test_cli/test_cli_admin_users.py::TestListUsers -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/cli.py \
        packages/server/tests/test_cli/test_cli_admin_users.py
git commit -m "phase-7(cli): admin sub-app scaffold + list-users"
```

---

## Task 4: `admin unlock <email>`

**Files:**
- Modify: `packages/server/src/openlia_server/cli.py`
- Modify: `packages/server/tests/test_cli/test_cli_admin_users.py`

Clears `locked_until` and `failed_login_attempts`. Per spec, `unlock` does not emit an audit event (v1 default).

- [ ] **Step 1: Write the failing test**

Append to `packages/server/tests/test_cli/test_cli_admin_users.py`:

```python
from datetime import timedelta


class TestUnlock:
    def test_clears_lock_state(self, cli_runner, company_mode, cli_engine, cli_session):
        now = datetime.now(timezone.utc)
        alice = User(
            id="u_alice",
            email="alice@company.com",
            display_name="Alice",
            password_hash="h",
            is_admin=False,
            is_disabled=False,
            failed_login_attempts=5,
            locked_until=now + timedelta(minutes=10),
        )
        cli_session.add(alice)
        cli_session.commit()

        result = cli_runner.invoke(app, ["admin", "unlock", "alice@company.com"])
        assert result.exit_code == 0, result.output
        assert "Unlocked: alice@company.com" in result.stdout
        cli_session.expire_all()
        refreshed = cli_session.get(User, "u_alice")
        assert refreshed.locked_until is None
        assert refreshed.failed_login_attempts == 0

    def test_user_not_found_exits_2(
        self, cli_runner, company_mode, cli_engine
    ):
        result = cli_runner.invoke(app, ["admin", "unlock", "ghost@company.com"])
        assert result.exit_code == 2
        assert "not found" in result.stderr.lower()
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest packages/server/tests/test_cli/test_cli_admin_users.py::TestUnlock -v`
Expected: `No such command 'unlock'`.

- [ ] **Step 3: Implement `admin unlock`**

Add to `cli.py` immediately after the `list-users` command (before `app.add_typer(admin_app, ...)`):

```python
@admin_app.command("unlock")
def admin_unlock(
    ctx: typer.Context,
    email: str = typer.Argument(..., help="Email of the user to unlock."),
) -> None:
    """Clear locked_until and failed_login_attempts for a user."""
    from openlia_server._cli_support import exit_not_found

    db = build_session(ctx.obj["db_url"])
    try:
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is None:
            exit_not_found("user", email)
        user.locked_until = None
        user.failed_login_attempts = 0
        db.commit()
        typer.echo(f"Unlocked: {email}")
    finally:
        db.close()
```

- [ ] **Step 4: Run the test to confirm it passes**

Run: `uv run pytest packages/server/tests/test_cli/test_cli_admin_users.py::TestUnlock -v`
Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/cli.py \
        packages/server/tests/test_cli/test_cli_admin_users.py
git commit -m "phase-7(cli): admin unlock clears locked_until + failed_login_attempts"
```

---

## Task 5: `admin lockout` — enable / disable / status

**Files:**
- Modify: `packages/server/src/openlia_server/cli.py`
- Create: `packages/server/tests/test_cli/test_cli_admin_lockout.py`

Toggles `config_store["auth.lockout.enabled"]` (canonical key from Plan 2). `enable` and `disable` emit `auth.lockout_setting_changed` audit rows; `status` reads current value + latest event.

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_cli/test_cli_admin_lockout.py`:

```python
from __future__ import annotations

import pytest
from sqlalchemy import select

from openlia_server.cli import app
from openlia_server.db.models.auth import AuthEvent
from openlia_server.db.models.infrastructure import ConfigStore


class TestLockoutEnable:
    def test_defaults_on_no_row_means_noop(
        self, cli_runner, company_mode, cli_engine, cli_session
    ):
        result = cli_runner.invoke(app, ["admin", "lockout", "enable"])
        assert result.exit_code == 0, result.output
        assert "Lockout enabled" in result.stdout
        row = cli_session.execute(
            select(ConfigStore).where(ConfigStore.key == "auth.lockout.enabled")
        ).scalar_one_or_none()
        assert row is not None
        assert row.value == {"enabled": True}
        events = cli_session.execute(
            select(AuthEvent).where(AuthEvent.event_type == "auth.lockout_setting_changed")
        ).scalars().all()
        assert len(events) == 1
        assert events[0].event_metadata["new"] is True
        assert events[0].event_metadata["source"] == "cli"
        assert events[0].actor_user_id is None

    def test_already_enabled_is_noop_no_event(
        self, cli_runner, company_mode, cli_engine, cli_session
    ):
        cli_session.add(ConfigStore(key="auth.lockout.enabled", value={"enabled": True}))
        cli_session.commit()
        result = cli_runner.invoke(app, ["admin", "lockout", "enable"])
        assert result.exit_code == 0
        assert "Lockout enabled" in result.stdout
        events = cli_session.execute(
            select(AuthEvent).where(AuthEvent.event_type == "auth.lockout_setting_changed")
        ).scalars().all()
        assert events == []


class TestLockoutDisable:
    def test_disables_and_warns_about_locked_accounts(
        self, cli_runner, company_mode, cli_engine, cli_session
    ):
        cli_session.add(ConfigStore(key="auth.lockout.enabled", value={"enabled": True}))
        cli_session.commit()
        result = cli_runner.invoke(app, ["admin", "lockout", "disable"])
        assert result.exit_code == 0
        assert "Lockout disabled" in result.stdout
        assert "openlia admin unlock" in result.stdout
        cli_session.expire_all()
        row = cli_session.execute(
            select(ConfigStore).where(ConfigStore.key == "auth.lockout.enabled")
        ).scalar_one()
        assert row.value == {"enabled": False}
        event = cli_session.execute(
            select(AuthEvent).where(AuthEvent.event_type == "auth.lockout_setting_changed")
        ).scalar_one()
        assert event.event_metadata["old"] is True
        assert event.event_metadata["new"] is False


class TestLockoutStatus:
    def test_prints_state_and_last_change(
        self, cli_runner, company_mode, cli_engine
    ):
        cli_runner.invoke(app, ["admin", "lockout", "disable"])
        result = cli_runner.invoke(app, ["admin", "lockout", "status"])
        assert result.exit_code == 0
        assert "Lockout: disabled" in result.stdout
        assert "actor: cli" in result.stdout

    def test_fresh_install_reports_enabled_default(
        self, cli_runner, company_mode, cli_engine
    ):
        result = cli_runner.invoke(app, ["admin", "lockout", "status"])
        assert result.exit_code == 0
        assert "Lockout: enabled" in result.stdout
        assert "Last changed: never" in result.stdout
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest packages/server/tests/test_cli/test_cli_admin_lockout.py -v`
Expected: `No such command 'lockout'`.

- [ ] **Step 3: Implement the `lockout` sub-app in `cli.py`**

Add after `admin_unlock` (before `app.add_typer(admin_app, ...)`):

```python
from datetime import datetime, timezone  # noqa: E402

from openlia_server.db.models.auth import AuthEvent  # noqa: E402
from openlia_server.db.models.infrastructure import ConfigStore  # noqa: E402
from openlia_server._cli_support import log_cli_event  # noqa: E402

LOCKOUT_CONFIG_KEY = "auth.lockout.enabled"

lockout_app = typer.Typer(
    name="lockout",
    help="Toggle or inspect the account-lockout feature.",
    no_args_is_help=True,
)


def _read_lockout_row(db) -> tuple[bool, ConfigStore | None]:
    row = db.execute(
        select(ConfigStore).where(ConfigStore.key == LOCKOUT_CONFIG_KEY)
    ).scalar_one_or_none()
    if row is None:
        return True, None  # default on
    value = row.value or {}
    return bool(value.get("enabled", True)), row


def _write_lockout(db, *, enabled: bool, previous: bool) -> None:
    row = db.execute(
        select(ConfigStore).where(ConfigStore.key == LOCKOUT_CONFIG_KEY)
    ).scalar_one_or_none()
    if row is None:
        db.add(ConfigStore(key=LOCKOUT_CONFIG_KEY, value={"enabled": enabled}))
    else:
        row.value = {"enabled": enabled}
    db.flush()
    log_cli_event(
        db,
        event_type="auth.lockout_setting_changed",
        metadata={"old": previous, "new": enabled},
    )
    db.commit()


@lockout_app.command("enable")
def lockout_enable(ctx: typer.Context) -> None:
    """Enable the account-lockout feature (sets auth.lockout.enabled=true)."""
    db = build_session(ctx.obj["db_url"])
    try:
        current, _ = _read_lockout_row(db)
        if current:
            typer.echo("Lockout enabled (already on).")
            return
        _write_lockout(db, enabled=True, previous=current)
        typer.echo("Lockout enabled.")
    finally:
        db.close()


@lockout_app.command("disable")
def lockout_disable(ctx: typer.Context) -> None:
    """Disable the account-lockout feature. Existing locked_until values
    are preserved — use `openlia admin unlock <email>` to clear them."""
    db = build_session(ctx.obj["db_url"])
    try:
        current, _ = _read_lockout_row(db)
        if not current:
            typer.echo("Lockout disabled (already off).")
            return
        _write_lockout(db, enabled=False, previous=current)
        typer.echo(
            "Lockout disabled. Currently-locked accounts remain locked until "
            "you run `openlia admin unlock <email>`."
        )
    finally:
        db.close()


@lockout_app.command("status")
def lockout_status(ctx: typer.Context) -> None:
    """Print current lockout state, last change, and actor."""
    db = build_session(ctx.obj["db_url"])
    try:
        current, _ = _read_lockout_row(db)
        last_event = db.execute(
            select(AuthEvent)
            .where(AuthEvent.event_type == "auth.lockout_setting_changed")
            .order_by(AuthEvent.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()
        state = "enabled" if current else "disabled"
        typer.echo(f"Lockout: {state}")
        if last_event is None:
            typer.echo("Last changed: never")
        else:
            actor = (last_event.event_metadata or {}).get("source", "cli")
            typer.echo(
                f"Last changed: {last_event.created_at.strftime('%Y-%m-%d %H:%M')} "
                f"(actor: {actor})"
            )
    finally:
        db.close()


admin_app.add_typer(lockout_app, name="lockout")
```

- [ ] **Step 4: Run the tests to confirm they pass**

Run: `uv run pytest packages/server/tests/test_cli/test_cli_admin_lockout.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/cli.py \
        packages/server/tests/test_cli/test_cli_admin_lockout.py
git commit -m "phase-7(cli): admin lockout enable/disable/status with audit rows"
```

---

## Task 6: `admin reset-password <email>`

**Files:**
- Modify: `packages/server/src/openlia_server/cli.py`
- Modify: `packages/server/src/openlia_server/services/auth/password_reset.py` (relax `admin_user_id`)
- Modify: `packages/server/tests/test_cli/test_cli_admin_users.py`

Prompts for a new password (hidden + confirmation), reuses `password_reset.admin_direct_reset`, which hashes with Argon2id, flips `must_change_password`, revokes sessions, and emits `password_reset_by_admin`.

- [ ] **Step 1: Relax `admin_direct_reset` signature**

Plan 2 Task 11 declares `admin_user_id: str` (required). The CLI has no logged-in admin. Open `packages/server/src/openlia_server/services/auth/password_reset.py` and change the signature to accept `admin_user_id: str | None`:

```python
def admin_direct_reset(
    db: DBSession, *, user_id: str, new_password: str, admin_user_id: str | None
) -> None:
    passwords.validate_password_policy(new_password)
    user = db.get(User, user_id)
    if user is None:
        raise TokenInvalidError("User not found.")

    user.password_hash = passwords.hash_password(new_password)
    user.must_change_password = True
    user.updated_at = datetime.now(timezone.utc)
    db.commit()
    sessions.revoke_all_sessions(db, user_id=user.id)

    events.log_auth_event(
        db,
        event_type="password_reset_by_admin",
        user_id=user.id,
        actor_user_id=admin_user_id,
    )
```

(Only the `admin_user_id` type annotation changes; no behavior change.)

- [ ] **Step 2: Write the failing CLI test**

Append to `packages/server/tests/test_cli/test_cli_admin_users.py`:

```python
from openlia_server.services.auth import passwords


class TestResetPassword:
    def test_with_password_flag_sets_must_change(
        self, cli_runner, company_mode, cli_engine, cli_session
    ):
        alice = User(
            id="u_alice",
            email="alice@company.com",
            display_name="Alice",
            password_hash="original",
            is_admin=False,
            is_disabled=False,
        )
        cli_session.add(alice)
        cli_session.commit()

        result = cli_runner.invoke(
            app,
            ["admin", "reset-password", "alice@company.com", "--password", "NewStrongP@ssw0rd1"],
        )
        assert result.exit_code == 0, result.output
        assert "Password reset for alice@company.com" in result.stdout
        cli_session.expire_all()
        refreshed = cli_session.get(User, "u_alice")
        assert refreshed.must_change_password is True
        assert refreshed.password_hash != "original"
        assert passwords.verify_password(refreshed.password_hash, "NewStrongP@ssw0rd1")

    def test_interactive_prompt_accepts_password(
        self, cli_runner, company_mode, cli_engine, cli_session
    ):
        alice = User(
            id="u_alice",
            email="alice@company.com",
            display_name="Alice",
            password_hash="original",
            is_admin=False,
            is_disabled=False,
        )
        cli_session.add(alice)
        cli_session.commit()

        # Typer's hidden-input-with-confirmation = password entered twice.
        result = cli_runner.invoke(
            app,
            ["admin", "reset-password", "alice@company.com"],
            input="PromptStrongP@ss1\nPromptStrongP@ss1\n",
        )
        assert result.exit_code == 0, result.output
        cli_session.expire_all()
        refreshed = cli_session.get(User, "u_alice")
        assert passwords.verify_password(refreshed.password_hash, "PromptStrongP@ss1")

    def test_user_not_found_exits_2(
        self, cli_runner, company_mode, cli_engine
    ):
        result = cli_runner.invoke(
            app,
            ["admin", "reset-password", "ghost@company.com", "--password", "x" * 20],
        )
        assert result.exit_code == 2
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest packages/server/tests/test_cli/test_cli_admin_users.py::TestResetPassword -v`
Expected: command doesn't exist.

- [ ] **Step 4: Implement `admin reset-password`**

Add to `cli.py` (immediately after `admin_unlock`):

```python
from openlia_server.services.auth import password_reset as password_reset_service  # noqa: E402
from openlia_server.services.auth.errors import AuthError, TokenInvalidError  # noqa: E402


@admin_app.command("reset-password")
def admin_reset_password(
    ctx: typer.Context,
    email: str = typer.Argument(..., help="Email of the user to reset."),
    password: str | None = typer.Option(
        None,
        "--password",
        help="New password (skip interactive prompt — visible in shell history).",
    ),
) -> None:
    """Reset a user's password. Sets must_change_password=true and revokes sessions."""
    from openlia_server._cli_support import exit_not_found

    if password is None:
        password = typer.prompt(
            "New password", hide_input=True, confirmation_prompt=True
        )

    db = build_session(ctx.obj["db_url"])
    try:
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is None:
            exit_not_found("user", email)
        try:
            password_reset_service.admin_direct_reset(
                db, user_id=user.id, new_password=password, admin_user_id=None
            )
        except AuthError as exc:
            from openlia_server._cli_support import echo_error

            echo_error(str(exc))
            raise typer.Exit(code=1) from exc
        except TokenInvalidError:
            exit_not_found("user", email)
        typer.echo(
            f"Password reset for {email}. User will be required to change it on next login."
        )
    finally:
        db.close()
```

- [ ] **Step 5: Run the tests to confirm they pass**

Run: `uv run pytest packages/server/tests/test_cli/test_cli_admin_users.py::TestResetPassword packages/server/tests/test_services/test_auth/test_password_reset.py -v`
Expected: all pass (relaxing the type didn't break Plan 2's tests).

- [ ] **Step 6: Commit**

```bash
git add packages/server/src/openlia_server/cli.py \
        packages/server/src/openlia_server/services/auth/password_reset.py \
        packages/server/tests/test_cli/test_cli_admin_users.py
git commit -m "phase-7(cli): admin reset-password (prompt + --password) with CLI-actor audit"
```

---

## Task 7: `admin disable-user` + `admin enable-user`

**Files:**
- Modify: `packages/server/src/openlia_server/cli.py`
- Modify: `packages/server/tests/test_cli/test_cli_admin_users.py`

- [ ] **Step 1: Write the failing tests**

Append to `packages/server/tests/test_cli/test_cli_admin_users.py`:

```python
from openlia_server.db.models.auth import Session as AuthSession


class TestDisableUser:
    def test_disables_and_revokes_sessions(
        self, cli_runner, company_mode, cli_engine, cli_session
    ):
        alice = User(
            id="u_alice",
            email="alice@company.com",
            display_name="Alice",
            password_hash="h",
            is_admin=False,
            is_disabled=False,
        )
        cli_session.add(alice)
        now = datetime.now(timezone.utc)
        for i in range(3):
            cli_session.add(
                AuthSession(
                    id=f"s_{i}",
                    user_id="u_alice",
                    token_hash=f"th_{i}",
                    last_seen_at=now,
                    expires_at=now + timedelta(days=1),
                )
            )
        cli_session.commit()

        result = cli_runner.invoke(app, ["admin", "disable-user", "alice@company.com"])
        assert result.exit_code == 0, result.output
        assert "Disabled: alice@company.com" in result.stdout
        assert "3 sessions revoked" in result.stdout
        cli_session.expire_all()
        assert cli_session.get(User, "u_alice").is_disabled is True
        live_sessions = cli_session.execute(
            select(AuthSession).where(
                AuthSession.user_id == "u_alice", AuthSession.revoked_at.is_(None)
            )
        ).scalars().all()
        assert live_sessions == []

    def test_user_not_found_exits_2(
        self, cli_runner, company_mode, cli_engine
    ):
        result = cli_runner.invoke(app, ["admin", "disable-user", "ghost@company.com"])
        assert result.exit_code == 2


class TestEnableUser:
    def test_enables(self, cli_runner, company_mode, cli_engine, cli_session):
        alice = User(
            id="u_alice",
            email="alice@company.com",
            display_name="Alice",
            password_hash="h",
            is_admin=False,
            is_disabled=True,
        )
        cli_session.add(alice)
        cli_session.commit()

        result = cli_runner.invoke(app, ["admin", "enable-user", "alice@company.com"])
        assert result.exit_code == 0
        assert "Enabled: alice@company.com" in result.stdout
        cli_session.expire_all()
        assert cli_session.get(User, "u_alice").is_disabled is False

    def test_user_not_found_exits_2(self, cli_runner, company_mode, cli_engine):
        result = cli_runner.invoke(app, ["admin", "enable-user", "ghost@company.com"])
        assert result.exit_code == 2
```

(add `from datetime import timedelta` to the top of the file if not already present.)

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest packages/server/tests/test_cli/test_cli_admin_users.py::TestDisableUser packages/server/tests/test_cli/test_cli_admin_users.py::TestEnableUser -v`
Expected: commands don't exist.

- [ ] **Step 3: Implement both commands**

Add to `cli.py` (after `admin_reset_password`):

```python
from openlia_server.db.models.auth import Session as AuthSession  # noqa: E402
from openlia_server.services.auth import sessions as sessions_service  # noqa: E402


@admin_app.command("disable-user")
def admin_disable_user(
    ctx: typer.Context,
    email: str = typer.Argument(..., help="Email of the user to disable."),
) -> None:
    """Disable a user account and revoke all their sessions."""
    from openlia_server._cli_support import exit_not_found

    db = build_session(ctx.obj["db_url"])
    try:
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is None:
            exit_not_found("user", email)
        live_before = db.execute(
            select(AuthSession).where(
                AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)
            )
        ).scalars().all()
        user.is_disabled = True
        user.updated_at = datetime.now(timezone.utc)
        db.flush()
        sessions_service.revoke_all_sessions(db, user_id=user.id)
        log_cli_event(db, event_type="user_disabled", user_id=user.id)
        typer.echo(f"Disabled: {email} ({len(live_before)} sessions revoked)")
    finally:
        db.close()


@admin_app.command("enable-user")
def admin_enable_user(
    ctx: typer.Context,
    email: str = typer.Argument(..., help="Email of the user to enable."),
) -> None:
    """Re-enable a disabled user account."""
    from openlia_server._cli_support import exit_not_found

    db = build_session(ctx.obj["db_url"])
    try:
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is None:
            exit_not_found("user", email)
        user.is_disabled = False
        user.updated_at = datetime.now(timezone.utc)
        db.flush()
        log_cli_event(db, event_type="user_enabled", user_id=user.id)
        db.commit()
        typer.echo(f"Enabled: {email}")
    finally:
        db.close()
```

- [ ] **Step 4: Run the tests to confirm they pass**

Run: `uv run pytest packages/server/tests/test_cli/test_cli_admin_users.py::TestDisableUser packages/server/tests/test_cli/test_cli_admin_users.py::TestEnableUser -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/cli.py \
        packages/server/tests/test_cli/test_cli_admin_users.py
git commit -m "phase-7(cli): admin disable-user + enable-user with session revoke + audit"
```

---

## Task 8: `admin revoke-sessions <email>`

**Files:**
- Modify: `packages/server/src/openlia_server/cli.py`
- Modify: `packages/server/tests/test_cli/test_cli_admin_users.py`

- [ ] **Step 1: Write the failing test**

Append to `packages/server/tests/test_cli/test_cli_admin_users.py`:

```python
class TestRevokeSessions:
    def test_revokes_all_sessions(
        self, cli_runner, company_mode, cli_engine, cli_session
    ):
        alice = User(
            id="u_alice",
            email="alice@company.com",
            display_name="Alice",
            password_hash="h",
            is_admin=False,
            is_disabled=False,
        )
        cli_session.add(alice)
        now = datetime.now(timezone.utc)
        for i in range(4):
            cli_session.add(
                AuthSession(
                    id=f"s_{i}",
                    user_id="u_alice",
                    token_hash=f"th_{i}",
                    last_seen_at=now,
                    expires_at=now + timedelta(days=1),
                )
            )
        cli_session.commit()

        result = cli_runner.invoke(app, ["admin", "revoke-sessions", "alice@company.com"])
        assert result.exit_code == 0, result.output
        assert "Revoked 4 sessions for alice@company.com" in result.stdout
        live = cli_session.execute(
            select(AuthSession).where(
                AuthSession.user_id == "u_alice", AuthSession.revoked_at.is_(None)
            )
        ).scalars().all()
        assert live == []

    def test_no_sessions_still_succeeds(
        self, cli_runner, company_mode, cli_engine, cli_session
    ):
        alice = User(
            id="u_alice",
            email="alice@company.com",
            display_name="Alice",
            password_hash="h",
            is_admin=False,
            is_disabled=False,
        )
        cli_session.add(alice)
        cli_session.commit()
        result = cli_runner.invoke(app, ["admin", "revoke-sessions", "alice@company.com"])
        assert result.exit_code == 0
        assert "Revoked 0 sessions" in result.stdout

    def test_user_not_found_exits_2(self, cli_runner, company_mode, cli_engine):
        result = cli_runner.invoke(app, ["admin", "revoke-sessions", "ghost@company.com"])
        assert result.exit_code == 2
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest packages/server/tests/test_cli/test_cli_admin_users.py::TestRevokeSessions -v`
Expected: no such command.

- [ ] **Step 3: Implement**

Add to `cli.py` (after `admin_enable_user`):

```python
@admin_app.command("revoke-sessions")
def admin_revoke_sessions(
    ctx: typer.Context,
    email: str = typer.Argument(..., help="Email of the user to revoke sessions for."),
) -> None:
    """Revoke all active sessions for a user."""
    from openlia_server._cli_support import exit_not_found

    db = build_session(ctx.obj["db_url"])
    try:
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is None:
            exit_not_found("user", email)
        live_count = db.execute(
            select(AuthSession).where(
                AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)
            )
        ).scalars().all()
        sessions_service.revoke_all_sessions(db, user_id=user.id)
        log_cli_event(
            db,
            event_type="session_revoked",
            user_id=user.id,
            metadata={"count": len(live_count)},
        )
        typer.echo(f"Revoked {len(live_count)} sessions for {email}.")
    finally:
        db.close()
```

- [ ] **Step 4: Run the tests to confirm they pass**

Run: `uv run pytest packages/server/tests/test_cli/test_cli_admin_users.py::TestRevokeSessions -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/cli.py \
        packages/server/tests/test_cli/test_cli_admin_users.py
git commit -m "phase-7(cli): admin revoke-sessions bulk-invalidates user sessions"
```

---

## Task 9: `admin create-invite`

**Files:**
- Modify: `packages/server/src/openlia_server/cli.py`
- Create: `packages/server/tests/test_cli/test_cli_admin_invites.py`

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_cli/test_cli_admin_invites.py`:

```python
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from openlia_server.cli import app
from openlia_server.db.models.auth import SignupInvite


class TestCreateInvite:
    def test_defaults(self, cli_runner, company_mode, cli_engine, cli_session):
        result = cli_runner.invoke(app, ["admin", "create-invite"])
        assert result.exit_code == 0, result.output
        out = result.stdout
        assert "Invite created." in out
        assert "URL:" in out
        assert "Expires:  --" in out or "Expires:  none" in out
        row = cli_session.execute(select(SignupInvite)).scalar_one()
        assert row.expires_at is None
        assert row.max_uses is None
        assert row.label is None
        assert row.token in out

    def test_with_label_max_uses_and_expires(
        self, cli_runner, company_mode, cli_engine, cli_session
    ):
        result = cli_runner.invoke(
            app,
            [
                "admin", "create-invite",
                "--label", "Engineering team",
                "--max-uses", "10",
                "--expires", "7d",
            ],
        )
        assert result.exit_code == 0, result.output
        assert "Label:    Engineering team" in result.stdout
        assert "Max uses: 10" in result.stdout
        row = cli_session.execute(select(SignupInvite)).scalar_one()
        assert row.label == "Engineering team"
        assert row.max_uses == 10
        assert row.expires_at is not None
        delta = row.expires_at - datetime.now(timezone.utc)
        # Allow 60s of test jitter
        assert timedelta(days=7) - timedelta(seconds=60) <= delta <= timedelta(days=7) + timedelta(seconds=60)

    def test_invalid_duration_exits_1(
        self, cli_runner, company_mode, cli_engine
    ):
        result = cli_runner.invoke(
            app, ["admin", "create-invite", "--expires", "not-a-duration"]
        )
        assert result.exit_code == 1
        assert "Invalid duration" in result.stderr
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest packages/server/tests/test_cli/test_cli_admin_invites.py::TestCreateInvite -v`
Expected: no such command.

- [ ] **Step 3: Implement `admin create-invite`**

Add to `cli.py` (after `admin_revoke_sessions`):

```python
import uuid  # noqa: E402

from openlia_server.db.models.auth import SignupInvite  # noqa: E402
from openlia_server.services.auth import tokens as tokens_service  # noqa: E402
from openlia_server._cli_support import parse_duration, echo_error  # noqa: E402


@admin_app.command("create-invite")
def admin_create_invite(
    ctx: typer.Context,
    label: str | None = typer.Option(None, "--label", help="Human-readable label."),
    max_uses: int | None = typer.Option(
        None, "--max-uses", min=1, help="Maximum registrations with this invite."
    ),
    expires: str | None = typer.Option(
        None, "--expires", help="Expiry duration (e.g. 7d, 24h, 30m, 2w). None = no expiry."
    ),
) -> None:
    """Create a signup invite and print the URL + metadata."""
    expires_at = None
    if expires is not None:
        try:
            expires_at = datetime.now(timezone.utc) + parse_duration(expires)
        except ValueError as exc:
            echo_error(str(exc))
            raise typer.Exit(code=1) from exc

    db = build_session(ctx.obj["db_url"])
    try:
        invite = SignupInvite(
            id=str(uuid.uuid4()),
            token=tokens_service.generate_opaque_token(),
            label=label,
            max_uses=max_uses,
            use_count=0,
            expires_at=expires_at,
        )
        db.add(invite)
        db.flush()
        log_cli_event(
            db,
            event_type="invite_created",
            metadata={"invite_id": invite.id, "max_uses": max_uses, "label": label},
        )
        db.commit()
        base_url = os.environ.get("OPENLIA_PUBLIC_URL", "http://localhost:8000")
        typer.echo("Invite created.")
        typer.echo(f"URL:      {base_url}/register?invite={invite.token}")
        typer.echo(f"Label:    {label or '--'}")
        typer.echo(f"Max uses: {max_uses if max_uses is not None else 'unlimited'}")
        typer.echo(
            f"Expires:  {expires_at.strftime('%Y-%m-%d') if expires_at else '--'}"
        )
    finally:
        db.close()
```

- [ ] **Step 4: Run the tests to confirm they pass**

Run: `uv run pytest packages/server/tests/test_cli/test_cli_admin_invites.py::TestCreateInvite -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/cli.py \
        packages/server/tests/test_cli/test_cli_admin_invites.py
git commit -m "phase-7(cli): admin create-invite with duration parsing + audit"
```

---

## Task 10: `admin list-invites` + `admin revoke-invite`

**Files:**
- Modify: `packages/server/src/openlia_server/cli.py`
- Modify: `packages/server/tests/test_cli/test_cli_admin_invites.py`

- [ ] **Step 1: Write the failing tests**

Append to `packages/server/tests/test_cli/test_cli_admin_invites.py`:

```python
class TestListInvites:
    def test_groups_active_expired_revoked_exhausted(
        self, cli_runner, company_mode, cli_engine, cli_session
    ):
        now = datetime.now(timezone.utc)
        active = SignupInvite(
            id="inv_1", token="abc123def456abcdef", label="Engineering",
            max_uses=10, use_count=3, expires_at=now + timedelta(days=6),
        )
        exhausted = SignupInvite(
            id="inv_2", token="mno345pqr678abcdef", label=None,
            max_uses=1, use_count=1,
            expires_at=None,
        )
        expired = SignupInvite(
            id="inv_3", token="xyz789abc012abcdef", label="old",
            max_uses=None, use_count=2, expires_at=now - timedelta(days=1),
        )
        revoked = SignupInvite(
            id="inv_4", token="rev000000000abcdef", label="gone",
            max_uses=None, use_count=0, expires_at=None, revoked_at=now,
        )
        cli_session.add_all([active, exhausted, expired, revoked])
        cli_session.commit()

        result = cli_runner.invoke(app, ["admin", "list-invites"])
        assert result.exit_code == 0, result.output
        out = result.stdout

        def row_for(prefix: str) -> str:
            return next(line for line in out.splitlines() if line.startswith(prefix))

        assert "abc123def456" in out
        assert "mno345pqr678" in out
        assert "xyz789abc012" in out
        assert "rev000000000" in out

        # Only the first 12 chars of the token are shown.
        assert "abc123def456abcdef" not in out
        assert "3/10" in row_for("abc123def456")
        assert "1/1" in row_for("mno345pqr678")
        assert "unlimited" in row_for("xyz789abc012")
        assert "active" in row_for("abc123def456")
        assert "exhausted" in row_for("mno345pqr678")
        assert "expired" in row_for("xyz789abc012")
        assert "revoked" in row_for("rev000000000")


class TestRevokeInvite:
    def test_by_full_token(self, cli_runner, company_mode, cli_engine, cli_session):
        invite = SignupInvite(
            id="inv_x", token="abc123def456fullxyz", label="Q2",
            max_uses=None, use_count=0,
        )
        cli_session.add(invite)
        cli_session.commit()
        result = cli_runner.invoke(app, ["admin", "revoke-invite", invite.token])
        assert result.exit_code == 0
        assert "Invite revoked" in result.stdout
        cli_session.expire_all()
        assert cli_session.get(SignupInvite, "inv_x").revoked_at is not None

    def test_by_prefix(self, cli_runner, company_mode, cli_engine, cli_session):
        invite = SignupInvite(
            id="inv_p", token="abc123def456fullxyz", label="Q3",
            max_uses=None, use_count=0,
        )
        cli_session.add(invite)
        cli_session.commit()
        result = cli_runner.invoke(app, ["admin", "revoke-invite", "abc123def456"])
        assert result.exit_code == 0
        cli_session.expire_all()
        assert cli_session.get(SignupInvite, "inv_p").revoked_at is not None

    def test_not_found_exits_2(self, cli_runner, company_mode, cli_engine):
        result = cli_runner.invoke(app, ["admin", "revoke-invite", "doesnotexist"])
        assert result.exit_code == 2

    def test_ambiguous_prefix_exits_1(
        self, cli_runner, company_mode, cli_engine, cli_session
    ):
        cli_session.add_all(
            [
                SignupInvite(
                    id="inv_a", token="samepref_aaaaaaaaa", label=None,
                    max_uses=None, use_count=0,
                ),
                SignupInvite(
                    id="inv_b", token="samepref_bbbbbbbbb", label=None,
                    max_uses=None, use_count=0,
                ),
            ]
        )
        cli_session.commit()
        result = cli_runner.invoke(app, ["admin", "revoke-invite", "samepref"])
        assert result.exit_code == 1
        assert "multiple" in result.stderr.lower()
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest packages/server/tests/test_cli/test_cli_admin_invites.py -v`
Expected: list-invites / revoke-invite missing.

- [ ] **Step 3: Implement both commands**

Add to `cli.py` (after `admin_create_invite`):

```python
def _invite_status(invite: SignupInvite, *, now: datetime) -> str:
    if invite.revoked_at is not None:
        return "revoked"
    if invite.expires_at is not None and invite.expires_at < now:
        return "expired"
    if invite.max_uses is not None and invite.use_count >= invite.max_uses:
        return "exhausted"
    return "active"


@admin_app.command("list-invites")
def admin_list_invites(ctx: typer.Context) -> None:
    """List every invite with usage stats and status."""
    db = build_session(ctx.obj["db_url"])
    try:
        now = datetime.now(timezone.utc)
        rows = []
        invites = db.execute(
            select(SignupInvite).order_by(SignupInvite.created_at.desc())
        ).scalars().all()
        for inv in invites:
            uses = (
                f"{inv.use_count}/{inv.max_uses}"
                if inv.max_uses is not None
                else f"{inv.use_count}/unlimited"
            )
            rows.append(
                [
                    inv.token[:12],
                    inv.label or "--",
                    uses,
                    inv.created_at.strftime("%Y-%m-%d"),
                    inv.expires_at.strftime("%Y-%m-%d") if inv.expires_at else "--",
                    _invite_status(inv, now=now),
                ]
            )
        typer.echo(
            format_table(
                headers=["Token", "Label", "Uses", "Created", "Expires", "Status"],
                rows=rows,
            )
        )
    finally:
        db.close()


@admin_app.command("revoke-invite")
def admin_revoke_invite(
    ctx: typer.Context,
    token: str = typer.Argument(..., help="Full token or 12-char prefix."),
) -> None:
    """Revoke an invite by full token or first 12-char prefix."""
    from openlia_server._cli_support import exit_not_found

    db = build_session(ctx.obj["db_url"])
    try:
        candidates = db.execute(
            select(SignupInvite).where(SignupInvite.token.like(f"{token}%"))
        ).scalars().all()
        if not candidates:
            exit_not_found("invite", token)
        if len(candidates) > 1:
            echo_error(
                f"prefix {token!r} matches multiple invites "
                f"({len(candidates)}). Use the full token."
            )
            raise typer.Exit(code=1)
        invite = candidates[0]
        if invite.revoked_at is None:
            invite.revoked_at = datetime.now(timezone.utc)
            log_cli_event(
                db,
                event_type="invite_revoked",
                metadata={"invite_id": invite.id},
            )
            db.commit()
        typer.echo(f"Invite revoked: {invite.token[:12]}...")
    finally:
        db.close()
```

- [ ] **Step 4: Run the tests to confirm they pass**

Run: `uv run pytest packages/server/tests/test_cli/test_cli_admin_invites.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/cli.py \
        packages/server/tests/test_cli/test_cli_admin_invites.py
git commit -m "phase-7(cli): admin list-invites + revoke-invite with prefix matching"
```

---

## Task 11: `wizard reset`

**Files:**
- Modify: `packages/server/src/openlia_server/cli.py`
- Create: `packages/server/tests/test_cli/test_cli_wizard.py`

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_cli/test_cli_wizard.py`:

```python
from __future__ import annotations

from sqlalchemy import select

from openlia_server.cli import app
from openlia_server.db.models.infrastructure import ConfigStore, WizardState


class TestWizardReset:
    def test_yes_flag_skips_confirmation(
        self, cli_runner, cli_engine, cli_session
    ):
        cli_session.add(
            WizardState(id=1, status="completed", current_step=8, mode="personal")
        )
        cli_session.add(ConfigStore(key="wizard.completed", value=True))
        cli_session.commit()

        result = cli_runner.invoke(app, ["wizard", "reset", "--yes"])
        assert result.exit_code == 0, result.output
        assert "Wizard state reset" in result.stdout

        cli_session.expire_all()
        state = cli_session.execute(select(WizardState)).scalar_one()
        assert state.status == "not_started"
        assert state.current_step == 1
        wc = cli_session.execute(
            select(ConfigStore).where(ConfigStore.key == "wizard.completed")
        ).scalar_one()
        assert wc.value is False

    def test_interactive_yes(
        self, cli_runner, cli_engine, cli_session
    ):
        cli_session.add(
            WizardState(id=1, status="completed", current_step=8, mode="company")
        )
        cli_session.commit()

        result = cli_runner.invoke(app, ["wizard", "reset"], input="y\n")
        assert result.exit_code == 0, result.output
        cli_session.expire_all()
        assert cli_session.execute(select(WizardState)).scalar_one().status == "not_started"

    def test_interactive_abort(self, cli_runner, cli_engine, cli_session):
        cli_session.add(
            WizardState(id=1, status="completed", current_step=8, mode="company")
        )
        cli_session.commit()

        result = cli_runner.invoke(app, ["wizard", "reset"], input="n\n")
        assert result.exit_code == 1
        cli_session.expire_all()
        # Aborted — row stays completed
        assert cli_session.execute(select(WizardState)).scalar_one().status == "completed"

    def test_works_without_existing_wizard_row(
        self, cli_runner, cli_engine, cli_session
    ):
        """Fresh install: wizard_state hasn't been touched yet. Reset should
        still create a row in `not_started` state."""
        assert cli_session.execute(select(WizardState)).scalar_one_or_none() is None
        result = cli_runner.invoke(app, ["wizard", "reset", "--yes"])
        assert result.exit_code == 0
        cli_session.expire_all()
        state = cli_session.execute(select(WizardState)).scalar_one()
        assert state.status == "not_started"
        assert state.current_step == 1
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest packages/server/tests/test_cli/test_cli_wizard.py -v`
Expected: no such command.

- [ ] **Step 3: Implement the wizard sub-app**

Add to `cli.py` (after the admin block, before `main`):

```python
from openlia_server.db.models.infrastructure import WizardState  # noqa: E402

wizard_app = typer.Typer(
    name="wizard",
    help="Setup-wizard operations.",
    no_args_is_help=True,
)


@wizard_app.command("reset")
def wizard_reset(
    ctx: typer.Context,
    yes: bool = typer.Option(False, "--yes", help="Skip the confirmation prompt."),
) -> None:
    """Reset the setup wizard to run from step 1 on next visit. API keys,
    providers, and user accounts are preserved."""
    if not yes:
        confirmed = typer.confirm(
            "This will reset the setup wizard. Existing configuration "
            "(API keys, providers, user accounts) is preserved — only the "
            "wizard completion flag is cleared. Continue?",
            default=False,
        )
        if not confirmed:
            raise typer.Exit(code=1)

    db = build_session(ctx.obj["db_url"])
    try:
        state = db.execute(select(WizardState)).scalar_one_or_none()
        now = datetime.now(timezone.utc)
        if state is None:
            db.add(
                WizardState(
                    id=1,
                    status="not_started",
                    current_step=1,
                    mode=None,
                    step_data={},
                )
            )
        else:
            state.status = "not_started"
            state.current_step = 1
            state.completed_at = None
            state.started_at = None
            state.updated_at = now
        # Flip the KV mirror used by the frontend guard.
        wc = db.execute(
            select(ConfigStore).where(ConfigStore.key == "wizard.completed")
        ).scalar_one_or_none()
        if wc is None:
            db.add(ConfigStore(key="wizard.completed", value=False))
        else:
            wc.value = False
        db.commit()
        typer.echo("Wizard state reset. The setup wizard will run on next visit.")
    finally:
        db.close()


app.add_typer(wizard_app, name="wizard")
```

- [ ] **Step 4: Run the tests to confirm they pass**

Run: `uv run pytest packages/server/tests/test_cli/test_cli_wizard.py -v`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/cli.py \
        packages/server/tests/test_cli/test_cli_wizard.py
git commit -m "phase-7(cli): wizard reset — re-run setup from step 1"
```

---

## Task 12: `crypto.encrypt_with_key` / `decrypt_with_key`

**Files:**
- Modify: `packages/server/src/openlia_server/db/crypto.py`
- Create: `packages/server/tests/test_cli/test_cli_crypto_rotation.py`

Add two keyed helpers that bypass the module-level cache. The existing `encrypt_for_row` / `decrypt_for_row` call `load_secret_key()` internally; that won't work for rotation because old and new keys must coexist inside one transaction. These variants take the key as an argument.

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_cli/test_cli_crypto_rotation.py`:

```python
from __future__ import annotations

import pytest

from openlia_server.db import crypto


class TestEncryptDecryptWithKey:
    def test_roundtrip(self) -> None:
        key = b"\x00" * 32
        ciphertext = crypto.encrypt_with_key(key, "row-1", "hello")
        assert crypto.decrypt_with_key(key, "row-1", ciphertext) == "hello"

    def test_different_keys_do_not_decrypt(self) -> None:
        key_a = b"\x00" * 32
        key_b = b"\xff" * 32
        ciphertext = crypto.encrypt_with_key(key_a, "row-1", "hello")
        with pytest.raises(crypto.DecryptError):
            crypto.decrypt_with_key(key_b, "row-1", ciphertext)

    def test_aad_binds_to_row_id(self) -> None:
        key = b"\x00" * 32
        ciphertext = crypto.encrypt_with_key(key, "correct-row", "hello")
        with pytest.raises(crypto.DecryptError):
            crypto.decrypt_with_key(key, "other-row", ciphertext)

    def test_fresh_nonce_each_call(self) -> None:
        key = b"\x00" * 32
        a = crypto.encrypt_with_key(key, "row", "same")
        b = crypto.encrypt_with_key(key, "row", "same")
        assert a != b

    def test_rejects_non_32_byte_key(self) -> None:
        short_key = b"\x00" * 16
        with pytest.raises(crypto.SecretKeyError):
            crypto.encrypt_with_key(short_key, "row", "hello")
        with pytest.raises(crypto.SecretKeyError):
            crypto.decrypt_with_key(short_key, "row", "ignored")
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest packages/server/tests/test_cli/test_cli_crypto_rotation.py -v`
Expected: `AttributeError: encrypt_with_key`.

- [ ] **Step 3: Implement**

Open `packages/server/src/openlia_server/db/crypto.py` and append:

```python
def _validate_key(key: bytes) -> None:
    if len(key) != KEY_LENGTH_BYTES:
        raise SecretKeyError(
            f"key must be exactly {KEY_LENGTH_BYTES} bytes, got {len(key)}"
        )


def encrypt_with_key(key: bytes, row_id: str, plaintext: str) -> str:
    """AES-256-GCM encrypt with an explicit key. Bypasses the module cache
    so old/new keys can coexist during rotation. Returns base64-encoded
    (nonce || ciphertext || tag)."""
    _validate_key(key)
    nonce = secrets.token_bytes(NONCE_LENGTH_BYTES)
    aead = AESGCM(key)
    blob = aead.encrypt(nonce, plaintext.encode("utf-8"), row_id.encode("utf-8"))
    return base64.b64encode(nonce + blob).decode("ascii")


def decrypt_with_key(key: bytes, row_id: str, token: str) -> str:
    """AES-256-GCM decrypt with an explicit key. Counterpart of
    encrypt_with_key. Raises DecryptError on any failure (bad key, tampered
    ciphertext, wrong row_id AAD)."""
    _validate_key(key)
    try:
        raw = base64.b64decode(token, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise DecryptError("invalid base64") from exc
    if len(raw) < NONCE_LENGTH_BYTES + 16:
        raise DecryptError("ciphertext too short")
    nonce, blob = raw[:NONCE_LENGTH_BYTES], raw[NONCE_LENGTH_BYTES:]
    aead = AESGCM(key)
    try:
        plaintext = aead.decrypt(nonce, blob, row_id.encode("utf-8"))
    except Exception as exc:  # cryptography raises InvalidTag
        raise DecryptError("decryption failed") from exc
    return plaintext.decode("utf-8")
```

If `DecryptError` doesn't exist yet (Plan 2 Task 3 is expected to define it), add:

```python
class DecryptError(RuntimeError):
    """Raised when ciphertext fails to decrypt — bad key, tampered blob, or
    wrong row-id AAD."""
```

Only add the class if grep confirms it's missing. Run:

```bash
grep -n "class DecryptError" packages/server/src/openlia_server/db/crypto.py
```

Expected: one hit (Plan 2 already defined it). If zero hits, add the class right above `encrypt_for_row`.

- [ ] **Step 4: Run the tests to confirm they pass**

Run: `uv run pytest packages/server/tests/test_cli/test_cli_crypto_rotation.py -v`
Expected: 5 passed. Re-run the Plan 2 crypto suite to make sure nothing regressed: `uv run pytest packages/server/tests/test_db/test_crypto.py -v`.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/db/crypto.py \
        packages/server/tests/test_cli/test_cli_crypto_rotation.py
git commit -m "phase-7(crypto): encrypt_with_key/decrypt_with_key for key rotation"
```

---

## Task 13: `secrets rotate-key`

**Files:**
- Modify: `packages/server/src/openlia_server/cli.py`
- Create: `packages/server/tests/test_cli/test_cli_secrets.py`

Walks every `api_key_encrypted` column (`llm_providers`, `data_providers`, `web_search_providers`), decrypts with the old key, re-encrypts with the new key, all under one exclusive transaction. If `secret.key` exists on disk, rewrite it; otherwise print the new base64-encoded key for the env-var path.

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_cli/test_cli_secrets.py`:

```python
from __future__ import annotations

import base64
import os

import pytest
from sqlalchemy import select

from openlia_server.cli import app
from openlia_server.db import crypto
from openlia_server.db.models.config import (
    DataProvider,
    LLMProvider,
    WebSearchProvider,
)


@pytest.fixture
def seeded_encrypted_rows(cli_session, cli_secret_key):
    """Insert one row per encrypted-column table, encrypted with the old key."""
    old_key = cli_secret_key
    llm = LLMProvider(
        id="llm_1",
        kind="openai",
        label="OpenAI",
        api_key_encrypted=crypto.encrypt_with_key(old_key, "llm_1", "sk-llm-secret"),
    )
    data = DataProvider(
        id="data_1",
        kind="eodhd",
        label="EODHD",
        api_key_encrypted=crypto.encrypt_with_key(old_key, "data_1", "eodhd-secret"),
    )
    ws = WebSearchProvider(
        id="ws_1",
        kind="brave",
        label="Brave",
        api_key_encrypted=crypto.encrypt_with_key(old_key, "ws_1", "brave-secret"),
    )
    cli_session.add_all([llm, data, ws])
    cli_session.commit()
    return {"llm": llm, "data": data, "ws": ws}


class TestRotateKey:
    def test_rotates_using_env_key_path(
        self,
        cli_runner,
        cli_engine,
        cli_secret_key,
        cli_home,
        seeded_encrypted_rows,
        monkeypatch,
    ):
        # secret.key does NOT exist — install is env-keyed.
        assert not (cli_home / "secret.key").exists()

        new_key = b"\x33" * 32
        new_key_b64 = base64.b64encode(new_key).decode()

        # Provide --new-key explicitly so the test is deterministic.
        result = cli_runner.invoke(
            app, ["secrets", "rotate-key", "--new-key", new_key_b64]
        )
        assert result.exit_code == 0, result.output
        assert "3 values re-encrypted" in result.stdout
        assert "Update your OPENLIA_SECRET_KEY" in result.stdout
        assert new_key_b64 in result.stdout
        # secret.key not written in env-keyed mode
        assert not (cli_home / "secret.key").exists()

        # Every row now decrypts with the NEW key.
        from openlia_server.db.models.config import (
            LLMProvider as Llm, DataProvider as Data, WebSearchProvider as Ws,
        )
        with cli_engine.connect() as c:
            # Use a fresh session bound to the same engine
            pass
        # Simplest — query through the existing cli_session factory.
        from openlia_server.db.session import SessionLocal
        s = SessionLocal()
        try:
            llm = s.execute(select(Llm)).scalar_one()
            data = s.execute(select(Data)).scalar_one()
            ws = s.execute(select(Ws)).scalar_one()
            assert crypto.decrypt_with_key(new_key, "llm_1", llm.api_key_encrypted) == "sk-llm-secret"
            assert crypto.decrypt_with_key(new_key, "data_1", data.api_key_encrypted) == "eodhd-secret"
            assert crypto.decrypt_with_key(new_key, "ws_1", ws.api_key_encrypted) == "brave-secret"
        finally:
            s.close()

    def test_rotates_using_file_key_path(
        self,
        cli_runner,
        cli_engine,
        cli_home,
        seeded_encrypted_rows,
        monkeypatch,
    ):
        # Ensure env-key is unset and seed the file-based key.
        monkeypatch.delenv("OPENLIA_SECRET_KEY", raising=False)
        old_key = b"\x22" * 32
        key_file = cli_home / "secret.key"
        key_file.write_bytes(base64.b64encode(old_key))
        key_file.chmod(0o600)
        # Re-encrypt the seeded rows with the file key (fixture used env key).
        from openlia_server.db.session import SessionLocal
        from openlia_server.db.models.config import (
            LLMProvider as Llm, DataProvider as Data, WebSearchProvider as Ws,
        )
        s = SessionLocal()
        try:
            for row_id_attr, Model, plaintext in [
                ("llm_1", Llm, "sk-llm-secret"),
                ("data_1", Data, "eodhd-secret"),
                ("ws_1", Ws, "brave-secret"),
            ]:
                row = s.get(Model, row_id_attr)
                row.api_key_encrypted = crypto.encrypt_with_key(
                    old_key, row_id_attr, plaintext
                )
            s.commit()
        finally:
            s.close()
        crypto._reset_cached_key()

        new_key = b"\x44" * 32
        new_key_b64 = base64.b64encode(new_key).decode()
        result = cli_runner.invoke(
            app, ["secrets", "rotate-key", "--new-key", new_key_b64]
        )
        assert result.exit_code == 0, result.output
        assert "3 values re-encrypted" in result.stdout
        assert "New key written to" in result.stdout
        # File was rewritten and still 0600
        assert key_file.exists()
        assert oct(key_file.stat().st_mode & 0o777) == "0o600"
        new_on_disk = base64.b64decode(key_file.read_bytes(), validate=True)
        assert new_on_disk == new_key

    def test_refuses_if_database_locked(
        self, cli_runner, cli_engine, cli_secret_key, seeded_encrypted_rows, monkeypatch
    ):
        """Simulate the server holding a write lock by opening a long-running
        BEGIN IMMEDIATE on a second connection."""
        import sqlite3

        # Extract the DB file path from the engine URL.
        engine = cli_engine
        db_path = engine.url.database
        assert db_path is not None
        holder = sqlite3.connect(db_path, isolation_level=None)
        holder.execute("BEGIN IMMEDIATE")

        new_key_b64 = base64.b64encode(b"\x55" * 32).decode()
        result = cli_runner.invoke(
            app, ["secrets", "rotate-key", "--new-key", new_key_b64]
        )
        holder.close()

        assert result.exit_code == 1
        assert "stop the server before rotating keys" in result.stderr

    def test_invalid_new_key_exits_1(
        self, cli_runner, cli_engine, cli_secret_key, seeded_encrypted_rows
    ):
        result = cli_runner.invoke(
            app, ["secrets", "rotate-key", "--new-key", "not-valid-base64!"]
        )
        assert result.exit_code == 1
        assert "OPENLIA_SECRET_KEY" in result.stderr or "new key" in result.stderr.lower()

    def test_no_encrypted_rows_reports_zero(
        self,
        cli_runner,
        cli_engine,
        cli_secret_key,
        cli_home,
    ):
        # No providers seeded — rotation should still succeed trivially.
        new_key_b64 = base64.b64encode(b"\x66" * 32).decode()
        result = cli_runner.invoke(
            app, ["secrets", "rotate-key", "--new-key", new_key_b64]
        )
        assert result.exit_code == 0
        assert "0 values re-encrypted" in result.stdout
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest packages/server/tests/test_cli/test_cli_secrets.py -v`
Expected: `No such command 'secrets'`.

- [ ] **Step 3: Implement the `secrets` sub-app**

Add to `cli.py` (after the wizard block):

```python
import base64  # noqa: E402
import secrets as secrets_module  # noqa: E402

from sqlalchemy.exc import OperationalError  # noqa: E402

from openlia_server.db.models.config import (  # noqa: E402
    DataProvider,
    LLMProvider,
    WebSearchProvider,
)
from openlia_server.db import crypto as crypto_module  # noqa: E402
from openlia_server.db.bootstrap import openlia_home  # noqa: E402

secrets_app = typer.Typer(
    name="secrets",
    help="Manage encryption keys for stored provider API keys.",
    no_args_is_help=True,
)


def _decode_new_key(raw: str) -> bytes:
    try:
        key = base64.b64decode(raw, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise typer.BadParameter(
            "--new-key must be valid base64 decoding to 32 bytes.",
        ) from exc
    if len(key) != crypto_module.KEY_LENGTH_BYTES:
        raise typer.BadParameter(
            f"--new-key must decode to exactly {crypto_module.KEY_LENGTH_BYTES} bytes "
            f"(got {len(key)})."
        )
    return key


@secrets_app.command("rotate-key")
def secrets_rotate_key(
    ctx: typer.Context,
    new_key: str | None = typer.Option(
        None,
        "--new-key",
        help="Base64-encoded 32-byte key. Omit to generate a random one.",
    ),
) -> None:
    """Re-encrypt every stored API key with a new AES-256-GCM key.

    All-or-nothing: if any row fails to decrypt with the old key or fails to
    re-encrypt, the transaction rolls back and the key file is not rewritten.
    Refuses to run if the database is currently locked by another process.
    """
    try:
        old_key = crypto_module.load_secret_key()
    except crypto_module.SecretKeyError as exc:
        echo_error(str(exc))
        raise typer.Exit(code=1) from exc

    try:
        new_key_bytes = (
            _decode_new_key(new_key)
            if new_key is not None
            else secrets_module.token_bytes(crypto_module.KEY_LENGTH_BYTES)
        )
    except typer.BadParameter as exc:
        echo_error(str(exc))
        raise typer.Exit(code=1) from exc

    if new_key_bytes == old_key:
        echo_error("new key must differ from the current key.")
        raise typer.Exit(code=1)

    db = build_session(ctx.obj["db_url"])
    try:
        try:
            db.execute(__import__("sqlalchemy").text("BEGIN EXCLUSIVE"))
        except OperationalError as exc:
            if "locked" in str(exc).lower():
                echo_error("stop the server before rotating keys.")
                db.rollback()
                raise typer.Exit(code=1) from exc
            raise

        total = 0
        for model, pk_attr in (
            (LLMProvider, "id"),
            (DataProvider, "id"),
            (WebSearchProvider, "id"),
        ):
            rows = db.execute(
                select(model).where(model.api_key_encrypted.is_not(None))
            ).scalars().all()
            for row in rows:
                row_id = getattr(row, pk_attr)
                plaintext = crypto_module.decrypt_with_key(
                    old_key, row_id, row.api_key_encrypted
                )
                row.api_key_encrypted = crypto_module.encrypt_with_key(
                    new_key_bytes, row_id, plaintext
                )
                total += 1
        db.commit()
    except crypto_module.DecryptError as exc:
        db.rollback()
        echo_error(f"failed to decrypt an existing row with the current key: {exc}")
        raise typer.Exit(code=1) from exc
    finally:
        db.close()

    key_file = openlia_home() / crypto_module.KEY_FILE_NAME
    new_key_b64 = base64.b64encode(new_key_bytes).decode("ascii")
    typer.echo(f"Rotated encryption key. {total} values re-encrypted.")
    if key_file.exists():
        key_file.write_bytes(base64.b64encode(new_key_bytes))
        key_file.chmod(crypto_module.KEY_FILE_MODE)
        typer.echo(f"New key written to {key_file}")
    else:
        typer.echo("Update your OPENLIA_SECRET_KEY env var to: " + new_key_b64)

    # Force the next `load_secret_key()` call (same process, e.g. tests) to
    # re-read from env/file so it observes the new key.
    crypto_module._reset_cached_key()


app.add_typer(secrets_app, name="secrets")
```

- [ ] **Step 4: Run the tests to confirm they pass**

Run: `uv run pytest packages/server/tests/test_cli/test_cli_secrets.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/cli.py \
        packages/server/tests/test_cli/test_cli_secrets.py
git commit -m "phase-7(cli): secrets rotate-key re-encrypts under exclusive DB lock"
```

---

## Task 14: `maintenance` — real run + `--dry-run`

**Files:**
- Modify: `packages/server/src/openlia_server/cli.py`
- Create: `packages/server/tests/test_cli/test_cli_maintenance.py`

Reuses Plan 6's `run_maintenance_once(session)`. Dry-run runs the sweep then rolls back, so no rows are actually deleted.

- [ ] **Step 1: Write the failing test**

Create `packages/server/tests/test_cli/test_cli_maintenance.py`:

```python
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from openlia_server.cli import app
from openlia_server.db.models.auth import Session as AuthSession, User


@pytest.fixture
def expired_sessions(cli_session):
    now = datetime.now(timezone.utc)
    user = User(
        id="u_1",
        email="u@e.com",
        display_name="u",
        password_hash="h",
        is_admin=False,
        is_disabled=False,
    )
    cli_session.add(user)
    cli_session.flush()
    for i in range(3):
        cli_session.add(
            AuthSession(
                id=f"s_{i}",
                user_id="u_1",
                token_hash=f"h_{i}",
                last_seen_at=now - timedelta(days=20),
                expires_at=now - timedelta(days=15),  # > 7d past expiry
            )
        )
    # One fresh session that should survive the sweep
    cli_session.add(
        AuthSession(
            id="s_fresh",
            user_id="u_1",
            token_hash="h_fresh",
            last_seen_at=now,
            expires_at=now + timedelta(days=1),
        )
    )
    cli_session.commit()


class TestMaintenance:
    def test_real_run_deletes_expired(
        self, cli_runner, cli_engine, cli_session, expired_sessions
    ):
        result = cli_runner.invoke(app, ["maintenance"])
        assert result.exit_code == 0, result.output
        assert "sessions:" in result.stdout
        assert "deleted 3 expired rows" in result.stdout
        cli_session.expire_all()
        remaining = cli_session.execute(select(AuthSession)).scalars().all()
        assert {s.id for s in remaining} == {"s_fresh"}

    def test_dry_run_does_not_delete(
        self, cli_runner, cli_engine, cli_session, expired_sessions
    ):
        result = cli_runner.invoke(app, ["maintenance", "--dry-run"])
        assert result.exit_code == 0, result.output
        # Every line prefixed
        for line in [
            l for l in result.stdout.splitlines() if l.strip()
        ]:
            assert line.startswith("[dry-run]")
        cli_session.expire_all()
        remaining = cli_session.execute(select(AuthSession)).scalars().all()
        assert len(remaining) == 4  # nothing deleted

    def test_fresh_database_reports_all_zeros(
        self, cli_runner, cli_engine
    ):
        result = cli_runner.invoke(app, ["maintenance"])
        assert result.exit_code == 0
        assert "deleted 0" in result.stdout or "0 expired" in result.stdout
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest packages/server/tests/test_cli/test_cli_maintenance.py -v`
Expected: no such command.

- [ ] **Step 3: Implement `maintenance`**

Add to `cli.py` (after the secrets block, before `main`):

```python
from openlia_server.scheduler.executors.maintenance import run_maintenance_once  # noqa: E402


@app.command()
def maintenance(
    ctx: typer.Context,
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Print what would be pruned without deleting."
    ),
) -> None:
    """Run the nightly pruning sweep manually (sessions, reset requests,
    MR cache, RS snapshots, notifications, job_runs)."""
    db = build_session(ctx.obj["db_url"])
    try:
        counts = run_maintenance_once(db)
        if dry_run:
            db.rollback()
        else:
            db.commit()
    finally:
        db.close()

    prefix = "[dry-run] " if dry_run else ""
    lines = [
        ("sessions:", f"deleted {counts['sessions_deleted']} expired rows"),
        (
            "password_reset_requests:",
            f"expired {counts['password_resets_expired']} rows, "
            f"deleted {counts['password_resets_deleted']} old rows",
        ),
        ("mr_assessment_cache:", f"deleted {counts['mr_cache_deleted']} stale rows"),
        ("rs_snapshots:", f"deleted {counts['rs_snapshots_deleted']} old snapshots"),
        ("user_notifications:", f"deleted {counts['notifications_deleted']} old notifications"),
        ("job_runs:", f"deleted {counts['job_runs_deleted']} old completed runs"),
    ]
    width = max(len(label) for label, _ in lines)
    for label, detail in lines:
        typer.echo(f"{prefix}{label.ljust(width)} {detail}")
```

- [ ] **Step 4: Run the tests to confirm they pass**

Run: `uv run pytest packages/server/tests/test_cli/test_cli_maintenance.py -v`
Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/server/src/openlia_server/cli.py \
        packages/server/tests/test_cli/test_cli_maintenance.py
git commit -m "phase-7(cli): maintenance sweeper with --dry-run"
```

---

## Task 15: Acceptance + docs update + roadmap flip

**Files:**
- Modify: `planning/projectStructure.md`
- Modify: `planning/implementation-plans/README.md`

- [ ] **Step 1: Update `projectStructure.md`**

Two small edits. First, update the `cli.py` comment to reference `cli-surface-design.md`:

Open `planning/projectStructure.md` and find the `cli.py` line. Replace its comment with:

```
│           ├── cli.py                  # Typer app: serve, admin, wizard, secrets, maintenance
                                         # (spec: planning/specs/systems/cli-surface-design.md)
```

Second, update the `middleware/auth.py` location (Plan 2 shipped `services/auth/` as a package, not a single file — Plan 2 Task 18 explicitly deferred this doc update to Plan 7 Task 1). Find the `services/` entry and replace with:

```
│           ├── services/
│           │   ├── auth/             # Package: passwords, tokens, sessions,
│           │   │                     # registration, login, password_reset, events,
│           │   │                     # signup_policy
```

- [ ] **Step 2: Run the full acceptance checklist**

```bash
uv run ruff check .
uv run ruff format --check .
uv run pytest -v
```

Manual smoke test list (per spec § Testing Strategy):

1. `openlia --version` → prints `0.1.0`, exit 0.
2. `openlia --help` → lists `serve, admin, wizard, secrets, maintenance`.
3. `OPENLIA_MODE=personal openlia admin list-users` → exit 1, stderr "admin commands require company mode.".
4. `OPENLIA_MODE=company openlia admin list-users` → exit 0, renders table with headers.
5. `openlia admin create-invite --label Q2 --max-uses 5 --expires 7d` → prints URL + metadata, row persisted.
6. `openlia admin list-invites` → shows the Q2 row with status=active.
7. `openlia admin revoke-invite <prefix>` → exit 0, row.revoked_at set.
8. `openlia admin reset-password alice@company.com --password NewStrongP@ss1` → exit 0, user.must_change_password=true, all sessions revoked.
9. `openlia admin lockout disable` → config_store flipped, auth_events row appended.
10. `openlia admin lockout status` → prints "Lockout: disabled".
11. `openlia admin lockout enable` → restores.
12. `openlia wizard reset --yes` → wizard_state.status=not_started, config_store["wizard.completed"]=false.
13. `openlia maintenance --dry-run` → every line prefixed `[dry-run]`, no rows deleted.
14. `openlia maintenance` → deletes expired rows per Plan 6's sweep.
15. Start the server, run `openlia secrets rotate-key` → exit 1, stderr "stop the server before rotating keys.".
16. Stop the server, run `openlia secrets rotate-key` → exit 0, every `api_key_encrypted` now decrypts with the new key.

Acceptance criteria:

1. `uv run ruff check .` passes.
2. `uv run ruff format --check .` passes.
3. `uv run pytest -v` passes (no regressions in Plans 1A/1B/2/3/4/5/6 test suites).
4. Every command in `cli-surface-design.md § Command Tree` is implemented with at least one integration test.
5. `admin` commands exit 1 in personal mode (`OPENLIA_MODE=personal`).
6. User-not-found cases for `admin unlock`, `reset-password`, `disable-user`, `enable-user`, `revoke-sessions` exit 2.
7. `admin reset-password`, `disable-user`, `enable-user`, `revoke-sessions`, `create-invite`, `revoke-invite`, `lockout enable|disable` each emit one `auth_events` row with `actor_user_id=NULL` and `metadata.source="cli"`.
8. `admin unlock` emits no event (v1 omit) — confirm via integration test that query returns 0 rows with `event_type=account_locked`.
9. `secrets rotate-key` refuses to run when `BEGIN EXCLUSIVE` fails with "database is locked" and reports the exact spec message.
10. `maintenance --dry-run` leaves every target table unchanged while real run deletes per Plan 6's counts.
11. `wizard reset` preserves users, providers, invites, and chat history — only `wizard_state` and `config_store["wizard.completed"]` change.
12. `--db-url` overrides `OPENLIA_DB_URL` for any non-`serve` command (tested by passing a fresh temp DB to `list-users` and observing empty output).

- [ ] **Step 3: Mark Plan 7 as Draft in the roadmap**

Edit `planning/implementation-plans/README.md` — update the Plan 7 row to:

```markdown
| 7 | 3 | CLI surface (`admin`, `wizard reset`, `secrets rotate-key`, `maintenance`) | Draft | `2026-04-17-phase-7-cli-surface.md` |
```

- [ ] **Step 4: Commit**

```bash
git add planning/projectStructure.md planning/implementation-plans/README.md
git commit -m "phase-7(cli): mark plan as Draft in roadmap + sync projectStructure"
```

---

## Notes for the implementer

- **`cli.py` is growing large.** At ~700 lines this is still readable because every command is a small, stable, spec-backed unit. Resist the urge to split until Plan 7's commands change shape — the spec locks in what they do, so churn is minimal.

- **Click context propagation.** `ctx.obj` holds `{"db_url": ..., "no_color": ...}`. Every subcommand takes `ctx: typer.Context` as its first parameter. Typer places this after the context binding when it parses CLI args — no special ordering rules.

- **`BEGIN EXCLUSIVE` timing.** SQLite's busy-timeout PRAGMA (5000 ms, set in Plan 1A) will cause the `BEGIN EXCLUSIVE` to block for up to 5 seconds before raising `database is locked`. For the typical case where the server is running that's acceptable; the admin just has to stop the server and retry. If you need an instant fail, drop the busy-timeout temporarily via `PRAGMA busy_timeout = 0` on the same connection before the BEGIN — not required for v1.

- **`OperationalError` message stability.** The "database is locked" string is SQLite's canonical error message and has been stable across versions. If a future SQLite renames it, the `"locked" in str(exc).lower()` check in `secrets rotate-key` is the tripwire.

- **Rich integration is deferred.** Typer auto-installs Rich if available — the tests run without it because `mix_stderr=False` + `CliRunner` don't care. If Rich lands later via another plan, the `format_table` helper can be swapped out without touching command code.

- **Env var for the invite URL base.** `OPENLIA_PUBLIC_URL` is read by `create-invite` to build the invite URL. If unset, it defaults to `http://localhost:8000`. This is documented in the spec as implicit behavior — no new wiring needed.

- **`revoke-sessions` count race.** We count live sessions *before* calling `revoke_all_sessions`. If another process revokes one between the count and the revoke, the printed number will be one too high. Accept this — it's a CLI used by one operator at a time.

- **`admin` commands do not require the user to be an admin.** The CLI has no logged-in user; it's assumed that CLI access == admin access (same model as `sudo`). Mode guard is enough.

- **Ordering in `cli.py`.** Keep the file top-to-bottom: root app + callback, `serve`, admin sub-app + admin commands (list-users, unlock, lockout sub-app, reset-password, disable-user, enable-user, revoke-sessions, create-invite, list-invites, revoke-invite), wizard sub-app + wizard reset, secrets sub-app + rotate-key, top-level maintenance, `main`. Import blocks are inline at the point of use to keep each command's dependencies local and minimize top-of-file reshuffling across tasks.

## Execution handoff

Plan complete and saved to `planning/implementation-plans/2026-04-17-phase-7-cli-surface.md`.

Two execution options:

1. **Subagent-Driven (recommended)** — fresh subagent per task, two-stage review after each, fast iteration. Use `superpowers:subagent-driven-development`.
2. **Inline Execution** — batch the tasks through `superpowers:executing-plans` with checkpoints for review.

Pause to choose when ready to execute.
