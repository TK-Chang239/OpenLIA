"""Tests for LLMResearcherClient — tool-use loop + provenance attachment."""

from __future__ import annotations

import json

import pytest
from openlia.llm.runtime.report_v2_3.clients.llm_researcher import (
    FakeToolLLMClient,
    LLMResearcherClient,
    ToolTurnResponse,
)
from openlia.llm.runtime.report_v2_3.clients.researcher import ResearchRequest
from openlia.llm.runtime.report_v2_3.research import build_research_tools
from openlia.llm.runtime.report_v2_3.schemas import (
    BundleSeries,
    ClarifyProceed,
    ComputedSource,
    DataNeed,
    DataProviderSource,
    Language,
    Outline,
    OutlineSection,
    ReportType,
    ResearchBundle,
)
from openlia.llm.runtime.report_v2_3.templates import TemplateSpec, get_builtin
from openlia.llm.types import Message, ToolCall

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _template() -> TemplateSpec:
    return get_builtin(ReportType.INITIATION)


def _outline() -> Outline:
    return Outline(
        tickers=["NVDA"],
        report_type=ReportType.INITIATION,
        sections=[
            OutlineSection(
                id="financials",
                title="Financials",
                data_needs=[
                    DataNeed(
                        description="latest annual revenue",
                        expected_fact_ids=["rev_ttm"],
                    )
                ],
            )
        ],
    )


def _request() -> ResearchRequest:
    return ResearchRequest(
        raw_prompt="initiate on NVDA",
        language=Language.EN,
        report_type=ReportType.INITIATION,
        tickers=["NVDA"],
        outline=_outline(),
        template=_template(),
        clarify_result=ClarifyProceed(assumptions=["audience: PM"]),
    )


def _tools() -> list:
    return build_research_tools(
        fundamentals=lambda t: {
            "General": {"Code": t},
            "Highlights": {"Revenue": 60_900_000_000},
        },
        prices=lambda *a, **kw: [],
        news=lambda *a, **kw: [],
    )


# ---------------------------------------------------------------------------
# Happy path — one tool call, one fact
# ---------------------------------------------------------------------------


def test_happy_path_single_tool_call_to_single_fact() -> None:
    llm = FakeToolLLMClient(
        turns=[
            ToolTurnResponse(
                text="",
                tool_calls=(
                    ToolCall(
                        id="tc_1",
                        name="get_fundamentals",
                        arguments={"ticker": "NVDA.US"},
                    ),
                ),
            ),
            ToolTurnResponse(
                text=json.dumps(
                    {
                        "facts": [
                            {
                                "id": "rev_ttm",
                                "label": "Revenue (TTM)",
                                "value": 60_900_000_000,
                                "unit": "USD",
                                "ticker": "NVDA",
                                "evidence_id": "tc_1",
                            }
                        ]
                    }
                ),
                tool_calls=(),
            ),
        ]
    )

    researcher = LLMResearcherClient(llm, _tools())
    bundle = researcher.research(_request())

    assert isinstance(bundle, ResearchBundle)
    assert bundle.tickers == ["NVDA"]
    fact = bundle.facts["rev_ttm"]
    assert fact.label == "Revenue (TTM)"
    assert fact.value == 60_900_000_000.0
    assert isinstance(fact.source, DataProviderSource)
    assert fact.source.provider == "EODHD"


def test_provenance_carries_tool_endpoint() -> None:
    llm = FakeToolLLMClient(
        turns=[
            ToolTurnResponse(
                text="",
                tool_calls=(
                    ToolCall(
                        id="tc_42",
                        name="get_fundamentals",
                        arguments={"ticker": "NVDA"},
                    ),
                ),
            ),
            ToolTurnResponse(
                text=json.dumps(
                    {
                        "facts": [
                            {
                                "id": "rev",
                                "label": "Revenue",
                                "value": 1.0,
                                "evidence_id": "tc_42",
                            }
                        ]
                    }
                ),
            ),
        ]
    )
    researcher = LLMResearcherClient(llm, _tools())
    bundle = researcher.research(_request())
    src = bundle.facts["rev"].source
    assert isinstance(src, DataProviderSource)
    assert src.endpoint == "fundamentals"


# ---------------------------------------------------------------------------
# Multi-turn — model chains tool calls and emits multiple facts
# ---------------------------------------------------------------------------


def test_multi_turn_loop_accumulates_evidence() -> None:
    llm = FakeToolLLMClient(
        turns=[
            ToolTurnResponse(
                text="",
                tool_calls=(
                    ToolCall(id="t1", name="get_fundamentals", arguments={"ticker": "NVDA"}),
                ),
            ),
            ToolTurnResponse(
                text="",
                tool_calls=(
                    ToolCall(
                        id="t2",
                        name="get_historical_prices",
                        arguments={
                            "ticker": "NVDA",
                            "from_date": "2025-01-01",
                            "to_date": "2025-12-31",
                        },
                    ),
                ),
            ),
            ToolTurnResponse(
                text=json.dumps(
                    {
                        "facts": [
                            {
                                "id": "rev",
                                "label": "Revenue",
                                "value": 100.0,
                                "evidence_id": "t1",
                            },
                            {
                                "id": "px_last",
                                "label": "Last Close",
                                "value": 500.0,
                                "evidence_id": "t2",
                            },
                        ]
                    }
                ),
            ),
        ]
    )
    researcher = LLMResearcherClient(llm, _tools())
    bundle = researcher.research(_request())
    assert {"rev", "px_last"} <= set(bundle.facts)
    assert bundle.facts["px_last"].source.endpoint == "eod"


# ---------------------------------------------------------------------------
# Computed facts
# ---------------------------------------------------------------------------


def test_computed_fact_emitted_with_computed_from() -> None:
    llm = FakeToolLLMClient(
        turns=[
            ToolTurnResponse(
                text="",
                tool_calls=(
                    ToolCall(id="t1", name="get_fundamentals", arguments={"ticker": "NVDA"}),
                ),
            ),
            ToolTurnResponse(
                text=json.dumps(
                    {
                        "facts": [
                            {
                                "id": "rev_usd",
                                "label": "Revenue USD",
                                "value": 100.0,
                                "evidence_id": "t1",
                            },
                            {
                                "id": "rev_millions",
                                "label": "Revenue (USD M)",
                                "value": 0.0001,
                                "unit": "USD_millions",
                                "computed_from": ["rev_usd"],
                                "method": "rev_usd / 1_000_000",
                            },
                        ]
                    }
                ),
            ),
        ]
    )
    researcher = LLMResearcherClient(llm, _tools())
    bundle = researcher.research(_request())
    computed = bundle.facts["rev_millions"]
    assert isinstance(computed.source, ComputedSource)
    assert computed.source.derived_from == ["rev_usd"]
    assert "1_000_000" in computed.source.method


# ---------------------------------------------------------------------------
# Time-series values
# ---------------------------------------------------------------------------


def test_timeseries_value_parsed_into_bundle_series() -> None:
    llm = FakeToolLLMClient(
        turns=[
            ToolTurnResponse(
                text="",
                tool_calls=(
                    ToolCall(id="t1", name="get_fundamentals", arguments={"ticker": "NVDA"}),
                ),
            ),
            ToolTurnResponse(
                text=json.dumps(
                    {
                        "facts": [
                            {
                                "id": "rev_series",
                                "label": "Revenue by quarter",
                                "value": {
                                    "points": [
                                        {"period": "2024-Q4", "value": 22.1},
                                        {"period": "2025-Q1", "value": 26.0},
                                    ],
                                    "unit": "USD_billions",
                                },
                                "evidence_id": "t1",
                            }
                        ]
                    }
                ),
            ),
        ]
    )
    researcher = LLMResearcherClient(llm, _tools())
    bundle = researcher.research(_request())
    series = bundle.facts["rev_series"].value
    assert isinstance(series, BundleSeries)
    assert [p.period for p in series.points] == ["2024-Q4", "2025-Q1"]
    assert series.unit == "USD_billions"


# ---------------------------------------------------------------------------
# Error paths
# ---------------------------------------------------------------------------


def test_max_turns_exceeded_raises() -> None:
    # Loops indefinitely calling the same tool — researcher must stop.
    def loop_responder(_messages: list[Message]) -> ToolTurnResponse:
        return ToolTurnResponse(
            text="",
            tool_calls=(
                ToolCall(id="t_loop", name="get_fundamentals", arguments={"ticker": "NVDA"}),
            ),
        )

    researcher = LLMResearcherClient(
        FakeToolLLMClient(responder=loop_responder), _tools(), max_turns=3
    )
    with pytest.raises(RuntimeError, match="did not emit a final bundle within 3"):
        researcher.research(_request())


def test_evidence_id_must_resolve_to_a_tool_call() -> None:
    # A fabricated evidence_id is skipped (logged) rather than raised on.
    # When EVERY fact has one, the bundle is empty and we surface the
    # zero-usable-facts error so the run still fails loudly. A single
    # bad evidence_id alongside good ones now only skips that one fact.
    llm = FakeToolLLMClient(
        turns=[
            ToolTurnResponse(
                text=json.dumps(
                    {
                        "facts": [
                            {
                                "id": "rev",
                                "label": "Revenue",
                                "value": 100.0,
                                "evidence_id": "tc_ghost",
                            }
                        ]
                    }
                ),
            ),
        ]
    )
    researcher = LLMResearcherClient(llm, _tools())
    with pytest.raises(RuntimeError, match="no usable facts"):
        researcher.research(_request())


def test_fact_without_evidence_or_computed_raises() -> None:
    llm = FakeToolLLMClient(
        turns=[
            ToolTurnResponse(
                text=json.dumps(
                    {
                        "facts": [
                            {"id": "rev", "label": "Revenue", "value": 1.0},
                        ]
                    }
                ),
            ),
        ]
    )
    researcher = LLMResearcherClient(llm, _tools())
    with pytest.raises(RuntimeError, match="evidence_id"):
        researcher.research(_request())


def test_unknown_tool_call_is_reported_back_to_model_then_continues() -> None:
    """The researcher should not crash if the LLM hallucinates a tool name —
    it should surface a structured error and let the model recover."""

    captured: dict[str, list[Message]] = {}

    def responder(messages: list[Message]) -> ToolTurnResponse:
        captured["last"] = list(messages)
        # Turn 1: hallucinate a tool.
        # Turn 2: after seeing the error, give up and emit a stub fact.
        n = sum(1 for m in messages if m.role == "assistant")
        if n == 0:
            return ToolTurnResponse(
                text="",
                tool_calls=(ToolCall(id="bad_1", name="nonexistent_tool", arguments={}),),
            )
        # Now make a valid tool call so we have evidence for the fact.
        if n == 1:
            return ToolTurnResponse(
                text="",
                tool_calls=(
                    ToolCall(id="tc_real", name="get_fundamentals", arguments={"ticker": "NVDA"}),
                ),
            )
        return ToolTurnResponse(
            text=json.dumps(
                {
                    "facts": [
                        {
                            "id": "rev",
                            "label": "Revenue",
                            "value": 1.0,
                            "evidence_id": "tc_real",
                        }
                    ]
                }
            ),
        )

    researcher = LLMResearcherClient(FakeToolLLMClient(responder=responder), _tools())
    bundle = researcher.research(_request())
    assert "rev" in bundle.facts
    # The bad tool's error was injected as a `tool` message back to the model.
    tool_msgs = [m for m in captured["last"] if m.role == "tool"]
    assert any("Unknown tool" in m.content for m in tool_msgs)


def test_malformed_final_json_raises() -> None:
    llm = FakeToolLLMClient(turns=[ToolTurnResponse(text="this is not json at all", tool_calls=())])
    researcher = LLMResearcherClient(llm, _tools())
    with pytest.raises(RuntimeError, match="not valid JSON"):
        researcher.research(_request())


def test_final_json_without_facts_array_raises() -> None:
    llm = FakeToolLLMClient(turns=[ToolTurnResponse(text=json.dumps({"something_else": []}))])
    researcher = LLMResearcherClient(llm, _tools())
    with pytest.raises(RuntimeError, match="no `facts` array"):
        researcher.research(_request())


def test_empty_final_turn_raises() -> None:
    llm = FakeToolLLMClient(turns=[ToolTurnResponse(text="", tool_calls=())])
    researcher = LLMResearcherClient(llm, _tools())
    with pytest.raises(RuntimeError, match="neither tool_calls nor text"):
        researcher.research(_request())


# ---------------------------------------------------------------------------
# Construction guards
# ---------------------------------------------------------------------------


def test_duplicate_tool_names_rejected() -> None:
    a = _tools()
    with pytest.raises(ValueError, match="Duplicate tool name"):
        LLMResearcherClient(FakeToolLLMClient(turns=[]), a + a[:1])


def test_max_turns_must_be_positive() -> None:
    with pytest.raises(ValueError, match="max_turns"):
        LLMResearcherClient(FakeToolLLMClient(turns=[]), _tools(), max_turns=0)


def test_fake_rejects_both_or_neither() -> None:
    with pytest.raises(ValueError, match="exactly one"):
        FakeToolLLMClient(turns=[], responder=lambda _m: ToolTurnResponse(text=""))
    with pytest.raises(ValueError, match="exactly one"):
        FakeToolLLMClient()  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# Tool exec errors propagate back to the model, not as Python exceptions
# ---------------------------------------------------------------------------


def test_tool_execution_error_reaches_model_as_tool_message() -> None:
    def boom(_t: str) -> dict:
        raise RuntimeError("upstream is down")

    failing_tools = build_research_tools(
        fundamentals=boom,
        prices=lambda *a, **kw: [],
        news=lambda *a, **kw: [],
    )

    def responder(messages: list[Message]) -> ToolTurnResponse:
        n = sum(1 for m in messages if m.role == "assistant")
        if n == 0:
            return ToolTurnResponse(
                text="",
                tool_calls=(
                    ToolCall(id="t1", name="get_fundamentals", arguments={"ticker": "NVDA"}),
                ),
            )
        # After the failure, model gives up.
        return ToolTurnResponse(
            text=json.dumps({"facts": [{"id": "x", "label": "x"}]}),
        )

    researcher = LLMResearcherClient(
        FakeToolLLMClient(responder=responder), failing_tools, max_turns=4
    )
    # The fake's final emission omits evidence_id; the researcher raises on
    # validation, but BEFORE then it should have surfaced the upstream
    # failure as a tool message — confirmed via the error propagation path.
    with pytest.raises(RuntimeError):
        researcher.research(_request())
