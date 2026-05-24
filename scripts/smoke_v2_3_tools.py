"""Smoke-test every v2.3 research tool end-to-end.

Hits live EODHD + native OpenAI web_search. Prints PASS/FAIL per tool.
Run with: uv run python scripts/smoke_v2_3_tools.py
"""

from __future__ import annotations

import json
import os
import sys
import traceback
from pathlib import Path

# Load .env so EODHD_API_KEY / OPENAI_API_KEY are visible.
root = Path(__file__).resolve().parents[1]
env_path = root / ".env"
if env_path.exists():
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def _pp(obj: object, head: int = 220) -> str:
    s = json.dumps(obj, default=str)
    return s[:head] + ("..." if len(s) > head else "")


def smoke_eodhd_tools() -> tuple[int, int]:
    from openlia.llm.runtime.report_v2_3.research.registry import build_eodhd_tools

    from openlia_server.services.v2_3_wiring import _trim_eodhd_fundamentals

    eodhd_key = os.environ["EODHD_API_KEY"]
    from eodhd import APIClient

    client = APIClient(api_key=eodhd_key)

    def fundamentals(t: str) -> dict:
        raw = client.get_fundamentals_data(t)
        if isinstance(raw, dict):
            payload = raw
        elif isinstance(raw, list) and raw and isinstance(raw[0], dict):
            payload = raw[0]
        else:
            return {"value": raw}
        return _trim_eodhd_fundamentals(payload)

    def prices(t: str, frm: str, to: str) -> list:
        rows = client.get_eod_historical_stock_market_data(
            symbol=t, period="d", from_date=frm, to_date=to
        )
        return list(rows) if rows else []

    def news(t: str, limit: int) -> list:
        rows = client.financial_news(s=t, limit=limit)
        return list(rows) if rows else []

    tools = build_eodhd_tools(fundamentals=fundamentals, prices=prices, news=news)
    by_name = {t.descriptor.name: t for t in tools}

    cases: list[tuple[str, dict]] = [
        ("get_fundamentals", {"ticker": "NVDA.US"}),
        ("get_historical_prices", {"ticker": "NVDA.US", "from_date": "2026-04-01", "to_date": "2026-04-30"}),
        ("get_company_news", {"ticker": "NVDA.US", "limit": 3}),
    ]
    passed = failed = 0
    for name, args in cases:
        tool = by_name[name]
        try:
            res = tool.execute(args)
            assert res.payload, f"{name} returned empty payload"
            assert res.provenance, f"{name} returned no provenance"
            print(f"  PASS {name}: {res.summary} | payload={_pp(res.payload, 140)}")
            passed += 1
        except Exception:
            print(f"  FAIL {name}:")
            traceback.print_exc(limit=2)
            failed += 1
    return passed, failed


def smoke_web_search_tool() -> tuple[int, int]:
    """Native web_search runs *inside* the LLM call, not standalone.
    We test the explicit-callable form here (the optional fourth tool)
    by binding a tiny transport that returns canned results — the path
    that's exercised when an OpenRouter/Anthropic model is configured
    without native web search."""
    from openlia.llm.runtime.report_v2_3.research.registry import build_web_search_tool

    def fake_transport(query: str, k: int) -> list[dict]:
        return [
            {"url": "https://example.com/a", "title": "A", "snippet": "snippet a"},
            {"url": "https://example.com/b", "title": "B", "snippet": "snippet b"},
        ][:k]

    tool = build_web_search_tool(fake_transport)
    try:
        res = tool.execute({"query": "NVDA earnings", "max_results": 2})
        assert res.payload["results"], "web_search returned no results"
        print(f"  PASS web_search (callable form): {res.summary}")
        return 1, 0
    except Exception:
        print("  FAIL web_search (callable form):")
        traceback.print_exc(limit=2)
        return 0, 1


def smoke_native_web_search_via_openai() -> tuple[int, int]:
    """The other web_search path: native, embedded as a tool spec in the
    Responses API call. Two checks:
      1. The tool-builder emits the new ``web_search_preview`` wire-type
         (the fix that unblocked URL-citation harvesting for gpt-5.4).
      2. An actual round-trip lands url_citation annotations on the
         returned LLMResponse.
    """
    from openlia.llm.adapters.openai_responses import (
        OpenAIResponsesAdapter,
        _build_responses_tools,
    )
    from openlia.llm.types import (
        Capabilities,
        LLMRequest,
        Message,
        ProviderCredentials,
    )
    import asyncio

    passed = failed = 0

    # 1. Wire-shape check.
    try:
        req = LLMRequest(
            messages=[Message(role="user", content="hi")],
            native_tools=("web_search",),
        )
        tools = _build_responses_tools(req)
        assert tools and any(
            t.get("type") == "web_search_preview" for t in tools
        ), f"expected web_search_preview in tool spec, got {tools}"
        print(f"  PASS native web_search wire shape: {tools}")
        passed += 1
    except Exception:
        print("  FAIL native web_search wire shape:")
        traceback.print_exc(limit=2)
        failed += 1

    # 2. Live round-trip.
    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        print("  SKIP native web_search round-trip: no OPENAI_API_KEY")
        return passed, failed

    try:
        model = os.environ.get("OPENLIA_SMOKE_MODEL", "gpt-5.4")
        adapter = OpenAIResponsesAdapter(
            credentials=ProviderCredentials(api_key=api_key, base_url=None),
            model=model,
            capabilities=Capabilities(web_search_native=True),
        )
        req = LLMRequest(
            system="You are a helpful assistant. Use web_search to answer.",
            messages=[
                Message(
                    role="user", content="What is the URL of openai.com? Cite the source."
                )
            ],
            native_tools=("web_search",),
            max_tokens=300,
        )
        resp = asyncio.run(adapter.generate(req))
        cit_count = len(resp.citations or ())
        text = (resp.text or "")[:160]
        assert cit_count > 0, f"no citations returned (text={text!r})"
        print(f"  PASS native web_search round-trip: citations={cit_count} text={text!r}")
        passed += 1
    except Exception:
        print("  FAIL native web_search round-trip:")
        traceback.print_exc(limit=3)
        failed += 1

    return passed, failed


def smoke_llm_stage_clients() -> tuple[int, int]:
    """Exercise each LLM stage client (PLAN, COMPUTE, SYNTHESIZE, WRITE,
    VERIFY) with a fake json_call so the prompt + repair plumbing is
    exercised without burning real tokens. Catches regressions in
    sanitiser/post-validator wiring."""
    from openlia.llm.runtime.report_v2_3.clients.llm_stage_clients import (
        LLMComputeClient,
        LLMPlannerClient,
        LLMSynthesizerClient,
        LLMVerifierClient,
        LLMWriterClient,
    )
    from openlia.llm.runtime.report_v2_3.clients.compute import ComputeRequest
    from openlia.llm.runtime.report_v2_3.clients.planner import PlannerRequest
    from openlia.llm.runtime.report_v2_3.clients.synthesizer import SynthesizerRequest
    from openlia.llm.runtime.report_v2_3.clients.verifier import VerifierRequest
    from openlia.llm.runtime.report_v2_3.clients.writer import WriterRequest
    from openlia.llm.runtime.report_v2_3.schemas import (
        BundleFact,
        CanonicalFigure,
        ClarifyProceed,
        DataProviderSource,
        Language,
        Outline,
        OutlineSection,
        ReportLength,
        ReportThesis,
        ReportType,
        ResearchBundle,
        SectionMandate,
        ValuationMethod,
        ValuationPlan,
        WrittenSection,
    )
    from datetime import UTC, datetime

    src = DataProviderSource(
        provider="EODHD", endpoint="fundamentals", period="TTM", retrieved_at=datetime.now(UTC)
    )
    bundle = ResearchBundle(
        tickers=["NVDA"],
        facts={"rev_ttm": BundleFact(id="rev_ttm", label="Revenue TTM", value=100.0, source=src)},
    )
    outline = Outline(
        tickers=["NVDA"],
        report_type=ReportType.INITIATION,
        sections=[OutlineSection(id="overview", title="Overview")],
        valuation_plan=ValuationPlan(methods=[ValuationMethod.DCF]),
    )
    thesis = ReportThesis(
        language=Language.EN,
        central_argument="growth",
        key_takeaways=["x"],
        valuation_stance="fair",
        valuation_plan=ValuationPlan(methods=[ValuationMethod.DCF]),
        canonical_figures=[CanonicalFigure(fact_id="rev_ttm", display="$100M")],
        mandates=[
            SectionMandate(
                section_id="overview",
                covers="business",
                does_not_cover="valuation",
                relevant_fact_ids=["rev_ttm"],
            )
        ],
        charts=[],
    )

    passed = failed = 0

    # PLAN
    plan_response = {
        "tickers": ["NVDA"],
        "report_type": "initiation",
        "sections": [
            {
                "id": "overview",
                "title": "Overview",
                "section_type": "qualitative",
                "data_needs": [
                    {"description": "products", "expected_fact_ids": ["products"]}
                ],
            }
        ],
        "valuation_plan": {"methods": ["dcf"]},
    }
    try:
        client = LLMPlannerClient(json_call=lambda **_: plan_response)
        out = client.plan(
            PlannerRequest(
                tickers=["NVDA"],
                raw_prompt="initiate NVDA",
                language=Language.EN,
                report_type=ReportType.INITIATION,
                clarify_result=ClarifyProceed(assumptions=[]),
            )
        )
        assert isinstance(out, Outline) and out.sections[0].id == "overview"
        print("  PASS PLAN stage client")
        passed += 1
    except Exception:
        print("  FAIL PLAN stage client:")
        traceback.print_exc(limit=2)
        failed += 1

    # COMPUTE — one method per call; LLM returns the method-specific
    # input dict (e.g. DCFInputs shape) directly.
    dcf_response = {
        "revenue_base_fact_id": "rev_ttm",
        "revenue_growth_path": [0.10, 0.08, 0.06, 0.05, 0.04],
        "margin_path": [0.35, 0.35, 0.36, 0.36, 0.37],
        "wacc": 0.10,
        "terminal_growth": 0.025,
        "tax_rate": 0.21,
        "grounding_fact_ids": ["rev_ttm"],
    }
    try:
        client = LLMComputeClient(json_call=lambda **_: dcf_response)
        out = client.propose_inputs(
            ComputeRequest(
                method=ValuationMethod.DCF,
                raw_prompt="initiate NVDA",
                language=Language.EN,
                bundle=bundle,
                outline=outline,
                clarify_result=ClarifyProceed(assumptions=[]),
            )
        )
        assert out.wacc == 0.10 and out.revenue_base_fact_id == "rev_ttm"
        print("  PASS COMPUTE stage client")
        passed += 1
    except Exception:
        print("  FAIL COMPUTE stage client:")
        traceback.print_exc(limit=2)
        failed += 1

    # SYNTHESIZE
    synth_response = {
        "language": "en",
        "central_argument": "growth",
        "key_takeaways": ["one"],
        "valuation_stance": "fair",
        "valuation_plan": {"methods": ["dcf"]},
        "canonical_figures": [{"fact_id": "rev_ttm", "display": "$100M"}],
        "mandates": [
            {
                "section_id": "overview",
                "covers": "business",
                "does_not_cover": "valuation",
                "relevant_fact_ids": ["rev_ttm"],
            }
        ],
        "charts": [],
    }
    try:
        client = LLMSynthesizerClient(json_call=lambda **_: synth_response)
        out = client.synthesize(
            SynthesizerRequest(
                raw_prompt="initiate NVDA",
                language=Language.EN,
                bundle=bundle,
                outline=outline,
                clarify_result=ClarifyProceed(assumptions=[]),
            )
        )
        assert out.central_argument == "growth"
        print("  PASS SYNTHESIZE stage client")
        passed += 1
    except Exception:
        print("  FAIL SYNTHESIZE stage client:")
        traceback.print_exc(limit=2)
        failed += 1

    # WRITE
    write_response = {
        "section_id": "overview",
        "title": "Overview",
        "body": "NVDA is a chipmaker. {{CITE:rev_ttm}}",
    }
    try:
        client = LLMWriterClient(json_call=lambda **_: write_response)
        out = client.write(
            WriterRequest(
                section_mandate=thesis.mandates[0],
                thesis=thesis,
                language=Language.EN,
                relevant_facts={"rev_ttm": bundle.facts["rev_ttm"]},
                assigned_charts=[],
                length=ReportLength.NORMAL,
            )
        )
        assert isinstance(out, WrittenSection) and out.cited_fact_ids() == ["rev_ttm"]
        print("  PASS WRITE stage client")
        passed += 1
    except Exception:
        print("  FAIL WRITE stage client:")
        traceback.print_exc(limit=2)
        failed += 1

    # VERIFY
    verify_response = {"issues": []}
    try:
        section = WrittenSection.model_validate(write_response)
        client = LLMVerifierClient(json_call=lambda **_: verify_response)
        out = client.verify(
            VerifierRequest(
                raw_prompt="initiate NVDA",
                language=Language.EN,
                thesis=thesis,
                bundle=bundle,
                sections=[section],
            )
        )
        assert out.issues == []
        print("  PASS VERIFY stage client")
        passed += 1
    except Exception:
        print("  FAIL VERIFY stage client:")
        traceback.print_exc(limit=2)
        failed += 1

    return passed, failed


def main() -> int:
    total_p = total_f = 0

    print("\n=== v2.3 RESEARCH tools (live EODHD) ===")
    p, f = smoke_eodhd_tools()
    total_p += p
    total_f += f

    print("\n=== v2.3 RESEARCH tools (web_search via callable) ===")
    p, f = smoke_web_search_tool()
    total_p += p
    total_f += f

    print("\n=== v2.3 RESEARCH tools (native web_search via OpenAI) ===")
    p, f = smoke_native_web_search_via_openai()
    total_p += p
    total_f += f

    print("\n=== v2.3 LLM stage clients ===")
    p, f = smoke_llm_stage_clients()
    total_p += p
    total_f += f

    print(f"\n=== Total: {total_p} passed, {total_f} failed ===")
    return 0 if total_f == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
