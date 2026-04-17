"""Typer CLI entry point. Registered as the `openlia` console script."""

import typer
import uvicorn

app = typer.Typer(
    name="openlia",
    help="OpenLIA — open-source self-hosted AI investor assistant.",
)


@app.callback(invoke_without_command=True)
def default(ctx: typer.Context) -> None:
    """Default callback to show help when no subcommand is provided.

    Note: We use a callback with invoke_without_command instead of
    no_args_is_help=True because that flag would prevent proper subcommand
    recognition in Typer.
    """
    if ctx.invoked_subcommand is None:
        typer.echo(ctx.get_help())


@app.command()
def serve(
    host: str = typer.Option("127.0.0.1", help="Bind address."),
    port: int = typer.Option(8000, help="Bind port."),
    reload: bool = typer.Option(False, help="Auto-reload on code changes (development)."),
) -> None:
    """Start the OpenLIA HTTP server."""
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
