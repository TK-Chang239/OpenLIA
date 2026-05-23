"""End-to-end smoke driver for the v2.3 subagent pipeline.

Drives the v2.3 ``ReportRunner`` through CLARIFY -> PLAN -> RESEARCH
-> COMPUTE -> SYNTHESIZE -> WRITE -> VISUALIZE -> VERIFY -> ASSEMBLE
against real LLM providers. Stages without an API key fall back to
NoOp so a partially-keyed environment still exercises the parts you
can pay for.

Usage:

    uv run python -m openlia.scripts.smoke_v2_3 \\
        --ticker NVDA \\
        --prompt "Initiate coverage on NVIDIA."

    # Multi-ticker:
    uv run python -m openlia.scripts.smoke_v2_3 \\
        --ticker NVDA --ticker AVGO --report-type initiation \\
        --output /tmp/v2_3_smoke.docx

Required env (CLARIFY at minimum):
    OPENAI_API_KEY                real OpenAI key
    OPENLIA_V2_3_CLARIFY_MODEL    e.g. "gpt-5.4-mini"

Optional env (each gates its stage; missing -> NoOp):
    OPENLIA_V2_3_PLAN_MODEL
    OPENLIA_V2_3_RESEARCH_MODEL + EODHD_API_KEY
    OPENLIA_V2_3_COMPUTE_MODEL
    OPENLIA_V2_3_SYNTHESIZE_MODEL
    OPENLIA_V2_3_WRITE_MODEL
    OPENLIA_V2_3_VERIFY_MODEL

The driver prints stage events live (via the runner observer) so you
can watch the pipeline walk through. On a suspended CLARIFY it prints
the questions; pass --auto-default to accept the stated defaults.

Stays core-only: builds its own LLM providers and clients via
``openlia.llm.adapters.build_adapter``. Does NOT import the server
package — this script must work with just ``openlia-core`` installed.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import re
import sys
import uuid
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from openlia.llm.runtime.report_v2_3.events import RunnerEvent


def _require_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        print(f"ERROR: environment variable {name!r} is not set.", file=sys.stderr)
        sys.exit(2)
    return value


# ---------------------------------------------------------------------------
# Minimal sync JSON / tool-use clients (core-only — no SyncJsonLlmClient
# from the server package).
# ---------------------------------------------------------------------------


_FENCE_RE = re.compile(r"^```(?:json)?\s*\n?(.*?)\n?```$", re.DOTALL)


class _SyncJsonClient:
    """Sync ``call(system, user) -> dict`` over an async LLMProvider."""

    def __init__(self, provider: Any, *, max_tokens: int = 4096, temperature: float = 0.2) -> None:
        from openlia.llm.types import ResponseFormat  # local import

        self._provider = provider
        self._max_tokens = max_tokens
        self._temperature = temperature
        self._json_format = ResponseFormat(kind="json_object")

    def call(self, *, system: str | None, user: Any) -> dict[str, Any]:
        from openlia.llm.types import LLMRequest, Message

        user_text = user if isinstance(user, str) else json.dumps(user, default=str)
        req = LLMRequest(
            messages=[Message(role="user", content=user_text)],
            system=(system or "")
            + "\n\nReturn ONLY a single JSON object. No prose, no markdown fences.",
            response_format=self._json_format,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
        )
        response = asyncio.run(self._provider.generate(req))
        text = (response.text or "").strip()
        match = _FENCE_RE.match(text)
        if match is not None:
            text = match.group(1).strip()
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            first = text.find("{")
            last = text.rfind("}")
            parsed = json.loads(text[first : last + 1]) if first != -1 and last > first else {}
        return parsed if isinstance(parsed, dict) else {"value": parsed}


class _SyncToolClient:
    """Sync .send(...) wrapper that runs ONE tool-use provider turn."""

    def __init__(self, provider: Any, *, max_tokens: int = 4096, temperature: float = 0.3) -> None:
        self._provider = provider
        self._max_tokens = max_tokens
        self._temperature = temperature

    def send(self, *, system: str, messages: list, tools: list):
        from openlia.llm.runtime.report_v2_3.clients.llm_researcher import ToolTurnResponse
        from openlia.llm.types import LLMRequest

        req = LLMRequest(
            messages=list(messages),
            system=system,
            tools=list(tools) if tools else None,
            max_tokens=self._max_tokens,
            temperature=self._temperature,
        )
        response = asyncio.run(self._provider.generate(req))
        return ToolTurnResponse(
            text=response.text or "",
            tool_calls=tuple(response.tool_calls),
        )


def _build_openai_provider(
    model: str, *, tool_calling: bool = False, max_tokens: int = 4096
) -> Any:
    from openlia.llm.adapters import build_adapter
    from openlia.llm.types import Capabilities, ProviderCredentials

    creds = ProviderCredentials(
        api_key=_require_env("OPENAI_API_KEY"),
        base_url=os.environ.get("OPENAI_BASE_URL"),
        env_var_name="OPENAI_API_KEY",
    )
    return build_adapter(
        kind="openai",
        credentials=creds,
        model=model,
        capabilities=Capabilities(
            structured_output=True,
            tool_calling=tool_calling,
            max_context_tokens=128_000,
            max_output_tokens=max_tokens,
        ),
    )


def _build_eodhd_tools() -> list:
    """Build EODHD tools if EODHD_API_KEY present, else empty list."""
    key = os.environ.get("EODHD_API_KEY")
    if not key:
        return []
    from eodhd import APIClient

    from openlia.llm.runtime.report_v2_3.research import build_research_tools

    client = APIClient(api_key=key)

    def fundamentals(ticker: str) -> dict:
        raw = client.get_fundamentals_data(ticker)
        if isinstance(raw, dict):
            return raw
        return {"value": raw}

    def prices(ticker: str, from_date: str, to_date: str) -> list:
        rows = client.get_eod_historical_stock_market_data(
            symbol=ticker, period="d", from_date=from_date, to_date=to_date
        )
        return list(rows) if rows else []

    def news(ticker: str, limit: int) -> list:
        rows = client.financial_news(s=ticker, limit=limit)
        return list(rows) if rows else []

    return build_research_tools(fundamentals=fundamentals, prices=prices, news=news)


def _build_factory() -> Callable[[], Any]:
    """Build a V23RunnerFactory using core-only imports."""
    from openlia.llm.runtime.report_v2_3.clients.llm_clarifier import LLMClarifierClient
    from openlia.llm.runtime.report_v2_3.clients.llm_researcher import LLMResearcherClient
    from openlia.llm.runtime.report_v2_3.clients.llm_stage_clients import (
        LLMComputeClient,
        LLMPlannerClient,
        LLMSynthesizerClient,
        LLMVerifierClient,
        LLMWriterClient,
    )
    from openlia.llm.runtime.report_v2_3.runner import ReportRunner
    from openlia.llm.runtime.report_v2_3.slots import V23Slot
    from openlia.llm.runtime.report_v2_3.stages import (
        PIPELINE_ORDER,
        ClarifyStage,
        ComputeStage,
        NoOpStage,
        PlanStage,
        RealAssembleStage,
        ResearchStage,
        StageContext,
        SynthesizeStage,
        VerifyStage,
        VisualizeStage,
        WriteStage,
    )

    clarify_model = _require_env("OPENLIA_V2_3_CLARIFY_MODEL")
    clarifier = LLMClarifierClient(
        _SyncJsonClient(_build_openai_provider(clarify_model, max_tokens=1024)).call
    )

    def _maybe_client(env_var: str, ctor: Any, *, max_tokens: int = 4096) -> Any | None:
        model = os.environ.get(env_var)
        if not model:
            return None
        return ctor(_SyncJsonClient(_build_openai_provider(model, max_tokens=max_tokens)).call)

    planner = _maybe_client("OPENLIA_V2_3_PLAN_MODEL", LLMPlannerClient, max_tokens=2048)
    compute = _maybe_client("OPENLIA_V2_3_COMPUTE_MODEL", LLMComputeClient, max_tokens=1024)
    synthesizer = _maybe_client("OPENLIA_V2_3_SYNTHESIZE_MODEL", LLMSynthesizerClient)
    writer = _maybe_client("OPENLIA_V2_3_WRITE_MODEL", LLMWriterClient)
    verifier = _maybe_client("OPENLIA_V2_3_VERIFY_MODEL", LLMVerifierClient, max_tokens=2048)

    researcher = None
    research_model = os.environ.get("OPENLIA_V2_3_RESEARCH_MODEL")
    tools = _build_eodhd_tools()
    if research_model and tools:
        prov = _build_openai_provider(research_model, tool_calling=True)
        researcher = LLMResearcherClient(_SyncToolClient(prov), tools, max_turns=12)
    elif research_model and not tools:
        print("WARN: OPENLIA_V2_3_RESEARCH_MODEL set but EODHD_API_KEY missing; RESEARCH = NoOp.")

    def _factory() -> ReportRunner:
        stages = {slot: NoOpStage(slot) for slot in PIPELINE_ORDER}
        stages[V23Slot.CLARIFY] = ClarifyStage(clarifier)
        if planner is not None:
            stages[V23Slot.PLAN] = PlanStage(planner)
        if researcher is not None:
            stages[V23Slot.RESEARCH] = ResearchStage(researcher)
        if compute is not None:
            stages[V23Slot.COMPUTE] = ComputeStage(compute)
        if synthesizer is not None:
            stages[V23Slot.SYNTHESIZE] = SynthesizeStage(synthesizer)
        if writer is not None:
            stages[V23Slot.WRITE] = WriteStage(writer)
        stages[V23Slot.VISUALIZE] = VisualizeStage()
        if verifier is not None:
            stages[V23Slot.VERIFY] = VerifyStage(verifier)
        return ReportRunner(
            stages=stages,
            assemble=RealAssembleStage(),
            ctx=StageContext(clients={}, tools={}, extras={}),
        )

    return _factory


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    from openlia.llm.runtime.report_v2_3.events import (
        Completed,
        Failed,
        StageCompleted,
        StageStarted,
        Suspended,
    )
    from openlia.llm.runtime.report_v2_3.schemas import (
        ClarifyAnswers,
        Language,
        ReportType,
    )
    from openlia.llm.runtime.report_v2_3.state import ReportState

    factory = _build_factory()
    runner = factory()

    state = ReportState(
        run_id=str(uuid.uuid4()),
        user_id="smoke-cli",
        raw_prompt=args.prompt,
        language=Language(args.language),
        report_type=ReportType(args.report_type),
        tickers=list(args.tickers),
    )

    print(f"=== v2.3 smoke run {state.run_id[:12]} on {state.tickers} ===")

    def _observer(event: RunnerEvent) -> None:
        if isinstance(event, StageStarted):
            print(f"  > {event.slot.value} ...", flush=True)
        elif isinstance(event, StageCompleted):
            retry = f" (retry {event.retry_count})" if event.retry_count else ""
            print(f"  + {event.slot.value} done{retry}", flush=True)
        elif isinstance(event, Suspended):
            print(f"  ! {event.slot.value} suspended on {len(event.questions)} question(s)")
            for q in event.questions:
                print(f"      [{q.id}] {q.question}")
                print(f"          why: {q.why_blocking}")
                print(f"          default: {q.default}")
        elif isinstance(event, Failed):
            target = event.slot.value if event.slot is not None else "pipeline"
            print(f"  X {target} failed: {event.error}")
        elif isinstance(event, Completed):
            print("  * pipeline complete")

    state = runner.start(state, observer=_observer)

    if state.status.value == "waiting_on_user":
        if args.auto_default:
            print("Resuming with default answers...", flush=True)
            answers = ClarifyAnswers(
                answers={q.id: q.default for q in state.pending_questions},
            )
            state = runner.resume(state, answers, observer=_observer)
        else:
            print("\nRun suspended in CLARIFY. Re-run with --auto-default to accept the defaults.")
            return 1

    if state.status.value != "complete":
        print(f"\nRun ended with status={state.status.value}; last_error={state.last_error!r}")
        return 1

    print("\n--- final state ---")
    if state.resolved is not None:
        print(f"  sections: {sorted(state.resolved.section_bodies.keys())}")
        print(f"  footnotes: {len(state.resolved.footnotes)}")
        print(f"  figures: {len(state.resolved.figure_labels)}")

    if args.output:
        # Renderer lives in the server package; import lazily so the
        # default --output-less smoke does not require the server install.
        try:
            from openlia_server.services.v2_3_docx import render_docx
        except ImportError:
            print("\nWARN: openlia-server not installed; --output ignored.", file=sys.stderr)
            return 0
        blob = render_docx(state)
        with open(args.output, "wb") as fh:
            fh.write(blob)
        print(f"  wrote {len(blob):,} bytes -> {args.output}")

    return 0


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="smoke_v2_3", description=(__doc__ or "").split("\n", 1)[0])
    p.add_argument(
        "--ticker",
        dest="tickers",
        action="append",
        required=True,
        help="Ticker (EODHD-formatted, e.g. NVDA). Repeat for multi-ticker.",
    )
    p.add_argument("--prompt", required=True, help="The raw user prompt.")
    p.add_argument(
        "--report-type",
        choices=["initiation", "update", "morning_brief", "earnings_review"],
        default="initiation",
    )
    p.add_argument("--language", choices=["en", "zh-TW"], default="en")
    p.add_argument(
        "--auto-default",
        action="store_true",
        help="Accept CLARIFY's stated defaults automatically.",
    )
    p.add_argument(
        "--output",
        help="If set, write the rendered .docx to this path on success.",
    )
    return p.parse_args(argv)


if __name__ == "__main__":  # pragma: no cover — CLI entry point
    raise SystemExit(main())
