"""Typer CLI entry point. Registered as the `openlia` console script."""

from __future__ import annotations

import os

import typer
import uvicorn

from openlia_server._cli_support import print_version_and_exit
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


def main() -> None:
    """Console-script entry point."""
    app()


__all__ = ["app", "main"]
