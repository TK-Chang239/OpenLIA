"""Typer CLI entry point. Registered as the `openlia` console script."""

import typer
import uvicorn

from openlia_server.db.bootstrap import bootstrap

app = typer.Typer(
    name="openlia",
    help="OpenLIA — open-source self-hosted AI investor assistant.",
    no_args_is_help=True,
)


@app.callback()
def _root() -> None:
    """Force Typer into multi-command mode so `serve` shows as a named subcommand."""


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Bind address."),
    port: int = typer.Option(8000, help="Bind port."),
    reload: bool = typer.Option(False, help="Auto-reload on code changes (development)."),
) -> None:
    """Start the OpenLIA HTTP server.

    Runs DB bootstrap (directory + migrations + local-user seed) before
    handing off to uvicorn.
    """
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
