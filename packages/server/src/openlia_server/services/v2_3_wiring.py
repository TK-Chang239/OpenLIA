"""Startup-time wiring for the v2.3 runner factory.

Reads env vars and, when present, instantiates the LLM-backed stage
clients plus the v2.3 runner factory, returning it for the caller
(typically `app.py`) to assign onto `app.state.v2_3_runner_factory`.

Env contract — CLARIFY (required to enable the engine at all):
- ``OPENAI_API_KEY``                — auth for the OpenAI adapter
- ``OPENLIA_V2_3_CLARIFY_MODEL``    — OpenAI model id, e.g. ``gpt-5.4-mini``

Env contract — RESEARCH (optional; enables real research):
- ``OPENLIA_V2_3_RESEARCH_MODEL``   — OpenAI model id used for the
  RESEARCH tool-use loop (typically the same family as CLARIFY but
  with tool_calling enabled)
- ``EODHD_API_KEY``                 — auth for the EODHD data tools

Env contract — other stages (each optional; each NoOps when unset):
- ``OPENLIA_V2_3_PLAN_MODEL``        — PLAN model id
- ``OPENLIA_V2_3_COMPUTE_MODEL``     — COMPUTE input-proposal model id
- ``OPENLIA_V2_3_SYNTHESIZE_MODEL``  — SYNTHESIZE model id
- ``OPENLIA_V2_3_WRITE_MODEL``       — WRITE model id
- ``OPENLIA_V2_3_VERIFY_MODEL``      — VERIFY model id

CLARIFY-only optionals:
- ``OPENAI_BASE_URL``                       — base URL override
- ``OPENLIA_V2_3_CLARIFY_MAX_TOKENS``       — int; default 1024
- ``OPENLIA_V2_3_CLARIFY_TEMPERATURE``      — float; default 0.2

RESEARCH-only optionals:
- ``OPENLIA_V2_3_RESEARCH_MAX_TOKENS``      — int; default 4096
- ``OPENLIA_V2_3_RESEARCH_TEMPERATURE``     — float; default 0.3
- ``OPENLIA_V2_3_RESEARCH_MAX_TURNS``       — int; default 12

Each non-CLARIFY stage also takes ``OPENLIA_V2_3_<STAGE>_MAX_TOKENS``
and ``OPENLIA_V2_3_<STAGE>_TEMPERATURE`` overrides. The defaults are
tuned per stage in ``_STAGE_DEFAULTS`` below.

When any CLARIFY var is missing the function returns ``None`` and the
v2.3 routes respond 503 — same shape as the v2.2 engine. The other
stages fall back to NoOp when their own vars are missing, so the rest
of the pipeline still composes for tests / no-EODHD smoke runs.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from typing import Any

from openlia.llm.adapters import build_adapter
from openlia.llm.runtime.report_v2_3.clients.llm_clarifier import LLMClarifierClient
from openlia.llm.runtime.report_v2_3.clients.llm_researcher import LLMResearcherClient
from openlia.llm.runtime.report_v2_3.clients.llm_stage_clients import (
    LLMComputeClient,
    LLMPlannerClient,
    LLMSynthesizerClient,
    LLMVerifierClient,
    LLMWriterClient,
)
from openlia.llm.runtime.report_v2_3.clients.researcher import ResearcherClient
from openlia.llm.runtime.report_v2_3.research import build_research_tools
from openlia.llm.types import Capabilities, ProviderCredentials, ReasoningEffort

from .v2_3_runner_factory import V23RunnerFactory, make_v2_3_runner_factory
from .v2_stage_factory import SyncJsonLlmClient, SyncToolLlmClient

log = logging.getLogger(__name__)


def build_v2_3_runner_factory_from_env() -> V23RunnerFactory | None:
    """Return a v2.3 factory configured from env, or None if not configured."""
    api_key = os.getenv("OPENAI_API_KEY")
    clarify_model = os.getenv("OPENLIA_V2_3_CLARIFY_MODEL")
    if not api_key or not clarify_model:
        log.info(
            "v2.3 engine env vars not set (OPENAI_API_KEY=%s, "
            "OPENLIA_V2_3_CLARIFY_MODEL=%s); v2.3 routes will respond 503",
            "***" if api_key else "missing",
            "set" if clarify_model else "missing",
        )
        return None

    base_url = os.getenv("OPENAI_BASE_URL")
    clarifier = _build_clarifier(api_key=api_key, model=clarify_model, base_url=base_url)
    researcher = _build_researcher(api_key=api_key, base_url=base_url)
    planner = _build_json_stage_client(
        api_key=api_key, base_url=base_url, stage="PLAN", ctor=LLMPlannerClient
    )
    compute = _build_json_stage_client(
        api_key=api_key, base_url=base_url, stage="COMPUTE", ctor=LLMComputeClient
    )
    synthesizer = _build_json_stage_client(
        api_key=api_key, base_url=base_url, stage="SYNTHESIZE", ctor=LLMSynthesizerClient
    )
    writer = _build_json_stage_client(
        api_key=api_key, base_url=base_url, stage="WRITE", ctor=LLMWriterClient
    )
    verifier = _build_json_stage_client(
        api_key=api_key, base_url=base_url, stage="VERIFY", ctor=LLMVerifierClient
    )

    log.info(
        "v2.3 engine wired (clarify=%s, research=%s, plan=%s, compute=%s, "
        "synthesize=%s, write=%s, verify=%s)",
        clarify_model,
        "real" if researcher is not None else "noop",
        "real" if planner is not None else "noop",
        "real" if compute is not None else "noop",
        "real" if synthesizer is not None else "noop",
        "real" if writer is not None else "noop",
        "real" if verifier is not None else "noop",
    )
    return make_v2_3_runner_factory(
        clarifier,
        planner_client=planner,
        researcher_client=researcher,
        compute_client=compute,
        synthesizer_client=synthesizer,
        writer_client=writer,
        verifier_client=verifier,
    )


# ---------------------------------------------------------------------------
# Per-stage defaults (model token budget + temperature)
# ---------------------------------------------------------------------------


# PLACEHOLDER ceilings — these are truncation guards, not budgets. The
# model writes what it writes; if output runs past `max_tokens`, the
# response is cut off mid-emission and downstream parsing fails (the
# SyncJsonLlmClient coerces the unparseable tail to ``{}``, which the
# repair loop has no useful signal to fix). The correct value is
# `observed_output_max * ~1.75` per stage, where `observed_output_max`
# comes from real runs — see the `llm_usage` log line emitted on every
# call. Until that observation pass runs, these are interim numbers
# generous enough to clear known truncation points; the follow-up PR
# replaces every literal here from logged usage.
#
# NOTE: extended-thinking models charge thinking tokens against the
# same ceiling. If/when a stage enables reasoning, the ceiling must
# grow to cover `thinking_budget + expected_output + margin`, not just
# the visible answer — under-sizing then truncates *inside* the
# thinking pass and produces the same ``head='{}'`` symptom with no
# visible output bytes.
_STAGE_DEFAULTS: dict[str, tuple[int, float]] = {
    # max_tokens, temperature
    # PLAN bumped 2048 -> 8192 (interim): production hit truncation at
    # 2048 with `head='{}'`. 8192 = ~4x the observed truncation point,
    # mirrors per-user WRITE.
    "PLAN": (8192, 0.3),
    "COMPUTE": (1024, 0.2),
    "SYNTHESIZE": (16384, 0.3),
    "WRITE": (4096, 0.4),
    "VERIFY": (2048, 0.2),
}


def _build_json_stage_client(
    *,
    api_key: str,
    base_url: str | None,
    stage: str,
    ctor: Callable[[Callable[..., dict]], Any],
) -> Any | None:
    """Generic builder for the JSON-only stages (PLAN/COMPUTE/SYNTHESIZE/
    WRITE/VERIFY). Each follows the LLMClarifier pattern: one OpenAI
    provider, one SyncJsonLlmClient, one stage client constructor."""
    model = os.getenv(f"OPENLIA_V2_3_{stage}_MODEL")
    if not model:
        log.info("OPENLIA_V2_3_%s_MODEL unset; %s stage will NoOp.", stage, stage)
        return None
    default_max, default_temp = _STAGE_DEFAULTS[stage]
    max_tokens = int(os.getenv(f"OPENLIA_V2_3_{stage}_MAX_TOKENS", str(default_max)))
    temperature = float(os.getenv(f"OPENLIA_V2_3_{stage}_TEMPERATURE", str(default_temp)))

    credentials = ProviderCredentials(
        api_key=api_key,
        base_url=base_url,
        env_var_name="OPENAI_API_KEY",
    )
    provider = build_adapter(
        kind="openai",
        credentials=credentials,
        model=model,
        capabilities=Capabilities(
            structured_output=True,
            max_context_tokens=128_000,
            max_output_tokens=max_tokens,
        ),
    )
    json_client = SyncJsonLlmClient(
        provider, max_tokens=max_tokens, temperature=temperature, stage=stage
    )
    return ctor(json_client.call)


def _build_clarifier(*, api_key: str, model: str, base_url: str | None) -> LLMClarifierClient:
    max_tokens = int(os.getenv("OPENLIA_V2_3_CLARIFY_MAX_TOKENS", "1024"))
    temperature = float(os.getenv("OPENLIA_V2_3_CLARIFY_TEMPERATURE", "0.2"))

    credentials = ProviderCredentials(
        api_key=api_key,
        base_url=base_url,
        env_var_name="OPENAI_API_KEY",
    )
    provider = build_adapter(
        kind="openai",
        credentials=credentials,
        model=model,
        capabilities=Capabilities(
            structured_output=True,
            max_context_tokens=128_000,
            max_output_tokens=max_tokens,
        ),
    )
    json_client = SyncJsonLlmClient(
        provider, max_tokens=max_tokens, temperature=temperature, stage="clarify"
    )
    return LLMClarifierClient(json_client.call)


def _build_researcher(*, api_key: str, base_url: str | None) -> ResearcherClient | None:
    research_model = os.getenv("OPENLIA_V2_3_RESEARCH_MODEL")
    eodhd_key = os.getenv("EODHD_API_KEY")
    if not research_model:
        log.info("OPENLIA_V2_3_RESEARCH_MODEL unset; RESEARCH stage will NoOp.")
        return None
    if not eodhd_key:
        log.info("EODHD_API_KEY unset; RESEARCH stage will NoOp (no data tools).")
        return None

    max_tokens = int(os.getenv("OPENLIA_V2_3_RESEARCH_MAX_TOKENS", "8192"))
    temperature = float(os.getenv("OPENLIA_V2_3_RESEARCH_TEMPERATURE", "0.3"))
    max_turns = int(os.getenv("OPENLIA_V2_3_RESEARCH_MAX_TURNS", "12"))

    credentials = ProviderCredentials(
        api_key=api_key,
        base_url=base_url,
        env_var_name="OPENAI_API_KEY",
    )
    capabilities = Capabilities(
        tool_calling=True,
        structured_output=True,
        web_search_native=True,
        max_context_tokens=128_000,
        max_output_tokens=max_tokens,
    )
    provider = build_adapter(
        kind="openai",
        credentials=credentials,
        model=research_model,
        capabilities=capabilities,
    )
    tool_client = SyncToolLlmClient(
        provider,
        max_tokens=max_tokens,
        temperature=temperature,
        native_tools=("web_search",),
        stage="research",
    )
    tools = _build_eodhd_tool_set(eodhd_key)
    return LLMResearcherClient(tool_client, tools, max_turns=max_turns)


# ---------------------------------------------------------------------------
# Per-user factory builder — takes a {slot: ResolvedModel} mapping built
# from the caller's er_v2_3_model_assignments rows. Mirrors v2.2's
# ``build_runner_v2(models_by_slot=...)`` shape so the route layer can
# pick the right model per stage per user.
# ---------------------------------------------------------------------------


# PLACEHOLDER ceilings — see the header comment on _STAGE_DEFAULTS for
# the framing. Same caveat about extended-thinking models applies.
_STAGE_DEFAULTS_PER_USER: dict[str, tuple[int, float]] = {
    "clarify": (1024, 0.2),
    # PLAN bumped 2048 -> 8192 (interim): production hit truncation at
    # 2048 with `head='{}'`. 8192 = ~4x the observed truncation point.
    "plan": (8192, 0.3),
    "research": (16384, 0.3),
    "compute": (1024, 0.2),
    "synthesize": (16384, 0.3),
    "write": (8192, 0.4),
    "verify": (2048, 0.2),
}


# ---------------------------------------------------------------------------
# Extended-thinking / reasoning_effort wiring
# ---------------------------------------------------------------------------


# Token headroom added to `max_tokens` when reasoning is enabled. Thinking
# tokens count against the same ceiling as visible output on every
# provider, so the ceiling must absorb both. These numbers mirror the
# per-provider _REASONING_BUDGET_BY_EFFORT tables in the Anthropic and
# Gemini adapters. The sized-from-data ceiling pass will retune both
# once production `reasoning_out=` log lines accumulate.
_REASONING_OVERHEAD: dict[ReasoningEffort, int] = {
    ReasoningEffort.MEDIUM: 8192,
    ReasoningEffort.HIGH: 32768,
}


# Stages that get reasoning_effort applied when the user enables it.
# Restricted to the two stages where deeper deliberation moves quality:
# PLAN (structures the whole report; bad plan cascades into every later
# stage) and SYNTHESIZE (cross-section reasoning over the full bundle).
# Cheap stages (CLARIFY, COMPUTE, VERIFY) gain little, and WRITE is a
# per-section drafter where extra latency multiplies across N sections.
_REASONING_STAGES: frozenset[str] = frozenset({"plan", "synthesize"})


def _resolve_stage_reasoning(
    stage: str,
    base_max: int,
    reasoning_effort: ReasoningEffort | None,
) -> tuple[int, ReasoningEffort | None]:
    """Return (effective_max_tokens, effort_to_send) for ``stage``.

    Off mode (None) or non-reasoning stage: returns (base_max, None) so
    the client/adapter pair behaves exactly as before. Reasoning on
    AND stage in _REASONING_STAGES: returns
    (base_max + overhead[effort], effort) so the truncation guard
    absorbs the thinking budget. Adapters whose model does not support
    thinking will drop the effort and emit a flat call against the
    grown ceiling — slightly wasteful but never wrong."""
    if reasoning_effort is None or stage not in _REASONING_STAGES:
        return base_max, None
    return base_max + _REASONING_OVERHEAD[reasoning_effort], reasoning_effort


def build_v2_3_runner_factory_from_models(
    *,
    models_by_slot: dict[str, Any],  # actually ResolvedModel
    eodhd_api_key: str | None = None,
    research_max_turns: int = 12,
    reasoning_effort: ReasoningEffort | None = None,
) -> V23RunnerFactory:
    """Build a V23RunnerFactory from per-user resolved models.

    The route layer calls this per request after resolving the user's
    ``er_v2_3_model_assignments`` rows through ``SQLModelRegistry``.
    Slots absent from ``models_by_slot`` stay NoOp (the runner gates
    on CLARIFY only; the other six gracefully no-op when unbound).

    RESEARCH additionally requires ``eodhd_api_key`` to wire its tool
    set. Missing key -> NoOp RESEARCH stage even if a model is assigned.

    ``reasoning_effort`` is the user-selected pill value from the
    report request. When set, ``_REASONING_STAGES`` (PLAN + SYNTHESIZE)
    receive the effort directive AND have their ``max_tokens`` grown
    by ``_REASONING_OVERHEAD[effort]``. Other stages stay flat.
    """
    if "clarify" not in models_by_slot:
        raise ValueError(
            "v2.3 runner factory requires at least the 'clarify' slot to be "
            "assigned; v2.3 cannot start without a working clarifier."
        )

    clarifier = _build_json_client_from_resolved(
        models_by_slot["clarify"], stage="clarify", ctor=LLMClarifierClient
    )
    planner = (
        _build_json_client_from_resolved(
            models_by_slot["plan"],
            stage="plan",
            ctor=LLMPlannerClient,
            reasoning_effort=reasoning_effort,
        )
        if "plan" in models_by_slot
        else None
    )
    compute = (
        _build_json_client_from_resolved(
            models_by_slot["compute"], stage="compute", ctor=LLMComputeClient
        )
        if "compute" in models_by_slot
        else None
    )
    synthesizer = (
        _build_json_client_from_resolved(
            models_by_slot["synthesize"],
            stage="synthesize",
            ctor=LLMSynthesizerClient,
            reasoning_effort=reasoning_effort,
        )
        if "synthesize" in models_by_slot
        else None
    )
    writer = (
        _build_json_client_from_resolved(
            models_by_slot["write"], stage="write", ctor=LLMWriterClient
        )
        if "write" in models_by_slot
        else None
    )
    verifier = (
        _build_json_client_from_resolved(
            models_by_slot["verify"], stage="verify", ctor=LLMVerifierClient
        )
        if "verify" in models_by_slot
        else None
    )

    researcher: ResearcherClient | None = None
    if "research" in models_by_slot and eodhd_api_key:
        max_tokens, temperature = _STAGE_DEFAULTS_PER_USER["research"]
        resolved_research = models_by_slot["research"]
        # Native web_search support is provider-conditional. The resolved
        # model carries the capability from the model registry; we forward
        # it so the adapter routes to the Responses API and surfaces URL
        # citations that the researcher harvests into the evidence ledger.
        web_search_native = bool(
            getattr(getattr(resolved_research, "capabilities", None), "web_search_native", False)
        )
        provider = build_adapter(
            kind=resolved_research.provider_kind,
            credentials=resolved_research.credentials,
            model=resolved_research.model_ref,
            capabilities=Capabilities(
                tool_calling=True,
                structured_output=True,
                web_search_native=web_search_native,
                max_context_tokens=128_000,
                max_output_tokens=max_tokens,
            ),
        )
        tool_client = SyncToolLlmClient(
            provider,
            max_tokens=max_tokens,
            temperature=temperature,
            native_tools=("web_search",) if web_search_native else (),
            stage="research",
        )
        tools = _build_eodhd_tool_set(eodhd_api_key)
        researcher = LLMResearcherClient(tool_client, tools, max_turns=research_max_turns)
        log.info(
            "v2.3 researcher wired (model=%s, web_search_native=%s)",
            resolved_research.model_ref,
            web_search_native,
        )
    elif "research" in models_by_slot:
        log.info("research model assigned but EODHD_API_KEY missing; RESEARCH will NoOp.")

    return make_v2_3_runner_factory(
        clarifier,
        planner_client=planner,
        researcher_client=researcher,
        compute_client=compute,
        synthesizer_client=synthesizer,
        writer_client=writer,
        verifier_client=verifier,
    )


def _build_json_client_from_resolved(
    resolved: Any,  # ResolvedModel
    *,
    stage: str,
    ctor: Callable[[Callable[..., dict]], Any],
    reasoning_effort: ReasoningEffort | None = None,
) -> Any:
    base_max, temperature = _STAGE_DEFAULTS_PER_USER[stage]
    max_tokens, effort = _resolve_stage_reasoning(stage, base_max, reasoning_effort)
    provider = build_adapter(
        kind=resolved.provider_kind,
        credentials=resolved.credentials,
        model=resolved.model_ref,
        capabilities=Capabilities(
            structured_output=True,
            max_context_tokens=128_000,
            max_output_tokens=max_tokens,
        ),
    )
    json_client = SyncJsonLlmClient(
        provider,
        max_tokens=max_tokens,
        temperature=temperature,
        stage=stage,
        reasoning_effort=effort,
    )
    return ctor(json_client.call)


def _build_eodhd_tool_set(eodhd_api_key: str) -> list[Any]:
    """Adapt ``eodhd.APIClient`` to the v2.3 transport signatures."""
    from eodhd import APIClient

    client = APIClient(api_key=eodhd_api_key)

    def fundamentals(ticker: str) -> dict:
        raw = client.get_fundamentals_data(ticker)
        if isinstance(raw, dict):
            payload = raw
        elif isinstance(raw, list) and raw and isinstance(raw[0], dict):
            payload = raw[0]
        else:
            return {"value": raw}
        return _trim_eodhd_fundamentals(payload)

    def prices(ticker: str, from_date: str, to_date: str) -> list:
        rows = client.get_eod_historical_stock_market_data(
            symbol=ticker, period="d", from_date=from_date, to_date=to_date
        )
        return list(rows) if rows else []

    def news(ticker: str, limit: int) -> list:
        rows = client.financial_news(s=ticker, limit=limit)
        return list(rows) if rows else []

    return build_research_tools(fundamentals=fundamentals, prices=prices, news=news)


# How many periods to keep when trimming the multi-year statements.
# Five years annual + six quarters quarterly gives the model enough
# trend to compute YoY/QoQ and CAGR without dumping the decade-long
# EODHD history that bloats input cost by 5-10x.
_EODHD_KEEP_ANNUAL = 5
_EODHD_KEEP_QUARTERLY = 6

# Top-level sections to drop wholesale — high-volume, low-signal for an
# equity-research narrative. Holders/insider lists and the full splits/
# dividend history alone routinely add 5-15k tokens per ticker.
_EODHD_DROP_SECTIONS = frozenset(
    {
        "Holders",
        "InsiderTransactions",
        "outstandingShares",
        "ETF_Data",
        "ESGScores",
        "Components",
        "Listings",
    }
)

# Fields inside the `General` section to drop. These are either prose
# (stale company narrative, exec bios) or contact metadata that has no
# business shaping research output. Dropping them serves two ends:
#
#  - Token cost: `Description` + `Officers` together routinely add
#    2-5k tokens per fundamentals call, with zero load-bearing value
#    for an equity-research report.
#  - Behavioral: the prose is point-in-time and reads to the model as
#    "narrative coverage already supplied", which causes the researcher
#    to skip web_search for genuinely-current qualitative needs
#    (regulatory status, catalysts, management commentary). Removing
#    the false-sufficiency signal is the load-bearing reason to drop
#    them, even with the dual-lane data_fact_ids / web_fact_ids
#    routing in place.
_EODHD_GENERAL_DROP_FIELDS = frozenset(
    {
        "Description",
        "Officers",
        "Address",
        "AddressData",
        "Phone",
        "WebURL",
        "LogoURL",
        "InternationalDomestic",
    }
)


def _trim_eodhd_fundamentals(payload: dict[str, Any]) -> dict[str, Any]:
    """Strip EODHD fundamentals down to what an equity-research report
    actually needs.

    The raw EODHD payload is enormous: every quarter back to inception,
    every dividend, every insider trade, every share-count change. The
    model only reads a small slice of this to build a fact bundle, but
    we pay for the full payload as input tokens on every RESEARCH turn
    where the result is in scope. Trimming here cuts ~60-80% of the
    bytes the model has to read without losing anything load-bearing.
    """
    if not isinstance(payload, dict):
        return payload

    trimmed: dict[str, Any] = {}
    for key, value in payload.items():
        if key in _EODHD_DROP_SECTIONS:
            continue
        if key == "General" and isinstance(value, dict):
            trimmed[key] = _trim_general(value)
            continue
        if key == "SplitsDividends" and isinstance(value, dict):
            trimmed[key] = _trim_splits_dividends(value)
            continue
        if key == "Earnings" and isinstance(value, dict):
            trimmed[key] = _trim_earnings(value)
            continue
        if key == "Financials" and isinstance(value, dict):
            trimmed[key] = _trim_financials(value)
            continue
        trimmed[key] = value
    return trimmed


def _trim_general(section: dict[str, Any]) -> dict[str, Any]:
    """Drop prose + contact fields from `General`; keep structured
    metadata (sector/industry/country/employees/IPO date)."""
    return {k: v for k, v in section.items() if k not in _EODHD_GENERAL_DROP_FIELDS}


def _trim_splits_dividends(section: dict[str, Any]) -> dict[str, Any]:
    """Keep current yield / payout fields; drop historical lists."""
    keep_keys = {
        "ForwardAnnualDividendRate",
        "ForwardAnnualDividendYield",
        "PayoutRatio",
        "DividendDate",
        "ExDividendDate",
        "LastSplitFactor",
        "LastSplitDate",
    }
    return {k: section.get(k) for k in keep_keys if k in section}


def _trim_earnings(section: dict[str, Any]) -> dict[str, Any]:
    """Earnings has History (per-quarter EPS) + Trend + Annual. Cap each
    to the most recent N periods — older entries rarely earn their
    tokens."""
    out: dict[str, Any] = {}
    for sub_key in ("History", "Trend", "Annual"):
        block = section.get(sub_key)
        out[sub_key] = _cap_period_dict(block, _EODHD_KEEP_QUARTERLY)
    return out


def _trim_financials(section: dict[str, Any]) -> dict[str, Any]:
    """Income/Balance/CashFlow each carry yearly + quarterly maps keyed
    by ISO date. Keep the N most recent of each."""
    out: dict[str, Any] = {}
    for stmt_key in ("Income_Statement", "Balance_Sheet", "Cash_Flow"):
        stmt = section.get(stmt_key)
        if not isinstance(stmt, dict):
            continue
        out[stmt_key] = {
            "yearly": _cap_period_dict(stmt.get("yearly"), _EODHD_KEEP_ANNUAL),
            "quarterly": _cap_period_dict(stmt.get("quarterly"), _EODHD_KEEP_QUARTERLY),
            "currency_symbol": stmt.get("currency_symbol"),
        }
    return out


def _cap_period_dict(block: Any, keep: int) -> dict[str, Any] | None:
    """EODHD encodes period series as ``{"2025-12-31": {...}, ...}``.
    Keep the ``keep`` most recent keys (lexicographic sort works because
    keys are ISO dates)."""
    if not isinstance(block, dict) or not block:
        return block if isinstance(block, dict) else None
    most_recent_first = sorted(block.keys(), reverse=True)[:keep]
    return {k: block[k] for k in most_recent_first}
