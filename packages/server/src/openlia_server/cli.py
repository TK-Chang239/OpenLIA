"""Typer CLI entry point. Registered as the `openlia` console script."""

from __future__ import annotations

import os
import uuid
from datetime import UTC, datetime

import typer
import uvicorn
from sqlalchemy import select

from openlia_server._cli_support import (
    build_session,
    echo_error,
    exit_not_found,
    format_table,
    log_cli_event,
    parse_duration,
    print_version_and_exit,
    require_company,
)
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
        os.environ["OPENLIA_SCHEDULER_ENABLED"] = "false"
    bootstrap()
    uvicorn.run(
        "openlia_server.app:create_app",
        host=host,
        port=port,
        reload=reload,
        factory=True,
    )


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
                db, user_id=user.id, new_password=password, admin_user_id=None
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
            token=raw_token,
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
        base_url = os.environ.get("OPENLIA_PUBLIC_URL", "http://localhost:8000")
        typer.echo("Invite created.")
        typer.echo(f"URL:      {base_url}/register?invite={invite.token}")
        typer.echo(f"Label:    {label or '--'}")
        typer.echo(f"Max uses: {max_uses if max_uses is not None else 'unlimited'}")
        typer.echo(f"Expires:  {expires_at.strftime('%Y-%m-%d') if expires_at else '--'}")
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


# --- revoke-invite ----------------------------------------------------------


@admin_app.command("revoke-invite")
def admin_revoke_invite(
    ctx: typer.Context,
    token: str = typer.Argument(..., help="Full token or 12-char prefix."),
) -> None:
    """Revoke an invite by full token or first 12-char prefix."""
    db = build_session(ctx.obj["db_url"])
    try:
        candidates = (
            db.execute(select(SignupInvite).where(SignupInvite.token.like(f"{token}%")))
            .scalars()
            .all()
        )
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
            invite.revoked_at = datetime.now(UTC)
            log_cli_event(
                db,
                event_type="invite_revoked",
                metadata={"invite_id": invite.id},
            )
            db.commit()
        typer.echo(f"Invite revoked: {invite.token[:12]}...")
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
) -> None:
    """Reset the setup wizard to run from step 1 on next visit."""
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
        now = datetime.now(UTC)
        if state is None:
            db.add(
                WizardState(
                    id=1,
                    status="not_started",
                    current_step=1,
                    mode=None,
                )
            )
        else:
            state.status = "not_started"
            state.current_step = 1
            state.updated_at = now
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


# ---------------------------------------------------------------------------
# secrets sub-app
# ---------------------------------------------------------------------------
import base64  # noqa: E402
import secrets as secrets_module  # noqa: E402

import sqlalchemy  # noqa: E402
from sqlalchemy.exc import OperationalError  # noqa: E402

from openlia_server.db import crypto as crypto_module  # noqa: E402
from openlia_server.db.bootstrap import openlia_home  # noqa: E402
from openlia_server.db.models.config import (  # noqa: E402
    DataProvider,
    LLMProvider,
    WebSearchProvider,
)

secrets_app = typer.Typer(
    name="secrets",
    help="Manage encryption keys for stored provider API keys.",
    no_args_is_help=True,
)


def _decode_new_key(raw: str) -> bytes:
    try:
        key = base64.b64decode(raw, validate=True)
    except Exception as exc:
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
    """Re-encrypt every stored API key with a new AES-256-GCM key."""
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
            db.execute(sqlalchemy.text("BEGIN EXCLUSIVE"))
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
            rows = (
                db.execute(select(model).where(model.api_key_encrypted.is_not(None)))
                .scalars()
                .all()
            )
            for row in rows:
                row_id = getattr(row, pk_attr)
                plaintext = crypto_module.decrypt_with_key(old_key, row_id, row.api_key_encrypted)
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

    crypto_module._reset_cached_key()


app.add_typer(secrets_app, name="secrets")


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
        ("mr_assessment_cache:", f"deleted {counts['mr_cache_deleted']} stale rows"),
        ("rs_snapshots:", f"deleted {counts['rs_snapshots_deleted']} old snapshots"),
        (
            "user_notifications:",
            f"deleted {counts['notifications_deleted']} old notifications",
        ),
        ("job_runs:", f"deleted {counts['job_runs_deleted']} old completed runs"),
    ]
    width = max(len(label) for label, _ in lines)
    for label, detail in lines:
        typer.echo(f"{prefix}{label.ljust(width)} {detail}")


def main() -> None:
    """Console-script entry point."""
    app()


__all__ = ["app", "main"]
