"""Typer CLI entry point. Registered as the `openlia` console script."""

from __future__ import annotations

import os
import socket
import subprocess
import uuid
from datetime import UTC, datetime
from pathlib import Path

import typer
import uvicorn
from dotenv import find_dotenv, load_dotenv
from sqlalchemy import select

from openlia_server._cli_support import (
    OPENLIA_VERSION,
    build_session,
    echo_error,
    exit_not_found,
    format_table,
    log_cli_event,
    parse_duration,
    print_version_and_exit,
    render_startup_banner,
    require_company,
)
from openlia_server.db import bootstrap as bootstrap_module
from openlia_server.db.bootstrap import bootstrap
from openlia_server.db.models.auth import (
    AuthEvent,
    SignupInvite,
    User,
)
from openlia_server.db.models.auth import (
    Session as AuthSession,
)
from openlia_server.db.models.infrastructure import ConfigStore
from openlia_server.services.auth import password_reset as password_reset_service
from openlia_server.services.auth import sessions as sessions_service
from openlia_server.services.auth import tokens as tokens_service
from openlia_server.services.auth.errors import AuthError
from openlia_server.services.auth.password_reset import TokenInvalidError


# Load `.env` before any typer command body runs. All env reads live inside
# command functions, not at module import time, so loading here is safe.
# `override=False` means an explicit shell `export` always wins over the
# file. `.env.local` overlays `.env` only for keys not already present.
#
# Resolution order, each independent and using override=False:
#   1. Walk up from the current working directory.
#   2. Walk up from this module's directory (covers `uv run openlia serve`
#      invoked from a subdir like ./frontend/, where the CWD-based search
#      would miss the repo-root .env).
def _load_env_files() -> None:
    seen: set[str] = set()
    for filename in (".env", ".env.local"):
        for path in (
            find_dotenv(filename=filename, usecwd=True),
            find_dotenv(filename=filename, raise_error_if_not_found=False),
        ):
            if not path:
                continue
            resolved = str(Path(path).resolve())
            if resolved in seen:
                continue
            load_dotenv(resolved, override=False)
            seen.add(resolved)


_load_env_files()

app = typer.Typer(
    name="openlia",
    help="OpenLIA — open-source self-hosted AI investor assistant.",
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        print_version_and_exit()


def _no_color_callback(value: bool) -> bool:
    if value:
        # Disable colored output everywhere: Click's own help, Rich's help
        # renderer used by Typer, and any downstream child process that
        # respects NO_COLOR. Must run before --help so eager ordering matters.
        os.environ["NO_COLOR"] = "1"
        os.environ.pop("FORCE_COLOR", None)
        os.environ.pop("PY_COLORS", None)
        import typer.rich_utils as rich_utils

        rich_utils.FORCE_TERMINAL = False
        rich_utils.COLOR_SYSTEM = None
    return value


@app.callback()
def _root(
    ctx: typer.Context,
    no_color: bool = typer.Option(
        False,
        "--no-color",
        help="Disable colored output (for piping/scripting).",
        is_eager=True,
        callback=_no_color_callback,
    ),
    db_url: str | None = typer.Option(
        None,
        "--db-url",
        help="Override the database URL (defaults to OPENLIA_DB_URL).",
    ),
    version: bool = typer.Option(
        False,
        "--version",
        help="Print version and exit.",
        is_eager=True,
        callback=_version_callback,
    ),
) -> None:
    """Force Typer into multi-command mode and stash global flags in context."""
    ctx.obj = {"no_color": no_color, "db_url": db_url, "version": version}


def _default_host() -> str:
    env = os.environ.get("OPENLIA_HOST")
    if env:
        return env
    mode = os.environ.get("OPENLIA_MODE", "personal").lower()
    return "0.0.0.0" if mode == "company" else "127.0.0.1"


def _default_port() -> int:
    env = os.environ.get("OPENLIA_PORT")
    if env:
        return int(env)
    return 8080


def _find_listener_pid(host: str, port: int) -> int | None:
    """Best-effort lookup of the PID squatting on `port` via lsof.

    We deliberately do not pass `-sTCP:LISTEN` — on macOS that filter combined
    with `-iTCP:<port>` returns no hits even when a process IS the listener.
    A bind can also fail with no live LISTEN socket at all: a dead server's
    ESTABLISHED socket holds the local 4-tuple until the remote end closes,
    so the offender is the dead-server PID, not the client still connected to
    it. We ask lsof for every TCP socket on the port and rank candidates:

      1. LISTEN socket (NAME has no `->`).
      2. Server side of an ESTABLISHED connection (`:{port}->...`).
      3. Anything else holding a socket on the port.

    Host is unused; lsof's `-i@host:port` form misbehaves with wildcard binds.
    """
    del host  # see docstring
    try:
        result = subprocess.run(
            ["lsof", "-nP", f"-iTCP:{port}", "-Fpn"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    listener_pid: int | None = None
    server_pid: int | None = None
    any_pid: int | None = None
    current_pid: int | None = None
    port_suffix = f":{port}"
    for line in result.stdout.splitlines():
        if line.startswith("p") and line[1:].isdigit():
            current_pid = int(line[1:])
            if any_pid is None:
                any_pid = current_pid
            continue
        if not line.startswith("n") or current_pid is None:
            continue
        name = line[1:]
        if "->" not in name:
            listener_pid = current_pid
            break
        if server_pid is None:
            local, _, _remote = name.partition("->")
            if local.endswith(port_suffix):
                server_pid = current_pid
    return listener_pid or server_pid or any_pid


def _check_port_available(host: str, port: int) -> int | None:
    """Probe whether (host, port) can be bound. Returns None if free, otherwise
    the PID of the current listener (or 0 when the PID can't be determined).
    """
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.bind((host, port))
    except OSError:
        pid = _find_listener_pid(host, port)
        return pid if pid is not None else 0
    finally:
        sock.close()
    return None


@app.command()
def serve(
    host: str = typer.Option(None, help="Bind address (defaults to OPENLIA_HOST)."),
    port: int = typer.Option(None, help="Bind port (defaults to OPENLIA_PORT)."),
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
        os.environ["OPENLIA_SCHEDULER_ENABLED"] = "false"
    bootstrap()
    bind_host = host if host is not None else _default_host()
    bind_port = port if port is not None else _default_port()
    # Preflight bind check. uvicorn would otherwise emit a cryptic
    # `[Errno 48] address already in use` after the banner has printed and
    # the lifespan has started — leaving the user staring at a "Listening on..."
    # line that's a lie. Catch it up front, name the squatter, and exit.
    if not reload:
        listener_pid = _check_port_available(bind_host, bind_port)
        if listener_pid is not None:
            who = f"PID {listener_pid}" if listener_pid else "another process"
            echo_error(f"port {bind_port} on {bind_host} is already in use by {who}.")
            typer.echo("Either:", err=True)
            if listener_pid:
                typer.echo(f"  - stop the existing server:  kill {listener_pid}", err=True)
            typer.echo("  - pick a different port:     openlia serve --port <PORT>", err=True)
            typer.echo("  - or set OPENLIA_PORT=<PORT> in your environment", err=True)
            raise typer.Exit(code=1)
    mode = os.environ.get("OPENLIA_MODE", "personal").lower()
    scheduler_env = os.environ.get("OPENLIA_SCHEDULER_ENABLED", "true").lower()
    scheduler_enabled = scheduler_env not in {"false", "0", "no"}
    db_url = bootstrap_module.resolve_db_url()
    wizard_pending = _read_wizard_pending(db_url)
    typer.echo(
        render_startup_banner(
            version=OPENLIA_VERSION,
            mode=mode,
            db_url=db_url,
            host=bind_host,
            port=bind_port,
            scheduler_enabled=scheduler_enabled,
            wizard_pending=wizard_pending,
        )
    )
    uvicorn.run(
        "openlia_server.app:create_app",
        host=bind_host,
        port=bind_port,
        reload=reload,
        factory=True,
    )


def _read_wizard_pending(db_url: str) -> bool:
    """Read the `wizard.completed` config row on a short-lived session.
    Returns True when the wizard has not yet completed (row missing, falsy
    value, or DB unreachable — fail open: do not block startup)."""
    db = build_session(db_url)
    try:
        row = db.execute(
            select(ConfigStore).where(ConfigStore.key == "wizard.completed")
        ).scalar_one_or_none()
        if row is None:
            return True
        return not bool(row.value)
    except Exception:
        return False
    finally:
        db.close()


# ---------------------------------------------------------------------------
# admin sub-app
# ---------------------------------------------------------------------------

admin_app = typer.Typer(
    name="admin",
    help="Admin operations: manage users, invites, and sessions (company mode only).",
    no_args_is_help=True,
)


@admin_app.callback()
def _admin_callback() -> None:
    """Gate every admin subcommand on company mode."""
    require_company()


# --- list-users -------------------------------------------------------------


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
            last_login = u.last_login_at.strftime("%Y-%m-%d %H:%M") if u.last_login_at else ""
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


# --- unlock -----------------------------------------------------------------


@admin_app.command("unlock")
def admin_unlock(
    ctx: typer.Context,
    email: str = typer.Argument(..., help="Email of the user to unlock."),
) -> None:
    """Clear locked_until and failed_login_attempts for a user."""
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


# --- reset-password ---------------------------------------------------------


@admin_app.command("reset-password")
def admin_reset_password(
    ctx: typer.Context,
    email: str = typer.Argument(..., help="Email of the user to reset."),
    password: str | None = typer.Option(
        None,
        "--password",
        help="New password (skip interactive prompt).",
    ),
) -> None:
    """Reset a user's password. Sets must_change_password=true and revokes sessions."""
    if password is None:
        password = typer.prompt("New password", hide_input=True, confirmation_prompt=True)

    db = build_session(ctx.obj["db_url"])
    try:
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is None:
            exit_not_found("user", email)
        try:
            password_reset_service.admin_direct_reset(
                db,
                user_id=user.id,
                new_password=password,
                admin_user_id=None,
                metadata={"source": "cli"},
            )
        except (AuthError, TokenInvalidError) as exc:
            echo_error(str(exc))
            raise typer.Exit(code=1) from exc
        typer.echo(f"Password reset for {email}. User will be required to change it on next login.")
    finally:
        db.close()


# --- disable-user -----------------------------------------------------------


@admin_app.command("disable-user")
def admin_disable_user(
    ctx: typer.Context,
    email: str = typer.Argument(..., help="Email of the user to disable."),
) -> None:
    """Disable a user account and revoke all their sessions."""
    db = build_session(ctx.obj["db_url"])
    try:
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is None:
            exit_not_found("user", email)
        live_before = (
            db.execute(
                select(AuthSession).where(
                    AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)
                )
            )
            .scalars()
            .all()
        )
        user.is_disabled = True
        user.updated_at = datetime.now(UTC)
        db.flush()
        sessions_service.revoke_all_sessions(db, user_id=user.id)
        log_cli_event(db, event_type="user_disabled", user_id=user.id)
        db.commit()
        typer.echo(f"Disabled: {email} ({len(live_before)} sessions revoked)")
    finally:
        db.close()


# --- enable-user ------------------------------------------------------------


@admin_app.command("enable-user")
def admin_enable_user(
    ctx: typer.Context,
    email: str = typer.Argument(..., help="Email of the user to enable."),
) -> None:
    """Re-enable a disabled user account."""
    db = build_session(ctx.obj["db_url"])
    try:
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is None:
            exit_not_found("user", email)
        user.is_disabled = False
        user.updated_at = datetime.now(UTC)
        db.flush()
        log_cli_event(db, event_type="user_enabled", user_id=user.id)
        db.commit()
        typer.echo(f"Enabled: {email}")
    finally:
        db.close()


# --- revoke-sessions --------------------------------------------------------


@admin_app.command("revoke-sessions")
def admin_revoke_sessions(
    ctx: typer.Context,
    email: str = typer.Argument(..., help="Email of the user to revoke sessions for."),
) -> None:
    """Revoke all active sessions for a user."""
    db = build_session(ctx.obj["db_url"])
    try:
        user = db.execute(select(User).where(User.email == email)).scalar_one_or_none()
        if user is None:
            exit_not_found("user", email)
        live_sessions = (
            db.execute(
                select(AuthSession).where(
                    AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None)
                )
            )
            .scalars()
            .all()
        )
        sessions_service.revoke_all_sessions(db, user_id=user.id)
        log_cli_event(
            db,
            event_type="session_revoked",
            user_id=user.id,
            metadata={"count": len(live_sessions)},
        )
        db.commit()
        typer.echo(f"Revoked {len(live_sessions)} sessions for {email}.")
    finally:
        db.close()


# --- create-invite ----------------------------------------------------------


@admin_app.command("create-invite")
def admin_create_invite(
    ctx: typer.Context,
    label: str | None = typer.Option(None, "--label", help="Human-readable label."),
    max_uses: int | None = typer.Option(
        None, "--max-uses", min=1, help="Maximum registrations with this invite."
    ),
    expires: str | None = typer.Option(
        None, "--expires", help="Expiry duration (e.g. 7d, 24h, 30m, 2w)."
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Print machine-readable JSON ({invite_id, token, url}).",
    ),
) -> None:
    """Create a signup invite and print the URL + metadata."""
    expires_at = None
    if expires is not None:
        try:
            expires_at = datetime.now(UTC) + parse_duration(expires)
        except ValueError as exc:
            echo_error(str(exc))
            raise typer.Exit(code=1) from exc

    db = build_session(ctx.obj["db_url"])
    try:
        raw_token = tokens_service.generate_opaque_token()
        invite = SignupInvite(
            id=str(uuid.uuid4()),
            token_hash=tokens_service.hash_token(raw_token),
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
        base_url = os.environ.get("OPENLIA_PUBLIC_URL", "http://localhost:8080")
        url = f"{base_url}/register?invite={raw_token}"
        if json_output:
            import json as _json

            typer.echo(_json.dumps({"invite_id": invite.id, "token": raw_token, "url": url}))
            return
        typer.echo("Invite created.")
        typer.echo(f"URL:      {url}")
        typer.echo(f"ID:       {invite.id}")
        typer.echo(f"Label:    {label or '--'}")
        typer.echo(f"Max uses: {max_uses if max_uses is not None else 'unlimited'}")
        typer.echo(f"Expires:  {expires_at.strftime('%Y-%m-%d') if expires_at else '--'}")
    finally:
        db.close()


# --- seed-policy ------------------------------------------------------------


@admin_app.command("seed-policy")
def admin_seed_policy(
    ctx: typer.Context,
    mode: str = typer.Option(
        "invite_only",
        "--mode",
        help="Signup policy mode: invite_only or closed.",
    ),
) -> None:
    """Seed signup_policy for headless company-mode deployments.

    The setup wizard normally seeds this row on completion. For headless
    container operators who skip the wizard UI, this command writes the
    singleton row directly. Idempotent: if the row already exists, the
    mode is updated in place.
    """
    if mode not in ("invite_only", "closed"):
        echo_error("--mode must be 'invite_only' or 'closed'")
        raise typer.Exit(code=1)

    from openlia_server.db.models.auth import SignupPolicy

    db = build_session(ctx.obj["db_url"])
    try:
        row = db.get(SignupPolicy, 1)
        if row is None:
            db.add(SignupPolicy(id=1, mode=mode, allowed_email_domains=[]))
            action = "seeded"
        else:
            row.mode = mode
            action = "updated"
        db.commit()
        typer.echo(f"signup_policy {action}: mode={mode}")
    finally:
        db.close()


# --- list-invites -----------------------------------------------------------


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
        now = datetime.now(UTC)
        invites = (
            db.execute(select(SignupInvite).order_by(SignupInvite.created_at.desc()))
            .scalars()
            .all()
        )
        rows = []
        for inv in invites:
            uses = (
                f"{inv.use_count}/{inv.max_uses}"
                if inv.max_uses is not None
                else f"{inv.use_count}/unlimited"
            )
            rows.append(
                [
                    inv.id[:8],
                    inv.label or "--",
                    uses,
                    inv.created_at.strftime("%Y-%m-%d"),
                    inv.expires_at.strftime("%Y-%m-%d") if inv.expires_at else "--",
                    _invite_status(inv, now=now),
                ]
            )
        typer.echo(
            format_table(
                headers=["ID", "Label", "Uses", "Created", "Expires", "Status"],
                rows=rows,
            )
        )
    finally:
        db.close()


# --- revoke-invite ----------------------------------------------------------


@admin_app.command("revoke-invite")
def admin_revoke_invite(
    ctx: typer.Context,
    invite_id: str = typer.Argument(..., help="Invite ID (full UUID or 8-char prefix)."),
) -> None:
    """Revoke an invite by ID (full UUID or first 8-char prefix)."""
    db = build_session(ctx.obj["db_url"])
    try:
        candidates = (
            db.execute(select(SignupInvite).where(SignupInvite.id.like(f"{invite_id}%")))
            .scalars()
            .all()
        )
        if not candidates:
            exit_not_found("invite", invite_id)
        if len(candidates) > 1:
            echo_error(
                f"prefix {invite_id!r} matches multiple invites "
                f"({len(candidates)}). Use the full ID."
            )
            raise typer.Exit(code=1)
        invite = candidates[0]
        if invite.revoked_at is None:
            invite.revoked_at = datetime.now(UTC)
            log_cli_event(
                db,
                event_type="invite_revoked",
                metadata={"invite_id": invite.id},
            )
            db.commit()
        typer.echo(f"Invite revoked: {invite.id[:8]}...")
    finally:
        db.close()


# ---------------------------------------------------------------------------
# lockout sub-app
# ---------------------------------------------------------------------------

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
        return True, None
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
    """Enable the account-lockout feature."""
    db = build_session(ctx.obj["db_url"])
    try:
        current, row = _read_lockout_row(db)
        if current and row is not None:
            # Row exists and is already enabled — true no-op.
            typer.echo("Lockout enabled (already on).")
            return
        _write_lockout(db, enabled=True, previous=current)
        typer.echo("Lockout enabled.")
    finally:
        db.close()


@lockout_app.command("disable")
def lockout_disable(ctx: typer.Context) -> None:
    """Disable the account-lockout feature."""
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
                f"Last changed: {last_event.created_at.strftime('%Y-%m-%d %H:%M')} (actor: {actor})"
            )
    finally:
        db.close()


admin_app.add_typer(lockout_app, name="lockout")
app.add_typer(admin_app, name="admin")


# ---------------------------------------------------------------------------
# wizard sub-app
# ---------------------------------------------------------------------------

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
    purge: bool = typer.Option(
        False,
        "--purge",
        help=(
            "Also delete all configured data providers, LLM providers, and LLM keys "
            "so the wizard starts from a truly clean slate."
        ),
    ),
) -> None:
    """Reset the setup wizard to run from step 1 on next visit.

    By default, existing configuration (data providers, LLM keys, user
    accounts) is preserved and only the wizard completion flag is cleared.
    Pass `--purge` to additionally wipe data providers and LLM credentials.
    User accounts are always preserved.
    """
    if not yes:
        prompt = (
            "This will reset the setup wizard AND DELETE all configured data "
            "providers, LLM providers, and LLM keys. User accounts are preserved. "
            "Continue?"
            if purge
            else (
                "This will reset the setup wizard. Existing configuration "
                "(API keys, providers, user accounts) is preserved — only the "
                "wizard completion flag is cleared. Continue?"
            )
        )
        confirmed = typer.confirm(prompt, default=False)
        if not confirmed:
            raise typer.Exit(code=1)

    db = build_session(ctx.obj["db_url"])
    try:
        state = db.execute(select(WizardState)).scalar_one_or_none()
        now = datetime.now(UTC)
        if state is None:
            db.add(
                WizardState(
                    id=1,
                    status="not_started",
                    current_step="mode",
                    completed_steps=[],
                    active_session_token=None,
                    mode=None,
                )
            )
        else:
            state.status = "not_started"
            state.current_step = "mode"
            state.completed_steps = []
            state.active_session_token = None
            state.mode = None
            state.step_data = {}
            state.started_at = None
            state.completed_at = None
            state.updated_at = now
        wc = db.execute(
            select(ConfigStore).where(ConfigStore.key == "wizard.completed")
        ).scalar_one_or_none()
        if wc is None:
            db.add(ConfigStore(key="wizard.completed", value=False))
        else:
            wc.value = False

        purged_summary = ""
        if purge:
            from openlia_server.db.models.config import (
                LLMModel,
                LLMProvider,
            )

            llm_model_count = db.query(LLMModel).delete()
            llm_provider_count = db.query(LLMProvider).delete()
            purged_summary = (
                f" Purged {llm_model_count} LLM model(s) and {llm_provider_count} LLM provider(s)."
            )

        db.commit()
        typer.echo("Wizard state reset. The setup wizard will run on next visit." + purged_summary)
    finally:
        db.close()


app.add_typer(wizard_app, name="wizard")


# ---------------------------------------------------------------------------
# connectors sub-app
# ---------------------------------------------------------------------------

import asyncio  # noqa: E402

from openlia_server.services.connectors_service import (  # noqa: E402
    list_connectors,
    revalidate_connector,
)

connectors_app = typer.Typer(
    name="connectors",
    help="Manage connector entries.",
    no_args_is_help=True,
)


@connectors_app.command("list")
def connectors_list(ctx: typer.Context) -> None:
    """List all connectors with status."""
    db = build_session(ctx.obj["db_url"])
    try:
        rows = list_connectors(db)
        if not rows:
            typer.echo("No connectors configured.")
            return
        for row in rows:
            typer.echo(
                f"  {row.id}  {row.provider_id}  {row.display_name}  [{row.category}]  {row.status}"
            )
    finally:
        db.close()


@connectors_app.command("validate")
def connectors_validate(
    ctx: typer.Context,
    connector_id: str = typer.Argument(..., help="Connector id to revalidate."),
) -> None:
    """Re-run validation for a connector by id."""
    db = build_session(ctx.obj["db_url"])
    try:
        row = asyncio.run(revalidate_connector(db, connector_id))
        if row is None:
            echo_error(f"connector {connector_id!r} not found")
            raise typer.Exit(code=1)
        typer.echo(f"  {row.id}  status={row.status}  validated_at={row.validated_at}")
        if row.status == "failed":
            typer.echo(f"  error: {row.last_error}")
    finally:
        db.close()


app.add_typer(connectors_app, name="connectors")


# ---------------------------------------------------------------------------
# secrets sub-app
# Encryption-key rotation removed: API keys are stored plaintext under the
# admin-hosted single-tenant threat model (spec §3.2).


# ---------------------------------------------------------------------------
# top-level maintenance command
# ---------------------------------------------------------------------------
from openlia_server.scheduler.executors.maintenance import run_maintenance_once  # noqa: E402


@app.command()
def maintenance(
    ctx: typer.Context,
    dry_run: bool = typer.Option(
        False, "--dry-run", help="Print what would be pruned without deleting."
    ),
) -> None:
    """Run the nightly pruning sweep manually."""
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
        (
            "user_notifications:",
            f"deleted {counts['notifications_deleted']} old notifications",
        ),
        ("job_runs:", f"deleted {counts['job_runs_deleted']} old completed runs"),
    ]
    width = max(len(label) for label, _ in lines)
    for label, detail in lines:
        typer.echo(f"{prefix}{label.ljust(width)} {detail}")


from openlia_server.cli_guardrail import app as guardrail_app  # noqa: E402

app.add_typer(guardrail_app, name="guardrail-events")


def main() -> None:
    """Console-script entry point."""
    app()


__all__ = ["app", "main"]
