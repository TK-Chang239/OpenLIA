"""Side-by-side classic vs. waved report diff script.

Usage:
    uv run python -m openlia.scripts.side_by_side_report_diff --ticker NET.US
    uv run python -m openlia.scripts.side_by_side_report_diff --ticker NET.US --out ./out

Wiring summary:
    V2 (waved) path — uses the same wiring as smoke_report_v2.py:
        LLM provider  — real AnthropicAdapter (ANTHROPIC_API_KEY from env)
        EODHD         — real ExtendedAPIClient (EODHD_API_TOKEN from env)
        Web search    — no-op (returns [])
    V1 (classic) path — STUB. The classic ReportRunner requires a DB session,
        a PreparedConnector registry, and a UserPreferences record — all
        server-layer constructs that are not available in a standalone script.
        The v1 path raises NotImplementedError with a clear message.
        To produce a classic report, use the running server instead:
            POST /api/departments/equity-research/report  (with V2 flag off)
        and save the resulting JSON to {ticker}_classic.json, then re-run
        this script with --classic-json path/to/{ticker}_classic.json.

Status: DONE_WITH_CONCERNS — v2 standalone works; v1 standalone is stubbed.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Env helpers (copied inline to avoid importing smoke script module)
# ---------------------------------------------------------------------------


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        print(f"ERROR: environment variable {name!r} is not set or is empty.", file=sys.stderr)
        sys.exit(1)
    return value


# ---------------------------------------------------------------------------
# V2 (waved) run — reuses smoke_report_v2 wiring helpers directly
# ---------------------------------------------------------------------------


async def _run_waved(ticker: str, anthropic_key: str, eodhd_token: str) -> Any:
    """Run WavedReportRunner and return the WaveRunnerOutput (has .schema)."""
    from openlia.scripts.smoke_report_v2 import _build_runner

    runner = _build_runner(
        ticker=ticker,
        report_type="stock_initiation",
        anthropic_key=anthropic_key,
        eodhd_token=eodhd_token,
    )
    print(f"  Running WavedReportRunner for {ticker} ...")
    return await runner.run()


# ---------------------------------------------------------------------------
# V1 (classic) standalone — NOT IMPLEMENTED
# ---------------------------------------------------------------------------


def _run_classic_stub(ticker: str) -> None:
    """Classic ReportRunner requires server-layer constructs (DB, registry, etc.).

    Standalone invocation is not possible without a live server context.
    Use the running server to generate a classic report:

        # With OPENLIA_REPORT_V2_ENABLED unset or =false, POST to:
        POST /api/departments/equity-research/report
        Body: {"ticker": "<ticker>"}

    Save the JSON response body to {ticker}_classic.json, then pass it via
    --classic-json to this script to compute the diff.
    """
    raise NotImplementedError(
        "Classic ReportRunner standalone invocation needs server-context wiring "
        "(DB session, PreparedConnector registry, UserPreferences). "
        "Use the running server instead — see script docstring for instructions."
    )


# ---------------------------------------------------------------------------
# Main logic
# ---------------------------------------------------------------------------


async def _run(ticker: str, out_dir: Path, classic_json: Path | None) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)

    # --- V2 run ---
    anthropic_key = _require_env("ANTHROPIC_API_KEY")
    eodhd_token = _require_env("EODHD_API_TOKEN")

    os.environ["OPENLIA_REPORT_V2_ENABLED"] = "1"
    waved_output = await _run_waved(ticker, anthropic_key, eodhd_token)
    waved_schema = waved_output.schema

    waved_path = out_dir / f"{ticker}_waved.json"
    waved_path.write_text(waved_schema.model_dump_json(indent=2))
    print(f"  Waved report written → {waved_path}")

    # --- V1 path ---
    classic_schema = None

    if classic_json is not None:
        # Load a pre-generated classic report from disk.
        from openlia.reports.schema import ReportSchema

        raw = classic_json.read_text()
        classic_schema = ReportSchema.model_validate_json(raw)
        print(f"  Classic report loaded from {classic_json}")
    else:
        print()
        print("  NOTE: Classic (v1) standalone path is not implemented.")
        print("  The classic ReportRunner requires a DB session and server-layer")
        print("  constructs that are not available in a standalone script.")
        print()
        print("  To compute a full diff, generate a classic report via the running")
        print("  server (OPENLIA_REPORT_V2_ENABLED unset or =false), save the JSON,")
        print(f"  then re-run with:  --classic-json <path>/{ticker}_classic.json")
        print()

    # --- Diff ---
    if classic_schema is not None:
        from openlia.llm.runtime.report_v2.diff import diff_reports

        diff = diff_reports(classic_schema, waved_schema)
        diff_path = out_dir / f"{ticker}_diff.json"
        diff_path.write_text(json.dumps(diff, indent=2, default=str))
        print(f"  Diff written → {diff_path}")
        print()
        print(json.dumps(diff, indent=2, default=str))
    else:
        note = {
            "note": "Diff not computed — classic report not available.",
            "waved_sections": len(waved_schema.sections),
            "waved_citations": len(waved_schema.citations),
            "waved_key_metrics": [
                {"label": m.label, "value": m.value} for m in waved_schema.cover.key_metrics
            ],
        }
        note_path = out_dir / f"{ticker}_diff_note.json"
        note_path.write_text(json.dumps(note, indent=2))
        print(f"  Diff note written → {note_path}")
        print(json.dumps(note, indent=2))


def main() -> None:
    p = argparse.ArgumentParser(
        description=(
            "Run WavedReportRunner and optionally diff against a classic report. "
            "V2 (waved) path is fully standalone. "
            "V1 (classic) path requires a pre-generated JSON from the running server."
        )
    )
    p.add_argument("--ticker", required=True, help="Ticker symbol, e.g. NET.US")
    p.add_argument(
        "--out",
        default="./report_diff_output",
        help="Output directory for JSON files (default: ./report_diff_output)",
    )
    p.add_argument(
        "--classic-json",
        default=None,
        metavar="PATH",
        help=(
            "Path to a pre-generated classic report JSON. "
            "If omitted, only the waved report is produced and diff is skipped."
        ),
    )
    args = p.parse_args()

    classic_json = Path(args.classic_json) if args.classic_json else None
    if classic_json is not None and not classic_json.exists():
        print(f"ERROR: --classic-json path does not exist: {classic_json}", file=sys.stderr)
        sys.exit(1)

    asyncio.run(_run(ticker=args.ticker, out_dir=Path(args.out), classic_json=classic_json))


if __name__ == "__main__":
    main()
