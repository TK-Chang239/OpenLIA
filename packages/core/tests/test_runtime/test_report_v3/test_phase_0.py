"""Phase 0 scaffolding tests for the v3 engine.

Covers:
  - Schema validation for ChartSpec / RunRequest / RunResult.
  - Citation ledger append + lookup + per-prefix counter.
  - LLMSession capability gate accepts web_search_native models and
    rejects Ollama (the canonical no-web-search provider).
  - Runner returns a placeholder RunResult and propagates
    CapabilityError when the capability gate trips.

No live provider calls. Phase 0 ships scaffolding only.
"""

from __future__ import annotations

import pytest
from openlia.llm.runtime.report_v2_3.schemas import ReportType
from openlia.llm.runtime.report_v2_3.templates.builtins import get_builtin
from openlia.llm.runtime.report_v3 import (
    CapabilityError,
    ChartSpec,
    CitationLedger,
    Language,
    LLMSession,
    ReportLength,
    Runner,
    RunRequest,
    RunResult,
    TemplateSpec,
)

# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------


def test_chart_spec_validates_minimum_fields():
    spec = ChartSpec(
        chart_id="rev_growth",
        chart_type="line",
        title="Revenue YoY",
        data=[{"label": "FY24", "value": 100.0}, {"label": "FY25", "value": 125.0}],
    )
    assert spec.chart_id == "rev_growth"
    assert len(spec.data) == 2


def test_chart_spec_rejects_empty_data():
    with pytest.raises(ValueError):
        ChartSpec(chart_id="x", chart_type="line", title="t", data=[])


def test_chart_spec_rejects_invalid_chart_type():
    with pytest.raises(ValueError):
        ChartSpec(
            chart_id="x",
            chart_type="sankey",  # type: ignore[arg-type]
            title="t",
            data=[{"label": "a", "value": 1.0}],
        )


def test_chart_spec_chart_id_must_be_slug():
    with pytest.raises(ValueError):
        ChartSpec(
            chart_id="Rev Growth!",
            chart_type="line",
            title="t",
            data=[{"label": "a", "value": 1.0}],
        )


def test_run_request_validates_min_fields():
    template = get_builtin(ReportType.INITIATION)
    req = RunRequest(
        subject="RKLB.US",
        template=template,
        language=Language.EN,
        length=ReportLength.NORMAL,
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
    )
    assert req.subject == "RKLB.US"
    assert isinstance(req.template, TemplateSpec)


# ---------------------------------------------------------------------------
# Citation ledger
# ---------------------------------------------------------------------------


def test_ledger_assigns_per_prefix_monotonic_source_ids():
    ledger = CitationLedger()
    a = ledger.append(tool_name="web_search", result_summary="hit 1")
    b = ledger.append(tool_name="web_search", result_summary="hit 2")
    c = ledger.append(tool_name="get_fundamentals", result_summary="rklb")
    d = ledger.append(tool_name="run_dcf", result_summary="rklb dcf")

    assert a.source_id == "web_1"
    assert b.source_id == "web_2"
    assert c.source_id == "eodhd_1"
    assert d.source_id == "dcf_1"


def test_ledger_lookup_returns_entry_by_source_id():
    ledger = CitationLedger()
    entry = ledger.append(
        tool_name="get_fundamentals",
        arguments={"ticker": "RKLB.US"},
        result_summary="snapshot",
    )
    assert ledger.lookup(entry.source_id) is entry
    assert ledger.lookup("does_not_exist") is None


def test_ledger_unknown_tool_uses_sanitized_tool_name_as_prefix():
    ledger = CitationLedger()
    entry = ledger.append(tool_name="future_tool_x", result_summary="x")
    assert entry.source_id == "future_tool_x_1"


def test_ledger_preserves_append_order_and_length():
    ledger = CitationLedger()
    ledger.append(tool_name="web_search")
    ledger.append(tool_name="run_dcf")
    ledger.append(tool_name="web_search")
    all_entries = ledger.all()
    assert len(ledger) == 3
    assert [e.tool_name for e in all_entries] == ["web_search", "run_dcf", "web_search"]


# ---------------------------------------------------------------------------
# Capability gate
# ---------------------------------------------------------------------------


def test_session_create_accepts_anthropic_sonnet():
    session = LLMSession.create(provider_kind="anthropic", model="claude-sonnet-4-6")
    assert session.capabilities.web_search_native is True
    assert session.provider_kind == "anthropic"


def test_session_create_accepts_openai_gpt_5_4():
    session = LLMSession.create(provider_kind="openai", model="gpt-5.4-2026-03-05")
    assert session.capabilities.web_search_native is True


def test_session_create_accepts_gemini_pro():
    session = LLMSession.create(provider_kind="gemini", model="gemini-3.1-pro")
    assert session.capabilities.web_search_native is True


def test_session_create_rejects_ollama():
    with pytest.raises(CapabilityError) as excinfo:
        LLMSession.create(provider_kind="ollama", model="llama3.1")
    msg = str(excinfo.value)
    assert "ollama" in msg.lower()
    assert "web search" in msg.lower()


def test_session_create_rejects_anthropic_haiku():
    # haiku is hosted but lacks web_search_native — the gate catches
    # this too, not just Ollama.
    with pytest.raises(CapabilityError):
        LLMSession.create(provider_kind="anthropic", model="claude-haiku-4-5")


def test_session_create_rejects_gpt_5_4_mini():
    with pytest.raises(CapabilityError):
        LLMSession.create(provider_kind="openai", model="gpt-5.4-mini")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_runner_returns_placeholder_result_on_capable_model():
    runner = Runner()
    template = get_builtin(ReportType.INITIATION)
    result = await runner.run(
        RunRequest(
            subject="RKLB.US",
            template=template,
            language=Language.EN,
            length=ReportLength.NORMAL,
            provider_kind="anthropic",
            model="claude-sonnet-4-6",
        )
    )
    assert isinstance(result, RunResult)
    assert result.status == "placeholder"
    assert result.subject == "RKLB.US"
    assert result.template_id == template.template_id
    assert "Phase 0" in result.message
    assert result.sections == []
    assert result.charts == []
    assert result.citations == []


@pytest.mark.asyncio
async def test_runner_raises_capability_error_on_ollama():
    runner = Runner()
    template = get_builtin(ReportType.INITIATION)
    with pytest.raises(CapabilityError):
        await runner.run(
            RunRequest(
                subject="RKLB.US",
                template=template,
                language=Language.EN,
                length=ReportLength.NORMAL,
                provider_kind="ollama",
                model="llama3.1",
            )
        )
