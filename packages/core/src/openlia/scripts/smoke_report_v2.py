"""End-to-end smoke test for WavedReportRunner.

Usage:
    uv run python -m openlia.scripts.smoke_report_v2 --ticker NET.US
    uv run python -m openlia.scripts.smoke_report_v2 --ticker NET.US --report-type stock_initiation

Wiring summary:
    LLM provider  — real AnthropicAdapter (ANTHROPIC_API_KEY from env)
    EODHD         — real ExtendedAPIClient via _EodhdDispatcher (EODHD_API_TOKEN from env)
                    Covers all 12 BASELINE_STOCK_INITIATION tools natively.
                    "news" provider calls are no-op (returns None → skipped by run_baseline).
    Web search    — no-op _NoOpWebSearch (returns [] — structural validation only)
    Writers       — ProviderSectionWriter + ProviderStructuredOutput wrapping the same adapter

Assumptions:
    - AnthropicAdapter constructor matches LLMProvider.__init__: credentials, model, capabilities.
    - ExtendedAPIClient is a subclass of eodhd.APIClient; constructor takes api_key= kwarg.
    - EODHD tool names in BASELINE_STOCK_INITIATION map to ExtendedAPIClient methods via
      _TOOL_MAP below.  If the live SDK renames a method, update _TOOL_MAP accordingly.
    - OPENLIA_REPORT_V2_ENABLED env var is checked as a feature-flag guard (any truthy value).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from typing import Any

# ---------------------------------------------------------------------------
# Env guard — check before importing heavyweight modules so error is instant.
# ---------------------------------------------------------------------------


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        print(f"ERROR: environment variable {name!r} is not set or is empty.", file=sys.stderr)
        sys.exit(1)
    return value


def _check_env() -> tuple[str, str, str]:
    """Verify required env vars. Returns (llm_api_key, llm_provider, eodhd_token).

    Provider selected by OPENLIA_SMOKE_PROVIDER env var (default 'openai').
    Acceptable: 'openai', 'anthropic'. Picks the matching API_KEY env var.
    """
    v2_flag = os.environ.get("OPENLIA_REPORT_V2_ENABLED", "").strip()
    if not v2_flag or v2_flag.lower() in ("0", "false", "no"):
        print(
            "ERROR: OPENLIA_REPORT_V2_ENABLED is not set to a truthy value. "
            "Export it before running the smoke test:\n"
            "    export OPENLIA_REPORT_V2_ENABLED=1",
            file=sys.stderr,
        )
        sys.exit(1)
    provider = os.environ.get("OPENLIA_SMOKE_PROVIDER", "openai").strip().lower()
    if provider not in ("openai", "anthropic"):
        print(
            f"ERROR: OPENLIA_SMOKE_PROVIDER must be 'openai' or 'anthropic', got {provider!r}",
            file=sys.stderr,
        )
        sys.exit(1)
    key_var = "OPENAI_API_KEY" if provider == "openai" else "ANTHROPIC_API_KEY"
    llm_api_key = _require_env(key_var)
    eodhd_token = _require_env("EODHD_API_TOKEN")
    return llm_api_key, provider, eodhd_token


# ---------------------------------------------------------------------------
# Lightweight EODHD dispatcher wrapping ExtendedAPIClient directly.
#
# The full Dispatcher in connectors/dispatch.py requires a PreparedConnector
# registry hydrated from the DB — too heavy for a standalone script.
# Instead we build a minimal ToolDispatcher (the Protocol from baseline.py)
# that routes every "eodhd" call to ExtendedAPIClient methods and ignores
# the "news" provider (baseline skips None results gracefully).
#
# Tool name → SDK method mapping via _method_for().  Multiple tool names map
# to the same SDK call when their data lives inside the same payload (e.g.
# income_statement, balance_sheet, cash_flow, holders, earnings_trends all live
# inside the fundamentals dict returned by get_fundamentals_data).
# ---------------------------------------------------------------------------


class _EodhdDispatcher:
    """Minimal ToolDispatcher that routes 'eodhd' tools to ExtendedAPIClient.

    If ExtendedAPIClient lacks a method for a given tool name, the call returns
    None and run_baseline skips the entry — no crash, degraded manifest at worst.
    Failures are printed to stdout so they are visible during smoke testing.
    """

    def __init__(self, client: Any, default_ticker: str = "") -> None:
        self._client = client
        self._default_ticker = default_ticker

    async def dispatch(self, provider: str, tool: str, args: dict[str, Any]) -> Any:
        if provider != "eodhd":
            # "news" and any other provider: no connector wired; baseline skips None.
            return None
        ticker = args.get("ticker", "").strip()
        if not ticker:
            ticker = self._default_ticker
        method_name = self._method_for(tool)
        if method_name is None:
            return None
        method = getattr(self._client, method_name, None)
        if method is None:
            print(
                f"  [EODHD warn] SDK has no method {method_name!r} (tool={tool!r})",
                flush=True,
            )
            return None
        loop = asyncio.get_event_loop()
        try:
            return await loop.run_in_executor(None, lambda: method(ticker))
        except Exception as e:
            # Surface the failure so it is visible during smoke testing.
            print(
                f"  [EODHD warn] {tool}({ticker}) → {type(e).__name__}: {e}",
                flush=True,
            )
            return None

    @staticmethod
    def _method_for(tool: str) -> str | None:
        # Multiple tool names map to the same SDK method when their data lives
        # inside the same payload (fundamentals contains income/balance/cashflow).
        if tool in {
            "get_fundamentals_data",
            "get_income_statement",
            "get_balance_sheet",
            "get_cash_flow",
            "get_earnings_trends",
            "get_holders",
        }:
            return "get_fundamentals_data"
        if tool == "get_live_prices":
            return "get_live_stock_prices"
        if tool == "get_insider_transactions":
            return "get_insider_transactions_data"
        if tool in {"get_historical_prices", "get_historical_prices_long"}:
            return "get_historical_data"
        # get_historical_market_cap has no direct SDK method in this version.
        return None


class _NoOpWebSearch:
    """Returns empty results for every query — structural validation only."""

    async def search(self, query: str) -> list[dict[str, Any]]:
        _ = query
        return []


# ---------------------------------------------------------------------------
# Runner wiring
# ---------------------------------------------------------------------------


def _build_provider(
    *, provider_kind: str, api_key: str, model_id: str
) -> tuple[Any, Any]:
    """Construct provider adapter + ResolvedModel for the given kind."""
    from openlia.llm.types import Capabilities, ProviderCredentials, ResolvedModel

    if provider_kind == "openai":
        from openlia.llm.adapters.openai import OpenAIAdapter
        adapter_cls = OpenAIAdapter
        env_var = "OPENAI_API_KEY"
    elif provider_kind == "anthropic":
        from openlia.llm.adapters.anthropic import AnthropicAdapter
        adapter_cls = AnthropicAdapter
        env_var = "ANTHROPIC_API_KEY"
    else:
        raise ValueError(f"unsupported provider_kind: {provider_kind}")

    credentials = ProviderCredentials(api_key=api_key, base_url=None, env_var_name=env_var)
    capabilities = Capabilities(
        streaming=False,
        tool_calling=True,
        structured_output=True,
        max_context_tokens=200_000,
        max_output_tokens=8192,
    )
    provider = adapter_cls(credentials=credentials, model=model_id, capabilities=capabilities)
    resolved = ResolvedModel(
        provider_kind=provider_kind,
        provider_id=provider_kind,
        model_id=model_id,
        model_ref=model_id,
        credentials=credentials,
        capabilities=capabilities,
        overrides={},
    )
    return provider, resolved


def _build_runner(
    ticker: str,
    report_type: str,
    llm_api_key: str,
    provider_kind: str,
    eodhd_token: str,
) -> Any:
    """Construct WavedReportRunner with selected LLM provider + EODHD."""
    from openlia.data.eodhd_extended import ExtendedAPIClient
    from openlia.llm.runtime.report_v2.runner import WavedReportRunner
    from openlia.llm.runtime.report_v2.writers import (
        ProviderSectionWriter,
        ProviderStructuredOutput,
    )

    # Two-model strategy:
    # - Body & synthesis writers: stronger model (default gpt-5.4 or claude-sonnet-4-6).
    # - Preflight (structured output): cheaper mini model (default gpt-5.4-mini).
    if provider_kind == "openai":
        body_model_id = os.environ.get("OPENLIA_SMOKE_BODY_MODEL", "gpt-5.4").strip()
        preflight_model_id = os.environ.get(
            "OPENLIA_SMOKE_PREFLIGHT_MODEL", "gpt-5.4-mini"
        ).strip()
    else:
        body_model_id = os.environ.get(
            "OPENLIA_SMOKE_BODY_MODEL", "claude-sonnet-4-6"
        ).strip()
        preflight_model_id = os.environ.get(
            "OPENLIA_SMOKE_PREFLIGHT_MODEL", body_model_id
        ).strip()

    body_provider, body_resolved = _build_provider(
        provider_kind=provider_kind, api_key=llm_api_key, model_id=body_model_id
    )
    preflight_provider_obj, preflight_resolved = _build_provider(
        provider_kind=provider_kind, api_key=llm_api_key, model_id=preflight_model_id
    )

    print(f"  provider: {provider_kind}")
    print(f"  body/synthesis model: {body_model_id}")
    print(f"  preflight model: {preflight_model_id}")

    # EODHD client — ExtendedAPIClient wraps eodhd.APIClient.
    eodhd_client = ExtendedAPIClient(api_key=eodhd_token)
    dispatcher = _EodhdDispatcher(eodhd_client, default_ticker=ticker)

    websearch = _NoOpWebSearch()

    body_writer = ProviderSectionWriter(
        provider=body_provider,
        resolved_model=body_resolved,
        max_tokens=8192,
        temperature=0.7,
    )
    synthesis_writer = ProviderSectionWriter(
        provider=body_provider,
        resolved_model=body_resolved,
        max_tokens=8192,
        temperature=0.7,
    )
    preflight_provider = ProviderStructuredOutput(
        provider=preflight_provider_obj,
        resolved_model=preflight_resolved,
        max_tokens=4096,
        temperature=0.0,
    )

    return WavedReportRunner(
        report_type=report_type,
        ticker=ticker,
        dispatcher=dispatcher,
        websearch=websearch,
        preflight_provider=preflight_provider,
        body_writer=body_writer,
        synthesis_writer=synthesis_writer,
        preflight_concurrency=3,
        body_concurrency=1,
        synthesis_concurrency=1,
    )


# ---------------------------------------------------------------------------
# Summary printer
# ---------------------------------------------------------------------------


def _print_summary(ticker: str, output: Any) -> None:
    schema = output.schema
    telemetry = output.telemetry
    snap = telemetry.snapshot()

    print()
    print("=" * 70)
    print("SMOKE TEST SUMMARY")
    print("=" * 70)
    print("  department : equity_research")
    print(f"  ticker     : {ticker}")
    print(f"  generated  : {schema.generated_at}")
    print()

    # Section count
    n_sections = len(schema.sections)
    print(f"  sections   : {n_sections}  (expect 15: 11 body + 4 synthesis)")

    # Cover key_metrics
    cover = schema.cover
    print(f"  cover.title: {cover.title!r}")
    km = cover.key_metrics
    if km:
        print(f"  key_metrics ({len(km)}):")
        for m in km:
            label = getattr(m, "label", None) or getattr(m, "name", "?")
            value = getattr(m, "value", "?")
            print(f"    - {label}: {value}")
    else:
        print("  key_metrics: (none)")

    # Citations
    n_cit = len(schema.citations)
    print(f"  citations  : {n_cit}")

    # Telemetry
    print()
    print("  Telemetry:")
    print(f"    wave timings (ms): {snap['wave_ms']}")
    print(f"    section_states   : {snap['section_states']}")
    proposed = snap["proposed_facts"]
    total_proposed = sum(len(v) for v in proposed.values())
    print(f"    proposed_facts   : {total_proposed} total across {len(proposed)} sections")

    # Degraded / exhausted sections
    problem_sections = [
        (sid, info)
        for sid, info in snap["sections"].items()
        if info["state"] in ("degraded", "exhausted")
    ]
    if problem_sections:
        print()
        print(f"  Degraded/exhausted sections ({len(problem_sections)}):")
        for sid, info in problem_sections:
            errs = info.get("validation_errors", [])
            print(f"    [{info['state'].upper()}] {sid}")
            for e in errs:
                print(f"      - {e}")
    else:
        print()
        print("  All sections: SUCCESS")

    print("=" * 70)
    print()


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


async def _run(
    ticker: str,
    report_type: str,
    llm_api_key: str,
    provider_kind: str,
    eodhd_token: str,
) -> None:
    print(f"Starting WavedReportRunner: {report_type} / {ticker}")
    runner = _build_runner(ticker, report_type, llm_api_key, provider_kind, eodhd_token)
    print(f"(Live API calls to {provider_kind.upper()} and EODHD.)")
    print()
    output = await runner.run()
    _print_summary(ticker, output)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="End-to-end smoke test for WavedReportRunner (live API calls)."
    )
    parser.add_argument("--ticker", default="NET.US", help="Ticker symbol, e.g. NET.US")
    parser.add_argument(
        "--report-type",
        default="stock_initiation",
        choices=["stock_initiation"],
        help="Report type (only stock_initiation supported)",
    )
    args = parser.parse_args()

    llm_api_key, provider_kind, eodhd_token = _check_env()
    asyncio.run(
        _run(args.ticker, args.report_type, llm_api_key, provider_kind, eodhd_token)
    )


if __name__ == "__main__":
    main()
