"""Shared plumbing for the Typer CLI."""

from __future__ import annotations

import os
import re
from datetime import timedelta
from typing import Any

import typer
from sqlalchemy.orm import Session as DBSession

from openlia_server.db import bootstrap
from openlia_server.db import session as session_mod
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
    on malformed input."""
    match = _DURATION_PATTERN.fullmatch(raw)
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
    """Plain column-aligned text table. Double-space gutter between columns."""
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
    """Exit 1 unless OPENLIA_MODE is 'company'."""
    mode = os.environ.get("OPENLIA_MODE", "personal").lower()
    if mode != "company":
        echo_error("admin commands require company mode.")
        raise typer.Exit(code=1)


def build_session(db_url: str | None) -> DBSession:
    """Open a synchronous SQLAlchemy session for a CLI command."""
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
    """Audit wrapper. Guarantees actor_user_id=None and metadata.source=cli."""
    merged: dict[str, Any] = {"source": "cli"}
    if metadata:
        merged = {**merged, **metadata}
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
    """`--version` handler."""
    typer.echo(OPENLIA_VERSION)
    raise typer.Exit()
