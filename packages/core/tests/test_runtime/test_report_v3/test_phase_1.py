"""Phase 1 tests for the v3 tool catalog + tool-use loop.

Exercises:
  - Pure-math valuation tools (run_dcf, run_comps, run_sensitivity)
  - Output tools (emit_chart, write_section, finalize) with the
    workspace + ledger integration
  - Citation validation on write_section
  - The end-to-end runner loop driven by a FakeLLMProvider script
  - Hard limits (max_turns) and finalize-gate behavior

No live API calls. Real provider smoke is a manual reviewer step.
"""

from __future__ import annotations

import pytest
from openlia.llm.runtime.report_v2_3.schemas import ReportType
from openlia.llm.runtime.report_v2_3.templates.builtins import get_builtin
from openlia.llm.runtime.report_v3 import (
    CitationLedger,
    Language,
    LLMSession,
    ReportLength,
    Runner,
    RunRequest,
    RunWorkspace,
)
from openlia.llm.runtime.report_v3.tools.output_tools import build_output_tools
from openlia.llm.runtime.report_v3.tools.valuation_tools import build_valuation_tools
from openlia.llm.runtime.report_v3.tools.web_search import (
    format_web_citation_notice,
    ingest_web_citations,
)
from openlia.llm.types import Citation, ReasoningEffort

from ._fakes import (
    FakeLLMProvider,
    script_text,
    script_tool_call,
    script_tool_calls,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fresh_workspace() -> tuple[RunWorkspace, CitationLedger]:
    template = get_builtin(ReportType.INITIATION)
    ledger = CitationLedger()
    return (
        RunWorkspace(template=template, ledger=ledger, subject="RKLB.US"),
        ledger,
    )


def _request() -> RunRequest:
    return RunRequest(
        subject="RKLB.US",
        template=get_builtin(ReportType.INITIATION),
        language=Language.EN,
        length=ReportLength.NORMAL,
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
    )


def _runner_with_fake(responses) -> tuple[Runner, LLMSession, FakeLLMProvider]:
    session = LLMSession.create(
        provider_kind="anthropic", model="claude-sonnet-4-6"
    )
    fake = FakeLLMProvider(scripted_responses=responses)
    session.attach_adapter(fake)
    runner = Runner(max_turns=20)
    return runner, session, fake


# ---------------------------------------------------------------------------
# Valuation tools
# ---------------------------------------------------------------------------


def test_run_dcf_returns_fair_value_and_logs_to_ledger():
    ledger = CitationLedger()
    tools = {t.name: t for t in build_valuation_tools(ledger=ledger)}
    result = tools["run_dcf"].execute(
        {
            "revenue_base": 1000.0,
            "revenue_growth_path": [0.20, 0.15, 0.10, 0.08, 0.05],
            "margin_path": [0.10, 0.12, 0.14, 0.16, 0.18],
            "wacc": 0.10,
            "terminal_growth": 0.03,
            "tax_rate": 0.21,
            "net_debt": 100.0,
            "shares_outstanding": 100.0,
        }
    )
    body = result.payload["result"]
    assert body["enterprise_value"] > 0
    assert body["equity_value"] == body["enterprise_value"] - 100.0
    assert body["fair_value_per_share"] == pytest.approx(body["equity_value"] / 100.0)
    assert result.payload["source_id"].startswith("dcf_")
    assert ledger.lookup(result.payload["source_id"]) is not None


def test_run_dcf_rejects_wacc_below_terminal_growth():
    ledger = CitationLedger()
    tools = {t.name: t for t in build_valuation_tools(ledger=ledger)}
    with pytest.raises(RuntimeError):
        tools["run_dcf"].execute(
            {
                "revenue_base": 100.0,
                "revenue_growth_path": [0.1],
                "margin_path": [0.1],
                "wacc": 0.02,
                "terminal_growth": 0.05,
            }
        )


def test_run_comps_uses_median_per_multiple():
    ledger = CitationLedger()
    tools = {t.name: t for t in build_valuation_tools(ledger=ledger)}
    result = tools["run_comps"].execute(
        {
            "peer_multiples": {
                "ev_ebitda": [10.0, 12.0, 14.0],
                "pe": [20.0, 30.0],
            },
            "subject_metrics": {"ev_ebitda": 100.0, "pe": 5.0},
        }
    )
    body = result.payload["result"]
    assert body["median_multiple_by_name"]["ev_ebitda"] == 12.0
    assert body["median_multiple_by_name"]["pe"] == 25.0
    assert body["implied_value_by_multiple"]["ev_ebitda"] == 1200.0
    assert body["implied_value_by_multiple"]["pe"] == 125.0


def test_run_sensitivity_produces_grid_of_fair_values():
    ledger = CitationLedger()
    tools = {t.name: t for t in build_valuation_tools(ledger=ledger)}
    base = {
        "revenue_base": 1000.0,
        "revenue_growth_path": [0.1, 0.1, 0.1],
        "margin_path": [0.1, 0.1, 0.1],
        "wacc": 0.10,
        "terminal_growth": 0.02,
        "tax_rate": 0.21,
        "shares_outstanding": 100.0,
    }
    result = tools["run_sensitivity"].execute(
        {
            "base": base,
            "row_driver": "wacc",
            "col_driver": "terminal_growth",
            "row_values": [0.08, 0.10, 0.12],
            "col_values": [0.01, 0.02, 0.03],
        }
    )
    grid = result.payload["result"]["fair_value_per_share_grid"]
    assert len(grid) == 3
    assert len(grid[0]) == 3
    # Lower WACC + higher terminal growth => higher fair value.
    assert grid[0][2] > grid[2][0]


# ---------------------------------------------------------------------------
# Output tools — citation validation
# ---------------------------------------------------------------------------


def test_write_section_rejects_unresolved_citations():
    workspace, _ = _fresh_workspace()
    tools = {t.name: t for t in build_output_tools(workspace=workspace)}
    first_id = workspace.template.sections[0].id

    with pytest.raises(RuntimeError) as excinfo:
        tools["write_section"].execute(
            {
                "section_id": first_id,
                "markdown": "RKLB launched Neutron [^web_99].",
            }
        )
    assert "Unresolved citations" in str(excinfo.value)


def test_write_section_accepts_resolved_citations():
    workspace, ledger = _fresh_workspace()

    ledger.append(tool_name="web_search", result_summary="neutron launch")
    tools = {t.name: t for t in build_output_tools(workspace=workspace)}
    first_id = workspace.template.sections[0].id

    result = tools["write_section"].execute(
        {
            "section_id": first_id,
            "markdown": "RKLB launched Neutron [^web_1].",
        }
    )
    assert result.payload["ok"] is True
    assert first_id in workspace.sections


def test_write_section_rejects_unknown_section_id():
    workspace, _ = _fresh_workspace()
    tools = {t.name: t for t in build_output_tools(workspace=workspace)}
    with pytest.raises(RuntimeError) as excinfo:
        tools["write_section"].execute(
            {"section_id": "not_a_section", "markdown": "x"}
        )
    assert "Unknown section_id" in str(excinfo.value)


def test_write_section_rejects_chart_ref_to_unknown_chart():
    workspace, ledger = _fresh_workspace()
    ledger.append(tool_name="web_search")
    tools = {t.name: t for t in build_output_tools(workspace=workspace)}
    first_id = workspace.template.sections[0].id
    with pytest.raises(RuntimeError) as excinfo:
        tools["write_section"].execute(
            {
                "section_id": first_id,
                "markdown": "See chart {{chart:missing}} [^web_1].",
            }
        )
    assert "Unknown chart refs" in str(excinfo.value)


def test_emit_chart_validates_spec_and_resolves_source_ids():
    workspace, ledger = _fresh_workspace()
    entry = ledger.append(tool_name="get_historical_prices")
    tools = {t.name: t for t in build_output_tools(workspace=workspace)}
    result = tools["emit_chart"].execute(
        {
            "chart_id": "price_5y",
            "chart_type": "line",
            "title": "RKLB 5y price",
            "data": [{"x": "2021", "y": 12.5}, {"x": "2022", "y": 6.0}],
            "source_ids": [entry.source_id],
        }
    )
    assert result.payload["ok"] is True
    assert "price_5y" in workspace.charts


def test_emit_chart_rejects_unknown_source_id():
    workspace, _ = _fresh_workspace()
    tools = {t.name: t for t in build_output_tools(workspace=workspace)}
    with pytest.raises(RuntimeError):
        tools["emit_chart"].execute(
            {
                "chart_id": "x",
                "chart_type": "line",
                "title": "x",
                "data": [{"x": "1", "y": 1.0}],
                "source_ids": ["web_999"],
            }
        )


def test_emit_chart_rejects_invalid_chart_type():
    workspace, _ = _fresh_workspace()
    tools = {t.name: t for t in build_output_tools(workspace=workspace)}
    with pytest.raises(RuntimeError):
        tools["emit_chart"].execute(
            {
                "chart_id": "x",
                "chart_type": "sankey",
                "title": "x",
                "data": [{"x": "1", "y": 1.0}],
            }
        )


def test_set_cover_populates_workspace_with_validated_spec():
    workspace, _ = _fresh_workspace()
    tools = {t.name: t for t in build_output_tools(workspace=workspace)}
    result = tools["set_cover"].execute(
        {
            "subtitle": "Q1 2026 initiation",
            "tagline": "Neutron launch cadence unlocks the next leg of revenue",
            "tldr": [
                "Backlog at record $1.2B",
                "Engine 9 production ramping on schedule",
                "Margin trajectory: 35% by 2027",
            ],
            "key_metrics": [
                {
                    "label": "Revenue FY24",
                    "value": "$436M",
                    "change": "+24% YoY",
                    "tone": "positive",
                },
                {"label": "Backlog", "value": "$1.2B"},
            ],
            "rating": "Buy",
            "upside_pct": 28.5,
        }
    )
    assert result.payload["ok"] is True
    assert result.payload["tldr_count"] == 3
    assert result.payload["metrics_count"] == 2
    assert result.payload["rating"] == "Buy"
    assert workspace.cover is not None
    assert workspace.cover.tagline.startswith("Neutron")
    assert workspace.cover.key_metrics[0].tone == "positive"
    assert workspace.cover_written_this_run is True


def test_set_cover_accepts_partial_payload():
    """Every cover field is optional — minimal payloads succeed."""
    workspace, _ = _fresh_workspace()
    tools = {t.name: t for t in build_output_tools(workspace=workspace)}
    result = tools["set_cover"].execute({"tagline": "Pure-play launch provider"})
    assert result.payload["ok"] is True
    assert workspace.cover is not None
    assert workspace.cover.tagline == "Pure-play launch provider"
    assert workspace.cover.tldr == []
    assert workspace.cover.rating is None


def test_set_cover_last_write_wins():
    workspace, _ = _fresh_workspace()
    tools = {t.name: t for t in build_output_tools(workspace=workspace)}
    tools["set_cover"].execute({"rating": "Hold"})
    tools["set_cover"].execute({"rating": "Buy", "upside_pct": 20.0})
    assert workspace.cover is not None
    assert workspace.cover.rating == "Buy"
    assert workspace.cover.upside_pct == 20.0


def test_set_cover_rejects_invalid_metric_tone():
    workspace, _ = _fresh_workspace()
    tools = {t.name: t for t in build_output_tools(workspace=workspace)}
    with pytest.raises(RuntimeError):
        tools["set_cover"].execute(
            {
                "key_metrics": [
                    {"label": "x", "value": "1", "tone": "amazing"},
                ],
            }
        )


def test_set_cover_propagates_to_run_result():
    workspace, _ = _fresh_workspace()
    tools = {t.name: t for t in build_output_tools(workspace=workspace)}
    tools["set_cover"].execute(
        {"tagline": "Best-in-class operator", "rating": "Overweight"}
    )
    result = workspace.to_result(status="completed")
    assert result.cover is not None
    assert result.cover.tagline == "Best-in-class operator"
    assert result.cover.rating == "Overweight"


def test_workspace_with_no_set_cover_call_leaves_result_cover_none():
    workspace, _ = _fresh_workspace()
    result = workspace.to_result(status="completed")
    assert result.cover is None


def test_finalize_reports_missing_sections_until_all_written():
    workspace, ledger = _fresh_workspace()
    ledger.append(tool_name="web_search")
    tools = {t.name: t for t in build_output_tools(workspace=workspace)}

    pending = tools["finalize"].execute({})
    assert pending.payload["ok"] is False
    assert pending.payload["missing_sections"] == workspace.required_section_ids()

    for spec in workspace.template.sections:
        tools["write_section"].execute(
            {"section_id": spec.id, "markdown": f"{spec.title} [^web_1]."}
        )

    done = tools["finalize"].execute({})
    assert done.payload["ok"] is True
    assert workspace.finalized is True


# ---------------------------------------------------------------------------
# Web citation ingest
# ---------------------------------------------------------------------------


def test_ingest_web_citations_assigns_source_ids_and_dedupes_by_url():
    ledger = CitationLedger()
    citations = (
        Citation(id="c1", kind="web", url="https://a.com", title="A"),
        Citation(id="c2", kind="web", url="https://b.com", title="B"),
        Citation(id="c3", kind="web", url="https://a.com", title="A2"),
        Citation(id="ctool", kind="tool", url=None),
    )
    rewrites = ingest_web_citations(citations, ledger)
    assert rewrites["c1"] == "web_1"
    assert rewrites["c2"] == "web_2"
    assert rewrites["c3"] == "web_1"  # dedupe to existing url
    assert "ctool" not in rewrites
    assert len(ledger) == 2


def test_format_web_citation_notice_lists_markers_and_dedupes():
    ledger = CitationLedger()
    citations = (
        Citation(id="c1", kind="web", url="https://a.com", title="Alpha"),
        Citation(id="c2", kind="web", url="https://b.com", title="Beta"),
        Citation(id="c3", kind="web", url="https://a.com", title="Alpha dup"),
        Citation(id="ctool", kind="tool", url=None),
    )
    rewrites = ingest_web_citations(citations, ledger)
    notice = format_web_citation_notice(citations, rewrites)
    assert notice is not None
    assert "[^web_1]" in notice
    assert "[^web_2]" in notice
    assert "Alpha" in notice and "Beta" in notice
    assert "https://a.com" in notice
    # Two bullet lines despite three web citations (two share a URL).
    bullet_lines = [ln for ln in notice.splitlines() if ln.startswith("- [^")]
    assert len(bullet_lines) == 2
    # The non-web tool citation is not announced.
    assert "ctool" not in notice


def test_format_web_citation_notice_returns_none_without_web_citations():
    ledger = CitationLedger()
    citations = (Citation(id="ctool", kind="tool", url=None),)
    rewrites = ingest_web_citations(citations, ledger)
    assert format_web_citation_notice(citations, rewrites) is None


# ---------------------------------------------------------------------------
# Runner end-to-end (FakeLLMProvider)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_runner_runs_minimal_happy_path():
    """Model fetches one fact, then writes every section, then finalizes."""
    template = get_builtin(ReportType.INITIATION)
    section_ids = [s.id for s in template.sections]

    script = []
    # Turn 1: web_search (provider-native — no actual dispatch; we
    # simulate the result by attaching a citation on the same response)
    script.append(
        script_tool_calls(
            ("get_company_news", {"ticker": "RKLB.US"}),
        )
    )
    # Turn 2: write each section
    for sid in section_ids:
        script.append(
            script_tool_calls(
                ("write_section", {"section_id": sid, "markdown": f"{sid} body."}),
            )
        )
    # Final turn: finalize
    script.append(script_tool_calls(("finalize", {})))

    runner, session, _ = _runner_with_fake(script)
    result = await runner.run(_request(), session=session)
    assert result.status == "completed"
    assert {s["section_id"] for s in result.sections} == set(section_ids)
    # Sections returned in template order:
    assert [s["section_id"] for s in result.sections] == section_ids


@pytest.mark.asyncio
async def test_runner_replays_missing_sections_when_model_finalizes_early():
    template = get_builtin(ReportType.INITIATION)
    section_ids = [s.id for s in template.sections]

    script = []
    # Write only the first section
    script.append(
        script_tool_calls(
            ("write_section", {"section_id": section_ids[0], "markdown": "draft."}),
        )
    )
    # Try to finalize -> blocked
    script.append(script_tool_calls(("finalize", {})))
    # Now write the rest one per turn
    for sid in section_ids[1:]:
        script.append(
            script_tool_calls(
                ("write_section", {"section_id": sid, "markdown": f"{sid} body."}),
            )
        )
    # Finalize -> ok
    script.append(script_tool_calls(("finalize", {})))

    runner, session, _ = _runner_with_fake(script)
    result = await runner.run(_request(), session=session)
    assert result.status == "completed"
    assert {s["section_id"] for s in result.sections} == set(section_ids)


@pytest.mark.asyncio
async def test_runner_returns_failed_on_text_only_response_without_finalize():
    script = [script_text("I think I'll stop here.")]
    runner, session, _ = _runner_with_fake(script)
    result = await runner.run(_request(), session=session)
    assert result.status == "failed"
    assert "without calling finalize" in result.message


@pytest.mark.asyncio
async def test_runner_hits_max_turns_when_model_loops_forever():
    # Model keeps requesting the same useless tool call.
    busy = script_tool_calls(("get_company_news", {"ticker": "RKLB.US"}))
    script = [busy] * 5
    runner, session, _ = _runner_with_fake(script)
    runner.max_turns = 3
    result = await runner.run(_request(), session=session)
    assert result.status == "failed"
    assert "hard limit of 3 model turns" in result.message


@pytest.mark.asyncio
async def test_runner_returns_structured_error_for_unknown_tool():
    """Unknown tool name comes back as a tool error message, loop continues."""
    template = get_builtin(ReportType.INITIATION)
    section_ids = [s.id for s in template.sections]

    script = [
        script_tool_calls(("nonexistent_tool", {})),
    ]
    for sid in section_ids:
        script.append(
            script_tool_calls(
                ("write_section", {"section_id": sid, "markdown": f"{sid} body."}),
            )
        )
    script.append(script_tool_calls(("finalize", {})))

    runner, session, fake = _runner_with_fake(script)
    result = await runner.run(_request(), session=session)
    # The bad tool call did not crash the loop; the run still completes.
    assert result.status == "completed"
    # The tool message for the unknown call should have been added.
    error_msgs = [
        m for m in fake.captured_requests[-1].messages
        if m.role == "tool" and "Unknown tool" in m.content
    ]
    assert error_msgs, "Expected the unknown-tool error to be replayed back to the model"


@pytest.mark.asyncio
async def test_runner_feeds_web_citation_ids_back_to_model():
    """After a turn that did native web search, the next request carries
    a message announcing the [^web_N] markers so the model can cite them."""
    template = get_builtin(ReportType.INITIATION)
    section_ids = [s.id for s in template.sections]

    script = [
        # Turn 1: native web search returns a citation alongside a tool call.
        script_tool_call(
            name="write_section",
            arguments={"section_id": section_ids[0], "markdown": f"{section_ids[0]} body."},
            citations=(
                Citation(id="c1", kind="web", url="https://snow.test/q1", title="SNOW Q1"),
            ),
        ),
    ]
    for sid in section_ids[1:]:
        script.append(
            script_tool_calls(
                ("write_section", {"section_id": sid, "markdown": f"{sid} body."}),
            )
        )
    script.append(script_tool_calls(("finalize", {})))

    runner, session, fake = _runner_with_fake(script)
    result = await runner.run(_request(), session=session)
    assert result.status == "completed"

    # Turn 2's request must carry the web-citation notice as a user message.
    turn2_user_msgs = [
        m.content
        for m in fake.captured_requests[1].messages
        if m.role == "user"
    ]
    notice = next((c for c in turn2_user_msgs if "[^web_1]" in c), None)
    assert notice is not None, "Expected a web-citation notice on the next turn"
    assert "SNOW Q1" in notice
    assert "https://snow.test/q1" in notice


@pytest.mark.asyncio
async def test_runner_threads_reasoning_effort_to_every_turn():
    """RunRequest.reasoning_effort propagates to every LLMRequest the
    adapter sees, and the max_tokens ceiling grows to absorb the
    thinking budget. v3 has no stage notion — reasoning applies on
    every turn or not at all."""
    template = get_builtin(ReportType.INITIATION)
    section_ids = [s.id for s in template.sections]

    script = []
    for sid in section_ids:
        script.append(
            script_tool_calls(
                ("write_section", {"section_id": sid, "markdown": f"{sid} body."}),
            )
        )
    script.append(script_tool_calls(("finalize", {})))

    runner, session, fake = _runner_with_fake(script)
    req = RunRequest(
        subject="RKLB.US",
        template=template,
        language=Language.EN,
        length=ReportLength.NORMAL,
        provider_kind="anthropic",
        model="claude-sonnet-4-6",
        reasoning_effort=ReasoningEffort.MEDIUM,
    )
    result = await runner.run(req, session=session)
    assert result.status == "completed"

    base_max = session.capabilities.max_output_tokens
    # MEDIUM overhead per session._REASONING_OVERHEAD
    expected_max = base_max + 8192
    assert len(fake.captured_requests) >= 1
    for captured in fake.captured_requests:
        assert captured.reasoning_effort == ReasoningEffort.MEDIUM
        assert captured.max_tokens == expected_max


@pytest.mark.asyncio
async def test_runner_default_reasoning_effort_none_leaves_max_tokens_untouched():
    """Default reasoning_effort=None: no reasoning param on the wire,
    max_tokens equals the model's capability ceiling exactly. Verifies
    the off-mode path doesn't accidentally bump the ceiling."""
    template = get_builtin(ReportType.INITIATION)
    section_ids = [s.id for s in template.sections]

    script = []
    for sid in section_ids:
        script.append(
            script_tool_calls(
                ("write_section", {"section_id": sid, "markdown": f"{sid} body."}),
            )
        )
    script.append(script_tool_calls(("finalize", {})))

    runner, session, fake = _runner_with_fake(script)
    result = await runner.run(_request(), session=session)
    assert result.status == "completed"
    base_max = session.capabilities.max_output_tokens
    for captured in fake.captured_requests:
        assert captured.reasoning_effort is None
        assert captured.max_tokens == base_max
