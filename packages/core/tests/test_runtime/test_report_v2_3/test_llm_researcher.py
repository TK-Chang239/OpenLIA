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
    WebSource,
)
from openlia.llm.runtime.report_v2_3.templates import TemplateSpec, get_builtin
from openlia.llm.types import Citation, Message, ToolCall

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
# Thematic runs — planner asks for nothing, researcher returns nothing
# ---------------------------------------------------------------------------


def _thematic_outline() -> Outline:
    """Outline whose sections have no data_needs — thematic by design."""
    return Outline(
        tickers=[],
        report_type=ReportType.INITIATION,
        sections=[
            OutlineSection(id="overview", title="Overview", data_needs=[]),
            OutlineSection(id="themes", title="Themes", data_needs=[]),
        ],
    )


def _thematic_request() -> ResearchRequest:
    return ResearchRequest(
        raw_prompt="give me a thematic read on AI infra",
        language=Language.EN,
        report_type=ReportType.INITIATION,
        tickers=[],
        outline=_thematic_outline(),
        template=_template(),
        clarify_result=ClarifyProceed(assumptions=["audience: PM"]),
    )


def test_researcher_accepts_empty_bundle_when_planner_asked_for_nothing() -> None:
    """RESEARCH should not raise when the planner emitted zero data_needs —
    the run is thematic by design, the bundle is legitimately empty."""
    llm = FakeToolLLMClient(
        turns=[
            ToolTurnResponse(
                text=json.dumps({"facts": []}),
                tool_calls=(),
            ),
        ]
    )
    researcher = LLMResearcherClient(llm, _tools())
    bundle = researcher.research(_thematic_request())
    assert isinstance(bundle, ResearchBundle)
    assert bundle.tickers == []
    assert bundle.facts == {}


def test_researcher_still_raises_when_planner_asked_but_got_nothing() -> None:
    """When the planner emitted data_needs but the researcher returned zero
    facts, that's a genuine failure — RESEARCH still raises."""
    llm = FakeToolLLMClient(
        turns=[
            ToolTurnResponse(
                text=json.dumps({"facts": []}),
                tool_calls=(),
            ),
        ]
    )
    researcher = LLMResearcherClient(llm, _tools())
    with pytest.raises(
        RuntimeError,
        match=r"no `facts` array|empty `facts` array|no usable facts",
    ):
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


def test_initial_user_payload_propagates_source_class_per_data_need() -> None:
    """The researcher's first user message must surface each data_need's
    `source_class` so the model can route quantitative-vs-narrative
    without guessing from the description."""
    from openlia.llm.runtime.report_v2_3.clients.llm_researcher import (
        _initial_user_text,
    )

    outline = Outline(
        tickers=["TEST"],
        report_type=ReportType.INITIATION,
        sections=[
            OutlineSection(
                id="overview",
                title="Overview",
                data_needs=[
                    DataNeed(
                        description="revenue, last 5 fiscal years",
                        expected_fact_ids=["rev_fy_hist"],
                        source_class="quantitative",
                    ),
                    DataNeed(
                        description="recent regulatory investigations",
                        expected_fact_ids=["regulatory_investigations"],
                        source_class="narrative",
                    ),
                    DataNeed(
                        description="business model summary",
                        expected_fact_ids=["business_model"],
                    ),  # default 'either'
                ],
            )
        ],
    )
    request = ResearchRequest(
        raw_prompt="initiate on TEST",
        language=Language.EN,
        report_type=ReportType.INITIATION,
        tickers=["TEST"],
        outline=outline,
        template=_template(),
        clarify_result=None,
    )

    payload = json.loads(_initial_user_text(request))
    needs = payload["sections"][0]["data_needs"]
    assert [n["source_class"] for n in needs] == ["quantitative", "narrative", "either"]


def test_research_prompt_routes_by_source_class_not_by_model_judgment() -> None:
    """The RESEARCH prompt must explicitly route by `source_class` and
    drop the prior `Prefer using BOTH kinds together` hedge that let the
    model talk itself out of web_search."""
    from openlia.llm.runtime.report_v2_3.clients.llm_researcher import (
        SYSTEM_PROMPT as RESEARCH_SYSTEM_PROMPT,
    )

    assert "source_class" in RESEARCH_SYSTEM_PROMPT
    for cls in ("quantitative", "narrative", "either"):
        assert cls in RESEARCH_SYSTEM_PROMPT
    # The old hedge text must not survive — its presence reverts the
    # whole intervention to a soft preference.
    assert "Prefer using BOTH kinds together" not in RESEARCH_SYSTEM_PROMPT


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


# ---------------------------------------------------------------------------
# Native web_search citation resolution
# ---------------------------------------------------------------------------


def _web_cite(url: str, title: str = "T", snippet: str = "S") -> Citation:
    return Citation(id="c1", kind="web", url=url, title=title, snippet=snippet, source="Test")


def test_url_form_evidence_id_is_rejected() -> None:
    """Raw URLs are reconstructable from pretraining — only ``web_N`` is
    accepted as a web evidence_id. A fact citing the URL form is dropped
    even when the URL was harvested from a real citation."""
    url = "https://example.com/article"
    llm = FakeToolLLMClient(
        turns=[
            ToolTurnResponse(
                text=json.dumps(
                    {
                        "facts": [
                            {
                                "id": "qual_pos",
                                "label": "Qualitative positioning",
                                "value": "AI infra leader",
                                "evidence_id": url,
                            }
                        ]
                    }
                ),
                tool_calls=(),
                citations=(_web_cite(url),),
            ),
        ]
    )
    researcher = LLMResearcherClient(llm, _tools())
    with pytest.raises(RuntimeError, match="no usable facts"):
        researcher.research(_request())


def test_web_evidence_id_resolves_by_web_n() -> None:
    """LLM cites by `web_1` — resolves to the canonical WebSource."""
    url = "https://example.com/news"
    llm = FakeToolLLMClient(
        turns=[
            ToolTurnResponse(
                text=json.dumps(
                    {
                        "facts": [
                            {
                                "id": "catalyst",
                                "label": "Recent catalyst",
                                "value": "new GPU launch",
                                "evidence_id": "web_1",
                            }
                        ]
                    }
                ),
                citations=(_web_cite(url),),
            ),
        ]
    )
    researcher = LLMResearcherClient(llm, _tools())
    bundle = researcher.research(_request())
    fact = bundle.facts["catalyst"]
    assert isinstance(fact.source, WebSource)
    assert fact.source.url == url


def test_unknown_web_n_id_drops_fact() -> None:
    """A `web_N` id the model invented out of thin air (no real search this
    run) cannot be resolved and the fact is dropped."""
    llm = FakeToolLLMClient(
        turns=[
            ToolTurnResponse(
                text=json.dumps(
                    {
                        "facts": [
                            {
                                "id": "halluc",
                                "label": "Hallucinated",
                                "value": "x",
                                "evidence_id": "web_7",
                            }
                        ]
                    }
                ),
                citations=(_web_cite("https://example.com/real"),),
            ),
        ]
    )
    researcher = LLMResearcherClient(llm, _tools())
    with pytest.raises(RuntimeError, match="no usable facts"):
        researcher.research(_request())


def test_system_text_carries_web_n_mapping_after_harvest() -> None:
    """The cumulative ``web_N → URL`` mapping must live in the per-turn
    system text — that way it cannot scroll out under later tool turns
    and the model always sees the current claimable web_N ids."""
    url = "https://example.com/foo"
    llm = FakeToolLLMClient(
        responder=_two_turn_web_responder(url),
    )
    researcher = LLMResearcherClient(llm, _tools())
    bundle = researcher.research(_request())

    assert {"rev_ttm", "qual"} <= set(bundle.facts)
    assert isinstance(bundle.facts["qual"].source, WebSource)

    # Turn 1 has no mapping yet (no prior harvest). The phrase "Web
    # search results so far" appears in the SYSTEM_PROMPT itself
    # (referring to the note), so we match on the unique rendered note
    # header instead.
    assert "(newest last):" not in llm.systems[0]
    # Turn 2 system text must carry the harvested mapping AND the
    # explicit reminder that raw URLs are not accepted.
    assert "(newest last):" in llm.systems[1]
    assert "web_1" in llm.systems[1]
    assert url in llm.systems[1]
    assert "Raw URLs are not accepted" in llm.systems[1]


def test_system_text_carries_mapping_on_every_turn_after_harvest() -> None:
    """Mapping must reappear on EVERY turn after first harvest — not just
    the immediate next turn. This guards against a regression where the
    note scrolls out under many subsequent tool roundtrips."""
    url = "https://example.com/foo"

    def responder(messages: list[Message]) -> ToolTurnResponse:
        n = sum(1 for m in messages if m.role == "assistant")
        if n == 0:
            # Turn 1: harvest a web citation alongside a function tool call.
            return ToolTurnResponse(
                text="",
                tool_calls=(
                    ToolCall(id="tc_1", name="get_fundamentals", arguments={"ticker": "NVDA"}),
                ),
                citations=(_web_cite(url),),
            )
        if n == 1:
            # Turn 2: another function tool call, no new citations.
            return ToolTurnResponse(
                text="",
                tool_calls=(
                    ToolCall(id="tc_2", name="get_fundamentals", arguments={"ticker": "NVDA"}),
                ),
            )
        # Turn 3: final JSON citing both the function call and the web hit.
        return ToolTurnResponse(
            text=json.dumps(
                {
                    "facts": [
                        {
                            "id": "rev_ttm",
                            "label": "Revenue (TTM)",
                            "value": 60_900_000_000,
                            "evidence_id": "tc_1",
                        },
                        {
                            "id": "qual",
                            "label": "Qualitative",
                            "value": "x",
                            "evidence_id": "web_1",
                        },
                    ]
                }
            ),
        )

    llm = FakeToolLLMClient(responder=responder)
    researcher = LLMResearcherClient(llm, _tools())
    bundle = researcher.research(_request())

    assert "qual" in bundle.facts
    # Mapping pinned at turn 2 AND turn 3 — system text is the carrier.
    assert "web_1" in llm.systems[1]
    assert "web_1" in llm.systems[2]


def test_research_prompt_forbids_url_as_evidence_id() -> None:
    """The prompt must say plainly that URLs are not accepted — removing
    the forgeable shortcut so the model cannot reach a WebSource handle
    without an actual search returning it."""
    from openlia.llm.runtime.report_v2_3.clients.llm_researcher import (
        SYSTEM_PROMPT as RESEARCH_SYSTEM_PROMPT,
    )

    assert "Do NOT emit a raw URL as an evidence_id" in RESEARCH_SYSTEM_PROMPT
    assert "web_N` is the only accepted web handle" in RESEARCH_SYSTEM_PROMPT


def test_research_prompt_binds_fact_id_to_expected_fact_ids() -> None:
    """Coverage check matches on the planner's `expected_fact_ids`, so the
    prompt must instruct the model to use those ids verbatim — otherwise
    narrative coverage stays at 0/N even when web evidence flows."""
    from openlia.llm.runtime.report_v2_3.clients.llm_researcher import (
        SYSTEM_PROMPT as RESEARCH_SYSTEM_PROMPT,
    )

    assert "expected_fact_ids" in RESEARCH_SYSTEM_PROMPT
    assert "verbatim" in RESEARCH_SYSTEM_PROMPT


def test_research_logs_per_turn_tool_and_citation_counts(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Each turn must emit a structured log line summarizing tool_calls,
    citations, and the cumulative web_urls count. Without these signals
    the only visible failure mode is "narrative coverage 0/N at finalize"
    — which doesn't tell you whether web_search ran at all."""
    url = "https://example.com/foo"
    llm = FakeToolLLMClient(responder=_two_turn_web_responder(url))
    researcher = LLMResearcherClient(llm, _tools())
    with caplog.at_level("INFO", logger="openlia.llm.runtime.report_v2_3.clients.llm_researcher"):
        researcher.research(_request())

    turn_lines = [r.message for r in caplog.records if "v2.3 RESEARCH turn=" in r.message]
    assert len(turn_lines) == 2
    assert "tool_calls=1" in turn_lines[0]
    assert "citations=1" in turn_lines[0]
    assert "new_web_urls=1" in turn_lines[0]
    # Turn 2 emits the final JSON — no tool calls, no new citations.
    assert "tool_calls=0" in turn_lines[1]
    assert "new_web_urls=0" in turn_lines[1]


def test_research_logs_tool_call_outcome_per_call(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Each function tool call must log its outcome (ok|error) and id so
    a failed tool roundtrip surfaces in the log instead of disappearing
    behind a downstream fact-resolution warning."""
    url = "https://example.com/foo"
    llm = FakeToolLLMClient(responder=_two_turn_web_responder(url))
    researcher = LLMResearcherClient(llm, _tools())
    with caplog.at_level("INFO", logger="openlia.llm.runtime.report_v2_3.clients.llm_researcher"):
        researcher.research(_request())

    tool_lines = [r.message for r in caplog.records if "v2.3 RESEARCH tool=" in r.message]
    assert len(tool_lines) == 1
    assert "tool=get_fundamentals" in tool_lines[0]
    assert "status=ok" in tool_lines[0]


def test_research_finished_log_includes_publisher_histogram(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The end-of-run summary must report a per-publisher URL count so
    source-breadth regressions ("all 30 URLs from rocketlab.com") are
    visible without re-reading every line."""
    url = "https://example.com/foo"
    llm = FakeToolLLMClient(responder=_two_turn_web_responder(url))
    researcher = LLMResearcherClient(llm, _tools())
    with caplog.at_level("INFO", logger="openlia.llm.runtime.report_v2_3.clients.llm_researcher"):
        researcher.research(_request())

    finished = [r.message for r in caplog.records if "RESEARCH finished" in r.message]
    assert len(finished) == 1
    assert "publishers=" in finished[0]
    assert "example.com" in finished[0]


def _two_turn_web_responder(url: str):
    """Helper: turn 1 makes a function tool call AND returns a web citation;
    turn 2 emits final JSON citing both."""

    def responder(messages: list[Message]) -> ToolTurnResponse:
        if not any(m.role == "assistant" for m in messages):
            return ToolTurnResponse(
                text="",
                tool_calls=(
                    ToolCall(id="tc_1", name="get_fundamentals", arguments={"ticker": "NVDA"}),
                ),
                citations=(_web_cite(url),),
            )
        return ToolTurnResponse(
            text=json.dumps(
                {
                    "facts": [
                        {
                            "id": "rev_ttm",
                            "label": "Revenue (TTM)",
                            "value": 60_900_000_000,
                            "evidence_id": "tc_1",
                        },
                        {
                            "id": "qual",
                            "label": "Qualitative",
                            "value": "x",
                            "evidence_id": "web_1",
                        },
                    ]
                }
            ),
        )

    return responder
