"""Phase 4 tests — dynamic tool discovery (find_tools + extended tier).

Exercises:
  - The extended-tool stubs compute correct values + log to the ledger
  - match_extended_tools category/keyword filtering + truncation reporting
  - find_tools activates matched tools and returns their schemas
  - The catalog keeps the extended tier out of the request until
    discovered, then surfaces it via active_schemas / active_tools_by_name
  - End-to-end: the model discovers a tool mid-run, calls it, and cites
    its result in a section

No live API calls.
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
from openlia.llm.runtime.report_v3.tools import (
    FIND_TOOLS_NAME,
    ToolDiscoveryState,
    build_catalog,
    build_extended_tools,
    build_find_tools_tool,
    match_extended_tools,
)

from ._fakes import FakeLLMProvider, script_tool_calls

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _dummy_transport(*_args, **_kwargs):
    raise AssertionError("data transport should not be called in these tests")


def _catalog():
    template = get_builtin(ReportType.INITIATION)
    ledger = CitationLedger()
    workspace = RunWorkspace(template=template, ledger=ledger, subject="RKLB.US")
    catalog = build_catalog(
        ledger=ledger,
        workspace=workspace,
        fundamentals=_dummy_transport,
        prices=_dummy_transport,
        news=_dummy_transport,
    )
    return catalog, ledger


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
    session = LLMSession.create(provider_kind="anthropic", model="claude-sonnet-4-6")
    fake = FakeLLMProvider(scripted_responses=responses)
    session.attach_adapter(fake)
    runner = Runner(max_turns=20)
    return runner, session, fake


# ---------------------------------------------------------------------------
# Stub math
# ---------------------------------------------------------------------------


def test_piotroski_counts_passing_criteria():
    ledger = CitationLedger()
    tool = build_extended_tools(ledger=ledger)["piotroski_f_score"].tool
    out = tool.execute(
        {
            "net_income": 100.0,
            "operating_cash_flow": 150.0,  # > NI -> accruals pass
            "roa_current": 0.12,
            "roa_prior": 0.10,  # rising
            "long_term_debt_ratio_current": 0.20,
            "long_term_debt_ratio_prior": 0.25,  # falling leverage
            "current_ratio_current": 2.0,
            "current_ratio_prior": 1.5,  # rising
            "shares_current": 100.0,
            "shares_prior": 100.0,  # no dilution
            "gross_margin_current": 0.40,
            "gross_margin_prior": 0.38,  # rising
            "asset_turnover_current": 1.1,
            "asset_turnover_prior": 1.0,  # rising
        }
    )
    body = out.payload["result"]
    assert body["f_score"] == 9
    assert body["interpretation"] == "high quality"
    assert out.payload["source_id"].startswith("piotroski_f_score_")
    assert ledger.lookup(out.payload["source_id"]) is not None


def test_beneish_m_score_flags_manipulator_above_threshold():
    ledger = CitationLedger()
    tool = build_extended_tools(ledger=ledger)["beneish_m_score"].tool
    # Inflated indices push M well above -1.78.
    out = tool.execute(
        {
            "dsri": 1.5,
            "gmi": 1.3,
            "aqi": 1.2,
            "sgi": 1.4,
            "depi": 1.1,
            "sgai": 1.0,
            "tata": 0.1,
            "lvgi": 1.0,
        }
    )
    body = out.payload["result"]
    assert body["m_score"] > body["threshold"]
    assert body["likely_manipulator"] is True


def test_roic_panel_computes_spread_and_economic_profit():
    ledger = CitationLedger()
    tool = build_extended_tools(ledger=ledger)["roic_panel"].tool
    out = tool.execute(
        {
            "nopat": 120.0,
            "invested_capital": 1000.0,
            "prior_nopat": 90.0,
            "prior_invested_capital": 900.0,
            "wacc": 0.09,
        }
    )
    body = out.payload["result"]
    assert body["roic"] == pytest.approx(0.12)
    assert body["prior_roic"] == pytest.approx(0.10)
    assert body["roiic"] == pytest.approx((120.0 - 90.0) / (1000.0 - 900.0))
    assert body["roic_wacc_spread"] == pytest.approx(0.03)
    assert body["creates_value"] is True


def test_roic_panel_rejects_zero_invested_capital():
    ledger = CitationLedger()
    tool = build_extended_tools(ledger=ledger)["roic_panel"].tool
    with pytest.raises(RuntimeError):
        tool.execute(
            {
                "nopat": 1.0,
                "invested_capital": 0.0,
                "prior_nopat": 1.0,
                "prior_invested_capital": 100.0,
                "wacc": 0.09,
            }
        )


# ---------------------------------------------------------------------------
# match_extended_tools
# ---------------------------------------------------------------------------


def test_match_by_category_returns_all_in_category():
    extended = build_extended_tools(ledger=CitationLedger())
    matched, total = match_extended_tools(extended, query=None, category="forensic_ratios")
    names = {e.name for e in matched}
    assert names == {"piotroski_f_score", "beneish_m_score"}
    assert total == 2


def test_match_by_keyword_scores_and_filters():
    extended = build_extended_tools(ledger=CitationLedger())
    matched, _ = match_extended_tools(extended, query="earnings manipulation", category=None)
    # Beneish is the manipulation detector; it must rank first.
    assert matched[0].name == "beneish_m_score"


def test_match_reports_total_when_truncated():
    extended = build_extended_tools(ledger=CitationLedger())
    matched, total = match_extended_tools(extended, query=None, category="forensic_ratios", limit=1)
    assert len(matched) == 1
    assert total == 2


# ---------------------------------------------------------------------------
# find_tools
# ---------------------------------------------------------------------------


def test_find_tools_activates_and_returns_schemas():
    extended = build_extended_tools(ledger=CitationLedger())
    state = ToolDiscoveryState(extended=extended)
    tool = build_find_tools_tool(state)
    out = tool.execute({"category": "forensic_ratios"})
    returned = {t["name"] for t in out.payload["matched_tools"]}
    assert returned == {"piotroski_f_score", "beneish_m_score"}
    assert state.activated == {"piotroski_f_score", "beneish_m_score"}
    # Every returned tool carries its full parameter schema.
    for entry in out.payload["matched_tools"]:
        assert entry["parameters"]["type"] == "object"


def test_find_tools_requires_query_or_category():
    state = ToolDiscoveryState(extended=build_extended_tools(ledger=CitationLedger()))
    tool = build_find_tools_tool(state)
    with pytest.raises(RuntimeError):
        tool.execute({})


def test_find_tools_rejects_unknown_category():
    state = ToolDiscoveryState(extended=build_extended_tools(ledger=CitationLedger()))
    tool = build_find_tools_tool(state)
    with pytest.raises(RuntimeError):
        tool.execute({"category": "not_a_real_category"})


# ---------------------------------------------------------------------------
# Catalog wiring
# ---------------------------------------------------------------------------


def test_catalog_core_excludes_extended_until_discovered():
    catalog, _ = _catalog()
    core_names = {s.name for s in catalog.core_schemas()}
    assert FIND_TOOLS_NAME in core_names
    assert "piotroski_f_score" not in core_names
    # active == core when nothing discovered yet
    assert {s.name for s in catalog.active_schemas()} == core_names


def test_catalog_active_schemas_grow_after_activation():
    catalog, _ = _catalog()
    before = {s.name for s in catalog.active_schemas()}
    catalog.discovery.activate(["roic_panel"])
    after = {s.name for s in catalog.active_schemas()}
    assert after - before == {"roic_panel"}
    assert "roic_panel" in catalog.active_tools_by_name()


# ---------------------------------------------------------------------------
# Runner end-to-end
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_runner_discovers_tool_then_calls_and_cites_it():
    template = get_builtin(ReportType.INITIATION)
    section_ids = [s.id for s in template.sections]

    beneish_inputs = {
        "dsri": 1.5,
        "gmi": 1.3,
        "aqi": 1.2,
        "sgi": 1.4,
        "depi": 1.1,
        "sgai": 1.0,
        "tata": 0.1,
        "lvgi": 1.0,
    }

    script = [
        # Turn 1: discover the forensic tool
        script_tool_calls(("find_tools", {"query": "earnings manipulation risk"})),
        # Turn 2: call the now-activated tool
        script_tool_calls(("beneish_m_score", beneish_inputs)),
    ]
    # Turn 3+: write sections; cite the discovered tool's result in the first
    for i, sid in enumerate(section_ids):
        marker = " [^beneish_m_score_1]" if i == 0 else ""
        script.append(
            script_tool_calls(
                ("write_section", {"section_id": sid, "markdown": f"{sid} body.{marker}"}),
            )
        )
    script.append(script_tool_calls(("finalize", {})))

    runner, session, fake = _runner_with_fake(script)
    result = await runner.run(_request(), session=session)

    assert result.status == "completed"
    # The discovered tool's citation resolved (write_section would have
    # rejected an unresolved marker).
    overview = next(s for s in result.sections if s["section_id"] == section_ids[0])
    assert "[^beneish_m_score_1]" in overview["markdown"]
    # Turn 1's request did NOT carry the extended tool; turn 2's did.
    turn1_tools = {t.name for t in fake.captured_requests[0].tools}
    turn2_tools = {t.name for t in fake.captured_requests[1].tools}
    assert "beneish_m_score" not in turn1_tools
    assert FIND_TOOLS_NAME in turn1_tools
    assert "beneish_m_score" in turn2_tools


@pytest.mark.asyncio
async def test_runner_hints_find_tools_on_unknown_extended_call():
    """Calling an extended tool before discovering it errors with a hint."""
    template = get_builtin(ReportType.INITIATION)
    section_ids = [s.id for s in template.sections]

    script = [script_tool_calls(("roic_panel", {}))]  # not discovered yet
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
    err = [
        m
        for m in fake.captured_requests[-1].messages
        if m.role == "tool" and "find_tools" in m.content and "Unknown tool" in m.content
    ]
    assert err, "Expected an unknown-tool error nudging the model to call find_tools"
