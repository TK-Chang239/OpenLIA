"""`openlia guardrail-events` — query the audit table from the shell."""

from __future__ import annotations

import json as _json

import typer

from openlia_server._cli_support import build_session
from openlia_server.services.guardrail_log import list_events

app = typer.Typer(
    name="guardrail-events",
    help="Query the Lia guardrail audit log.",
    no_args_is_help=False,
    invoke_without_command=True,
)


@app.callback(invoke_without_command=True)
def guardrail_events_cmd(
    ctx: typer.Context,
    since: str = typer.Option("7d", "--since", help="Window e.g. '7d', '30d'."),
    category: str | None = typer.Option(None, "--category"),
    department_id: str | None = typer.Option(None, "--department"),
    limit: int = typer.Option(200, "--limit"),
    as_json: bool = typer.Option(False, "--json", help="Output JSON."),
) -> None:
    if not since.endswith("d"):
        typer.echo("Error: --since must look like '7d'", err=True)
        raise typer.Exit(code=1)
    days = int(since[:-1])

    db_url = (ctx.obj or {}).get("db_url") if ctx.obj else None
    db = build_session(db_url)
    try:
        rows = list_events(
            db,
            since_days=days,
            category=category,
            department_id=department_id,
            limit=limit,
        )
    finally:
        db.close()

    if as_json:
        out = [
            {
                "id": r.id,
                "created_at": r.created_at.isoformat(),
                "session_id": r.session_id,
                "user_id": r.user_id,
                "department_id": r.department_id,
                "event_type": r.event_type,
                "category": r.category,
                "action_taken": r.action_taken,
                "tripwire_pattern": r.tripwire_pattern,
                "response_excerpt": r.response_excerpt,
                "model_ref": r.model_ref,
            }
            for r in rows
        ]
        typer.echo(_json.dumps(out, indent=2))
        return
    typer.echo(f"{len(rows)} events in last {days}d")
    for r in rows:
        typer.echo(
            f"  {r.created_at.isoformat()}  {r.department_id:18s}  "
            f"{r.event_type:16s}  {r.category:24s}  {r.action_taken:8s}"
        )
